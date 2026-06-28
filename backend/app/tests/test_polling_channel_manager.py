"""Tests for PollingChannelManager and channel config fetch."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.channels.polling_manager import PollingChannelManager
from app.router_agents.dao import AgentChannelConnectionDAO


class _StubManager(PollingChannelManager):
    def __init__(self) -> None:
        super().__init__(
            lock_key=99_001,
            lock_name="test_manager",
            poll_interval_seconds=60,
            channel_name="TestManager",
            log_prefix="test",
            restart_on_fingerprint_change=True,
        )
        self.run_worker_calls: list[int] = []

    async def fetch_configs(self) -> list[dict]:
        return [{"connection_id": 1, "bot_id": 10}]

    async def run_worker(self, cfg: dict, stop: asyncio.Event) -> None:
        self.run_worker_calls.append(int(cfg["connection_id"]))
        await stop.wait()


@pytest.mark.asyncio
async def test_polling_manager_starts_worker_for_config():
    manager = _StubManager()
    with patch.object(manager._leader_lock, "ensure_acquired", AsyncMock(return_value=True)):
        await manager._sync_workers([{"connection_id": 1, "bot_id": 10}])
    assert manager.active_count == 1
    assert manager.run_worker_calls == [1]
    await manager.shutdown()


@pytest.mark.asyncio
async def test_polling_manager_removes_stale_worker():
    manager = _StubManager()
    with patch.object(manager._leader_lock, "ensure_acquired", AsyncMock(return_value=True)):
        await manager._sync_workers([{"connection_id": 1, "bot_id": 10}])
        await manager._sync_workers([])
    assert manager.active_count == 0
    await manager.shutdown()


def test_map_channel_config_row_telegram():
    row = {
        "agent_id": 3,
        "bot_id": 100,
        "connection_id": 7,
        "system_prompt": "hi",
        "welcome_message": "welcome",
        "template_type": "qa",
        "template_config": '{"k":1}',
        "external_id": None,
        "encrypted_credentials": "enc",
    }
    mapped = AgentChannelConnectionDAO._map_channel_config_row(row, "telegram_userbot")
    assert mapped["encrypted_userbot_bundle"] == "enc"
    assert mapped["template_config"] == {"k": 1}
    assert mapped["bot_id"] == 100


def test_map_channel_config_row_whatsapp_phone():
    row = {
        "agent_id": 3,
        "bot_id": None,
        "connection_id": 7,
        "system_prompt": "",
        "welcome_message": None,
        "template_type": "sales_manager",
        "template_config": None,
        "external_id": "+79001234567",
        "encrypted_credentials": "enc",
    }
    mapped = AgentChannelConnectionDAO._map_channel_config_row(row, "whatsapp_userbot")
    assert mapped["bot_id"] == 3
    assert mapped["phone_number"] == "+79001234567"
