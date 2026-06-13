"""Add article publisher tables: settings, topics, images, jobs

Revision ID: b9e4f2a7c1d3
Revises: a8d3f1c9e2b7
Create Date: 2026-05-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9e4f2a7c1d3"
down_revision: Union[str, Sequence[str], None] = "a8d3f1c9e2b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "article_publisher_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("posting_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("posting_frequency_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("vcru_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("vcru_email", sa.String(255), nullable=True),
        sa.Column("vcru_password_enc", sa.Text(), nullable=True),
        sa.Column("vcru_subsite_id", sa.String(64), nullable=True),
        sa.Column("zen_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("zen_oauth_token_enc", sa.Text(), nullable=True),
        sa.Column("zen_channel_id", sa.String(128), nullable=True),
        sa.Column("auto_topics_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "topic_categories_json",
            sa.Text(),
            nullable=False,
            server_default='["ИИ","IT","Автоматизация","Искусственный интеллект","Нейросети"]',
        ),
        sa.Column("promo_ratio", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("company_name", sa.String(256), nullable=False, server_default="RSD AI"),
        sa.Column("company_url", sa.String(512), nullable=True),
        sa.Column("company_description", sa.Text(), nullable=True),
        sa.Column("article_min_words", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("article_max_words", sa.Integer(), nullable=False, server_default="1500"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "article_publisher_topics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_article_publisher_topics_created_at",
        "article_publisher_topics",
        ["created_at"],
    )

    op.create_table(
        "article_publisher_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.String(512), nullable=False),
        sa.Column("storage_filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_filename"),
    )
    op.create_index(
        "ix_article_publisher_images_created_at",
        "article_publisher_images",
        ["created_at"],
    )

    op.create_table(
        "article_publisher_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("is_promo", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("article_title", sa.Text(), nullable=True),
        sa.Column("article_content", sa.Text(), nullable=True),
        sa.Column("published_url", sa.String(1024), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_article_publisher_jobs_status_scheduled",
        "article_publisher_jobs",
        ["status", "scheduled_for"],
    )


def downgrade() -> None:
    op.drop_index("ix_article_publisher_jobs_status_scheduled", table_name="article_publisher_jobs")
    op.drop_table("article_publisher_jobs")
    op.drop_index("ix_article_publisher_images_created_at", table_name="article_publisher_images")
    op.drop_table("article_publisher_images")
    op.drop_index("ix_article_publisher_topics_created_at", table_name="article_publisher_topics")
    op.drop_table("article_publisher_topics")
    op.drop_table("article_publisher_settings")
