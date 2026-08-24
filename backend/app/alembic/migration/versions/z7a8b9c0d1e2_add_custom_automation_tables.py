"""add custom automation tables

Revision ID: z7a8b9c0d1e2
Revises: b1c2d3e4f5g6
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "z7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5g6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. custom_admins
    op.create_table(
        "custom_admins",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_custom_admins_username", "custom_admins", ["username"], unique=True)
    op.create_index("ix_custom_admins_is_active", "custom_admins", ["is_active"], unique=False)

    # 2. custom_automations
    op.create_table(
        "custom_automations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("client_name", sa.String(length=200), nullable=True),
        sa.Column("industry", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("is_chat_monitoring_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_neurocommenting_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_digital_footprint_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_dmp_one_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_amocrm_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("rotation_strategy", sa.String(length=32), server_default=sa.text("'round_robin'"), nullable=False),
        sa.Column("max_daily_messages_per_account", sa.Integer(), server_default=sa.text("50"), nullable=False),
        sa.Column("lead_warmup_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("lead_manager_contact", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["custom_admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_custom_automations_status", "custom_automations", ["status"], unique=False)
    op.create_index("ix_custom_automations_created_by_admin_id", "custom_automations", ["created_by_admin_id"], unique=False)

    # 3. custom_automation_credentials
    op.create_table(
        "custom_automation_credentials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("custom_automation_id", "username"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_custom_automation_credentials_automation_id", "custom_automation_credentials", ["custom_automation_id"], unique=False)
    op.create_index("ix_custom_automation_credentials_is_active", "custom_automation_credentials", ["is_active"], unique=False)

    # 4. social_accounts
    op.create_table(
        "social_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=32), server_default=sa.text("'telegram'"), nullable=False),
        sa.Column("phone_number", sa.String(length=32), nullable=True),
        sa.Column("username", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("encrypted_session", sa.Text(), nullable=False),
        sa.Column("session_file_path", sa.String(length=512), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("avatar_file_path", sa.String(length=512), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("current_bio", sa.Text(), nullable=True),
        sa.Column("current_avatar_hash", sa.String(length=64), nullable=True),
        sa.Column("account_class", sa.String(length=32), server_default=sa.text("'one_day'"), nullable=False),
        sa.Column("auto_classified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("trust_score", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_banned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("banned_at", sa.DateTime(), nullable=True),
        sa.Column("ban_reason", sa.String(length=255), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("last_health_check_at", sa.DateTime(), nullable=True),
        sa.Column("daily_messages_sent", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("daily_messages_reset_at", sa.DateTime(), nullable=True),
        sa.Column("purchase_cost_rub", sa.Float(), nullable=True),
        sa.Column("purchase_source", sa.String(length=255), nullable=True),
        sa.Column("account_age_days", sa.Integer(), nullable=True),
        sa.Column("friends_count", sa.Integer(), nullable=True),
        sa.Column("activity_score", sa.Float(), nullable=True),
        sa.Column("spam_complaints_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_social_accounts_provider", "social_accounts", ["provider"], unique=False)
    op.create_index("ix_social_accounts_username", "social_accounts", ["username"], unique=False)
    op.create_index("ix_social_accounts_account_class", "social_accounts", ["account_class"], unique=False)
    op.create_index("ix_social_accounts_is_active", "social_accounts", ["is_active"], unique=False)
    op.create_index("ix_social_accounts_is_banned", "social_accounts", ["is_banned"], unique=False)

    # 5. account_pools
    op.create_table(
        "account_pools",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_pools_automation_id", "account_pools", ["custom_automation_id"], unique=False)
    op.create_index("ix_account_pools_is_default", "account_pools", ["is_default"], unique=False)

    # 6. pool_accounts
    op.create_table(
        "pool_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("account_pool_id", sa.Integer(), nullable=False),
        sa.Column("social_account_id", sa.Integer(), nullable=False),
        sa.Column("assigned_class", sa.String(length=32), server_default=sa.text("'one_day'"), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_pool_id"], ["account_pools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["social_account_id"], ["social_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_pool_id", "social_account_id"),
    )
    op.create_index("ix_pool_accounts_automation_id", "pool_accounts", ["custom_automation_id"], unique=False)
    op.create_index("ix_pool_accounts_pool_id", "pool_accounts", ["account_pool_id"], unique=False)
    op.create_index("ix_pool_accounts_social_account_id", "pool_accounts", ["social_account_id"], unique=False)
    op.create_index("ix_pool_accounts_assigned_class", "pool_accounts", ["assigned_class"], unique=False)

    # 7. chat_import_jobs
    op.create_table(
        "chat_import_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("total_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("processed_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_log", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["custom_admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_import_jobs_automation_id", "chat_import_jobs", ["custom_automation_id"], unique=False)
    op.create_index("ix_chat_import_jobs_status", "chat_import_jobs", ["status"], unique=False)

    # 8. custom_prompts (must exist before chat_discovery_tasks and chat_messages)
    op.create_table(
        "custom_prompts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("prompt_type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=64), server_default=sa.text("'deepseek-chat'"), nullable=False),
        sa.Column("temperature", sa.Float(), server_default=sa.text("0.7"), nullable=False),
        sa.Column("max_tokens", sa.Integer(), server_default=sa.text("1000"), nullable=False),
        sa.Column("response_format", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_custom_prompts_automation_id", "custom_prompts", ["custom_automation_id"], unique=False)
    op.create_index("ix_custom_prompts_prompt_type", "custom_prompts", ["prompt_type"], unique=False)
    op.create_index("ix_custom_prompts_is_active", "custom_prompts", ["is_active"], unique=False)

    # 9. chat_discovery_tasks
    op.create_table(
        "chat_discovery_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("prompt_id", sa.Integer(), nullable=True),
        sa.Column("mode", sa.String(length=32), server_default=sa.text("'monitoring'"), nullable=False),
        sa.Column("max_chats", sa.Integer(), server_default=sa.text("50"), nullable=False),
        sa.Column("require_approval", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("relevance_threshold", sa.Numeric(precision=3, scale=2), server_default=sa.text("0.6"), nullable=False),
        sa.Column("found_chats", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("joined_chats", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rejected_chats", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prompt_id"], ["custom_prompts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_discovery_tasks_automation_id", "chat_discovery_tasks", ["custom_automation_id"], unique=False)
    op.create_index("ix_chat_discovery_tasks_status", "chat_discovery_tasks", ["status"], unique=False)
    op.create_index("ix_chat_discovery_tasks_prompt_id", "chat_discovery_tasks", ["prompt_id"], unique=False)

    # 10. chat_targets
    op.create_table(
        "chat_targets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), server_default=sa.text("'telegram'"), nullable=False),
        sa.Column("external_chat_id", sa.String(length=128), nullable=True),
        sa.Column("invite_link", sa.String(length=512), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("chat_type", sa.String(length=32), nullable=True),
        sa.Column("mode", sa.String(length=32), server_default=sa.text("'inactive'"), nullable=False),
        sa.Column("source", sa.String(length=32), server_default=sa.text("'manual'"), nullable=False),
        sa.Column("import_job_id", sa.Integer(), nullable=True),
        sa.Column("discovery_task_id", sa.Integer(), nullable=True),
        sa.Column("monitoring_config", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("neurocommenting_config", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("discussion_config", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("join_status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("join_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_join_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("last_join_error", sa.Text(), nullable=True),
        sa.Column("next_join_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
        sa.Column("joined_by_account_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_scanned_at", sa.DateTime(), nullable=True),
        sa.Column("last_message_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["discovery_task_id"], ["chat_discovery_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["import_job_id"], ["chat_import_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["joined_by_account_id"], ["social_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_targets_automation_id", "chat_targets", ["custom_automation_id"], unique=False)
    op.create_index("ix_chat_targets_external_chat_id", "chat_targets", ["external_chat_id"], unique=False)
    op.create_index("ix_chat_targets_mode", "chat_targets", ["mode"], unique=False)
    op.create_index("ix_chat_targets_source", "chat_targets", ["source"], unique=False)
    op.create_index("ix_chat_targets_join_status", "chat_targets", ["join_status"], unique=False)
    op.create_index("ix_chat_targets_import_job_id", "chat_targets", ["import_job_id"], unique=False)
    op.create_index("ix_chat_targets_discovery_task_id", "chat_targets", ["discovery_task_id"], unique=False)
    op.create_index("ix_chat_targets_joined_by_account_id", "chat_targets", ["joined_by_account_id"], unique=False)
    op.create_index("ix_chat_targets_is_active", "chat_targets", ["is_active"], unique=False)

    # 11. chat_messages
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("chat_target_id", sa.Integer(), nullable=False),
        sa.Column("external_message_id", sa.String(length=128), nullable=False),
        sa.Column("external_chat_id", sa.String(length=128), nullable=False),
        sa.Column("sender_id", sa.String(length=128), nullable=True),
        sa.Column("sender_username", sa.String(length=128), nullable=True),
        sa.Column("sender_name", sa.String(length=128), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("dedup_key", sa.String(length=255), nullable=True),
        sa.Column("processed_by_account_id", sa.Integer(), nullable=True),
        sa.Column("is_processed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_duplicate", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("matched_intent", sa.String(length=64), nullable=True),
        sa.Column("trigger_confidence", sa.Float(), nullable=True),
        sa.Column("matched_prompt_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chat_target_id"], ["chat_targets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_prompt_id"], ["custom_prompts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["processed_by_account_id"], ["social_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("custom_automation_id", "dedup_key", name="uq_chat_message_dedup"),
    )
    op.create_index("ix_chat_messages_automation_id", "chat_messages", ["custom_automation_id"], unique=False)
    op.create_index("ix_chat_messages_chat_target_id", "chat_messages", ["chat_target_id"], unique=False)
    op.create_index("ix_chat_messages_external_chat_id", "chat_messages", ["external_chat_id"], unique=False)
    op.create_index("ix_chat_messages_external_message_id", "chat_messages", ["external_message_id"], unique=False)
    op.create_index("ix_chat_messages_dedup_key", "chat_messages", ["dedup_key"], unique=False)
    op.create_index("ix_chat_messages_is_processed", "chat_messages", ["is_processed"], unique=False)
    op.create_index("ix_chat_messages_is_duplicate", "chat_messages", ["is_duplicate"], unique=False)
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"], unique=False)

    # 12. dmp_one_imports (must exist before custom_leads)
    op.create_table(
        "dmp_one_imports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("import_type", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=True),
        sa.Column("requested_count", sa.Integer(), nullable=True),
        sa.Column("received_count", sa.Integer(), nullable=True),
        sa.Column("purchased_count", sa.Integer(), nullable=True),
        sa.Column("cost_rub", sa.Float(), nullable=True),
        sa.Column("cpl_rub", sa.Float(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dmp_one_imports_automation_id", "dmp_one_imports", ["custom_automation_id"], unique=False)
    op.create_index("ix_dmp_one_imports_status", "dmp_one_imports", ["status"], unique=False)

    # 13. custom_leads
    op.create_table(
        "custom_leads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("chat_message_id", sa.Integer(), nullable=True),
        sa.Column("dmp_one_import_id", sa.Integer(), nullable=True),
        sa.Column("contact_type", sa.String(length=32), nullable=False),
        sa.Column("contact_value", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("position", sa.String(length=255), nullable=True),
        sa.Column("dmp_raw_data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("assigned_account_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'new'"), nullable=False),
        sa.Column("status_history", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("amocrm_lead_id", sa.String(length=128), nullable=True),
        sa.Column("amocrm_contact_id", sa.String(length=128), nullable=True),
        sa.Column("amocrm_pipeline_id", sa.String(length=128), nullable=True),
        sa.Column("amocrm_status_id", sa.String(length=128), nullable=True),
        sa.Column("transferred_at", sa.DateTime(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chat_message_id"], ["chat_messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["dmp_one_import_id"], ["dmp_one_imports.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_account_id"], ["social_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_custom_leads_automation_id", "custom_leads", ["custom_automation_id"], unique=False)
    op.create_index("ix_custom_leads_source", "custom_leads", ["source"], unique=False)
    op.create_index("ix_custom_leads_status", "custom_leads", ["status"], unique=False)
    op.create_index("ix_custom_leads_assigned_account_id", "custom_leads", ["assigned_account_id"], unique=False)
    op.create_index("ix_custom_leads_chat_message_id", "custom_leads", ["chat_message_id"], unique=False)
    op.create_index("ix_custom_leads_dmp_one_import_id", "custom_leads", ["dmp_one_import_id"], unique=False)

    # 14. custom_lead_messages
    op.create_table(
        "custom_lead_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_lead_id", sa.Integer(), nullable=False),
        sa.Column("social_account_id", sa.Integer(), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("external_message_id", sa.String(length=128), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["custom_lead_id"], ["custom_leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["social_account_id"], ["social_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_custom_lead_messages_lead_id", "custom_lead_messages", ["custom_lead_id"], unique=False)
    op.create_index("ix_custom_lead_messages_social_account_id", "custom_lead_messages", ["social_account_id"], unique=False)
    op.create_index("ix_custom_lead_messages_sent_at", "custom_lead_messages", ["sent_at"], unique=False)

    # 15. automation_action_logs
    op.create_table(
        "automation_action_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("social_account_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["social_account_id"], ["social_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_action_logs_automation_id", "automation_action_logs", ["custom_automation_id"], unique=False)
    op.create_index("ix_automation_action_logs_social_account_id", "automation_action_logs", ["social_account_id"], unique=False)
    op.create_index("ix_automation_action_logs_action_type", "automation_action_logs", ["action_type"], unique=False)
    op.create_index("ix_automation_action_logs_result", "automation_action_logs", ["result"], unique=False)
    op.create_index("ix_automation_action_logs_created_at", "automation_action_logs", ["created_at"], unique=False)

    # 16. amocrm_connections
    op.create_table(
        "amocrm_connections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("custom_automation_id", sa.Integer(), nullable=False),
        sa.Column("subdomain", sa.String(length=128), nullable=False),
        sa.Column("access_token_hash", sa.String(length=255), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=255), nullable=True),
        sa.Column("pipeline_id", sa.String(length=128), nullable=True),
        sa.Column("responsible_user_id", sa.String(length=128), nullable=True),
        sa.Column("lead_status_id", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["custom_automation_id"], ["custom_automations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("custom_automation_id"),
    )
    op.create_index("ix_amocrm_connections_automation_id", "amocrm_connections", ["custom_automation_id"], unique=True)
    op.create_index("ix_amocrm_connections_is_active", "amocrm_connections", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_amocrm_connections_is_active", table_name="amocrm_connections")
    op.drop_index("ix_amocrm_connections_automation_id", table_name="amocrm_connections")
    op.drop_table("amocrm_connections")

    op.drop_index("ix_automation_action_logs_created_at", table_name="automation_action_logs")
    op.drop_index("ix_automation_action_logs_result", table_name="automation_action_logs")
    op.drop_index("ix_automation_action_logs_action_type", table_name="automation_action_logs")
    op.drop_index("ix_automation_action_logs_social_account_id", table_name="automation_action_logs")
    op.drop_index("ix_automation_action_logs_automation_id", table_name="automation_action_logs")
    op.drop_table("automation_action_logs")

    op.drop_index("ix_custom_lead_messages_sent_at", table_name="custom_lead_messages")
    op.drop_index("ix_custom_lead_messages_social_account_id", table_name="custom_lead_messages")
    op.drop_index("ix_custom_lead_messages_lead_id", table_name="custom_lead_messages")
    op.drop_table("custom_lead_messages")

    op.drop_index("ix_custom_leads_dmp_one_import_id", table_name="custom_leads")
    op.drop_index("ix_custom_leads_chat_message_id", table_name="custom_leads")
    op.drop_index("ix_custom_leads_assigned_account_id", table_name="custom_leads")
    op.drop_index("ix_custom_leads_status", table_name="custom_leads")
    op.drop_index("ix_custom_leads_source", table_name="custom_leads")
    op.drop_index("ix_custom_leads_automation_id", table_name="custom_leads")
    op.drop_table("custom_leads")

    op.drop_index("ix_dmp_one_imports_status", table_name="dmp_one_imports")
    op.drop_index("ix_dmp_one_imports_automation_id", table_name="dmp_one_imports")
    op.drop_table("dmp_one_imports")

    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_is_duplicate", table_name="chat_messages")
    op.drop_index("ix_chat_messages_is_processed", table_name="chat_messages")
    op.drop_index("ix_chat_messages_dedup_key", table_name="chat_messages")
    op.drop_index("ix_chat_messages_external_message_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_external_chat_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_chat_target_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_automation_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("ix_chat_targets_is_active", table_name="chat_targets")
    op.drop_index("ix_chat_targets_joined_by_account_id", table_name="chat_targets")
    op.drop_index("ix_chat_targets_discovery_task_id", table_name="chat_targets")
    op.drop_index("ix_chat_targets_import_job_id", table_name="chat_targets")
    op.drop_index("ix_chat_targets_join_status", table_name="chat_targets")
    op.drop_index("ix_chat_targets_source", table_name="chat_targets")
    op.drop_index("ix_chat_targets_mode", table_name="chat_targets")
    op.drop_index("ix_chat_targets_external_chat_id", table_name="chat_targets")
    op.drop_index("ix_chat_targets_automation_id", table_name="chat_targets")
    op.drop_table("chat_targets")

    op.drop_index("ix_chat_discovery_tasks_prompt_id", table_name="chat_discovery_tasks")
    op.drop_index("ix_chat_discovery_tasks_status", table_name="chat_discovery_tasks")
    op.drop_index("ix_chat_discovery_tasks_automation_id", table_name="chat_discovery_tasks")
    op.drop_table("chat_discovery_tasks")

    op.drop_index("ix_custom_prompts_is_active", table_name="custom_prompts")
    op.drop_index("ix_custom_prompts_prompt_type", table_name="custom_prompts")
    op.drop_index("ix_custom_prompts_automation_id", table_name="custom_prompts")
    op.drop_table("custom_prompts")

    op.drop_index("ix_chat_import_jobs_status", table_name="chat_import_jobs")
    op.drop_index("ix_chat_import_jobs_automation_id", table_name="chat_import_jobs")
    op.drop_table("chat_import_jobs")

    op.drop_index("ix_pool_accounts_assigned_class", table_name="pool_accounts")
    op.drop_index("ix_pool_accounts_social_account_id", table_name="pool_accounts")
    op.drop_index("ix_pool_accounts_pool_id", table_name="pool_accounts")
    op.drop_table("pool_accounts")

    op.drop_index("ix_account_pools_is_default", table_name="account_pools")
    op.drop_index("ix_account_pools_automation_id", table_name="account_pools")
    op.drop_table("account_pools")

    op.drop_index("ix_social_accounts_is_banned", table_name="social_accounts")
    op.drop_index("ix_social_accounts_is_active", table_name="social_accounts")
    op.drop_index("ix_social_accounts_account_class", table_name="social_accounts")
    op.drop_index("ix_social_accounts_username", table_name="social_accounts")
    op.drop_index("ix_social_accounts_provider", table_name="social_accounts")
    op.drop_table("social_accounts")

    op.drop_index("ix_custom_automation_credentials_is_active", table_name="custom_automation_credentials")
    op.drop_index("ix_custom_automation_credentials_automation_id", table_name="custom_automation_credentials")
    op.drop_table("custom_automation_credentials")

    op.drop_index("ix_custom_automations_created_by_admin_id", table_name="custom_automations")
    op.drop_index("ix_custom_automations_status", table_name="custom_automations")
    op.drop_table("custom_automations")

    op.drop_index("ix_custom_admins_is_active", table_name="custom_admins")
    op.drop_index("ix_custom_admins_username", table_name="custom_admins")
    op.drop_table("custom_admins")
