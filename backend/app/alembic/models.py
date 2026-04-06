import sys
from os.path import dirname, abspath
sys.path.insert(0, dirname(dirname(abspath(__file__))))



from sqlalchemy import BigInteger, Boolean, String, ForeignKey, Text, DateTime, Integer, UniqueConstraint
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
    password: Mapped[str] = mapped_column(String(100), nullable=True)
    
    subscription_type: Mapped[str] = mapped_column(String(50), default="Free")
    subscription_end_date: Mapped[date] = mapped_column(DateTime, nullable=True)
    
    # telegram_id is optional to allow web-only registration without Telegram
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True, nullable=True)
    
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    registered: Mapped[date] = mapped_column(default=datetime.now(timezone.utc))

    agents: Mapped[list['Agent']] = relationship(back_populates='user', cascade="all, delete-orphan")


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
    encrypted_token: Mapped[str] = mapped_column(String(500), unique=True)
    encrypted_external_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_api_key_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=True) 
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
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now_naive, index=True)

    agent: Mapped["Agent"] = relationship(back_populates="analytics_messages")


class AgentDocument(Base):
    __table_args__ = {'extend_existing': True}
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    
    file_name: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(15), default="processing") # processing, ready, error
    created_at: Mapped[date] = mapped_column(default=datetime.now(timezone.utc))
    agent: Mapped["Agent"] = relationship(back_populates="documents")


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

