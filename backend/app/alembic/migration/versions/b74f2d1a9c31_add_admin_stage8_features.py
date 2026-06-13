"""add stage8 admin template features

Revision ID: b74f2d1a9c31
Revises: a6c9d4e8f1b2
Create Date: 2026-04-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b74f2d1a9c31"
down_revision: Union[str, Sequence[str], None] = "a6c9d4e8f1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE admin_appointments
        DROP CONSTRAINT IF EXISTS ck_admin_appointments_status
        """
    )
    op.execute(
        """
        ALTER TABLE admin_appointments
        ADD CONSTRAINT ck_admin_appointments_status
        CHECK (status IN ('pending_confirmation','booked','confirmed','in_progress','cancelled','completed','no_show'))
        """
    )
    op.execute("ALTER TABLE admin_appointments DROP CONSTRAINT IF EXISTS ex_admin_appointments_staff_time")
    op.execute("ALTER TABLE admin_appointments DROP CONSTRAINT IF EXISTS ex_admin_appointments_resource_time")
    op.execute(
        """
        ALTER TABLE admin_appointments
        ADD CONSTRAINT ex_admin_appointments_staff_time
        EXCLUDE USING GIST (
            agent_id WITH =,
            staff_id WITH =,
            tsrange(starts_at, ends_at, '[)') WITH &&
        )
        WHERE (staff_id IS NOT NULL AND status IN ('pending_confirmation','booked','confirmed','in_progress'))
        """
    )
    op.execute(
        """
        ALTER TABLE admin_appointments
        ADD CONSTRAINT ex_admin_appointments_resource_time
        EXCLUDE USING GIST (
            agent_id WITH =,
            resource_id WITH =,
            tsrange(starts_at, ends_at, '[)') WITH &&
        )
        WHERE (resource_id IS NOT NULL AND status IN ('pending_confirmation','booked','confirmed','in_progress'))
        """
    )

    op.create_table(
        "admin_waitlist_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("client_external_id", sa.String(length=128), nullable=False),
        sa.Column("client_name", sa.String(length=128), nullable=True),
        sa.Column("service_id", sa.Integer(), nullable=True),
        sa.Column("desired_staff_id", sa.Integer(), nullable=True),
        sa.Column("desired_resource_id", sa.Integer(), nullable=True),
        sa.Column("earliest_starts_at", sa.DateTime(), nullable=True),
        sa.Column("latest_ends_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="waiting"),
        sa.Column("matched_appointment_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('waiting','matched','cancelled')", name="ck_admin_waitlist_entries_status"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["admin_services.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["desired_staff_id"], ["admin_staff.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["desired_resource_id"], ["admin_resources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["matched_appointment_id"], ["admin_appointments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_waitlist_entries_agent_id", "admin_waitlist_entries", ["agent_id"], unique=False)
    op.create_index("ix_admin_waitlist_entries_client_external_id", "admin_waitlist_entries", ["client_external_id"], unique=False)
    op.create_index("ix_admin_waitlist_entries_service_id", "admin_waitlist_entries", ["service_id"], unique=False)
    op.create_index("ix_admin_waitlist_entries_desired_staff_id", "admin_waitlist_entries", ["desired_staff_id"], unique=False)
    op.create_index("ix_admin_waitlist_entries_desired_resource_id", "admin_waitlist_entries", ["desired_resource_id"], unique=False)
    op.create_index("ix_admin_waitlist_entries_matched_appointment_id", "admin_waitlist_entries", ["matched_appointment_id"], unique=False)
    op.create_index("ix_admin_waitlist_entries_status", "admin_waitlist_entries", ["status"], unique=False)
    op.create_index(
        "ix_admin_waitlist_entries_agent_status_created",
        "admin_waitlist_entries",
        ["agent_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "admin_client_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("client_external_id", sa.String(length=128), nullable=False),
        sa.Column("client_name", sa.String(length=128), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=True),
        sa.Column("preferences_json", sa.Text(), nullable=True),
        sa.Column("history_json", sa.Text(), nullable=True),
        sa.Column("last_visit_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "client_external_id", name="uq_admin_client_profiles_agent_client"),
    )
    op.create_index("ix_admin_client_profiles_agent_id", "admin_client_profiles", ["agent_id"], unique=False)
    op.create_index("ix_admin_client_profiles_client_external_id", "admin_client_profiles", ["client_external_id"], unique=False)
    op.create_index("ix_admin_client_profiles_created_at", "admin_client_profiles", ["created_at"], unique=False)
    op.create_index(
        "ix_admin_client_profiles_agent_last_visit",
        "admin_client_profiles",
        ["agent_id", "last_visit_at"],
        unique=False,
    )

    op.create_table(
        "admin_quick_reply_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "title", name="uq_admin_quick_reply_agent_title"),
    )
    op.create_index("ix_admin_quick_reply_templates_agent_id", "admin_quick_reply_templates", ["agent_id"], unique=False)
    op.create_index("ix_admin_quick_reply_templates_created_at", "admin_quick_reply_templates", ["created_at"], unique=False)
    op.create_index(
        "ix_admin_quick_reply_agent_active",
        "admin_quick_reply_templates",
        ["agent_id", "is_active"],
        unique=False,
    )

    op.create_table(
        "admin_appointment_reminder_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=False),
        sa.Column("reminder_type", sa.String(length=16), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["appointment_id"], ["admin_appointments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "appointment_id",
            "reminder_type",
            name="uq_admin_appointment_reminder_logs_appointment_type",
        ),
    )
    op.create_index("ix_admin_appointment_reminder_logs_agent_id", "admin_appointment_reminder_logs", ["agent_id"], unique=False)
    op.create_index("ix_admin_appointment_reminder_logs_appointment_id", "admin_appointment_reminder_logs", ["appointment_id"], unique=False)
    op.create_index("ix_admin_appointment_reminder_logs_reminder_type", "admin_appointment_reminder_logs", ["reminder_type"], unique=False)
    op.create_index("ix_admin_appointment_reminder_logs_sent_at", "admin_appointment_reminder_logs", ["sent_at"], unique=False)
    op.create_index(
        "ix_admin_appointment_reminder_logs_agent_type_sent",
        "admin_appointment_reminder_logs",
        ["agent_id", "reminder_type", "sent_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_admin_appointment_reminder_logs_agent_type_sent", table_name="admin_appointment_reminder_logs")
    op.drop_index("ix_admin_appointment_reminder_logs_sent_at", table_name="admin_appointment_reminder_logs")
    op.drop_index("ix_admin_appointment_reminder_logs_reminder_type", table_name="admin_appointment_reminder_logs")
    op.drop_index("ix_admin_appointment_reminder_logs_appointment_id", table_name="admin_appointment_reminder_logs")
    op.drop_index("ix_admin_appointment_reminder_logs_agent_id", table_name="admin_appointment_reminder_logs")
    op.drop_table("admin_appointment_reminder_logs")

    op.drop_index("ix_admin_quick_reply_agent_active", table_name="admin_quick_reply_templates")
    op.drop_index("ix_admin_quick_reply_templates_created_at", table_name="admin_quick_reply_templates")
    op.drop_index("ix_admin_quick_reply_templates_agent_id", table_name="admin_quick_reply_templates")
    op.drop_table("admin_quick_reply_templates")

    op.drop_index("ix_admin_client_profiles_agent_last_visit", table_name="admin_client_profiles")
    op.drop_index("ix_admin_client_profiles_created_at", table_name="admin_client_profiles")
    op.drop_index("ix_admin_client_profiles_client_external_id", table_name="admin_client_profiles")
    op.drop_index("ix_admin_client_profiles_agent_id", table_name="admin_client_profiles")
    op.drop_table("admin_client_profiles")

    op.drop_index("ix_admin_waitlist_entries_agent_status_created", table_name="admin_waitlist_entries")
    op.drop_index("ix_admin_waitlist_entries_status", table_name="admin_waitlist_entries")
    op.drop_index("ix_admin_waitlist_entries_matched_appointment_id", table_name="admin_waitlist_entries")
    op.drop_index("ix_admin_waitlist_entries_desired_resource_id", table_name="admin_waitlist_entries")
    op.drop_index("ix_admin_waitlist_entries_desired_staff_id", table_name="admin_waitlist_entries")
    op.drop_index("ix_admin_waitlist_entries_service_id", table_name="admin_waitlist_entries")
    op.drop_index("ix_admin_waitlist_entries_client_external_id", table_name="admin_waitlist_entries")
    op.drop_index("ix_admin_waitlist_entries_agent_id", table_name="admin_waitlist_entries")
    op.drop_table("admin_waitlist_entries")

    op.execute("ALTER TABLE admin_appointments DROP CONSTRAINT IF EXISTS ex_admin_appointments_resource_time")
    op.execute("ALTER TABLE admin_appointments DROP CONSTRAINT IF EXISTS ex_admin_appointments_staff_time")
    op.execute(
        """
        ALTER TABLE admin_appointments
        ADD CONSTRAINT ex_admin_appointments_staff_time
        EXCLUDE USING GIST (
            agent_id WITH =,
            staff_id WITH =,
            tsrange(starts_at, ends_at, '[)') WITH &&
        )
        WHERE (staff_id IS NOT NULL AND status IN ('booked','confirmed','in_progress'))
        """
    )
    op.execute(
        """
        ALTER TABLE admin_appointments
        ADD CONSTRAINT ex_admin_appointments_resource_time
        EXCLUDE USING GIST (
            agent_id WITH =,
            resource_id WITH =,
            tsrange(starts_at, ends_at, '[)') WITH &&
        )
        WHERE (resource_id IS NOT NULL AND status IN ('booked','confirmed','in_progress'))
        """
    )
    op.execute("ALTER TABLE admin_appointments DROP CONSTRAINT IF EXISTS ck_admin_appointments_status")
    op.execute(
        """
        ALTER TABLE admin_appointments
        ADD CONSTRAINT ck_admin_appointments_status
        CHECK (status IN ('booked','confirmed','in_progress','cancelled','completed','no_show'))
        """
    )
