"""Heuristic classification for Telegram accounts."""
from ...alembic.models import AccountClass


def classify_account(info: dict | None) -> dict:
    """Return risk/trust scores and recommended account class.

    If ``info`` is None (Telegram check failed), the account gets the safest
    low-trust class and can be manually reviewed later.
    """
    if not info:
        return {
            "risk_score": 80.0,
            "trust_score": 20.0,
            "account_class": AccountClass.ONE_DAY.value,
            "recommended_class": AccountClass.ONE_DAY.value,
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

    if dialogs >= 50 and has_avatar and has_bio:
        cls = AccountClass.TRUSTED.value
    elif dialogs >= 20 and has_avatar:
        cls = AccountClass.MID.value
    else:
        cls = AccountClass.ONE_DAY.value

    return {
        "risk_score": round(risk, 2),
        "trust_score": round(trust, 2),
        "account_class": cls,
        "recommended_class": cls,
        "reason": "telegram_data",
    }
