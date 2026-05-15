"""Парсинг выгрузок контактов (2GIS и совместимые таблицы) в sales_outbound_contacts."""

from __future__ import annotations

import json
import re
from io import BytesIO
from typing import Any

from openpyxl import load_workbook

_ws_re = re.compile(r"\s+")


def _norm_header(h: object) -> str:
    s = str(h or "").replace("\ufeff", "").strip()
    s = _ws_re.sub(" ", s)
    return s.casefold()


def _cell_str(val: object) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and val == int(val):
        return str(int(val))
    return str(val).strip()


def _opt_str(val: object) -> str | None:
    s = _cell_str(val)
    return s or None


def _layout_by_position(headers: list[str]) -> dict[str, int] | None:
    """Стандартный порядок колонок из выгрузки (Название, ФИО ЛПР, Телефон, ...)."""
    n = [_norm_header(h) for h in headers]
    if len(n) < 6:
        return None
    ok0 = n[0] == "название" or n[0].startswith("название")
    ok1 = "фио" in n[1] and "лпр" in n[1]
    ok2 = n[2] == "телефон"
    ok3 = "мобильн" in n[3]
    ok4 = "телефон" in n[4] and "лпр" in n[4]
    if not (ok0 and ok1 and ok2 and ok3 and ok4):
        return None
    return {
        "org_name": 0,
        "lpr_name": 1,
        "org_phone": 2,
        "org_mobile": 3,
        "lpr_phone": 4,
        "import_status": 5,
    }


def _extend_mapping(headers: list[str], base: dict[str, int]) -> dict[str, int]:
    n = [_norm_header(h) for h in headers]
    used = set(base.values())
    m = dict(base)
    for i, ni in enumerate(n):
        if i in used:
            continue
        if ni in ("сайт", "website"):
            m.setdefault("website", i)
        elif ni in ("email", "e-mail", "e_mail", "почта"):
            m.setdefault("email", i)
    return m


def _fuzzy_mapping(headers: list[str]) -> dict[str, int]:
    n = [_norm_header(h) for h in headers]
    m: dict[str, int] = {}
    for i, (raw, ni) in enumerate(zip(headers, n)):
        if "фио" in ni and "лпр" in ni:
            m.setdefault("lpr_name", i)
        elif ni == "название" and "(eng)" not in str(raw).lower() and "англ" not in ni:
            m.setdefault("org_name", i)
        elif "мобильн" in ni or ni == "мобильный телефон":
            m.setdefault("org_mobile", i)
        elif "телефон" in ni and "лпр" in ni:
            m.setdefault("lpr_phone", i)
        elif ni == "телефон" or ni.startswith("телефон "):
            if "лпр" not in ni:
                m.setdefault("org_phone", i)
        elif ni == "статус":
            m.setdefault("import_status", i)
        elif ni in ("сайт", "website"):
            m.setdefault("website", i)
        elif ni in ("email", "e-mail", "e_mail", "почта"):
            m.setdefault("email", i)
    return _extend_mapping(headers, m)


def _pick_mapping(headers: list[str]) -> dict[str, int]:
    by_pos = _layout_by_position(headers)
    if by_pos is not None:
        return _extend_mapping(headers, by_pos)
    return _fuzzy_mapping(headers)


def parse_sales_excel(file_bytes: bytes) -> list[dict[str, Any]]:
    bio = BytesIO(file_bytes)
    wb = load_workbook(bio, read_only=True, data_only=True)
    try:
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        try:
            header_row = next(rows)
        except StopIteration:
            return []
        headers = [_cell_str(c) for c in header_row]
        colmap = _pick_mapping(headers)
        out: list[dict[str, Any]] = []
        for row in rows:
            raw_vals = list(row)
            while len(raw_vals) < len(headers):
                raw_vals.append(None)
            vals = raw_vals[: len(headers)]
            extras: dict[str, str] = {}
            picked: dict[str, str] = {}
            for key, idx in colmap.items():
                if idx < len(vals):
                    picked[key] = _cell_str(vals[idx])
            used_indices = set(colmap.values())
            for j, h in enumerate(headers):
                if j >= len(vals):
                    continue
                if j in used_indices:
                    continue
                hh = _cell_str(h)
                if hh:
                    extras[hh] = _cell_str(vals[j])
            org_name = picked.get("org_name", "").strip()
            if not org_name:
                col0 = _cell_str(vals[0]) if vals else ""
                if col0:
                    org_name = col0
                else:
                    continue
            out.append(
                {
                    "org_name": org_name[:512],
                    "lpr_name": _opt_str(picked.get("lpr_name")),
                    "lpr_phone": _opt_str(picked.get("lpr_phone")),
                    "org_phone": _opt_str(picked.get("org_phone")),
                    "org_mobile": _opt_str(picked.get("org_mobile")),
                    "import_status": _opt_str(picked.get("import_status")),
                    "email": _opt_str(picked.get("email")),
                    "website": _opt_str(picked.get("website")),
                    "extras": extras,
                }
            )
        return out
    finally:
        wb.close()


def extras_to_json(extras: dict[str, str]) -> str | None:
    if not extras:
        return None
    return json.dumps({"import_columns": extras}, ensure_ascii=False)
