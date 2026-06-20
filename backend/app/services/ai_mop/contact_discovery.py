"""OSINT-сбор контактов для outreach ИИ МОП.

Собирает пул email, username и телефонов из:
- карточки лида и extra_json (импорт / Яндекс Карты);
- CRM (sales_outbound_contacts по названию компании);
- пула импортированных контактов агента (AgentSalesImportedContact);
- свободного текста (комментарии, статусы) — ссылки t.me / wa.me, @username, телефоны.

Дедупликация — по паре (канал, чат): два разных Telegram-чата (username и номер) — ок,
два одинаковых target в одном канале — нет.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select

from ...alembic.database import async_session_maker
from ...alembic.models import (
    AgentChannelConnection,
    AgentSalesImportedContact,
    AiMopLead,
    SalesOutboundContact,
)
from ..sales.contact_target_resolver import (
    _normalize_ru_phone_digits,
    _telegram_dedup_key,
    build_cross_messenger_fallbacks,
    collect_all_messenger_channels,
)
from .llm_helpers import parse_lead_extra_json

logger = logging.getLogger(__name__)

_TG_LINK_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/[^\s,;\"'<>]+",
    re.I,
)
_WA_LINK_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:wa\.me|api\.whatsapp\.com)/[^\s,;\"'<>]+",
    re.I,
)
_AT_USERNAME_RE = re.compile(r"(?<![\w/])@([a-zA-Z][a-zA-Z0-9_]{4,31})\b")
_PHONE_IN_TEXT_RE = re.compile(
    r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b"
)

_PHONE_FIELD_KEYS = frozenset({
    "lpr_phone",
    "org_phone",
    "org_mobile",
    "phone",
    "телефон",
    "мобильный",
    "мобильныйтелефон",
    "телефонлпр",
})
_MESSENGER_FIELD_KEYS = {
    "telegram": frozenset({"telegram", "телеграм", "tg", "telegramlink"}),
    "whatsapp": frozenset({"whatsapp", "ватсап", "whatsapplink"}),
    "messenger_max": frozenset({"messenger_max", "max", "макс", "messenger max"}),
}


def normalize_org_name_key(org_name: str | None) -> str:
    return re.sub(r"\s+", " ", (org_name or "").strip().casefold())[:120]


def _unique_nonempty(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        text = (raw or "").strip()
        if not text or text in ("—", "-", "нет", "n/a", "none"):
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(text)
    return ordered


def _norm_field_key(key: str) -> str:
    return re.sub(r"[\s_\-]+", "", (key or "").casefold())


def _extract_links_and_phones_from_text(text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {
        "telegram": [],
        "whatsapp": [],
        "phones": [],
        "usernames": [],
    }
    if not text or not str(text).strip():
        return found

    for match in _TG_LINK_RE.finditer(text):
        found["telegram"].append(match.group(0).strip())
    for match in _WA_LINK_RE.finditer(text):
        found["whatsapp"].append(match.group(0).strip())
    for match in _AT_USERNAME_RE.finditer(text):
        found["usernames"].append(f"@{match.group(1)}")
    for match in _PHONE_IN_TEXT_RE.finditer(text):
        digits = _normalize_ru_phone_digits(match.group(0))
        if digits:
            found["phones"].append(f"+{digits}")

    return found


def _scan_extra_dict(extra: dict[str, Any]) -> dict[str, list[str]]:
    """Вытащить мессенджеры и телефоны из произвольных полей extra_json."""
    telegram: list[str] = []
    whatsapp: list[str] = []
    messenger_max: list[str] = []
    phones: list[str] = []

    for key, val in extra.items():
        if val is None:
            continue
        nk = _norm_field_key(str(key))

        if nk in _MESSENGER_FIELD_KEYS["telegram"]:
            telegram.append(str(val))
        elif nk in _MESSENGER_FIELD_KEYS["whatsapp"]:
            whatsapp.append(str(val))
        elif nk in _MESSENGER_FIELD_KEYS["messenger_max"]:
            messenger_max.append(str(val))
        elif nk in _PHONE_FIELD_KEYS or "телефон" in nk or "phone" in nk:
            phones.append(str(val))

        if isinstance(val, str):
            mined = _extract_links_and_phones_from_text(val)
            telegram.extend(mined["telegram"])
            whatsapp.extend(mined["whatsapp"])
            phones.extend(mined["phones"])
            for username in mined["usernames"]:
                telegram.append(username)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    mined = _extract_links_and_phones_from_text(item)
                    telegram.extend(mined["telegram"])
                    whatsapp.extend(mined["whatsapp"])
                    phones.extend(mined["phones"])
                    for username in mined["usernames"]:
                        telegram.append(username)

    return {
        "telegram": _unique_nonempty(telegram),
        "whatsapp": _unique_nonempty(whatsapp),
        "messenger_max": _unique_nonempty(messenger_max),
        "phones": _unique_nonempty(phones),
    }


def _parse_extra_json_blob(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


@dataclass
class MergedContactBundle:
    """Агрегированные контакты из всех источников до нормализации в каналы."""

    org_name: str
    lpr_name: str | None = None
    lpr_phone: str | None = None
    org_phone: str | None = None
    org_mobile: str | None = None
    telegram_links: list[str] = field(default_factory=list)
    whatsapp_links: list[str] = field(default_factory=list)
    messenger_max_values: list[str] = field(default_factory=list)
    extra_phones: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    import_pool_targets: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)
    sources: dict[str, Any] = field(default_factory=dict)

    def best_phones(self) -> tuple[str | None, str | None, str | None]:
        """lpr_phone, org_mobile, org_phone — приоритет явных полей, затем extra_phones."""
        extra_digits: list[str] = []
        for raw in self.extra_phones:
            digits = _normalize_ru_phone_digits(raw)
            if digits and digits not in extra_digits:
                extra_digits.append(digits)

        lpr = _normalize_ru_phone_digits(self.lpr_phone)
        mobile = _normalize_ru_phone_digits(self.org_mobile)
        org = _normalize_ru_phone_digits(self.org_phone)

        if not mobile and extra_digits:
            mobile = extra_digits[0]
        if not org and len(extra_digits) > 1:
            org = extra_digits[1]
        if not lpr and len(extra_digits) > 2:
            lpr = extra_digits[2]

        def _fmt(digits: str | None) -> str | None:
            return f"+{digits}" if digits else None

        return _fmt(lpr), _fmt(mobile), _fmt(org)

    def resolver_row_variants(self) -> list[dict[str, Any]]:
        """Комбинации строк для contact_target_resolver (каждая ссылка — отдельный проход)."""
        lpr_phone, org_mobile, org_phone = self.best_phones()
        base = {
            "org_name": self.org_name,
            "lpr_name": self.lpr_name,
            "lpr_phone": lpr_phone,
            "org_mobile": org_mobile,
            "org_phone": org_phone,
        }

        tg_links = self.telegram_links or [None]
        wa_links = self.whatsapp_links or [None]
        max_vals = self.messenger_max_values or [None]

        variants: list[dict[str, Any]] = []
        seen_sig: set[str] = set()
        for tg in tg_links:
            for wa in wa_links:
                for mx in max_vals:
                    row = {
                        **base,
                        "telegram": tg,
                        "whatsapp": wa,
                        "messenger_max": mx,
                    }
                    sig = json.dumps(row, sort_keys=True, ensure_ascii=False)
                    if sig in seen_sig:
                        continue
                    seen_sig.add(sig)
                    variants.append(row)
        return variants or [{**base, "telegram": None, "whatsapp": None, "messenger_max": None}]


def _merge_row_into_bundle(bundle: MergedContactBundle, row: dict[str, Any], *, source: str) -> None:
    bundle.lpr_name = bundle.lpr_name or (str(row.get("lpr_name") or "").strip() or None)
    bundle.lpr_phone = bundle.lpr_phone or (str(row.get("lpr_phone") or "").strip() or None)
    bundle.org_phone = bundle.org_phone or (str(row.get("org_phone") or "").strip() or None)
    bundle.org_mobile = bundle.org_mobile or (str(row.get("org_mobile") or "").strip() or None)

    if row.get("telegram"):
        bundle.telegram_links.append(str(row["telegram"]))
    if row.get("whatsapp"):
        bundle.whatsapp_links.append(str(row["whatsapp"]))
    if row.get("messenger_max"):
        bundle.messenger_max_values.append(str(row["messenger_max"]))
    email_val = str(row.get("email") or "").strip()
    if email_val and "@" in email_val:
        bundle.emails.append(email_val)

    for phone_key in ("lpr_phone", "org_phone", "org_mobile", "phone"):
        val = row.get(phone_key)
        if val:
            bundle.extra_phones.append(str(val))

    for text_field in ("comment", "import_status"):
        val = row.get(text_field)
        if val:
            mined = _extract_links_and_phones_from_text(str(val))
            bundle.telegram_links.extend(mined["telegram"])
            bundle.whatsapp_links.extend(mined["whatsapp"])
            bundle.extra_phones.extend(mined["phones"])
            for username in mined["usernames"]:
                bundle.telegram_links.append(username)

    extra = row.get("extra_json")
    if isinstance(extra, dict):
        scanned = _scan_extra_dict(extra)
    elif isinstance(extra, str):
        scanned = _scan_extra_dict(_parse_extra_json_blob(extra))
    else:
        scanned = _scan_extra_dict({})

    bundle.telegram_links.extend(scanned["telegram"])
    bundle.whatsapp_links.extend(scanned["whatsapp"])
    bundle.messenger_max_values.extend(scanned["messenger_max"])
    bundle.extra_phones.extend(scanned["phones"])

    bundle.sources[source] = bundle.sources.get(source, 0) + 1


def build_merged_contact_bundle(
    lead: AiMopLead,
    *,
    crm_rows: list[SalesOutboundContact] | None = None,
    imported_rows: list[AgentSalesImportedContact] | None = None,
) -> MergedContactBundle:
    """Собрать все контакты лида без обращения к БД (CRM/import передаются снаружи)."""
    extra = parse_lead_extra_json(lead)
    fallback_phone = str(lead.phone or "").strip() or None

    bundle = MergedContactBundle(org_name=str(lead.org_name or "").strip())
    lead_row: dict[str, Any] = {
        "lpr_name": lead.lpr_name,
        "lpr_phone": str(extra.get("lpr_phone") or "").strip() or fallback_phone,
        "org_phone": str(extra.get("org_phone") or "").strip() or fallback_phone,
        "org_mobile": str(extra.get("org_mobile") or "").strip() or fallback_phone,
        "telegram": lead.telegram or extra.get("telegram"),
        "whatsapp": lead.whatsapp or extra.get("whatsapp"),
        "messenger_max": extra.get("messenger_max") or extra.get("max") or extra.get("макс"),
        "extra_json": extra,
    }
    _merge_row_into_bundle(bundle, lead_row, source="lead")

    for comment_field in ("comment", "import_status", "статус", "примечание"):
        val = extra.get(comment_field)
        if val:
            mined = _extract_links_and_phones_from_text(str(val))
            bundle.telegram_links.extend(mined["telegram"])
            bundle.whatsapp_links.extend(mined["whatsapp"])
            bundle.extra_phones.extend(mined["phones"])
            for username in mined["usernames"]:
                bundle.telegram_links.append(username)

    for crm in crm_rows or []:
        crm_extra = _parse_extra_json_blob(crm.extra_json)
        _merge_row_into_bundle(
            bundle,
            {
                "lpr_name": crm.lpr_name,
                "lpr_phone": crm.lpr_phone,
                "org_phone": crm.org_phone,
                "org_mobile": crm.org_mobile,
                "telegram": crm.telegram,
                "whatsapp": crm.whatsapp,
                "messenger_max": crm.messenger_max,
                "extra_json": crm_extra,
                "comment": crm.comment,
                "import_status": crm.import_status,
            },
            source="crm",
        )

    for imp in imported_rows or []:
        imp_extra = _parse_extra_json_blob(imp.extra_json)
        _merge_row_into_bundle(
            bundle,
            {
                "lpr_name": imp.lpr_name,
                "lpr_phone": imp.lpr_phone,
                "org_phone": imp.org_phone,
                "org_mobile": imp.org_mobile,
                "telegram": imp.telegram,
                "whatsapp": imp.whatsapp,
                "extra_json": imp_extra,
            },
            source="import_pool",
        )
        channel = str(imp.channel or "").strip()
        target = str(imp.target_external_id or "").strip()
        if channel and target:
            hint: dict[str, Any] = {"source": "agent_import_pool", "imported_contact_id": imp.id}
            if imp.target_resolve_hint:
                try:
                    parsed = json.loads(imp.target_resolve_hint)
                    if isinstance(parsed, dict):
                        hint.update(parsed)
                except json.JSONDecodeError:
                    pass
            bundle.import_pool_targets.append((channel, target, hint))

    bundle.telegram_links = _unique_nonempty(bundle.telegram_links)
    bundle.whatsapp_links = _unique_nonempty(bundle.whatsapp_links)
    bundle.messenger_max_values = _unique_nonempty(bundle.messenger_max_values)
    bundle.extra_phones = _unique_nonempty(bundle.extra_phones)
    bundle.emails = _unique_nonempty(bundle.emails)
    return bundle


def outreach_target_dedup_key(*, channel: str, target: str) -> str:
    """Ключ уникальности чата: один канал + один идентификатор диалога."""
    ch = channel.strip().lower()
    tgt = target.strip()
    if ch == "telegram_userbot":
        tg_key = _telegram_dedup_key(tgt)
        return f"{ch}:{tg_key}"
    if ch == "whatsapp_userbot":
        digits = _normalize_ru_phone_digits(tgt) or tgt.casefold()
        return f"{ch}:{digits}"
    if ch == "max_userbot":
        digits = _normalize_ru_phone_digits(tgt)
        return f"{ch}:+{digits}" if digits else f"{ch}:{tgt.casefold()}"
    return f"{ch}:{tgt.casefold()}"


def collect_messenger_channels_from_bundle(
    bundle: MergedContactBundle,
    *,
    whatsapp_available: bool,
    telegram_available: bool,
    max_available: bool,
) -> list[tuple[str, str, dict[str, Any]]]:
    """Все уникальные мессенджер-каналы: без дублей в один чат, с кросс-каналом."""
    channels: list[tuple[str, str, dict[str, Any]]] = []
    seen: set[str] = set()

    def _append(channel: str, target: str, hint: dict[str, Any]) -> None:
        key = outreach_target_dedup_key(channel=channel, target=target)
        if key in seen:
            return
        seen.add(key)
        enriched = dict(hint)
        cross = build_cross_messenger_fallbacks(
            bundle.resolver_row_variants()[0],
            primary_channel=channel,
            whatsapp_available=whatsapp_available,
            telegram_available=telegram_available,
            max_available=max_available,
        )
        if cross:
            enriched.setdefault("cross_channel_fallbacks", cross)
        channels.append((channel, target, enriched))

    for row in bundle.resolver_row_variants():
        for channel, target, hint in collect_all_messenger_channels(
            row,
            whatsapp_available=whatsapp_available,
            telegram_available=telegram_available,
            max_available=max_available,
        ):
            merged_hint = dict(hint)
            merged_hint.setdefault("discover_source", "resolver")
            _append(channel, target, merged_hint)

    for channel, target, hint in bundle.import_pool_targets:
        if channel == "whatsapp_userbot" and not whatsapp_available:
            continue
        if channel == "telegram_userbot" and not telegram_available:
            continue
        if channel == "max_userbot" and not max_available:
            continue
        _append(channel, target, hint)

    return channels


@dataclass
class AgentMessengerAvailability:
    whatsapp: bool = False
    telegram: bool = False
    max_userbot: bool = False

    @property
    def any_messenger(self) -> bool:
        return self.whatsapp or self.telegram or self.max_userbot


@dataclass
class AiMopOutreachDiscovery:
    """Результат OSINT-поиска контактов для одного лида."""

    messengers: list[tuple[str, str, dict[str, Any]]]
    bundle: MergedContactBundle
    availability: AgentMessengerAvailability
    sources_summary: dict[str, Any]

    @property
    def has_messenger_channel(self) -> bool:
        return bool(self.messengers)


async def _agent_has_channel(agent_id: int, provider: str) -> bool:
    async with async_session_maker() as session:
        row = await session.scalar(
            select(AgentChannelConnection.id).where(
                AgentChannelConnection.agent_id == agent_id,
                AgentChannelConnection.provider == provider,
                AgentChannelConnection.is_active.is_(True),
            )
        )
        return row is not None


async def get_agent_messenger_availability(agent_id: int) -> AgentMessengerAvailability:
    return AgentMessengerAvailability(
        whatsapp=await _agent_has_channel(agent_id, "whatsapp_userbot"),
        telegram=await _agent_has_channel(agent_id, "telegram_userbot"),
        max_userbot=await _agent_has_channel(agent_id, "max_userbot"),
    )


async def _fetch_crm_rows_for_org(org_name: str, *, limit: int = 5) -> list[SalesOutboundContact]:
    key = normalize_org_name_key(org_name)
    if not key:
        return []
    async with async_session_maker() as session:
        rows = (
            await session.scalars(
                select(SalesOutboundContact)
                .where(
                    SalesOutboundContact.archived_at.is_(None),
                    func.lower(func.trim(SalesOutboundContact.org_name)) == key,
                )
                .order_by(SalesOutboundContact.updated_at.desc())
                .limit(limit)
            )
        ).all()
    return list(rows)


async def _fetch_agent_imported_rows(
    agent_id: int,
    org_name: str,
    *,
    limit: int = 10,
) -> list[AgentSalesImportedContact]:
    key = normalize_org_name_key(org_name)
    if not key or not agent_id:
        return []
    async with async_session_maker() as session:
        rows = (
            await session.scalars(
                select(AgentSalesImportedContact)
                .where(
                    AgentSalesImportedContact.agent_id == agent_id,
                    func.lower(func.trim(AgentSalesImportedContact.org_name)) == key,
                )
                .order_by(AgentSalesImportedContact.updated_at.desc())
                .limit(limit)
            )
        ).all()
    return list(rows)


async def discover_ai_mop_outreach_targets(
    *,
    agent_id: int,
    lead: AiMopLead,
) -> AiMopOutreachDiscovery:
    """Полный OSINT-поиск мессенджер-каналов для outreach (все ИИ МОП, не только custom runtime)."""
    availability = await get_agent_messenger_availability(agent_id)
    if not availability.any_messenger:
        bundle = build_merged_contact_bundle(lead)
        return AiMopOutreachDiscovery(
            messengers=[],
            bundle=bundle,
            availability=availability,
            sources_summary={"channels_connected": False},
        )

    crm_rows = await _fetch_crm_rows_for_org(lead.org_name)
    imported_rows = await _fetch_agent_imported_rows(agent_id, lead.org_name)
    bundle = build_merged_contact_bundle(lead, crm_rows=crm_rows, imported_rows=imported_rows)

    messengers = collect_messenger_channels_from_bundle(
        bundle,
        whatsapp_available=availability.whatsapp,
        telegram_available=availability.telegram,
        max_available=availability.max_userbot,
    )

    sources_summary = {
        "channels_connected": True,
        "crm_matches": len(crm_rows),
        "import_pool_matches": len(imported_rows),
        "telegram_links": len(bundle.telegram_links),
        "whatsapp_links": len(bundle.whatsapp_links),
        "messenger_max_values": len(bundle.messenger_max_values),
        "extra_phones": len(bundle.extra_phones),
        "import_pool_targets": len(bundle.import_pool_targets),
        "messengers_found": len(messengers),
        "bundle_sources": dict(bundle.sources),
    }
    logger.info(
        "AI MOP contact discovery lead_id=%s agent_id=%s: %s",
        lead.id,
        agent_id,
        sources_summary,
    )

    return AiMopOutreachDiscovery(
        messengers=messengers,
        bundle=bundle,
        availability=availability,
        sources_summary=sources_summary,
    )


async def resolve_all_lead_messenger_channels(
    *,
    agent_id: int,
    lead: AiMopLead,
) -> list[tuple[str, str, dict[str, Any]]]:
    """Совместимость: список (channel, target, hint) для outreach."""
    discovery = await discover_ai_mop_outreach_targets(agent_id=agent_id, lead=lead)
    avail = discovery.availability
    if not avail.whatsapp:
        logger.debug(
            "AI MOP lead_id=%s agent_id=%s: WhatsApp userbot не подключён — WA пропущен",
            lead.id,
            agent_id,
        )
    if not avail.telegram:
        logger.debug(
            "AI MOP lead_id=%s agent_id=%s: Telegram userbot не подключён — TG пропущен",
            lead.id,
            agent_id,
        )
    if not avail.max_userbot:
        logger.debug(
            "AI MOP lead_id=%s agent_id=%s: MAX userbot не подключён — MAX пропущен",
            lead.id,
            agent_id,
        )
    return discovery.messengers
