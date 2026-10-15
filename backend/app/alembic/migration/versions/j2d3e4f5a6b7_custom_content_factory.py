"""Custom AI content factory tables.

Revision ID: j2d3e4f5a6b7
Revises: i1c2d3e4f5a6
Create Date: 2026-10-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "j2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "i1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

jsonb = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "custom_content_factory_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "custom_automation_id",
            sa.Integer(),
            sa.ForeignKey("custom_automations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sandbox_mode", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("product_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("product_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("product_url", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("cta_text", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("audience", sa.Text(), nullable=False, server_default=""),
        sa.Column("niche", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("content_formats", jsonb, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("visual_styles", jsonb, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("language", sa.String(length=16), nullable=False, server_default="ru"),
        sa.Column("tone", sa.String(length=64), nullable=False, server_default="expert_friendly"),
        sa.Column("brand_voice", sa.Text(), nullable=False, server_default=""),
        sa.Column("forbidden_topics", sa.Text(), nullable=False, server_default=""),
        sa.Column("videos_per_day", sa.Float(), nullable=False, server_default="1"),
        sa.Column("duration_min", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("duration_max", sa.Integer(), nullable=False, server_default="45"),
        sa.Column("aspect_ratio", sa.String(length=16), nullable=False, server_default="9:16"),
        sa.Column("posting_window_start", sa.String(length=8), nullable=False, server_default="09:00"),
        sa.Column("posting_window_end", sa.String(length=8), nullable=False, server_default="21:00"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Moscow"),
        sa.Column("idea_model", sa.String(length=128), nullable=False, server_default="deepseek-chat"),
        sa.Column("script_model", sa.String(length=128), nullable=False, server_default="deepseek-chat"),
        sa.Column("video_model", sa.String(length=128), nullable=False, server_default="kling"),
        sa.Column("tts_model", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("openai_api_key_enc", sa.Text(), nullable=True),
        sa.Column("anthropic_api_key_enc", sa.Text(), nullable=True),
        sa.Column("kling_api_key_enc", sa.Text(), nullable=True),
        sa.Column("runway_api_key_enc", sa.Text(), nullable=True),
        sa.Column("luma_api_key_enc", sa.Text(), nullable=True),
        sa.Column("elevenlabs_api_key_enc", sa.Text(), nullable=True),
        sa.Column("warmup_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("warmup_actions_per_day", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("max_posts_per_account_per_day", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("stagger_min_minutes", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("uniqualize_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("unique_per_platform", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("hook_required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("avoid_exact_hour", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("shadowban_pause_zero_views", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("shadowban_zero_views_threshold", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_enqueued_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("custom_automation_id", name="uq_content_factory_settings_automation"),
    )
    op.create_index(
        "ix_custom_content_factory_settings_custom_automation_id",
        "custom_content_factory_settings",
        ["custom_automation_id"],
        unique=True,
    )
    op.create_index("ix_custom_content_factory_settings_enabled", "custom_content_factory_settings", ["enabled"])

    op.create_table(
        "custom_content_factory_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "custom_automation_id",
            sa.Integer(),
            sa.ForeignKey("custom_automations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("handle", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("external_id", sa.String(length=191), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="connected"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("credentials_enc", sa.Text(), nullable=True),
        sa.Column("warmup_started_at", sa.DateTime(), nullable=True),
        sa.Column("warmup_completed_at", sa.DateTime(), nullable=True),
        sa.Column("warmup_actions_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_posted_at", sa.DateTime(), nullable=True),
        sa.Column("posts_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("posts_today_date", sa.Date(), nullable=True),
        sa.Column("health_score", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("risk_flags", jsonb, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("extra", jsonb, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_custom_content_factory_accounts_custom_automation_id",
        "custom_content_factory_accounts",
        ["custom_automation_id"],
    )
    op.create_index("ix_custom_content_factory_accounts_platform", "custom_content_factory_accounts", ["platform"])
    op.create_index("ix_custom_content_factory_accounts_status", "custom_content_factory_accounts", ["status"])
    op.create_index(
        "ix_cf_accounts_automation_platform",
        "custom_content_factory_accounts",
        ["custom_automation_id", "platform"],
    )
    op.create_index("ix_custom_content_factory_accounts_created_at", "custom_content_factory_accounts", ["created_at"])

    op.create_table(
        "custom_content_factory_videos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "custom_automation_id",
            sa.Integer(),
            sa.ForeignKey("custom_automations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("scheduled_for", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("idea", sa.Text(), nullable=False, server_default=""),
        sa.Column("hook", sa.Text(), nullable=False, server_default=""),
        sa.Column("script", sa.Text(), nullable=False, server_default=""),
        sa.Column("caption", sa.Text(), nullable=False, server_default=""),
        sa.Column("hashtags", jsonb, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("content_format", sa.String(length=64), nullable=False, server_default="educational"),
        sa.Column("visual_style", sa.String(length=64), nullable=False, server_default="realism"),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="35"),
        sa.Column("aspect_ratio", sa.String(length=16), nullable=False, server_default="9:16"),
        sa.Column("video_url", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("storyboard", jsonb, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("uniqualization", jsonb, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("uniqueness_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("token_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("render_task_id", sa.String(length=191), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("extra", jsonb, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_custom_content_factory_videos_custom_automation_id",
        "custom_content_factory_videos",
        ["custom_automation_id"],
    )
    op.create_index("ix_custom_content_factory_videos_status", "custom_content_factory_videos", ["status"])
    op.create_index("ix_cf_videos_automation_status", "custom_content_factory_videos", ["custom_automation_id", "status"])
    op.create_index("ix_cf_videos_scheduled_for", "custom_content_factory_videos", ["scheduled_for"])
    op.create_index("ix_custom_content_factory_videos_uniqueness_hash", "custom_content_factory_videos", ["uniqueness_hash"])
    op.create_index("ix_custom_content_factory_videos_created_at", "custom_content_factory_videos", ["created_at"])

    op.create_table(
        "custom_content_factory_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "video_id",
            sa.Integer(),
            sa.ForeignKey("custom_content_factory_videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("custom_content_factory_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("external_id", sa.String(length=191), nullable=False, server_default=""),
        sa.Column("posted_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("caption_variant", sa.Text(), nullable=False, server_default=""),
        sa.Column("uniqualization_applied", jsonb, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("likes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shares", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("saves", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hold_reason", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("analytics_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_custom_content_factory_posts_video_id", "custom_content_factory_posts", ["video_id"])
    op.create_index("ix_custom_content_factory_posts_account_id", "custom_content_factory_posts", ["account_id"])
    op.create_index("ix_custom_content_factory_posts_platform", "custom_content_factory_posts", ["platform"])
    op.create_index("ix_custom_content_factory_posts_status", "custom_content_factory_posts", ["status"])
    op.create_index("ix_cf_posts_video_platform", "custom_content_factory_posts", ["video_id", "platform"])
    op.create_index("ix_custom_content_factory_posts_posted_at", "custom_content_factory_posts", ["posted_at"])

    op.create_table(
        "custom_content_factory_token_usages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "custom_automation_id",
            sa.Integer(),
            sa.ForeignKey("custom_automations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "video_id",
            sa.Integer(),
            sa.ForeignKey("custom_content_factory_videos.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_custom_content_factory_token_usages_custom_automation_id",
        "custom_content_factory_token_usages",
        ["custom_automation_id"],
    )
    op.create_index("ix_custom_content_factory_token_usages_video_id", "custom_content_factory_token_usages", ["video_id"])
    op.create_index("ix_custom_content_factory_token_usages_operation", "custom_content_factory_token_usages", ["operation"])
    op.create_index("ix_custom_content_factory_token_usages_created_at", "custom_content_factory_token_usages", ["created_at"])
    op.create_index(
        "ix_cf_tokens_automation_created",
        "custom_content_factory_token_usages",
        ["custom_automation_id", "created_at"],
    )

    op.create_table(
        "custom_content_factory_warmup_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("custom_content_factory_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False, server_default="ok"),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_custom_content_factory_warmup_events_account_id",
        "custom_content_factory_warmup_events",
        ["account_id"],
    )
    op.create_index("ix_custom_content_factory_warmup_events_created_at", "custom_content_factory_warmup_events", ["created_at"])
    op.create_index(
        "ix_cf_warmup_account_created",
        "custom_content_factory_warmup_events",
        ["account_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("custom_content_factory_warmup_events")
    op.drop_table("custom_content_factory_token_usages")
    op.drop_table("custom_content_factory_posts")
    op.drop_table("custom_content_factory_videos")
    op.drop_table("custom_content_factory_accounts")
    op.drop_table("custom_content_factory_settings")
