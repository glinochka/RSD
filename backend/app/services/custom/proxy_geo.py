"""Country / region matching for UBT proxy assignment."""
from __future__ import annotations

import re
from typing import Any

REGION_EUROPE = "europe"
REGION_NA = "na"
REGION_SA = "sa"
REGION_AFRICA = "africa"
REGION_ASIA = "asia"
REGIONS = (REGION_EUROPE, REGION_NA, REGION_SA, REGION_AFRICA, REGION_ASIA)

# ISO-3166 alpha-2 → region. Oceania is grouped with Asia for matching.
COUNTRY_REGION: dict[str, str] = {
    "AD": REGION_EUROPE, "AL": REGION_EUROPE, "AT": REGION_EUROPE, "BA": REGION_EUROPE,
    "BE": REGION_EUROPE, "BG": REGION_EUROPE, "BY": REGION_EUROPE, "CH": REGION_EUROPE,
    "CY": REGION_EUROPE, "CZ": REGION_EUROPE, "DE": REGION_EUROPE, "DK": REGION_EUROPE,
    "EE": REGION_EUROPE, "ES": REGION_EUROPE, "FI": REGION_EUROPE, "FR": REGION_EUROPE,
    "GB": REGION_EUROPE, "UK": REGION_EUROPE, "GR": REGION_EUROPE, "HR": REGION_EUROPE,
    "HU": REGION_EUROPE, "IE": REGION_EUROPE, "IS": REGION_EUROPE, "IT": REGION_EUROPE,
    "LI": REGION_EUROPE, "LT": REGION_EUROPE, "LU": REGION_EUROPE, "LV": REGION_EUROPE,
    "MC": REGION_EUROPE, "MD": REGION_EUROPE, "ME": REGION_EUROPE, "MK": REGION_EUROPE,
    "MT": REGION_EUROPE, "NL": REGION_EUROPE, "NO": REGION_EUROPE, "PL": REGION_EUROPE,
    "PT": REGION_EUROPE, "RO": REGION_EUROPE, "RS": REGION_EUROPE, "RU": REGION_EUROPE,
    "SE": REGION_EUROPE, "SI": REGION_EUROPE, "SK": REGION_EUROPE, "SM": REGION_EUROPE,
    "UA": REGION_EUROPE, "VA": REGION_EUROPE, "XK": REGION_EUROPE,
    "CA": REGION_NA, "MX": REGION_NA, "US": REGION_NA, "PR": REGION_NA, "GT": REGION_NA,
    "HN": REGION_NA, "SV": REGION_NA, "NI": REGION_NA, "CR": REGION_NA, "PA": REGION_NA,
    "CU": REGION_NA, "DO": REGION_NA, "HT": REGION_NA, "JM": REGION_NA, "TT": REGION_NA,
    "AR": REGION_SA, "BO": REGION_SA, "BR": REGION_SA, "CL": REGION_SA, "CO": REGION_SA,
    "EC": REGION_SA, "GY": REGION_SA, "PE": REGION_SA, "PY": REGION_SA, "SR": REGION_SA,
    "UY": REGION_SA, "VE": REGION_SA,
    "DZ": REGION_AFRICA, "AO": REGION_AFRICA, "EG": REGION_AFRICA, "ET": REGION_AFRICA,
    "GH": REGION_AFRICA, "KE": REGION_AFRICA, "MA": REGION_AFRICA, "NG": REGION_AFRICA,
    "SN": REGION_AFRICA, "TN": REGION_AFRICA, "TZ": REGION_AFRICA, "UG": REGION_AFRICA,
    "ZA": REGION_AFRICA, "ZW": REGION_AFRICA, "CI": REGION_AFRICA, "CM": REGION_AFRICA,
    "AE": REGION_ASIA, "AF": REGION_ASIA, "AM": REGION_ASIA, "AZ": REGION_ASIA,
    "BD": REGION_ASIA, "BH": REGION_ASIA, "CN": REGION_ASIA, "GE": REGION_ASIA,
    "HK": REGION_ASIA, "ID": REGION_ASIA, "IL": REGION_ASIA, "IN": REGION_ASIA,
    "IQ": REGION_ASIA, "IR": REGION_ASIA, "JO": REGION_ASIA, "JP": REGION_ASIA,
    "KG": REGION_ASIA, "KH": REGION_ASIA, "KR": REGION_ASIA, "KW": REGION_ASIA,
    "KZ": REGION_ASIA, "LA": REGION_ASIA, "LB": REGION_ASIA, "LK": REGION_ASIA,
    "MM": REGION_ASIA, "MN": REGION_ASIA, "MY": REGION_ASIA, "NP": REGION_ASIA,
    "OM": REGION_ASIA, "PH": REGION_ASIA, "PK": REGION_ASIA, "QA": REGION_ASIA,
    "SA": REGION_ASIA, "SG": REGION_ASIA, "SY": REGION_ASIA, "TH": REGION_ASIA,
    "TJ": REGION_ASIA, "TM": REGION_ASIA, "TR": REGION_ASIA, "TW": REGION_ASIA,
    "UZ": REGION_ASIA, "VN": REGION_ASIA, "YE": REGION_ASIA,
    "AU": REGION_ASIA, "NZ": REGION_ASIA, "PG": REGION_ASIA, "FJ": REGION_ASIA,
}

_NAME_TO_ISO: dict[str, str] = {
    "finland": "FI", "финляндия": "FI", "suomi": "FI",
    "germany": "DE", "deutschland": "DE", "германия": "DE",
    "netherlands": "NL", "holland": "NL", "нидерланды": "NL", "голландия": "NL",
    "france": "FR", "франция": "FR",
    "spain": "ES", "испания": "ES",
    "italy": "IT", "италия": "IT",
    "poland": "PL", "польша": "PL",
    "sweden": "SE", "швеция": "SE",
    "norway": "NO", "норвегия": "NO",
    "denmark": "DK", "дания": "DK",
    "belgium": "BE", "бельгия": "BE",
    "austria": "AT", "австрия": "AT",
    "switzerland": "CH", "швейцария": "CH",
    "czech": "CZ", "czechia": "CZ", "чехия": "CZ",
    "romania": "RO", "румыния": "RO",
    "hungary": "HU", "венгрия": "HU",
    "portugal": "PT", "португалия": "PT",
    "greece": "GR", "греция": "GR",
    "ireland": "IE", "ирландия": "IE",
    "uk": "GB", "unitedkingdom": "GB", "britain": "GB", "england": "GB",
    "великобритания": "GB", "англия": "GB",
    "ukraine": "UA", "украина": "UA",
    "belarus": "BY", "беларусь": "BY", "белоруссия": "BY",
    "russia": "RU", "россия": "RU",
    "usa": "US", "unitedstates": "US", "america": "US", "сша": "US", "америка": "US",
    "canada": "CA", "канада": "CA",
    "mexico": "MX", "мексика": "MX",
    "brazil": "BR", "бразилия": "BR",
    "argentina": "AR", "аргентина": "AR",
    "chile": "CL", "чили": "CL",
    "colombia": "CO", "колумбия": "CO",
    "peru": "PE", "перу": "PE",
    "southafrica": "ZA", "юар": "ZA",
    "egypt": "EG", "египет": "EG",
    "nigeria": "NG", "нигерия": "NG",
    "kenya": "KE", "кения": "KE",
    "morocco": "MA", "марокко": "MA",
    "uae": "AE", "emirates": "AE", "оаэ": "AE", "дубай": "AE", "dubai": "AE",
    "turkey": "TR", "türkiye": "TR", "турция": "TR",
    "israel": "IL", "израиль": "IL",
    "saudi": "SA", "saudiarabia": "SA", "саудовскаяаравия": "SA",
    "india": "IN", "индия": "IN",
    "china": "CN", "китай": "CN",
    "hongkong": "HK", "гонконг": "HK",
    "taiwan": "TW", "тайвань": "TW",
    "japan": "JP", "япония": "JP",
    "korea": "KR", "southkorea": "KR", "корея": "KR",
    "singapore": "SG", "сингапур": "SG",
    "indonesia": "ID", "индонезия": "ID",
    "thailand": "TH", "таиланд": "TH", "тайланд": "TH",
    "vietnam": "VN", "вьетнам": "VN",
    "malaysia": "MY", "малайзия": "MY",
    "philippines": "PH", "филиппины": "PH",
    "kazakhstan": "KZ", "казахстан": "KZ",
    "uzbekistan": "UZ", "узбекистан": "UZ",
    "azerbaijan": "AZ", "азербайджан": "AZ",
    "armenia": "AM", "армения": "AM",
    "georgia": "GE", "грузия": "GE",
    "australia": "AU", "австралия": "AU",
    "newzealand": "NZ", "новаязеландия": "NZ",
    "europe": "DE", "европа": "DE",
}

# Longest prefix first. NANP (+1) maps to US — both US and CA are region NA.
_CALLING_CODES: tuple[tuple[str, str], ...] = (
    ("1242", "BS"), ("1246", "BB"), ("1264", "AI"), ("1268", "AG"), ("1284", "VG"),
    ("1340", "VI"), ("1345", "KY"), ("1441", "BM"), ("1473", "GD"), ("1649", "TC"),
    ("1664", "MS"), ("1670", "MP"), ("1671", "GU"), ("1684", "AS"), ("1758", "LC"),
    ("1767", "DM"), ("1784", "VC"), ("1787", "PR"), ("1809", "DO"), ("1829", "DO"),
    ("1849", "DO"), ("1868", "TT"), ("1869", "KN"), ("1876", "JM"), ("1939", "PR"),
    ("1204", "CA"), ("1236", "CA"), ("1249", "CA"), ("1250", "CA"), ("1289", "CA"),
    ("1306", "CA"), ("1343", "CA"), ("1365", "CA"), ("1403", "CA"), ("1416", "CA"),
    ("1418", "CA"), ("1431", "CA"), ("1437", "CA"), ("1438", "CA"), ("1450", "CA"),
    ("1506", "CA"), ("1514", "CA"), ("1519", "CA"), ("1548", "CA"), ("1579", "CA"),
    ("1581", "CA"), ("1587", "CA"), ("1604", "CA"), ("1613", "CA"), ("1639", "CA"),
    ("1647", "CA"), ("1672", "CA"), ("1705", "CA"), ("1709", "CA"), ("1742", "CA"),
    ("1778", "CA"), ("1780", "CA"), ("1807", "CA"), ("1819", "CA"), ("1825", "CA"),
    ("1867", "CA"), ("1873", "CA"), ("1902", "CA"), ("1905", "CA"),
    ("77", "KZ"), ("76", "KZ"),
    ("20", "EG"), ("27", "ZA"), ("30", "GR"), ("31", "NL"), ("32", "BE"), ("33", "FR"),
    ("34", "ES"), ("36", "HU"), ("39", "IT"), ("40", "RO"), ("41", "CH"), ("43", "AT"),
    ("44", "GB"), ("45", "DK"), ("46", "SE"), ("47", "NO"), ("48", "PL"), ("49", "DE"),
    ("51", "PE"), ("52", "MX"), ("53", "CU"), ("54", "AR"), ("55", "BR"), ("56", "CL"),
    ("57", "CO"), ("58", "VE"), ("60", "MY"), ("61", "AU"), ("62", "ID"), ("63", "PH"),
    ("64", "NZ"), ("65", "SG"), ("66", "TH"), ("81", "JP"), ("82", "KR"), ("84", "VN"),
    ("86", "CN"), ("90", "TR"), ("91", "IN"), ("92", "PK"), ("93", "AF"), ("94", "LK"),
    ("95", "MM"), ("98", "IR"),
    ("212", "MA"), ("213", "DZ"), ("216", "TN"), ("218", "LY"), ("220", "GM"),
    ("221", "SN"), ("233", "GH"), ("234", "NG"), ("254", "KE"), ("255", "TZ"),
    ("256", "UG"), ("258", "MZ"), ("260", "ZM"), ("263", "ZW"), ("351", "PT"),
    ("352", "LU"), ("353", "IE"), ("354", "IS"), ("358", "FI"), ("359", "BG"),
    ("370", "LT"), ("371", "LV"), ("372", "EE"), ("373", "MD"), ("374", "AM"),
    ("375", "BY"), ("376", "AD"), ("380", "UA"), ("381", "RS"), ("382", "ME"),
    ("385", "HR"), ("386", "SI"), ("387", "BA"), ("389", "MK"), ("420", "CZ"),
    ("421", "SK"), ("423", "LI"), ("852", "HK"), ("853", "MO"), ("855", "KH"),
    ("856", "LA"), ("880", "BD"), ("886", "TW"), ("960", "MV"), ("961", "LB"),
    ("962", "JO"), ("963", "SY"), ("964", "IQ"), ("965", "KW"), ("966", "SA"),
    ("967", "YE"), ("968", "OM"), ("970", "PS"), ("971", "AE"), ("972", "IL"),
    ("973", "BH"), ("974", "QA"), ("975", "BT"), ("976", "MN"), ("977", "NP"),
    ("992", "TJ"), ("993", "TM"), ("994", "AZ"), ("995", "GE"), ("996", "KG"),
    ("998", "UZ"),
    ("1", "US"), ("7", "RU"),
)

_CALLING_CODES = tuple(sorted(_CALLING_CODES, key=lambda item: len(item[0]), reverse=True))

_ISO_RE = re.compile(r"^[A-Z]{2}$")
_TAIL_RE = re.compile(
    r"[\s,;]+(?:#|country[=:]?\s*)?([A-Za-zА-Яа-яЁё]{2,32})\s*$",
    re.IGNORECASE,
)


def normalize_country(raw: Any) -> str | None:
    text = " ".join(str(raw or "").strip().split())
    if not text:
        return None
    compact = re.sub(r"[^A-Za-zА-Яа-яЁё]", "", text).casefold()
    if len(text) == 2 and _ISO_RE.match(text.upper()):
        code = text.upper()
        if code == "UK":
            code = "GB"
        return code if code in COUNTRY_REGION or code == "GB" else None
    return _NAME_TO_ISO.get(compact)


def region_for_country(code: str | None) -> str | None:
    if not code:
        return None
    key = "GB" if code.upper() == "UK" else code.upper()
    return COUNTRY_REGION.get(key)


def country_from_phone(raw: Any) -> str | None:
    digits = re.sub(r"\D+", "", str(raw or ""))
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits:
        return None
    for prefix, iso in _CALLING_CODES:
        if digits.startswith(prefix):
            return iso
    return None


def split_country_tail(line: str) -> tuple[str, str | None]:
    match = _TAIL_RE.search(line or "")
    if not match:
        return (line or "").strip(), None
    code = normalize_country(match.group(1))
    if not code:
        return (line or "").strip(), None
    return (line or "")[: match.start()].strip(), code


def proxy_fit_score(account_country: str | None, proxy_country: str | None) -> int:
    """Lower is better: same country, same region, unknown proxy, other region."""
    want = (account_country or "").upper() or None
    have = (proxy_country or "").upper() or None
    if have == "UK":
        have = "GB"
    if want == "UK":
        want = "GB"
    want_region = region_for_country(want)
    have_region = region_for_country(have)
    if want and have and want == have:
        return 0
    if want_region and have_region and want_region == have_region:
        return 1
    if not have:
        return 2
    return 3
