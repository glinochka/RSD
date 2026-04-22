from fastapi import status

from core.backendAPI import APIread, get_response_status


async def get_plans_from_backend() -> list[dict]:
    """
    Single source of truth for plans is the backend (/api/payments/plans).
    Returns list of plan dicts as-is from backend.
    """
    data = await APIread.subscriptionPlans()
    response_status = get_response_status(data)
    if response_status != status.HTTP_200_OK:
        return []
    plans = data.get("plans") if isinstance(data, dict) else None
    return plans or []


def paid_plans_map(plans: list[dict]) -> dict[str, dict]:
    return {p["code"]: p for p in plans if p.get("is_paid") and p.get("code")}
