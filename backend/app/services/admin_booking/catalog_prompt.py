"""Снимок каталога записи для системного промпта crm_admin."""
from __future__ import annotations

import logging
from typing import Any

from .service import get_admin_booking_service

logger = logging.getLogger(__name__)

_STAFF_ROLE_LABELS: dict[str, str] = {
    "master": "мастер",
    "doctor": "врач",
    "mechanic": "механик",
    "therapist": "терапевт / массажист",
    "specialist": "специалист",
}

_TARGET_ROLE_LABELS: dict[str, str] = {
    "master": "мастер",
    "doctor": "врач",
    "mechanic": "механик",
    "therapist": "терапевт",
    "specialist": "специалист",
}


def _role_label(role: str | None, *, mapping: dict[str, str]) -> str:
    key = str(role or "").strip().lower()
    if not key:
        return "специалист"
    return mapping.get(key, key.replace("_", " "))


def _format_price_rub(price_rub: Any) -> str:
    try:
        value = float(price_rub)
    except (TypeError, ValueError):
        return "цена не указана"
    if value <= 0:
        return "бесплатно"
    if abs(value - round(value)) < 0.001:
        rub = int(round(value))
        return f"{rub:,}".replace(",", " ") + " ₽"
    text = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    return f"{text} ₽"


def _enrich_services_with_staff_names(
    staff_rows: list[dict[str, Any]],
    services: list[dict[str, Any]],
) -> None:
    names_by_id: dict[int, str] = {}
    for row in staff_rows:
        try:
            sid = int(row["id"])
        except (TypeError, ValueError, KeyError):
            continue
        name = str(row.get("full_name") or "").strip()
        if name:
            names_by_id[sid] = name
    for item in services:
        raw = item.get("staff_id")
        if raw is None:
            continue
        try:
            sid = int(raw)
        except (TypeError, ValueError):
            continue
        if sid in names_by_id:
            item["staff_full_name"] = names_by_id[sid]


def build_booking_catalog_knowledge_block(
    staff_rows: list[dict[str, Any]],
    service_rows: list[dict[str, Any]],
) -> str:
    """Текстовый блок «Актуальная база знаний» для LLM (не показывать клиенту целиком)."""
    active_staff = [row for row in staff_rows if row.get("is_active", True) is not False]
    active_services = [row for row in service_rows if row.get("is_active", True) is not False]

    lines: list[str] = ["Актуальная база знаний:"]

    if not active_staff and not active_services:
        lines.append("(каталог пуст — уточни у владельца или вызови list_staff и list_services)")
        return "\n".join(lines)

    if active_staff:
        lines.append("")
        lines.append("Специалисты:")
        for row in sorted(active_staff, key=lambda r: str(r.get("full_name") or "")):
            try:
                staff_id = int(row["id"])
            except (TypeError, ValueError, KeyError):
                continue
            name = str(row.get("full_name") or "Без имени").strip()
            role = _role_label(row.get("role"), mapping=_STAFF_ROLE_LABELS)
            specs = row.get("specializations") or []
            spec_text = ""
            if isinstance(specs, list) and specs:
                joined = ", ".join(str(s).strip() for s in specs if str(s).strip())
                if joined:
                    spec_text = f"; специализации: {joined}"
            lines.append(f"- {name} ({role}; staff_id={staff_id}{spec_text})")

    services_by_staff: dict[int | None, list[dict[str, Any]]] = {}
    for svc in active_services:
        raw_staff = svc.get("staff_id")
        key: int | None
        try:
            key = int(raw_staff) if raw_staff is not None else None
        except (TypeError, ValueError):
            key = None
        services_by_staff.setdefault(key, []).append(svc)

    lines.append("")
    lines.append("Услуги (цена в рублях, длительность в минутах):")

    staff_name_by_id = {}
    for row in active_staff:
        try:
            staff_name_by_id[int(row["id"])] = str(row.get("full_name") or "").strip()
        except (TypeError, ValueError, KeyError):
            continue

    bound_staff_ids = sorted(
        (sid for sid in services_by_staff if sid is not None),
        key=lambda sid: staff_name_by_id.get(sid or 0, ""),
    )
    for staff_id in bound_staff_ids:
        name = staff_name_by_id.get(staff_id, f"staff_id={staff_id}")
        lines.append(f"  — {name}:")
        for svc in sorted(services_by_staff.get(staff_id) or [], key=lambda s: str(s.get("title") or "")):
            title = str(svc.get("title") or "Услуга").strip()
            try:
                service_id = int(svc["id"])
            except (TypeError, ValueError, KeyError):
                continue
            price = _format_price_rub(svc.get("price_rub"))
            duration = int(svc.get("duration_minutes") or 0)
            lines.append(
                f"    · «{title}» — {price}, {duration} мин; service_id={service_id}"
            )

    unbound = services_by_staff.get(None) or []
    if unbound:
        lines.append("  — без привязки к специалисту:")
        for svc in sorted(unbound, key=lambda s: str(s.get("title") or "")):
            title = str(svc.get("title") or "Услуга").strip()
            try:
                service_id = int(svc["id"])
            except (TypeError, ValueError, KeyError):
                continue
            target = _role_label(svc.get("target_role"), mapping=_TARGET_ROLE_LABELS)
            price = _format_price_rub(svc.get("price_rub"))
            duration = int(svc.get("duration_minutes") or 0)
            lines.append(
                f"    · «{title}» — {price}, {duration} мин (роль: {target}); service_id={service_id}"
            )

    if not active_services:
        lines.append("(услуги не заданы)")

    lines.append("")
    lines.append(
        "Снимок каталога обновляется при каждом сообщении клиента. "
        "Для свободных слотов, создания и отмены записи всё равно вызывай tools. "
        "Цены и привязки услуг бери из этого блока; service_id и staff_id — только для tool calls, клиенту не озвучивай."
    )
    return "\n".join(lines)


async def load_booking_catalog_knowledge(*, agent_id: int) -> str:
    booking = get_admin_booking_service()
    try:
        staff_rows = await booking.list_staff(agent_id=agent_id, active_only=False)
        service_rows = await booking.list_services(agent_id=agent_id, active_only=False)
    except Exception:
        logger.exception("Failed to load booking catalog for agent_id=%s", agent_id)
        return (
            "Актуальная база знаний:\n"
            "(не удалось загрузить каталог — вызови list_staff и list_services)"
        )

    active_staff = [r for r in staff_rows if r.get("is_active", True) is not False]
    active_services = [r for r in service_rows if r.get("is_active", True) is not False]
    _enrich_services_with_staff_names(active_staff, active_services)
    return build_booking_catalog_knowledge_block(active_staff, active_services)
