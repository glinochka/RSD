"""Telephony channel constants."""

ANALYTICS_CHANNEL_PHONE = "phone"

TELEPHONY_CALL_STATUSES = frozenset(
    {"ringing", "active", "completed", "failed", "transferred"}
)

TELEPHONY_TURN_ROLES = frozenset({"user", "agent", "system"})

TELEPHONY_WEBHOOK_EVENTS = frozenset(
    {
        "call.inbound",
        "call.answered",
        "call.recording_ready",
        "call.hangup",
        "dtmf",
    }
)
