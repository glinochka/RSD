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
    Date,
    Float,
    Integer,
    UniqueConstraint,
    Index,
    CheckConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import  Mapped, mapped_column, relationship

try:
    from .database import Base
except ImportError:
    from database import Base
    

from datetime import datetime, date, timezone
from enum import Enum

from prompts.system_prompts import DEFAULT_AGENT_SYSTEM_PROMPT


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
    onboarding_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    password: Mapped[str] = mapped_column(String(100), nullable=True)
    
    subscription_type: Mapped[str] = mapped_column(String(50), default="Free")
    subscription_end_date: Mapped[date] = mapped_column(DateTime, nullable=True)
    
    # telegram_id is optional to allow web-only registration without Telegram
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True, nullable=True)
    
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    free_agent_activation: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    registered: Mapped[date] = mapped_column(default=datetime.now(timezone.utc))

    referral_code: Mapped[str | None] = mapped_column(String(16), unique=True, index=True, nullable=True)
    referred_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    agents: Mapped[list['Agent']] = relationship(back_populates='user', cascade="all, delete-orphan")
    projects: Mapped[list['Project']] = relationship(
        back_populates='user',
        cascade="all, delete-orphan",
    )
    payment_methods: Mapped[list['UserPaymentMethod']] = relationship(
        back_populates='user',
        cascade='all, delete-orphan',
    )
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

class UserPaymentMethod(Base):
    __tablename__ = "user_payment_methods"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "yookassa_payment_method_id",
            name="uq_user_payment_methods_user_method",
        ),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    yookassa_payment_method_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    card_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    user: Mapped["User"] = relationship(back_populates="payment_methods")


class Agent(Base):
    __table_args__ = {'extend_existing': True}
    id: Mapped[int] = mapped_column(primary_key=True)

    user: Mapped['User'] = relationship(back_populates='agents')
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete="CASCADE"))

    # Project relationship (nullable для обратной совместимости)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project: Mapped["Project | None"] = relationship(back_populates="agents")
    
    bot_username: Mapped[str] = mapped_column(String(100), nullable=True)
    encrypted_token: Mapped[str] = mapped_column(Text, unique=True)
    encrypted_external_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_booking_payment_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    system_prompt: Mapped[str] = mapped_column(Text, default=DEFAULT_AGENT_SYSTEM_PROMPT)
    

    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    activation_paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    maintenance_paid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    autopay_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    yookassa_payment_method_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    autopay_duration_months: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    autopay_last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    autopay_last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    welcome_message: Mapped[str] = mapped_column(Text, nullable=True)
    process_start_with_llm: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

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
    http_integrations: Mapped[list["AgentHttpIntegration"]] = relationship(
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
    sales_imported_contacts: Mapped[list["AgentSalesImportedContact"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    ai_mop_assignment: Mapped["AiMopAgentAssignment | None"] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        uselist=False,
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
    admin_applications: Mapped[list["AdminApplication"]] = relationship(
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
    telephony_calls: Mapped[list["AgentTelephonyCall"]] = relationship(
        back_populates="connection",
        cascade="all, delete-orphan",
    )


class AgentTelephonyCall(Base):
    __tablename__ = "agent_telephony_calls"
    __table_args__ = (
        UniqueConstraint("connection_id", "external_call_id", name="uq_agent_telephony_calls_connection_external"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("agent_channel_connections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False)
    external_call_id: Mapped[str] = mapped_column(String(191), nullable=False)
    caller_e164: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ringing", server_default="ringing", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recording_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    connection: Mapped["AgentChannelConnection"] = relationship(back_populates="telephony_calls")
    agent: Mapped["Agent"] = relationship()
    turns: Mapped[list["AgentTelephonyTurn"]] = relationship(
        back_populates="call",
        cascade="all, delete-orphan",
    )


class AgentTelephonyTurn(Base):
    __tablename__ = "agent_telephony_turns"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("agent_telephony_calls.id", ondelete="CASCADE"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)

    call: Mapped["AgentTelephonyCall"] = relationship(back_populates="turns")


class TelephonySipRoute(Base):
    """SIP trunk header mapping (variant 7C): From/To → connection_id."""

    __tablename__ = "telephony_sip_routes"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("agent_channel_connections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    match_from: Mapped[str | None] = mapped_column(String(128), nullable=True)
    match_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    connection: Mapped["AgentChannelConnection"] = relationship()


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


class AgentHttpIntegration(Base):
    __tablename__ = "agent_http_integrations"
    __table_args__ = (
        UniqueConstraint("agent_id", "name", name="uq_agent_http_integrations_agent_name"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    encrypted_config: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="http_integrations")


class AdminStaff(Base):
    __tablename__ = "admin_staff"
    __table_args__ = (
        Index("ix_admin_staff_agent_role_active", "agent_id", "role", "is_active"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
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
        UniqueConstraint("agent_id", "resource_type", "title", name="uq_admin_resources_agent_type_title"),
        Index("ix_admin_resources_agent_type_active", "agent_id", "resource_type", "is_active"),
        Index("ix_admin_resources_linked_staff_id", "linked_staff_id"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    linked_staff_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_staff.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="admin_resources")
    linked_staff: Mapped["AdminStaff | None"] = relationship(foreign_keys=[linked_staff_id])
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
        Index(
            "uq_admin_services_agent_title_staff",
            "agent_id",
            "title",
            "staff_id",
            unique=True,
            sqlite_where=text("staff_id IS NOT NULL"),
            postgresql_where=text("staff_id IS NOT NULL"),
        ),
        Index(
            "uq_admin_services_agent_title_general",
            "agent_id",
            "title",
            unique=True,
            sqlite_where=text("staff_id IS NULL"),
            postgresql_where=text("staff_id IS NULL"),
        ),
        Index("ix_admin_services_agent_role_active", "agent_id", "target_role", "is_active"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    target_role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
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
    booking_payment: Mapped["AdminBookingPayment | None"] = relationship(
        back_populates="appointment",
        uselist=False,
    )


class AdminApplication(Base):
    __tablename__ = "admin_applications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new','in_progress','completed','rejected','cancelled')",
            name="ck_admin_applications_status",
        ),
        Index("ix_admin_applications_agent_status_created", "agent_id", "status", "created_at"),
        Index("ix_admin_applications_client_lookup", "agent_id", "client_external_id"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    client_external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    client_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="new", server_default="new", index=True)
    fields_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", server_default="{}")
    source_channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="admin_applications")


class AdminBookingPayment(Base):
    __tablename__ = "admin_booking_payments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','paid','expired','refunded')",
            name="ck_admin_booking_payments_status",
        ),
        Index("ix_admin_booking_payments_agent_status", "agent_id", "status"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_appointments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    client_external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    yookassa_payment_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="RUB", server_default="RUB")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True, index=True)
    booking_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship()
    appointment: Mapped["AdminAppointment | None"] = relationship(back_populates="booking_payment")
    refund_request: Mapped["AdminBookingRefundRequest | None"] = relationship(
        back_populates="payment",
        uselist=False,
    )


class AdminBookingRefundRequest(Base):
    __tablename__ = "admin_booking_refund_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','refunded','failed')",
            name="ck_admin_booking_refund_requests_status",
        ),
        Index("ix_admin_booking_refund_requests_agent_status", "agent_id", "status"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("admin_booking_payments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    appointment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="RUB", server_default="RUB")
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_full_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    client_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    appointment_starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    service_title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    refund_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    yookassa_refund_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship()
    payment: Mapped["AdminBookingPayment"] = relationship(back_populates="refund_request")
    reviewed_by: Mapped["User | None"] = relationship()


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


class AgentSalesImportedContact(Base):
    """Контакты из Excel для холодного outreach sales_manager (per-agent)."""

    __tablename__ = "agent_sales_imported_contacts"
    __table_args__ = (
        UniqueConstraint("agent_id", "dedup_key", name="uq_agent_sales_imported_contact_dedup"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False)
    import_batch_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    org_name: Mapped[str] = mapped_column(String(512), nullable=False)
    lpr_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    lpr_phone: Mapped[str | None] = mapped_column(String(256), nullable=True)
    org_phone: Mapped[str | None] = mapped_column(String(256), nullable=True)
    org_mobile: Mapped[str | None] = mapped_column(String(256), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(512), nullable=True)
    telegram: Mapped[str | None] = mapped_column(String(512), nullable=True)
    extra_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    target_external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    target_resolve_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    outreach_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedup_key: Mapped[str] = mapped_column(String(128), nullable=False)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reply_received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    follow_up_day_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    follow_up_week_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    follow_up_month_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="sales_imported_contacts")


class AiMopLead(Base):
    """Общая база лидов для кастомного рантайма ИИ МОП (продажа платформы)."""

    __tablename__ = "ai_mop_leads"
    __table_args__ = (
        UniqueConstraint("dedup_key", name="uq_ai_mop_lead_dedup"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    org_name: Mapped[str] = mapped_column(String(512), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    lpr_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(256), nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    category: Mapped[str | None] = mapped_column(String(256), nullable=True)
    yandex_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    telegram: Mapped[str | None] = mapped_column(String(512), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(512), nullable=True)
    extra_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedup_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )  # pending, processing, provisioned, outreach_queued, outreach_sent, failed
    assigned_agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provisioned_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    provisioned_agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    provisioned_website_id: Mapped[int | None] = mapped_column(
        ForeignKey("websites.id", ondelete="SET NULL"),
        nullable=True,
    )
    website_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    temp_password: Mapped[str | None] = mapped_column(String(32), nullable=True)
    outreach_channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    outreach_target: Mapped[str | None] = mapped_column(String(256), nullable=True)
    failure_stage: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    dm_queue_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outreach_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    reply_received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    follow_up_day_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    follow_up_week_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    follow_up_month_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    import_batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    llm_prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    llm_completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    llm_cost_cny_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)


class AiMopAgentAssignment(Base):
    """Привязка sales_manager-агента к кастомному рантайму ИИ МОП."""

    __tablename__ = "ai_mop_agent_assignments"
    __table_args__ = (
        UniqueConstraint("agent_id", name="uq_ai_mop_agent_assignment"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_busy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    leads_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    leads_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    leads_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    agent: Mapped["Agent"] = relationship(back_populates="ai_mop_assignment")


class AiMopPipelineState(Base):
    """Глобальная пауза пайплайна ИИ МОП (одна строка id=1)."""

    __tablename__ = "ai_mop_pipeline_state"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(primary_key=True)
    is_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)


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


class ProjectDocument(Base):
    """Documents at project level - shared across all project agents."""

    __tablename__ = "project_documents"
    __table_args__ = (
        Index("ix_project_documents_project_id", "project_id"),
        Index("ix_project_documents_content_hash", "content_hash"),
        Index("ix_project_documents_status", "status"),
        Index("ix_project_documents_project_status", "project_id", "status"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_profile_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="bge_m3_v1",
        server_default="bge_m3_v1",
    )
    embedding_schema_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
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
    status: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
        default="processing",
        server_default="processing",
    )  # processing, ready, error
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utc_now_naive,
        index=True,
    )

    project: Mapped["Project"] = relationship(back_populates="documents")


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
    plan_name: Mapped[str] = mapped_column(String(64), nullable=False)
    payment_kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="subscription",
        server_default="subscription",
    )
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="RUB")
    total_amount: Mapped[int] = mapped_column(nullable=False)
    original_total_amount: Mapped[int] = mapped_column(nullable=False)
    discount_percent: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    duration_months: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
    promo_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    partner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    partner_promo_discount_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    yookassa_payment_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    is_processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    autopay_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_autopay_charge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
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


class PartnerPromoCode(Base):
    __tablename__ = "partner_promo_codes"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    partner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)


class PartnerPayoutRequest(Base):
    __tablename__ = "partner_payout_requests"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    partner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_details: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ReferralCommission(Base):
    __tablename__ = "referral_commissions"
    __table_args__ = (
        UniqueConstraint(
            "website_payment_transaction_id",
            name="uq_referral_commissions_website_payment_tx",
        ),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    partner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    buyer_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    website_payment_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("website_payment_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    gross_amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    commission_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    commission_amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    promo_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)


class UserErrorReport(Base):
    __tablename__ = "user_error_reports"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)

    user: Mapped["User"] = relationship(back_populates="error_reports")


class ApplicationErrorLog(Base):
    """Automatic server-side error log for admin bug tracking."""
    __tablename__ = "application_error_logs"
    __table_args__ = (
        Index("ix_application_error_logs_source_created", "source", "created_at"),
        Index("ix_application_error_logs_resolved_created", "is_resolved", "created_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="error", server_default="error")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="api", server_default="api")
    scenario: Mapped[str] = mapped_column(String(512), nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)

    user: Mapped["User | None"] = relationship()


# ---------------------------------------------------------------------------
# Project — контейнер цифровизации бизнеса
# ---------------------------------------------------------------------------

class Project(Base):
    """Проект — контейнер цифровизации малого/среднего бизнеса или отдела."""

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("user_id", "slug", name="uq_project_user_slug"),
        Index("ix_projects_user_id_status", "user_id", "status"),
        Index("ix_projects_is_default", "user_id", "is_default"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Основные поля
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSON поля для AI-плана
    brief_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    ai_plan_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    # Статус
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )  # draft | active | archived

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # Dashboard preferences
    checklist_hidden: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utc_now_naive, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utc_now_naive
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="projects")
    agents: Mapped[list["Agent"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    websites: Mapped[list["Website"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["ProjectDocument"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    integrations: Mapped[list["ProjectIntegration"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    external_events: Mapped[list["ProjectExternalEvent"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# Project Integrations — webhooks, external CRMs and business data
# ---------------------------------------------------------------------------

class ProjectIntegration(Base):
    """External integration configured for a project (webhook, CRM, API)."""

    __tablename__ = "project_integrations"
    __table_args__ = (
        Index("ix_project_integrations_type", "type"),
        Index("ix_project_integrations_is_active", "is_active"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    # Public config (URL, events, etc.) — no secrets.
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    # Encrypted JSON with credentials / tokens.
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    # Secret random token used in webhook URLs.
    webhook_token: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utc_now_naive, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utc_now_naive
    )

    project: Mapped["Project"] = relationship(back_populates="integrations")
    external_events: Mapped[list["ProjectExternalEvent"]] = relationship(
        back_populates="integration",
        cascade="all, delete-orphan",
    )


class ProjectExternalEvent(Base):
    """Raw event received from an external integration (webhook, CRM, etc.)."""

    __tablename__ = "project_external_events"
    __table_args__ = (
        Index("ix_project_external_events_event_type", "event_type"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    integration_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_integrations.id", ondelete="SET NULL"),
        nullable=True,
    )

    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utc_now_naive
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utc_now_naive
    )

    project: Mapped["Project"] = relationship(back_populates="external_events")
    integration: Mapped["ProjectIntegration | None"] = relationship(
        back_populates="external_events"
    )


# ---------------------------------------------------------------------------
# Article Publisher — private automation template for vc.ru / Yandex Zen
# ---------------------------------------------------------------------------

class ArticlePublisherSettings(Base):
    """Global settings for the article publisher automation."""
    __tablename__ = "article_publisher_settings"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    posting_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    posting_frequency_hours: Mapped[int] = mapped_column(Integer, default=24, server_default="24", nullable=False)
    # Platform flags
    vcru_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    vcru_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vcru_password_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    vcru_subsite_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    zen_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    zen_login: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zen_password_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Legacy field kept for backward compatibility; new flow uses browser emulation login/password.
    zen_oauth_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    zen_channel_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Content settings
    auto_topics_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    topic_categories_json: Mapped[str] = mapped_column(
        Text, default='["ИИ","IT","Автоматизация","Искусственный интеллект","Нейросети"]',
        server_default='["ИИ","IT","Автоматизация","Искусственный интеллект","Нейросети"]', nullable=False,
    )
    promo_ratio: Mapped[int] = mapped_column(Integer, default=60, server_default="60", nullable=False)
    company_name: Mapped[str] = mapped_column(String(256), default="RSD AI", server_default="RSD AI", nullable=False)
    company_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    company_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_min_words: Mapped[int] = mapped_column(Integer, default=600, server_default="600", nullable=False)
    article_max_words: Mapped[int] = mapped_column(Integer, default=1500, server_default="1500", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)


class ArticlePublisherTopic(Base):
    """Topic pool for article generation."""
    __tablename__ = "article_publisher_topics"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", server_default="manual")
    used: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)


class ArticlePublisherImage(Base):
    """Uploaded images pool for article illustrations."""
    __tablename__ = "article_publisher_images"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    original_name: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_filename: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)


class ArticlePublisherJob(Base):
    """Publication job tracking for the article publisher pipeline."""
    __tablename__ = "article_publisher_jobs"
    __table_args__ = (
        Index("ix_article_publisher_jobs_status_scheduled", "status", "scheduled_for"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending",
    )  # pending, generating, publishing, published, failed
    platform: Mapped[str] = mapped_column(String(32), nullable=False)  # vcru, yandex_zen
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    is_promo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    article_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)


class SalesTeamMember(Base):
    """Внутренние учётные записи отдела продаж (портал управления, не путать с users/agents)."""

    __tablename__ = "sales_team_members"
    __table_args__ = (
        CheckConstraint("role IN ('trainee','mop','rop')", name="ck_sales_team_members_role"),
        Index("ix_sales_team_members_supervisor_id", "supervisor_id"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    supervisor_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_team_members.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    plan_calls_monthly: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    plan_demos_monthly: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    plan_closes_monthly: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    daily_contacts_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_daily_allocation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    daily_pool_alloc_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    daily_allocation_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    supervisor: Mapped["SalesTeamMember | None"] = relationship(
        "SalesTeamMember",
        remote_side=[id],
        back_populates="subordinates",
    )
    subordinates: Mapped[list["SalesTeamMember"]] = relationship(
        "SalesTeamMember",
        back_populates="supervisor",
    )
    outreach_contacts: Mapped[list["SalesOutboundContact"]] = relationship(
        back_populates="assignee",
    )


class SalesOutboundContact(Base):
    """Локальная база контактов для прозвонов (импорт Excel 2GIS и др.)."""

    __tablename__ = "sales_outbound_contacts"
    __table_args__ = (
        CheckConstraint(
            "workflow_status IN ('new','in_progress','demo','closed','rejected','hesitating')",
            name="ck_sales_outbound_contacts_workflow",
        ),
        Index("ix_sales_outbound_contacts_assignee", "assignee_id"),
        Index("ix_sales_outbound_contacts_workflow_status", "workflow_status"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_team_members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    workflow_status: Mapped[str] = mapped_column(String(32), nullable=False, default="new", server_default="new")
    dedup_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    org_name: Mapped[str] = mapped_column(String(512), nullable=False, default="", server_default="")
    lpr_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    lpr_phone: Mapped[str | None] = mapped_column(String(256), nullable=True)
    org_phone: Mapped[str | None] = mapped_column(String(256), nullable=True)
    org_mobile: Mapped[str | None] = mapped_column(String(256), nullable=True)
    import_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(512), nullable=True)
    telegram: Mapped[str | None] = mapped_column(String(512), nullable=True)
    messenger_max: Mapped[str | None] = mapped_column(String(512), nullable=True)
    extra_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    called_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    demo_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    assignee: Mapped["SalesTeamMember | None"] = relationship(back_populates="outreach_contacts")


# ---------------------------------------------------------------------------
# Website Builder — сайты для владельцев ИИ-агентов
# ---------------------------------------------------------------------------

class WebsiteStatus:
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class WebsiteBlockType:
    HERO = "hero"
    SERVICES = "services"
    ABOUT = "about"
    CONTACTS = "contacts"
    CTA = "cta"
    FOOTER = "footer"
    CUSTOM = "custom"
    FULLPAGE = "fullpage"

class WebsiteDomainVerificationStatus:
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"

class WebsiteGenerationStatus:
    IDLE = "idle"
    QUEUED = "queued"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"

class WebsiteTemplate(Base):
    """Предустановленные шаблоны для сайтов."""
    __tablename__ = "website_templates"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    default_blocks: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    default_styles: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)


class Website(Base):
    """Основная модель сайта для ИИ-агента."""
    __tablename__ = "websites"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_website_slug"),
        Index("ix_website_owner_status", "owner_id", "status"),
        Index("ix_website_agent", "agent_id"),
        Index("ix_website_project", "project_id"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True)

    # Project relationship (nullable для обратной совместимости)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    template_id: Mapped[int | None] = mapped_column(ForeignKey("website_templates.id", ondelete="SET NULL"), nullable=True)

    # URL и идентификация
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)

    # SEO мета-данные
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    og_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    og_description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    og_image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Статус и публикация
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=WebsiteStatus.DRAFT,
        server_default=WebsiteStatus.DRAFT,
        index=True,
    )  # draft | published | archived
    generation_status: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        default=WebsiteGenerationStatus.IDLE,
        server_default=WebsiteGenerationStatus.IDLE,
    )  # idle | queued | generating | completed | failed

    # Стили сайта (переопределение шаблона)
    custom_styles: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    owner: Mapped["User"] = relationship()
    agent: Mapped["Agent | None"] = relationship()
    project: Mapped["Project | None"] = relationship(back_populates="websites")
    template: Mapped["WebsiteTemplate | None"] = relationship()
    blocks: Mapped[list["WebsiteBlock"]] = relationship(
        back_populates="website",
        cascade="all, delete-orphan",
        order_by="WebsiteBlock.order",
    )
    domains: Mapped[list["WebsiteDomain"]] = relationship(
        back_populates="website",
        cascade="all, delete-orphan",
    )


class WebsiteBlock(Base):
    """Блоки контента сайта (Hero, Services, About, etc.)."""
    __tablename__ = "website_blocks"
    __table_args__ = (
        Index("ix_website_block_website_order", "website_id", "order"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    website_id: Mapped[int] = mapped_column(ForeignKey("websites.id", ondelete="CASCADE"), nullable=False, index=True)

    # Порядок отображения
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Тип блока: hero | services | about | contacts | cta | footer | custom
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # Контент и стили (JSONB для гибкости)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    styles: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    # Видимость блока
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    # Relationships
    website: Mapped["Website"] = relationship(back_populates="blocks")


class WebsiteDomain(Base):
    """Кастомные домены для сайтов."""
    __tablename__ = "website_domains"
    __table_args__ = (
        UniqueConstraint("domain", name="uq_website_domain"),
        Index("ix_website_domain_website", "website_id"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    website_id: Mapped[int] = mapped_column(ForeignKey("websites.id", ondelete="CASCADE"), nullable=False, index=True)

    # Домен (полное имя, например: example.com)
    domain: Mapped[str] = mapped_column(String(253), nullable=False, unique=True, index=True)

    # SSL и верификация
    ssl_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    verification_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=WebsiteDomainVerificationStatus.PENDING,
        server_default=WebsiteDomainVerificationStatus.PENDING,
    )  # pending | verified | failed
    verification_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # DNS проверка
    last_dns_check_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dns_check_error: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    # Relationships
    website: Mapped["Website"] = relationship(back_populates="domains")


# ============================================================
# /custom — Custom Automation subsystem models
# ============================================================

class AccountClass(str, Enum):
    ONE_DAY = "one_day"
    MID = "mid"
    TRUSTED = "trusted"
    SHILLING = "shilling"


class ChatMode(str, Enum):
    MONITORING = "monitoring"
    NEUROCOMMENTING = "neurocommenting"
    DISCUSSION = "discussion"
    SHILLING = "shilling"
    INACTIVE = "inactive"


class ChatSource(str, Enum):
    MANUAL = "manual"
    BULK_IMPORT = "bulk_import"
    AI_DISCOVERY = "ai_discovery"


class ChatJoinStatus(str, Enum):
    PENDING = "pending"
    JOINING = "joining"
    JOINED = "joined"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    BANNED = "banned"


class PromptType(str, Enum):
    CHAT_MONITORING_TRIGGER = "chat_monitoring_trigger"
    CHAT_MONITORING_RESPONSE = "chat_monitoring_response"
    NEUROCOMMENTING = "neurocommenting"
    DISCUSSION_REPLY = "discussion_reply"
    CHAT_RELEVANCE = "chat_relevance"
    PROFILE_BIO = "profile_bio"
    LEAD_QUALIFICATION = "lead_qualification"
    DMP_OUTREACH = "dmp_outreach"
    SHILLING = "shilling"


class LeadStatus(str, Enum):
    NEW = "new"
    WARMING = "warming"
    QUALIFIED = "qualified"
    TRANSFERRED = "transferred"
    PROCESSING = "processing"
    CONVERTED = "converted"
    LOST = "lost"
    SPAM = "spam"


class CustomAdmin(Base):
    __tablename__ = "custom_admins"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    created_automations: Mapped[list["CustomAutomation"]] = relationship(
        back_populates="created_by_admin",
        cascade="all, delete-orphan",
    )


class CustomAutomation(Base):
    __tablename__ = "custom_automations"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="draft", server_default="draft", nullable=False, index=True
    )

    is_chat_monitoring_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    lead_keywords: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    is_neurocommenting_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    is_digital_footprint_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    is_dmp_one_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    is_amocrm_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    is_shilling_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    solution_kind: Mapped[str] = mapped_column(
        String(32), default="generic", server_default="generic", nullable=False, index=True
    )
    solution_slug: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)

    rotation_strategy: Mapped[str] = mapped_column(
        String(32), default="round_robin", server_default="round_robin", nullable=False
    )
    max_daily_messages_per_account: Mapped[int] = mapped_column(
        Integer, default=50, server_default="50", nullable=False
    )

    lead_warmup_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    lead_manager_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    partner_utm_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    partner_promo_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    conversion_check_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    dmp_webhook_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_lead_qualification_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    telegram_bot_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_bot_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    telegram_bot_webhook_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    google_sheets_spreadsheet_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    google_sheets_worksheet: Mapped[str | None] = mapped_column(String(128), nullable=True)
    google_sheets_credentials_enc: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("custom_admins.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    created_by_admin: Mapped["CustomAdmin | None"] = relationship(
        back_populates="created_automations",
        foreign_keys=[created_by_admin_id],
    )
    credentials: Mapped[list["CustomAutomationCredential"]] = relationship(
        back_populates="automation",
        cascade="all, delete-orphan",
    )
    account_pools: Mapped[list["AccountPool"]] = relationship(
        back_populates="automation",
        cascade="all, delete-orphan",
    )
    chat_targets: Mapped[list["ChatTarget"]] = relationship(
        back_populates="automation",
        cascade="all, delete-orphan",
    )
    chat_import_jobs: Mapped[list["ChatImportJob"]] = relationship(
        back_populates="automation",
        cascade="all, delete-orphan",
    )
    chat_discovery_tasks: Mapped[list["ChatDiscoveryTask"]] = relationship(
        back_populates="automation",
        cascade="all, delete-orphan",
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="automation",
        cascade="all, delete-orphan",
    )
    custom_leads: Mapped[list["CustomLead"]] = relationship(
        back_populates="automation",
        cascade="all, delete-orphan",
    )
    custom_prompts: Mapped[list["CustomPrompt"]] = relationship(
        back_populates="automation",
        cascade="all, delete-orphan",
    )
    action_logs: Mapped[list["AutomationActionLog"]] = relationship(
        back_populates="automation",
        cascade="all, delete-orphan",
    )
    dmp_one_imports: Mapped[list["DmpOneImport"]] = relationship(
        back_populates="automation",
        cascade="all, delete-orphan",
    )
    amocrm_connection: Mapped["AmocrmConnection | None"] = relationship(
        back_populates="automation",
        cascade="all, delete-orphan",
        uselist=False,
    )
    bot_subscribers: Mapped[list["CustomBotSubscriber"]] = relationship(
        back_populates="automation",
        cascade="all, delete-orphan",
    )


class CustomAutomationCredential(Base):
    __tablename__ = "custom_automation_credentials"
    __table_args__ = (
        UniqueConstraint("custom_automation_id", "username", name="uq_custom_automation_credential"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    custom_automation_id: Mapped[int] = mapped_column(
        ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False, index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    automation: Mapped["CustomAutomation"] = relationship(back_populates="credentials")


class CustomBotSubscriber(Base):
    __tablename__ = "custom_bot_subscribers"
    __table_args__ = (
        UniqueConstraint("custom_automation_id", "telegram_chat_id", name="uq_custom_bot_subscriber_chat"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    custom_automation_id: Mapped[int] = mapped_column(
        ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="idle", server_default="idle", nullable=False, index=True
    )
    pending_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pending_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    authenticated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    automation: Mapped["CustomAutomation"] = relationship(back_populates="bot_subscribers")


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(
        String(32), default="telegram", server_default="telegram", nullable=False, index=True
    )
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    username: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    encrypted_session: Mapped[str] = mapped_column(Text, nullable=False)
    session_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    avatar_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_avatar_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    account_class: Mapped[str] = mapped_column(
        String(32), default=AccountClass.ONE_DAY.value, server_default="one_day", nullable=False, index=True
    )
    auto_classified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    risk_score: Mapped[float | None] = mapped_column(nullable=True)
    trust_score: Mapped[float | None] = mapped_column(nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False, index=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, index=True)
    is_spamblocked: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False, index=True
    )
    banned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ban_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    spamblocked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    spamblock_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    daily_messages_sent: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    daily_messages_reset_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    purchase_cost_rub: Mapped[float | None] = mapped_column(nullable=True)
    purchase_source: Mapped[str | None] = mapped_column(String(255), nullable=True)

    account_age_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    friends_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activity_score: Mapped[float | None] = mapped_column(nullable=True)
    spam_complaints_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    pool_links: Mapped[list["PoolAccount"]] = relationship(
        back_populates="social_account",
        cascade="all, delete-orphan",
    )
    assigned_leads: Mapped[list["CustomLead"]] = relationship(
        back_populates="assigned_account",
        foreign_keys="CustomLead.assigned_account_id",
        cascade="all, delete-orphan",
    )
    lead_messages: Mapped[list["CustomLeadMessage"]] = relationship(
        back_populates="social_account",
        cascade="all, delete-orphan",
    )
    action_logs: Mapped[list["AutomationActionLog"]] = relationship(
        back_populates="social_account",
        cascade="all, delete-orphan",
    )


class AccountPool(Base):
    __tablename__ = "account_pools"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(primary_key=True)
    custom_automation_id: Mapped[int] = mapped_column(
        ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    automation: Mapped["CustomAutomation"] = relationship(back_populates="account_pools")
    pool_accounts: Mapped[list["PoolAccount"]] = relationship(
        back_populates="account_pool",
        cascade="all, delete-orphan",
    )


class PoolAccount(Base):
    __tablename__ = "pool_accounts"
    __table_args__ = (
        UniqueConstraint("account_pool_id", "social_account_id", name="uq_pool_account"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    custom_automation_id: Mapped[int] = mapped_column(
        ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_pool_id: Mapped[int] = mapped_column(
        ForeignKey("account_pools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    social_account_id: Mapped[int] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_class: Mapped[str] = mapped_column(
        String(32), default=AccountClass.ONE_DAY.value, server_default="one_day", nullable=False, index=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    account_pool: Mapped["AccountPool"] = relationship(back_populates="pool_accounts")
    social_account: Mapped["SocialAccount"] = relationship(back_populates="pool_links")


class ChatImportJob(Base):
    __tablename__ = "chat_import_jobs"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(primary_key=True)
    custom_automation_id: Mapped[int] = mapped_column(
        ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending", nullable=False, index=True
    )
    total_rows: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    error_rows: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    error_log: Mapped[dict] = mapped_column(
        JSONB, default=list, nullable=False
    )
    created_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("custom_admins.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    automation: Mapped["CustomAutomation"] = relationship(back_populates="chat_import_jobs")


class CustomPrompt(Base):
    __tablename__ = "custom_prompts"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(primary_key=True)
    custom_automation_id: Mapped[int] = mapped_column(
        ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(
        String(64), default="deepseek-chat", server_default="deepseek-chat", nullable=False
    )
    temperature: Mapped[float] = mapped_column(nullable=False, default=0.7, server_default="0.7")
    max_tokens: Mapped[int] = mapped_column(Integer, default=1000, server_default="1000", nullable=False)
    response_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    automation: Mapped["CustomAutomation"] = relationship(back_populates="custom_prompts")


class ChatDiscoveryTask(Base):
    __tablename__ = "chat_discovery_tasks"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(primary_key=True)
    custom_automation_id: Mapped[int] = mapped_column(
        ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending", nullable=False, index=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_id: Mapped[int | None] = mapped_column(
        ForeignKey("custom_prompts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mode: Mapped[str] = mapped_column(String(32), default="monitoring", server_default="monitoring", nullable=False)
    max_chats: Mapped[int] = mapped_column(Integer, default=50, server_default="50", nullable=False)
    require_approval: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    relevance_threshold: Mapped[float] = mapped_column(Float, default=0.6, server_default=text("0.6"), nullable=False)
    found_chats: Mapped[dict] = mapped_column(
        JSONB, default=list, nullable=False
    )
    joined_chats: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    rejected_chats: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    automation: Mapped["CustomAutomation"] = relationship(back_populates="chat_discovery_tasks")


class ChatTarget(Base):
    __tablename__ = "chat_targets"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(primary_key=True)
    custom_automation_id: Mapped[int] = mapped_column(
        ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(
        String(32), default="telegram", server_default="telegram", nullable=False
    )
    external_chat_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    invite_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    chat_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mode: Mapped[str] = mapped_column(
        String(32), default=ChatMode.INACTIVE.value, server_default="inactive", nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(
        String(32), default=ChatSource.MANUAL.value, server_default="manual", nullable=False, index=True
    )
    import_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_import_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    discovery_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_discovery_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    monitoring_config: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    neurocommenting_config: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    discussion_config: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    shilling_config: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    join_status: Mapped[str] = mapped_column(
        String(32), default=ChatJoinStatus.PENDING.value, server_default="pending", nullable=False, index=True
    )
    join_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_join_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_join_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_join_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    joined_by_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False, index=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    automation: Mapped["CustomAutomation"] = relationship(back_populates="chat_targets")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("custom_automation_id", "dedup_key", name="uq_chat_message_dedup"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    custom_automation_id: Mapped[int] = mapped_column(
        ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chat_target_id: Mapped[int] = mapped_column(
        ForeignKey("chat_targets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    external_chat_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sender_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sender_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sender_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    dedup_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    processed_by_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="SET NULL"), nullable=True
    )
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, index=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, index=True)
    matched_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trigger_confidence: Mapped[float | None] = mapped_column(nullable=True)
    matched_prompt_id: Mapped[int | None] = mapped_column(
        ForeignKey("custom_prompts.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)

    automation: Mapped["CustomAutomation"] = relationship(back_populates="chat_messages")


class DmpOneImport(Base):
    __tablename__ = "dmp_one_imports"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(primary_key=True)
    custom_automation_id: Mapped[int] = mapped_column(
        ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    import_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    requested_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    received_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purchased_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_rub: Mapped[float | None] = mapped_column(nullable=True)
    cpl_rub: Mapped[float | None] = mapped_column(nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(
        JSONB, default=dict, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending", nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    automation: Mapped["CustomAutomation"] = relationship(back_populates="dmp_one_imports")


class CustomLead(Base):
    __tablename__ = "custom_leads"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(primary_key=True)
    custom_automation_id: Mapped[int] = mapped_column(
        ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chat_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    dmp_one_import_id: Mapped[int | None] = mapped_column(
        ForeignKey("dmp_one_imports.id", ondelete="SET NULL"), nullable=True, index=True
    )
    contact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    contact_value: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dmp_raw_data: Mapped[dict | None] = mapped_column(
        JSONB, default=dict, nullable=True
    )
    assigned_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default=LeadStatus.NEW.value, server_default="new", nullable=False, index=True
    )
    status_history: Mapped[dict] = mapped_column(
        JSONB, default=list, nullable=False
    )
    amocrm_lead_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amocrm_contact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amocrm_pipeline_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amocrm_status_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    transferred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    bot_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sheets_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    bot_notified_chat_ids: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    automation: Mapped["CustomAutomation"] = relationship(back_populates="custom_leads")
    assigned_account: Mapped["SocialAccount | None"] = relationship(
        back_populates="assigned_leads",
        foreign_keys=[assigned_account_id],
    )
    messages: Mapped[list["CustomLeadMessage"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
    )


class CustomLeadMessage(Base):
    __tablename__ = "custom_lead_messages"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(primary_key=True)
    custom_lead_id: Mapped[int] = mapped_column(
        ForeignKey("custom_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    social_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    external_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)

    lead: Mapped["CustomLead"] = relationship(back_populates="messages")
    social_account: Mapped["SocialAccount | None"] = relationship(back_populates="lead_messages")


class AutomationActionLog(Base):
    __tablename__ = "automation_action_logs"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(primary_key=True)
    custom_automation_id: Mapped[int] = mapped_column(
        ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    social_account_id: Mapped[int] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)

    automation: Mapped["CustomAutomation"] = relationship(back_populates="action_logs")
    social_account: Mapped["SocialAccount"] = relationship(back_populates="action_logs")


class AmocrmConnection(Base):
    __tablename__ = "amocrm_connections"
    __table_args__ = (
        UniqueConstraint("custom_automation_id", name="uq_amocrm_connection_automation"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    custom_automation_id: Mapped[int] = mapped_column(
        ForeignKey("custom_automations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    subdomain: Mapped[str] = mapped_column(String(128), nullable=False)
    client_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    client_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pipeline_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    responsible_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lead_status_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False, index=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive)

    automation: Mapped["CustomAutomation"] = relationship(back_populates="amocrm_connection")
