"""Чек самозанятого через «Мой налог» (lknpd.nalog.ru) и PDF для отдела продаж."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import img2pdf
from moy_nalog import Client, IncomeType, MoyNalogClientSync, PaymentType
from moy_nalog.exceptions import AuthenticationError, MoyNalogError, ReceiptError

from ..alembic.models import SalesOutboundContact
from ..config import settings

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"\D+")


@dataclass(frozen=True)
class SalesMoyNalogReceiptResult:
    pdf_bytes: bytes
    receipt_uuid: str
    print_url: str
    total_amount: Decimal
    service_name: str


def moy_nalog_configured() -> bool:
    if (settings.MOY_NALOG_REFRESH_TOKEN or "").strip():
        return True
    inn = (settings.MOY_NALOG_INN or "").strip()
    password = (settings.MOY_NALOG_PASSWORD or "").strip()
    return bool(inn and password)


def _auth_config_hint() -> str:
    if (settings.MOY_NALOG_REFRESH_TOKEN or "").strip():
        return "проверьте MOY_NALOG_REFRESH_TOKEN"
    return "укажите MOY_NALOG_REFRESH_TOKEN или MOY_NALOG_INN + MOY_NALOG_PASSWORD"


def _quantize_amount_rub(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = _PHONE_RE.sub("", raw.strip())
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    if len(digits) == 11 and digits.startswith("7"):
        return f"+{digits}"
    return None


def _default_service_name(contact: SalesOutboundContact) -> str:
    template = (settings.SALES_INVOICE_SERVICE_NAME_TEMPLATE or "Услуги для {org_name}").strip()
    org = (contact.org_name or "клиента").strip() or "клиента"
    try:
        return template.format(org_name=org, contact_id=contact.id)
    except (KeyError, ValueError):
        return f"Услуги для {org}"


def _build_moy_nalog_client(contact: SalesOutboundContact, client_inn: str | None) -> Client:
    inn = (client_inn or "").strip()
    org = (contact.org_name or "").strip()
    lpr = (contact.lpr_name or "").strip()
    phone = _normalize_phone(contact.lpr_phone or contact.org_mobile or contact.org_phone)

    if inn and len(inn) in (10, 12):
        return Client(
            income_type=IncomeType.LEGAL_ENTITY,
            display_name=org or lpr or "Клиент",
            inn=inn,
        )

    display = lpr or org or "Клиент"
    if phone:
        return Client(
            income_type=IncomeType.INDIVIDUAL,
            display_name=display,
            contact_phone=phone,
        )
    return Client(
        income_type=IncomeType.INDIVIDUAL,
        display_name=display,
    )


def _authenticate_by_refresh_token(client: MoyNalogClientSync) -> None:
    refresh = (settings.MOY_NALOG_REFRESH_TOKEN or "").strip()
    if not refresh:
        return
    inn = (settings.MOY_NALOG_INN or "").strip() or None
    access = (settings.MOY_NALOG_ACCESS_TOKEN or "").strip()
    client.set_tokens(
        access_token=access or "init",
        refresh_token=refresh,
        inn=inn,
    )
    if access and not client.is_token_expired:
        return
    if not client.refresh_access_token():
        raise RuntimeError(
            "Не удалось обновить access token по MOY_NALOG_REFRESH_TOKEN. "
            "Получите новый refresh token (раз в ~год) через вход в lknpd.nalog.ru."
        )


def _ensure_authenticated(client: MoyNalogClientSync) -> None:
    if client.is_authenticated and not client.is_token_expired:
        return

    refresh = (settings.MOY_NALOG_REFRESH_TOKEN or "").strip()
    if refresh:
        _authenticate_by_refresh_token(client)
        return

    if client.is_authenticated and client.is_token_expired:
        if client.refresh_access_token():
            return

    username = (settings.MOY_NALOG_INN or "").strip()
    password = (settings.MOY_NALOG_PASSWORD or "").strip()
    if not username or not password:
        raise RuntimeError(f"Интеграция не настроена: {_auth_config_hint()}")
    client.auth_by_password(username, password)


def _png_to_pdf(png_bytes: bytes) -> bytes:
    return img2pdf.convert(png_bytes)


def create_contact_receipt_pdf(
    contact: SalesOutboundContact,
    *,
    amount_rub: Decimal,
    service_name: str | None = None,
    client_inn: str | None = None,
) -> SalesMoyNalogReceiptResult:
    """Создать чек в «Мой налог» и вернуть PDF (из официального print-изображения ФНС)."""
    if not moy_nalog_configured():
        raise RuntimeError(f"Интеграция с «Мой налог» не настроена. {_auth_config_hint()}")

    amount = _quantize_amount_rub(amount_rub)
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля")

    name = (service_name or "").strip() or _default_service_name(contact)
    if len(name) > 512:
        name = name[:512]

    session_file = (settings.MOY_NALOG_SESSION_FILE or "").strip() or None
    moy_client = _build_moy_nalog_client(contact, client_inn)

    receipt = None
    print_url = ""
    print_bytes = b""
    try:
        with MoyNalogClientSync(session_file=session_file) as api:
            _ensure_authenticated(api)
            receipt = api.create_receipt(
                name=name,
                amount=amount,
                client=moy_client,
                payment_type=PaymentType.CASH,
            )
            print_bytes = api.download_receipt_raw(receipt.uuid, format="print")
            print_url = receipt.print_url or api.get_receipt_print_url(receipt.uuid)
    except AuthenticationError as exc:
        logger.warning("Moy Nalog auth failed: %s", exc)
        raise RuntimeError(f"Не удалось войти в «Мой налог». {_auth_config_hint()}") from exc
    except ReceiptError as exc:
        logger.warning("Moy Nalog receipt error: %s", exc)
        raise RuntimeError(f"ФНС отклонила создание чека: {exc.message}") from exc
    except MoyNalogError as exc:
        logger.warning("Moy Nalog API error: %s", exc)
        raise RuntimeError(f"Ошибка API «Мой налог»: {exc.message}") from exc

    if not receipt or not print_bytes:
        raise RuntimeError("ФНС не вернула изображение чека")

    pdf_bytes = _png_to_pdf(print_bytes)

    return SalesMoyNalogReceiptResult(
        pdf_bytes=pdf_bytes,
        receipt_uuid=receipt.uuid,
        print_url=print_url,
        total_amount=receipt.total_amount or amount,
        service_name=name,
    )


def persist_receipt_metadata(contact: SalesOutboundContact, result: SalesMoyNalogReceiptResult) -> None:
    """Сохранить ссылку на последний чек в extra_json контакта."""
    try:
        extra: dict[str, Any] = json.loads(contact.extra_json or "{}")
    except json.JSONDecodeError:
        extra = {}
    extra["last_moy_nalog_receipt"] = {
        "uuid": result.receipt_uuid,
        "print_url": result.print_url,
        "amount": str(result.total_amount),
        "service_name": result.service_name,
    }
    contact.extra_json = json.dumps(extra, ensure_ascii=False)
