from pathlib import Path

from app.services.sales_excel_import import (
    PHONE_FIELD_MAX_LEN,
    _fit_phone,
    _normalize_whatsapp_import_value,
    parse_sales_excel,
)

_ROOT = Path(__file__).resolve().parents[3]
_YAMAP_XLSX = _ROOT / "yamap_with_lpr_prioritized.xlsx"


def test_normalize_whatsapp_import_value_fixes_erroneous_leading_one() -> None:
    assert _normalize_whatsapp_import_value("https://wa.me/179395030304") == "https://wa.me/79395030304"
    assert _normalize_whatsapp_import_value("+7 939 503-03-04") == "https://wa.me/79395030304"
    assert _normalize_whatsapp_import_value("8 (939) 503-03-04") == "https://wa.me/79395030304"
    assert _normalize_whatsapp_import_value("9395030304") == "https://wa.me/79395030304"


def test_fit_phone_truncates_beyond_limit() -> None:
    long_value = "+" + "7" * (PHONE_FIELD_MAX_LEN + 10)
    assert len(_fit_phone(long_value) or "") == PHONE_FIELD_MAX_LEN


def test_parse_yamap_phones_fit_db_columns() -> None:
    if not _YAMAP_XLSX.is_file():
        return
    rows = parse_sales_excel(_YAMAP_XLSX.read_bytes())
    assert len(rows) > 0
    for row in rows:
        for key in ("lpr_phone", "org_phone", "org_mobile"):
            value = row.get(key)
            if value:
                assert len(value) <= PHONE_FIELD_MAX_LEN, key


def test_parse_yamap_messenger_columns() -> None:
    if not _YAMAP_XLSX.is_file():
        return
    rows = parse_sales_excel(_YAMAP_XLSX.read_bytes())
    assert len(rows) > 0
    with_messengers = [
        r for r in rows if r.get("whatsapp") or r.get("telegram")
    ]
    assert with_messengers, "expected whatsapp/telegram in yamap fixture"
    sample = next(r["whatsapp"] for r in rows if r.get("whatsapp"))
    assert sample.startswith("https://wa.me/7"), sample
    assert "/17" not in sample.split("wa.me/", 1)[-1][:3]
