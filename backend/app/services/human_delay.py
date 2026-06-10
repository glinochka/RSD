"""Human-like delay simulation for AI agents on userbot channels.

Simulates natural human response patterns:
  1. "Come online" delay (1–3 min) when conversation has been inactive and
     is not a brand-new first-ever exchange.
  2. Short reading pause proportional to the incoming message length.
  3. Typing pause after LLM returns a response, proportional to response length.

Not applied to telephony channels (real-time voice cannot tolerate multi-minute delays).
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Dict, Tuple

from sqlalchemy import func, select

from ..alembic.database import async_session_maker
from ..alembic.models import AgentAnalyticsMessage

logger = logging.getLogger(__name__)

# How long a conversation is considered "active" (no re-entry delay within this window).
_ACTIVE_CONVERSATION_SECONDS = 600  # 10 minutes

# In-memory tracking: (agent_id, user_external_id, channel) → last activity datetime (UTC)
_last_activity: Dict[Tuple[int, str, str], datetime] = {}


def _key(agent_id: int, user_external_id: str, channel: str) -> Tuple[int, str, str]:
    return (agent_id, (user_external_id or "").strip().lower(), (channel or "").strip().lower())


async def _has_prior_messages(agent_id: int, user_external_id: str, channel: str) -> bool:
    """Check DB for any prior messages in this conversation."""
    uid = (user_external_id or "").strip()
    ch = (channel or "").strip().lower()
    if not uid or not ch:
        return False
    try:
        async with async_session_maker() as session:
            async with session.begin():
                count = await session.scalar(
                    select(func.count())
                    .select_from(AgentAnalyticsMessage)
                    .where(
                        AgentAnalyticsMessage.agent_id == agent_id,
                        AgentAnalyticsMessage.user_external_id == uid,
                        AgentAnalyticsMessage.channel == ch,
                        AgentAnalyticsMessage.role.in_(["user", "agent"]),
                    )
                )
                return int(count or 0) > 0
    except Exception:
        logger.debug("human_delay: DB check for prior messages failed", exc_info=True)
        return False


async def get_online_delay(agent_id: int, user_external_id: str, channel: str) -> float:
    """Return seconds to wait before the agent 'comes online' (shows read receipt + starts typing).

    Returns 0.0 if:
    - Conversation is currently active (last message within 10 min)
    - This is the very first message in the conversation (no prior DB records)
    """
    key = _key(agent_id, user_external_id, channel)
    now = datetime.now(timezone.utc)

    if key in _last_activity:
        elapsed = (now - _last_activity[key]).total_seconds()
        if elapsed <= _ACTIVE_CONVERSATION_SECONDS:
            # Active conversation — no re-entry delay
            return 0.0
        # Inactive but known conversation — apply re-entry delay
        return random.uniform(60.0, 180.0)

    # Not tracked in-memory (new session or first message) — check DB
    has_history = await _has_prior_messages(agent_id, user_external_id, channel)
    if has_history:
        # Resuming an existing conversation after inactivity
        return random.uniform(60.0, 180.0)
    # Brand-new conversation — agent responds immediately on first message
    return 0.0


def get_read_delay(message_len: int) -> float:
    """Seconds to simulate reading the incoming message.

    Roughly 15 chars/second with ±20 % jitter, clamped to 2–12 s.
    """
    raw = max(0, message_len) / 15.0
    delay = max(2.0, min(12.0, raw))
    return delay * random.uniform(0.8, 1.2)


def get_typing_delay(response_len: int) -> float:
    """Extra seconds to hold the typing indicator after the LLM has finished.

    The LLM generation already provides natural latency; this adds extra time
    proportional to response length so that very short answers don't arrive
    suspiciously fast.  Clamped to 2–30 s with ±15 % jitter.
    """
    # ~5 chars/second "typing" — deduct a few seconds since LLM already took time
    raw = max(0.0, response_len / 5.0 - 3.0)
    delay = max(2.0, min(30.0, raw))
    return delay * random.uniform(0.85, 1.15)


def mark_activity(agent_id: int, user_external_id: str, channel: str) -> None:
    """Record that this agent just responded in the conversation."""
    key = _key(agent_id, user_external_id, channel)
    _last_activity[key] = datetime.now(timezone.utc)


def is_human_delay_enabled(template_config: dict | None, channel: str) -> bool:
    """Return True if human delay should be applied for this request.

    Default: True for userbot channels, False for telephony.
    Can be overridden per-agent via template_config['enable_human_delay'].
    """
    ch = (channel or "").strip().lower()
    # Telephony is real-time — never add delays
    if ch in {"phone", "telephony"}:
        return False
    cfg = template_config or {}
    if "enable_human_delay" in cfg:
        return bool(cfg["enable_human_delay"])
    # Default ON for userbot channels
    return ch in {"telegram_userbot", "whatsapp_userbot", "max_userbot"}
