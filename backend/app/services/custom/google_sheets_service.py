"""Append DMP leads to a Google Sheet via a service account (no extra SDK)."""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import CustomAutomation, CustomLead
from ...utils.crypto import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
HEADER_ROW = ["Дата", "Телефон", "Сайт", "IP", "Страница", "Имя", "Компания", "Telegram", "Источник"]
_SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_spreadsheet_id(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    match = _SPREADSHEET_ID_RE.search(text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", text):
        return text
    return text


def parse_service_account(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Некорректный JSON сервисного аккаунта") from exc
    if not isinstance(data, dict):
        raise ValueError("JSON сервисного аккаунта должен быть объектом")
    email = str(data.get("client_email") or "").strip()
    private_key = str(data.get("private_key") or "").replace("\\n", "\n").strip()
    if not email or not private_key:
        raise ValueError("В JSON нужны client_email и private_key")
    data["client_email"] = email
    data["private_key"] = private_key
    return data


def encrypt_service_account_json(raw: str) -> str:
    parsed = parse_service_account(raw)
    return encrypt_token(json.dumps(parsed, ensure_ascii=False))


def decrypt_service_account(automation: CustomAutomation) -> dict[str, Any] | None:
    blob = (automation.google_sheets_credentials_enc or "").strip()
    if not blob:
        return None
    return parse_service_account(decrypt_token(blob))


def service_account_email(automation: CustomAutomation) -> str | None:
    try:
        data = decrypt_service_account(automation)
    except Exception:
        return None
    if not data:
        return None
    return str(data.get("client_email") or "") or None


def worksheet_name(automation: CustomAutomation) -> str:
    name = (automation.google_sheets_worksheet or "").strip()
    return name or "Лиды"


def _lead_raw(lead: CustomLead) -> dict[str, Any]:
    return lead.dmp_raw_data if isinstance(lead.dmp_raw_data, dict) else {}


def lead_sheet_row(lead: CustomLead) -> list[str]:
    raw = _lead_raw(lead)
    phone = str(raw.get("phone") or raw.get("phone_number") or "")
    if lead.contact_type == "phone":
        phone = phone or (lead.contact_value or "")
    telegram = ""
    if lead.contact_type == "telegram":
        telegram = lead.contact_value or ""
    telegram = telegram or str(raw.get("telegram") or raw.get("resolved_telegram") or "")
    created = lead.created_at or _utc_now()
    return [
        created.isoformat(sep=" ", timespec="seconds"),
        phone,
        str(raw.get("website") or lead.company or ""),
        str(raw.get("ip") or ""),
        str(raw.get("page") or lead.position or ""),
        lead.full_name or str(raw.get("name") or raw.get("full_name") or ""),
        lead.company or str(raw.get("company") or ""),
        telegram,
        lead.source or "dmp_one",
    ]


async def _access_token(credentials: dict[str, Any]) -> str:
    now = int(time.time())
    assertion = jwt.encode(
        {
            "iss": credentials["client_email"],
            "scope": SHEETS_SCOPE,
            "aud": TOKEN_URL,
            "iat": now,
            "exp": now + 3600,
        },
        credentials["private_key"],
        algorithm="RS256",
    )
    if isinstance(assertion, bytes):
        assertion = assertion.decode()
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
        response.raise_for_status()
        data = response.json()
    token = str(data.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("Google OAuth не вернул access_token")
    return token


def _range(automation: CustomAutomation, cells: str) -> str:
    sheet = worksheet_name(automation).replace("'", "''")
    return f"'{sheet}'!{cells}"


async def ensure_header_and_append(
    session: AsyncSession,
    automation: CustomAutomation,
    lead: CustomLead,
) -> dict[str, Any]:
    spreadsheet_id = parse_spreadsheet_id(automation.google_sheets_spreadsheet_id)
    credentials = decrypt_service_account(automation)
    if not spreadsheet_id or not credentials:
        return {"ok": False, "reason": "sheets_not_configured"}

    token = await _access_token(credentials)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    encoded_id = quote(spreadsheet_id, safe="")
    row = lead_sheet_row(lead)

    async with httpx.AsyncClient(timeout=20.0) as client:
        await _ensure_worksheet(client, encoded_id, worksheet_name(automation), headers)
        existing = await client.get(
            f"{SHEETS_API}/{encoded_id}/values/{quote(_range(automation, 'A1:I1'), safe='')}",
            headers=headers,
        )
        if existing.status_code == 200:
            values = (existing.json() or {}).get("values") or []
            has_header = bool(values and values[0])
        else:
            has_header = False
        if not has_header:
            header_put = await client.put(
                f"{SHEETS_API}/{encoded_id}/values/{quote(_range(automation, 'A1:I1'), safe='')}?valueInputOption=RAW",
                headers=headers,
                json={"values": [HEADER_ROW]},
            )
            header_put.raise_for_status()
        append = await client.post(
            (
                f"{SHEETS_API}/{encoded_id}/values/{quote(_range(automation, 'A1'), safe='')}:append"
                "?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
            ),
            headers=headers,
            json={"values": [row]},
        )
        append.raise_for_status()
    await session.flush()
    return {"ok": True, "spreadsheet_id": spreadsheet_id}


async def _ensure_worksheet(
    client: httpx.AsyncClient,
    encoded_id: str,
    title: str,
    headers: dict[str, str],
) -> None:
    meta = await client.get(f"{SHEETS_API}/{encoded_id}", headers=headers)
    meta.raise_for_status()
    titles = [
        str((sheet.get("properties") or {}).get("title") or "")
        for sheet in ((meta.json() or {}).get("sheets") or [])
        if isinstance(sheet, dict)
    ]
    if title in titles:
        return
    created = await client.post(
        f"{SHEETS_API}/{encoded_id}:batchUpdate",
        headers=headers,
        json={"requests": [{"addSheet": {"properties": {"title": title}}}]},
    )
    created.raise_for_status()
