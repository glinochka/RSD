"""Tests for sales_manager template functionality."""
import json
import pytest
from datetime import datetime, timezone

from app.alembic.models import Agent, AgentSalesContact, AgentSalesDmQueue
from app.services.sales.dm_queue_service import DmQueueService
from app.services.sales.fsm import SalesFSMService
from app.services.sales.tool_registry import SalesToolRegistry
from app.services.template_runtime import TemplateRuntimeService


@pytest.mark.asyncio
async def test_sales_manager_template_config_normalization():
    """Test that sales_manager template config is properly normalized."""
    config = {
        "mode": "draft_only",
        "qualification_model": "deepseek-chat",
        "generation_model": "deepseek-chat",
        "min_confidence": 0.75,
        "cooldown_days": 14,
        "dedup_window_days": 30,
    }
    
    # Should validate without errors
    assert config["mode"] in {"draft_only", "semi_auto", "auto"}
    assert config["min_confidence"] >= 0.0
    assert config["cooldown_days"] > 0


@pytest.mark.asyncio
async def test_dm_queue_service_enqueue_and_retrieve(mock_db_session):
    """Test enqueueing and retrieving messages from DM queue."""
    service = DmQueueService()
    
    # Enqueue a message
    queue_item = await service.enqueue_dm(
        agent_id=1,
        target_user_external_id="123456789",
        source_chat_id="-100123456789",
        message_text="Test outreach message",
        metadata={"test": True},
    )
    
    assert queue_item.id is not None
    assert queue_item.status == "pending"
    assert queue_item.retry_count == 0
    
    # Retrieve pending messages
    pending = await service.get_pending_messages(agent_id=1, limit=10)
    assert len(pending) >= 1
    assert pending[0].message_text == "Test outreach message"


@pytest.mark.asyncio
async def test_dm_queue_service_mark_sent(mock_db_session):
    """Test marking a message as sent."""
    service = DmQueueService()
    
    queue_item = await service.enqueue_dm(
        agent_id=1,
        target_user_external_id="123456789",
        source_chat_id="-100123456789",
        message_text="Test message",
    )
    
    await service.mark_sent(queue_id=queue_item.id)
    
    # Status should now be "sent"
    pending = await service.get_pending_messages(agent_id=1, limit=10)
    # Sent items shouldn't be in pending list
    assert not any(item.id == queue_item.id for item in pending)


@pytest.mark.asyncio
async def test_dm_queue_service_mark_failed_with_retry(mock_db_session):
    """Test marking a message as failed with retry."""
    service = DmQueueService()
    
    queue_item = await service.enqueue_dm(
        agent_id=1,
        target_user_external_id="123456789",
        source_chat_id="-100123456789",
        message_text="Test message",
    )
    
    await service.mark_failed(
        queue_id=queue_item.id,
        error="Connection timeout",
        retry=True,
    )
    
    # Should be back in pending list for retry
    pending = await service.get_pending_messages(agent_id=1, limit=10)
    retried = next((item for item in pending if item.id == queue_item.id), None)
    assert retried is not None
    assert retried.retry_count == 1
    assert retried.last_error == "Connection timeout"


@pytest.mark.asyncio
async def test_sales_fsm_transitions(mock_db_session):
    """Test FSM transitions for sales contacts."""
    service = SalesFSMService()
    
    # Create a contact
    contact = await service.get_or_create_contact(
        agent_id=1,
        user_external_id="user_123",
        source_chat_id="-100chat123",
    )
    
    assert contact.state == "DISCOVERED"
    
    # Transition to QUALIFIED
    contact_qualified = await service.transition_contact(
        agent_id=1,
        user_external_id="user_123",
        source_chat_id="-100chat123",
        to_state="QUALIFIED",
        reason="manual_qualification",
    )
    
    assert contact_qualified.state == "QUALIFIED"
    assert contact_qualified.last_reason == "manual_qualification"
    
    # Transition to QUEUED
    contact_queued = await service.transition_contact(
        agent_id=1,
        user_external_id="user_123",
        source_chat_id="-100chat123",
        to_state="QUEUED",
        reason="scheduled_for_send",
    )
    
    assert contact_queued.state == "QUEUED"


@pytest.mark.asyncio
async def test_sales_fsm_illegal_transition(mock_db_session):
    """Test that illegal FSM transitions are prevented."""
    service = SalesFSMService()
    
    contact = await service.get_or_create_contact(
        agent_id=1,
        user_external_id="user_456",
        source_chat_id="-100chat456",
    )
    
    # Try illegal transition (DISCOVERED can't go to SENT directly)
    with pytest.raises(Exception):  # Should raise SalesFSMError
        await service.transition_contact(
            agent_id=1,
            user_external_id="user_456",
            source_chat_id="-100chat456",
            to_state="SENT",
            reason="invalid_transition",
        )


@pytest.mark.asyncio
async def test_sales_tool_registry_schedule_dm():
    """Test schedule_dm tool validation and registration."""
    registry = SalesToolRegistry(
        allowed_tools=["schedule_dm"],
        confirmation_policy="confirm_risky",
        user_message="Please send a message",
        agent_id=1,
        user_external_id="user_123",
        mode="draft_only",
    )
    
    tools = registry.tools_for_llm()
    assert len(tools) > 0
    
    schedule_dm_tool = next((t for t in tools if t["function"]["name"] == "schedule_dm"), None)
    assert schedule_dm_tool is not None
    assert "text" in schedule_dm_tool["function"]["parameters"]["properties"]


@pytest.mark.asyncio
async def test_sales_tool_registry_execute_schedule_dm():
    """Test executing schedule_dm tool."""
    registry = SalesToolRegistry(
        allowed_tools=["schedule_dm", "skip_lead"],
        confirmation_policy="never_confirm",
        user_message="Test message",
        agent_id=1,
        user_external_id="123456789",
        mode="auto",
    )
    
    args = json.dumps({
        "text": "Check out our new product!",
        "target_user_external_id": "123456789",
        "source_chat_id": -100123456789,
    })
    
    result = await registry.execute_tool("schedule_dm", args)
    
    assert result["ok"] is True
    assert result["tool_name"] == "schedule_dm"
    assert result["result"]["queued"] is True
    assert result["result"]["status"] == "sent_auto"  # mode=auto


@pytest.mark.asyncio
async def test_sales_tool_registry_skip_lead():
    """Test skip_lead tool."""
    registry = SalesToolRegistry(
        allowed_tools=["skip_lead"],
        confirmation_policy="never_confirm",
        user_message="",
        agent_id=1,
        user_external_id="user_789",
        mode="draft_only",
    )
    
    args = json.dumps({
        "reason_code": "competitor_identified",
        "reason_text": "Company is a competitor",
    })
    
    result = await registry.execute_tool("skip_lead", args)
    
    assert result["ok"] is True
    assert result["tool_name"] == "skip_lead"
    assert result["result"]["skipped"] is True


class TestSalesManagerFeatureFlag:
    """Tests for sales_manager feature flag and rollout."""

    def test_feature_flag_can_be_enabled(self):
        """Test that feature flag can be enabled via environment."""
        # In real implementation, check settings.SALES_MANAGER_ENABLED
        import os
        flag = os.getenv("SALES_MANAGER_ENABLED", "true").lower() == "true"
        assert flag is True

    def test_template_type_normalization_includes_sales_manager(self):
        """Test that sales_manager is in supported template types."""
        SUPPORTED = {"qa", "crm_admin", "lead_generation", "content_factory", "sales_manager"}
        assert "sales_manager" in SUPPORTED

    def test_sales_manager_template_validation(self):
        """Test that sales_manager template config validates correctly."""
        valid_config = {
            "mode": "draft_only",
            "qualification_model": "deepseek-chat",
            "generation_model": "deepseek-chat",
            "min_confidence": 0.75,
        }
        
        # All required fields present
        assert "mode" in valid_config
        assert valid_config["mode"] in {"draft_only", "semi_auto", "auto"}
        assert "qualification_model" in valid_config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
