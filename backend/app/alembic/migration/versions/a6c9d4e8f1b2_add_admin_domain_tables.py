"""add admin domain tables for beauty/dental template

Revision ID: a6c9d4e8f1b2
Revises: d9a7c4e1f2b6
Create Date: 2026-04-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6c9d4e8f1b2"
down_revision: Union[str, Sequence[str], None] = "d9a7c4e1f2b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_staff",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("full_name", sa.String(length=128), nullable=False),
        sa.Column("specializations_json", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("role IN ('master','doctor')", name="ck_admin_staff_role"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_staff_agent_id", "admin_staff", ["agent_id"], unique=False)
    op.create_index("ix_admin_staff_role", "admin_staff", ["role"], unique=False)
    op.create_index("ix_admin_staff_created_at", "admin_staff", ["created_at"], unique=False)
    op.create_index(
        "ix_admin_staff_agent_role_active",
        "admin_staff",
        ["agent_id", "role", "is_active"],
        unique=False,
    )

    op.create_table(
        "admin_resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("resource_type", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("resource_type IN ('chair','room','equipment')", name="ck_admin_resources_type"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "resource_type", "title", name="uq_admin_resources_agent_type_title"),
    )
    op.create_index("ix_admin_resources_agent_id", "admin_resources", ["agent_id"], unique=False)
    op.create_index("ix_admin_resources_resource_type", "admin_resources", ["resource_type"], unique=False)
    op.create_index("ix_admin_resources_created_at", "admin_resources", ["created_at"], unique=False)
    op.create_index(
        "ix_admin_resources_agent_type_active",
        "admin_resources",
        ["agent_id", "resource_type", "is_active"],
        unique=False,
    )

    op.create_table(
        "admin_services",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("target_role", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("price_minor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resource_type_filters_json", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("duration_minutes > 0", name="ck_admin_services_duration_gt_zero"),
        sa.CheckConstraint("price_minor >= 0", name="ck_admin_services_price_non_negative"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "title", name="uq_admin_services_agent_title"),
    )
    op.create_index("ix_admin_services_agent_id", "admin_services", ["agent_id"], unique=False)
    op.create_index("ix_admin_services_target_role", "admin_services", ["target_role"], unique=False)
    op.create_index("ix_admin_services_created_at", "admin_services", ["created_at"], unique=False)
    op.create_index(
        "ix_admin_services_agent_role_active",
        "admin_services",
        ["agent_id", "target_role", "is_active"],
        unique=False,
    )

    op.create_table(
        "admin_schedule_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=True),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("slot_kind", sa.String(length=24), nullable=False, server_default="work"),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_admin_schedule_slots_time_order"),
        sa.CheckConstraint("(staff_id IS NOT NULL) OR (resource_id IS NOT NULL)", name="ck_admin_schedule_slots_target"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["admin_staff.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resource_id"], ["admin_resources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "staff_id", "starts_at", "ends_at", name="uq_admin_schedule_slots_staff_exact"),
        sa.UniqueConstraint(
            "agent_id",
            "resource_id",
            "starts_at",
            "ends_at",
            name="uq_admin_schedule_slots_resource_exact",
        ),
    )
    op.create_index("ix_admin_schedule_slots_agent_id", "admin_schedule_slots", ["agent_id"], unique=False)
    op.create_index("ix_admin_schedule_slots_staff_id", "admin_schedule_slots", ["staff_id"], unique=False)
    op.create_index("ix_admin_schedule_slots_resource_id", "admin_schedule_slots", ["resource_id"], unique=False)
    op.create_index("ix_admin_schedule_slots_starts_at", "admin_schedule_slots", ["starts_at"], unique=False)
    op.create_index("ix_admin_schedule_slots_ends_at", "admin_schedule_slots", ["ends_at"], unique=False)
    op.create_index("ix_admin_schedule_slots_created_at", "admin_schedule_slots", ["created_at"], unique=False)
    op.create_index(
        "ix_admin_schedule_slots_agent_time",
        "admin_schedule_slots",
        ["agent_id", "starts_at", "ends_at"],
        unique=False,
    )

    op.create_table(
        "admin_appointments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=True),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("service_id", sa.Integer(), nullable=True),
        sa.Column("client_external_id", sa.String(length=128), nullable=False),
        sa.Column("client_name", sa.String(length=128), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="booked"),
        sa.Column("source_channel", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_admin_appointments_time_order"),
        sa.CheckConstraint(
            "status IN ('booked','confirmed','in_progress','cancelled','completed','no_show')",
            name="ck_admin_appointments_status",
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["admin_staff.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resource_id"], ["admin_resources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["service_id"], ["admin_services.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_appointments_agent_id", "admin_appointments", ["agent_id"], unique=False)
    op.create_index("ix_admin_appointments_staff_id", "admin_appointments", ["staff_id"], unique=False)
    op.create_index("ix_admin_appointments_resource_id", "admin_appointments", ["resource_id"], unique=False)
    op.create_index("ix_admin_appointments_service_id", "admin_appointments", ["service_id"], unique=False)
    op.create_index("ix_admin_appointments_starts_at", "admin_appointments", ["starts_at"], unique=False)
    op.create_index("ix_admin_appointments_ends_at", "admin_appointments", ["ends_at"], unique=False)
    op.create_index("ix_admin_appointments_status", "admin_appointments", ["status"], unique=False)
    op.create_index("ix_admin_appointments_created_at", "admin_appointments", ["created_at"], unique=False)
    op.create_index(
        "ix_admin_appointments_agent_status_time",
        "admin_appointments",
        ["agent_id", "status", "starts_at"],
        unique=False,
    )
    op.create_index(
        "ix_admin_appointments_client_lookup",
        "admin_appointments",
        ["agent_id", "client_external_id"],
        unique=False,
    )

    # PostgreSQL-only anti-overlap constraints (staff/resource conflicts).
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE admin_schedule_slots
        ADD CONSTRAINT ex_admin_schedule_slots_staff_time
        EXCLUDE USING GIST (
            agent_id WITH =,
            staff_id WITH =,
            tsrange(starts_at, ends_at, '[)') WITH &&
        )
        WHERE (staff_id IS NOT NULL AND is_active IS TRUE)
        """
    )
    op.execute(
        """
        ALTER TABLE admin_schedule_slots
        ADD CONSTRAINT ex_admin_schedule_slots_resource_time
        EXCLUDE USING GIST (
            agent_id WITH =,
            resource_id WITH =,
            tsrange(starts_at, ends_at, '[)') WITH &&
        )
        WHERE (resource_id IS NOT NULL AND is_active IS TRUE)
        """
    )
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


def downgrade() -> None:
    op.execute("ALTER TABLE admin_appointments DROP CONSTRAINT IF EXISTS ex_admin_appointments_resource_time")
    op.execute("ALTER TABLE admin_appointments DROP CONSTRAINT IF EXISTS ex_admin_appointments_staff_time")
    op.execute("ALTER TABLE admin_schedule_slots DROP CONSTRAINT IF EXISTS ex_admin_schedule_slots_resource_time")
    op.execute("ALTER TABLE admin_schedule_slots DROP CONSTRAINT IF EXISTS ex_admin_schedule_slots_staff_time")

    op.drop_index("ix_admin_appointments_client_lookup", table_name="admin_appointments")
    op.drop_index("ix_admin_appointments_agent_status_time", table_name="admin_appointments")
    op.drop_index("ix_admin_appointments_created_at", table_name="admin_appointments")
    op.drop_index("ix_admin_appointments_status", table_name="admin_appointments")
    op.drop_index("ix_admin_appointments_ends_at", table_name="admin_appointments")
    op.drop_index("ix_admin_appointments_starts_at", table_name="admin_appointments")
    op.drop_index("ix_admin_appointments_service_id", table_name="admin_appointments")
    op.drop_index("ix_admin_appointments_resource_id", table_name="admin_appointments")
    op.drop_index("ix_admin_appointments_staff_id", table_name="admin_appointments")
    op.drop_index("ix_admin_appointments_agent_id", table_name="admin_appointments")
    op.drop_table("admin_appointments")

    op.drop_index("ix_admin_schedule_slots_agent_time", table_name="admin_schedule_slots")
    op.drop_index("ix_admin_schedule_slots_created_at", table_name="admin_schedule_slots")
    op.drop_index("ix_admin_schedule_slots_ends_at", table_name="admin_schedule_slots")
    op.drop_index("ix_admin_schedule_slots_starts_at", table_name="admin_schedule_slots")
    op.drop_index("ix_admin_schedule_slots_resource_id", table_name="admin_schedule_slots")
    op.drop_index("ix_admin_schedule_slots_staff_id", table_name="admin_schedule_slots")
    op.drop_index("ix_admin_schedule_slots_agent_id", table_name="admin_schedule_slots")
    op.drop_table("admin_schedule_slots")

    op.drop_index("ix_admin_services_agent_role_active", table_name="admin_services")
    op.drop_index("ix_admin_services_created_at", table_name="admin_services")
    op.drop_index("ix_admin_services_target_role", table_name="admin_services")
    op.drop_index("ix_admin_services_agent_id", table_name="admin_services")
    op.drop_table("admin_services")

    op.drop_index("ix_admin_resources_agent_type_active", table_name="admin_resources")
    op.drop_index("ix_admin_resources_created_at", table_name="admin_resources")
    op.drop_index("ix_admin_resources_resource_type", table_name="admin_resources")
    op.drop_index("ix_admin_resources_agent_id", table_name="admin_resources")
    op.drop_table("admin_resources")

    op.drop_index("ix_admin_staff_agent_role_active", table_name="admin_staff")
    op.drop_index("ix_admin_staff_created_at", table_name="admin_staff")
    op.drop_index("ix_admin_staff_role", table_name="admin_staff")
    op.drop_index("ix_admin_staff_agent_id", table_name="admin_staff")
    op.drop_table("admin_staff")
