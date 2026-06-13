"""Voximplant Platform API client (telephony channel setup and teardown)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class VoximplantApiError(RuntimeError):
    pass


def _api_base() -> str:
    return (settings.VOXIMPLANT_API_BASE_URL or "https://api.voximplant.com/platform_api").rstrip("/")


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(max(5.0, float(settings.TELEPHONY_VOXIMPLANT_API_TIMEOUT_SECONDS)))


async def _platform_get(method: str, **params: str) -> dict[str, Any]:
    url = f"{_api_base()}/{method}"
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            response = await client.get(url, params={k: v for k, v in params.items() if v is not None})
    except httpx.HTTPError as exc:
        logger.warning("voximplant: %s request failed: %s", method, exc)
        raise VoximplantApiError("Не удалось связаться с Voximplant API") from exc

    if response.status_code != 200:
        raise VoximplantApiError(f"Voximplant API ({method}) вернул HTTP {response.status_code}")

    try:
        payload = response.json()
    except Exception as exc:
        raise VoximplantApiError("Некорректный ответ Voximplant API") from exc

    if int(payload.get("error") or payload.get("error_code") or 0) != 0:
        message = str(payload.get("error_msg") or payload.get("error_message") or "invalid request")
        raise VoximplantApiError(message)

    result = payload.get("result")
    if result is None:
        return {}
    return result if isinstance(result, dict) else {"items": result}


def _normalize_e164(value: str) -> str:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if not digits:
        return ""
    return f"+{digits}"


def _phone_matches(candidate: str, expected_e164: str) -> bool:
    left = _normalize_e164(candidate)
    right = _normalize_e164(expected_e164)
    if not left or not right:
        return False
    return left == right or left.endswith(right.lstrip("+")) or right.endswith(left.lstrip("+"))


async def validate_voximplant_account(*, account_id: str, api_key: str) -> dict[str, Any]:
    """Verify account_id + api_key via Platform API AccountInfo."""
    return await _platform_get(
        "GetAccountInfo",
        account_id=account_id.strip(),
        api_key=api_key.strip(),
    )


async def validate_voximplant_channel_setup(
    *,
    account_id: str,
    api_key: str,
    phone_number_e164: str,
    application_id: str,
    rule_id: str,
) -> None:
    """Verify account, inbound number, application and routing rule."""
    await validate_voximplant_account(account_id=account_id, api_key=api_key)

    numbers_payload = await _platform_get(
        "GetPhoneNumbers",
        account_id=account_id.strip(),
        api_key=api_key.strip(),
        count="100",
    )
    numbers = numbers_payload.get("result") if isinstance(numbers_payload.get("result"), list) else []
    if not numbers and isinstance(numbers_payload, list):
        numbers = numbers_payload
    if not numbers and isinstance(numbers_payload.get("items"), list):
        numbers = numbers_payload["items"]

    matched = None
    for item in numbers:
        if not isinstance(item, dict):
            continue
        raw_number = str(
            item.get("phone_number")
            or item.get("phone_installation_custom_name")
            or item.get("phone_installation_name")
            or ""
        )
        if _phone_matches(raw_number, phone_number_e164):
            matched = item
            break

    if matched is None:
        raise VoximplantApiError(
            f"Номер {phone_number_e164} не найден в аккаунте Voximplant. "
            "Проверьте E.164 и привязку номера в кабинете."
        )

    bound_app = str(matched.get("application_id") or matched.get("application_name") or "").strip()
    app_id = application_id.strip()
    if bound_app and bound_app != app_id and not bound_app.endswith(app_id):
        raise VoximplantApiError(
            "Указанный номер не привязан к application_id из настроек канала."
        )

    rules_payload = await _platform_get(
        "GetRules",
        account_id=account_id.strip(),
        api_key=api_key.strip(),
        application_id=app_id,
        count="100",
    )
    rules = rules_payload.get("result") if isinstance(rules_payload.get("result"), list) else []
    if not rules and isinstance(rules_payload, list):
        rules = rules_payload
    if not rules and isinstance(rules_payload.get("items"), list):
        rules = rules_payload["items"]

    rule_ids = {str(item.get("rule_id")) for item in rules if isinstance(item, dict) and item.get("rule_id") is not None}
    if rule_id.strip() not in rule_ids:
        raise VoximplantApiError(
            f"rule_id {rule_id} не найден в application {application_id}. "
            "Проверьте правило входящих в Voximplant."
        )


async def deactivate_voximplant_inbound_rule(
    *,
    account_id: str,
    api_key: str,
    application_id: str,
    rule_id: str,
) -> None:
    """
    Disable inbound routing rule when telephony channel is removed.
    Best-effort: failures are logged and do not block channel deletion.
    """
    try:
        await _platform_get(
            "SetRuleInfo",
            account_id=account_id.strip(),
            api_key=api_key.strip(),
            application_id=application_id.strip(),
            rule_id=rule_id.strip(),
            rule_name=f"rsd_disabled_{rule_id.strip()}",
            rule_pattern="disabled_by_rsd",
        )
    except VoximplantApiError as exc:
        logger.warning(
            "voximplant: failed to deactivate rule application_id=%s rule_id=%s: %s",
            application_id,
            rule_id,
            exc,
        )
