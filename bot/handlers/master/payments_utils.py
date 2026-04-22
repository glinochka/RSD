PAYLOAD_PREFIX = "subscription"


def parse_payment_payload(payload: str) -> tuple[str | None, int | None]:
    """
    Формат payload: subscription:<PlanName>:<telegram_id>
    Возвращает (plan_name, telegram_id) или (None, None), если формат некорректный.
    """
    try:
        prefix, plan_name, tg_id_str = payload.split(":")
        if prefix != PAYLOAD_PREFIX:
            return None, None
        return plan_name, int(tg_id_str)
    except (ValueError, AttributeError):
        return None, None
