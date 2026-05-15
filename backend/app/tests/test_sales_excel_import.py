from pathlib import Path

from app.services.sales_excel_import import PHONE_FIELD_MAX_LEN, _fit_phone, parse_sales_excel

_ROOT = Path(__file__).resolve().parents[3]
_YAMAP_XLSX = _ROOT / "yamap_with_lpr_prioritized.xlsx"


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
