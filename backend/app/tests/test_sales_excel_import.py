from pathlib import Path

from app.services.sales_excel_import import (
    EMAIL_FIELD_MAX_LEN,
    PHONE_FIELD_MAX_LEN,
    _fit_email,
    _fit_phone,
    _normalize_whatsapp_import_value,
    parse_sales_excel,
)

_ROOT = Path(__file__).resolve().parents[3]
_YAMAP_XLSX = _ROOT / "yamap_with_lpr_prioritized.xlsx"
_YAMAP_2GIS = _ROOT / "yamap (3).xlsx"


def test_normalize_whatsapp_import_value_fixes_erroneous_leading_one() -> None:
    assert _normalize_whatsapp_import_value("https://wa.me/179395030304") == "https://wa.me/79395030304"
    assert _normalize_whatsapp_import_value("+7 939 503-03-04") == "https://wa.me/79395030304"
    assert _normalize_whatsapp_import_value("8 (939) 503-03-04") == "https://wa.me/79395030304"
    assert _normalize_whatsapp_import_value("9395030304") == "https://wa.me/79395030304"


def test_fit_phone_truncates_beyond_limit() -> None:
    long_value = "+" + "7" * (PHONE_FIELD_MAX_LEN + 10)
    assert len(_fit_phone(long_value) or "") == PHONE_FIELD_MAX_LEN


def test_fit_email_takes_first_from_comma_list() -> None:
    raw = "a@x.com, b@y.com, c@z.com"
    assert _fit_email(raw) == "a@x.com"


def test_fit_email_fits_db_column() -> None:
    assert len(_fit_email("a" * 300 + "@x.com") or "") <= EMAIL_FIELD_MAX_LEN


def test_parse_yamap_2gis_email_fits_db_columns() -> None:
    if not _YAMAP_2GIS.is_file():
        return
    rows = parse_sales_excel(_YAMAP_2GIS.read_bytes())
    assert len(rows) > 0
    for row in rows:
        email = row.get("email")
        if email:
            assert len(email) <= EMAIL_FIELD_MAX_LEN, email[:80]


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


def test_parse_yamap_headers_layout() -> None:
    from app.services.sales_excel_import import _layout_yandex_maps

    headers = [
        "ID",
        "Название",
        "Регион",
        "Город",
        "Адрес",
        "Индекс",
        "Телефон",
        "Мобильный телефон",
        "Email",
        "Сайт",
        "Рубрика",
        "Подрубрика",
        "Время работы",
        "Способы оплаты",
        "whatsapp",
        "telegram",
    ]
    mapping = _layout_yandex_maps(headers)
    assert mapping is not None
    assert mapping["org_name"] == 1
    assert mapping["category_rubric"] == 10
    assert mapping["email"] == 8
    assert mapping["whatsapp"] == 14
    assert mapping["telegram"] == 15


def test_parse_yamap_file_when_present() -> None:
    path = _ROOT / "yamap.xlsx"
    if not path.is_file():
        return
    rows = parse_sales_excel(path.read_bytes())
    assert len(rows) > 0
    sample = rows[0]
    assert sample.get("org_name")
    extras = sample.get("extras") or {}
    assert extras.get("rubric") or sample.get("category_rubric")
    assert sample.get("org_phone") or sample.get("org_mobile")


def test_collect_all_messenger_channels_returns_both() -> None:
    from app.services.sales.contact_target_resolver import collect_all_messenger_channels

    row = {
        "whatsapp": "https://wa.me/79395030304",
        "telegram": "https://t.me/user",
        "lpr_phone": "+79395030304",
    }
    channels = collect_all_messenger_channels(row, whatsapp_available=True, telegram_available=True)
    assert len(channels) == 2
    assert channels[0][0] == "whatsapp_userbot"
    assert channels[1][0] == "telegram_userbot"


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
