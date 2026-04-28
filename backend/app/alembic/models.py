import sys
from os.path import dirname, abspath
sys.path.insert(0, dirname(dirname(abspath(__file__))))



from sqlalchemy import (
    BigInteger,
    Boolean,
    String,
    ForeignKey,
    Text,
    DateTime,
    Integer,
    UniqueConstraint,
    Index,
    CheckConstraint,
)
from sqlalchemy.orm import  Mapped, mapped_column, relationship

try: from .database import Base
except ImportError: from database import Base
    

from datetime import datetime, date, timezone


def _utc_now_naive() -> datetime:
    """UTC 'now' without tzinfo — matches Postgres TIMESTAMP WITHOUT TIME ZONE + asyncpg."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __table_args__ = {'extend_existing': True}
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    email_verification_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    email_verification_attempts_left: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    email_verification_last_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_reset_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_reset_attempts_left: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    password_reset_last_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_reset_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    password_reset_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password: Mapped[str] = mapped_column(String(100), nullable=True)
    
    subscription_type: Mapped[str] = mapped_column(String(50), default="Free")
    subscription_end_date: Mapped[date] = mapped_column(DateTime, nullable=True)
    
    # telegram_id is optional to allow web-only registration without Telegram
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True, nullable=True)
    
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    registered: Mapped[date] = mapped_column(default=datetime.now(timezone.utc))

    agents: Mapped[list['Agent']] = relationship(back_populates='user', cascade="all, delete-orphan")
    external_identities: Mapped[list["UserExternalIdentity"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    auth_sessions: Mapped[list["UserAuthSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    error_reports: Mapped[list["UserErrorReport"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserAuthSession(Base):
    __tablename__ = "user_auth_sessions"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    user: Mapped["User"] = relationship(back_populates="auth_sessions")


class TelegramLinkChallenge(Base):
    __tablename__ = "telegram_link_challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    target_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    attempts_left: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class Agent(Base):
    __table_args__ = {'extend_existing': True}
    id: Mapped[int] = mapped_column(primary_key=True)

    user: Mapped['User'] = relationship(back_populates='agents')
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete="CASCADE"))
    
    bot_username: Mapped[str] = mapped_column(String(100), nullable=True)
    encrypted_token: Mapped[str] = mapped_column(Text, unique=True)
    encrypted_external_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_api_key_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    external_webhook_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=True) 
    primary_provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="telegram_bot",
        server_default="telegram_bot",
    )
    template_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="qa",
        server_default="qa",
    )
    template_config: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, default="Ты — полезный ассистент.")
    

    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    welcome_message: Mapped[str] = mapped_column(Text, nullable=True)

    registered: Mapped[date] = mapped_column(default=datetime.now(timezone.utc))

    documents: Mapped[list["AgentDocument"]] = relationship(
        back_populates="agent", 
        cascade="all, delete-orphan"
    )
    analytics_messages: Mapped[list["AgentAnalyticsMessage"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    frozen_users: Mapped[list["AgentFrozenUser"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    channel_connections: Mapped[list["AgentChannelConnection"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    reindex_jobs: Mapped[list["ReindexJob"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    crm_connections: Mapped[list["AgentCrmConnection"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    sales_contacts: Mapped[list["AgentSalesContact"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    sales_dm_queue: Mapped[list["AgentSalesDmQueue"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    content_jobs: Mapped[list["AgentContentJob"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    admin_staff: Mapped[list["AdminStaff"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    admin_resources: Mapped[list["AdminResource"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    admin_services: Mapped[list["AdminService"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    admin_schedule_slots: Mapped[list["AdminScheduleSlot"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    admin_appointments: Mapped[list["AdminAppointment"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    admin_waitlist_entries: Mapped[list["AdminWaitlistEntry"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    admin_client_profiles: Mapped[list["AdminClientProfile"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    admin_quick_replies: Mapped[list["AdminQuickReplyTemplate"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    admin_reminder_logs: Mapped[list["AdminAppointmentReminderLog"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )


class AgentFrozenUser(Base):
    __tablename__ = "agent_frozen_users"
    __table_args__ = (
        UniqueConstraint("agent_id", "user_external_id", name="uq_agent_frozen_user_external"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False)
    user_external_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="frozen_users")


class AgentAnalyticsMessage(Base):
    __tablename__ = "agent_analytics_messages"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False)
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # user | agent | operator
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="telegram", server_default="telegram")
    user_external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    user_display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    telegram_peer_access_hash: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    tool_args_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    tool_status: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    crm_provider: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)

    agent: Mapped["Agent"] = relationship(back_populates="analytics_messages")


class AgentChannelConnection(Base):
    __tablename__ = "agent_channel_connections"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_agent_channel_provider_external"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    connection_type: Mapped[str] = mapped_column(String(32), nullable=False, default="bot", server_default="bot")
    external_id: Mapped[str] = mapped_column(String(191), nullable=False, index=True)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="channel_connections")


class AgentCrmConnection(Base):
    __tablename__ = "agent_crm_connections"
    __table_args__ = (
        UniqueConstraint("agent_id", "provider", name="uq_agent_crm_agent_provider"),
        UniqueConstraint("provider", "external_id", name="uq_agent_crm_provider_external"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(191), nullable=False, index=True)
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="crm_connections")


class AdminStaff(Base):
    __tablename__ = "admin_staff"
    __table_args__ = (
        CheckConstraint("role IN ('master','doctor')", name="ck_admin_staff_role"),
        Index("ix_admin_staff_agent_role_active", "agent_id", "role", "is_active"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    specializations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="admin_staff")
    schedule_slots: Mapped[list["AdminScheduleSlot"]] = relationship(
        back_populates="staff",
        cascade="all, delete-orphan",
    )
    appointments: Mapped[list["AdminAppointment"]] = relationship(
        back_populates="staff",
        cascade="all, delete-orphan",
    )


class AdminResource(Base):
    __tablename__ = "admin_resources"
    __table_args__ = (
        CheckConstraint("resource_type IN ('chair','room','equipment')", name="ck_admin_resources_type"),
        UniqueConstraint("agent_id", "resource_type", "title", name="uq_admin_resources_agent_type_title"),
        Index("ix_admin_resources_agent_type_active", "agent_id", "resource_type", "is_active"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="admin_resources")
    schedule_slots: Mapped[list["AdminScheduleSlot"]] = relationship(
        back_populates="resource",
        cascade="all, delete-orphan",
    )
    appointments: Mapped[list["AdminAppointment"]] = relationship(
        back_populates="resource",
        cascade="all, delete-orphan",
    )


class AdminService(Base):
    __tablename__ = "admin_services"
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="ck_admin_services_duration_gt_zero"),
        CheckConstraint("price_minor >= 0", name="ck_admin_services_price_non_negative"),
        UniqueConstraint("agent_id", "title", name="uq_admin_services_agent_title"),
        Index("ix_admin_services_agent_role_active", "agent_id", "target_role", "is_active"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    target_role: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("admin_staff.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    resource_type_filters_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="admin_services")
    staff: Mapped["AdminStaff | None"] = relationship(foreign_keys=[staff_id])
    appointments: Mapped[list["AdminAppointment"]] = relationship(
        back_populates="service",
        cascade="all, delete-orphan",
    )


class AdminScheduleSlot(Base):
    __tablename__ = "admin_schedule_slots"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_admin_schedule_slots_time_order"),
        CheckConstraint("(staff_id IS NOT NULL) OR (resource_id IS NOT NULL)", name="ck_admin_schedule_slots_target"),
        UniqueConstraint("agent_id", "staff_id", "starts_at", "ends_at", name="uq_admin_schedule_slots_staff_exact"),
        UniqueConstraint("agent_id", "resource_id", "starts_at", "ends_at", name="uq_admin_schedule_slots_resource_exact"),
        Index("ix_admin_schedule_slots_agent_time", "agent_id", "starts_at", "ends_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("admin_staff.id", ondelete="CASCADE"), nullable=True, index=True)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("admin_resources.id", ondelete="CASCADE"), nullable=True, index=True)
    slot_kind: Mapped[str] = mapped_column(String(24), nullable=False, default="work", server_default="work")
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="admin_schedule_slots")
    staff: Mapped["AdminStaff"] = relationship(back_populates="schedule_slots")
    resource: Mapped["AdminResource"] = relationship(back_populates="schedule_slots")


class AdminAppointment(Base):
    __tablename__ = "admin_appointments"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_admin_appointments_time_order"),
        CheckConstraint(
            "status IN ('pending_confirmation','booked','confirmed','in_progress','cancelled','completed','no_show')",
            name="ck_admin_appointments_status",
        ),
        Index("ix_admin_appointments_agent_status_time", "agent_id", "status", "starts_at"),
        Index("ix_admin_appointments_client_lookup", "agent_id", "client_external_id"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("admin_staff.id", ondelete="SET NULL"), nullable=True, index=True)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("admin_resources.id", ondelete="SET NULL"), nullable=True, index=True)
    service_id: Mapped[int | None] = mapped_column(ForeignKey("admin_services.id", ondelete="SET NULL"), nullable=True, index=True)
    client_external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    client_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="booked", server_default="booked", index=True)
    source_channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="admin_appointments")
    staff: Mapped["AdminStaff"] = relationship(back_populates="appointments")
    resource: Mapped["AdminResource"] = relationship(back_populates="appointments")
    service: Mapped["AdminService"] = relationship(back_populates="appointments")


class AdminWaitlistEntry(Base):
    __tablename__ = "admin_waitlist_entries"
    __table_args__ = (
        CheckConstraint("status IN ('waiting','matched','cancelled')", name="ck_admin_waitlist_entries_status"),
        Index("ix_admin_waitlist_entries_agent_status_created", "agent_id", "status", "created_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    client_external_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    client_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    service_id: Mapped[int | None] = mapped_column(ForeignKey("admin_services.id", ondelete="SET NULL"), nullable=True, index=True)
    desired_staff_id: Mapped[int | None] = mapped_column(ForeignKey("admin_staff.id", ondelete="SET NULL"), nullable=True, index=True)
    desired_resource_id: Mapped[int | None] = mapped_column(ForeignKey("admin_resources.id", ondelete="SET NULL"), nullable=True, index=True)
    earliest_starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    latest_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="waiting", server_default="waiting", index=True)
    matched_appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_appointments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="admin_waitlist_entries")
    service: Mapped["AdminService"] = relationship()
    desired_staff: Mapped["AdminStaff"] = relationship()
    desired_resource: Mapped["AdminResource"] = relationship()
    matched_appointment: Mapped["AdminAppointment"] = relationship()


class AdminClientProfile(Base):
    __tablename__ = "admin_client_profiles"
    __table_args__ = (
        UniqueConstraint("agent_id", "client_external_id", name="uq_admin_client_profiles_agent_client"),
        Index("ix_admin_client_profiles_agent_last_visit", "agent_id", "last_visit_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    client_external_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    client_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferences_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    history_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_visit_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="admin_client_profiles")


class AdminQuickReplyTemplate(Base):
    __tablename__ = "admin_quick_reply_templates"
    __table_args__ = (
        UniqueConstraint("agent_id", "title", name="uq_admin_quick_reply_agent_title"),
        Index("ix_admin_quick_reply_agent_active", "agent_id", "is_active"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="admin_quick_replies")


class AdminAppointmentReminderLog(Base):
    __tablename__ = "admin_appointment_reminder_logs"
    __table_args__ = (
        UniqueConstraint(
            "appointment_id",
            "reminder_type",
            name="uq_admin_appointment_reminder_logs_appointment_type",
        ),
        Index("ix_admin_appointment_reminder_logs_agent_type_sent", "agent_id", "reminder_type", "sent_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("admin_appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reminder_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # t24h | t2h
    channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued", server_default="queued")
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent: Mapped["Agent"] = relationship(back_populates="admin_reminder_logs")
    appointment: Mapped["AdminAppointment"] = relationship()


class AgentSalesContact(Base):
    __tablename__ = "agent_sales_contacts"
    __table_args__ = (
        UniqueConstraint("agent_id", "user_external_id", "source_chat_id", name="uq_agent_sales_contact_key"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False)
    user_external_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_chat_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="DISCOVERED", server_default="DISCOVERED", index=True)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="sales_contacts")


class AgentSalesDmQueue(Base):
    """Queue for outgoing DM (Direct Messages) in sales_manager template."""
    __tablename__ = "agent_sales_dm_queue"
    __table_args__ = (
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False)
    target_user_external_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_chat_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), 
        nullable=False, 
        default="pending", 
        server_default="pending",
        index=True
    )  # pending, sending, sent, failed, skipped
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)

    agent: Mapped["Agent"] = relationship(
        back_populates="sales_dm_queue",
        foreign_keys=[agent_id],
    )


class AgentContentJob(Base):
    """Pipeline job state for content_factory template."""
    __tablename__ = "agent_content_jobs"
    __table_args__ = (
        Index("ix_agent_content_jobs_status_scheduled_for", "status", "scheduled_for"),
        Index("ix_agent_content_jobs_kling_task_id", "kling_task_id"),
        Index("ix_agent_content_jobs_youtube_video_id", "youtube_video_id"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="planned",
        server_default="planned",
    )  # planned, script_ready, rendering, rendered, publishing, published, failed
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    script_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    script_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    kling_task_id: Mapped[str | None] = mapped_column(String(191), nullable=True)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    youtube_video_id: Mapped[str | None] = mapped_column(String(191), nullable=True)
    youtube_video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="content_jobs")


class UserExternalIdentity(Base):
    __tablename__ = "user_external_identities"
    __table_args__ = (
        UniqueConstraint("provider", "external_user_id", name="uq_user_identity_provider_external"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_user_id: Mapped[str] = mapped_column(String(191), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)

    user: Mapped["User"] = relationship(back_populates="external_identities")


class AgentDocument(Base):
    __table_args__ = {'extend_existing': True}
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    
    file_name: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    embedding_profile_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="bge_m3_v1",
        server_default="bge_m3_v1",
        index=True,
    )
    embedding_schema_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        index=True,
    )
    embedding_model_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="BAAI/bge-m3",
        server_default="BAAI/bge-m3",
    )
    chunk_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1000,
        server_default="1000",
    )
    chunk_overlap: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        server_default="100",
    )
    status: Mapped[str] = mapped_column(String(15), default="processing") # processing, ready, error
    created_at: Mapped[date] = mapped_column(default=datetime.now(timezone.utc))
    agent: Mapped["Agent"] = relationship(back_populates="documents")


class ReindexJob(Base):
    __tablename__ = "reindex_jobs"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False)
    requested_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued", server_default="queued", index=True)
    target_embedding_profile_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_embedding_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    target_embedding_model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    document_cursor: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    processed_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    success_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    agent: Mapped["Agent"] = relationship(back_populates="reindex_jobs")


class PaymentTransaction(Base):
    
    __tablename__ = "payment_transactions"
    __table_args__ = {'extend_existing': True}
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    plan_name: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    total_amount: Mapped[int] = mapped_column(nullable=False)

    telegram_payment_charge_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    provider_payment_charge_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_payload: Mapped[str | None] = mapped_column(Text, nullable=True)

    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))


class WebsitePaymentTransaction(Base):
    __tablename__ = "website_payment_transactions"
    __table_args__ = {'extend_existing': True}
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    plan_name: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="RUB")
    total_amount: Mapped[int] = mapped_column(nullable=False)
    original_total_amount: Mapped[int] = mapped_column(nullable=False)
    discount_percent: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    duration_months: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
    promo_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    yookassa_payment_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    is_processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now_naive)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TurnkeyAgentRequest(Base):
    __tablename__ = "turnkey_agent_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    requested_agent: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now_naive, index=True)


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)


class UserErrorReport(Base):
    __tablename__ = "user_error_reports"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)

    user: Mapped["User"] = relationship(back_populates="error_reports")

