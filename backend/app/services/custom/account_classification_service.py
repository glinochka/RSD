"""Heuristic classification for Telegram accounts.

Account classes are no longer used for gating.  This module only computes
risk / trust / activity scores that influence rotation weighting.
"""


def classify_account(info: dict | None) -> dict:
    """Return risk/trust/activity scores.

    If ``info`` is None (Telegram check failed), the account gets low trust
    and can be manually reviewed later.
    """
    if not info:
        return {
            "risk_score": 80.0,
            "trust_score": 20.0,
            "activity_score": 0.0,
            "reason": "no_telegram_data",
        }

    dialogs = int(info.get("dialogs_count", 0) or 0)
    has_avatar = bool(info.get("has_avatar", False))
    has_bio = bool(info.get("bio"))
    premium = bool(info.get("is_premium", False))

    risk = 0.0
    if dialogs < 5:
        risk += 25.0
    elif dialogs < 20:
        risk += 10.0
    if not has_avatar:
        risk += 20.0
    if not has_bio:
        risk += 15.0
    if not premium:
        risk += 5.0

    trust = max(0.0, 100.0 - risk)
    activity = min(100.0, dialogs * 0.5 + (10 if has_avatar else 0) + (5 if has_bio else 0) + (10 if premium else 0))

    return {
        "risk_score": round(risk, 2),
        "trust_score": round(trust, 2),
        "activity_score": round(activity, 2),
        "reason": "telegram_data",
    }
