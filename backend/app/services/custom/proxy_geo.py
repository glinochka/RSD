"""Country / region matching for UBT proxy assignment."""
from __future__ import annotations

import math
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

# Approximate country centroids (capital / geographic middle) for nearest-proxy ranking.
_COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "AD": (42.51, 1.52), "AE": (24.45, 54.38), "AF": (34.53, 69.17), "AL": (41.33, 19.82),
    "AM": (40.18, 44.51), "AO": (-8.84, 13.23), "AR": (-34.60, -58.38), "AT": (48.21, 16.37),
    "AU": (-35.28, 149.13), "AZ": (40.41, 49.87), "BA": (43.86, 18.41), "BD": (23.81, 90.41),
    "BE": (50.85, 4.35), "BG": (42.70, 23.32), "BH": (26.23, 50.59), "BO": (-16.50, -68.15),
    "BR": (-15.79, -47.88), "BY": (53.90, 27.57), "CA": (45.42, -75.70), "CH": (46.95, 7.45),
    "CI": (6.83, -5.27), "CL": (-33.45, -70.67), "CM": (3.87, 11.52), "CN": (39.90, 116.41),
    "CO": (4.71, -74.07), "CR": (9.93, -84.09), "CU": (23.11, -82.37), "CY": (35.19, 33.38),
    "CZ": (50.08, 14.44), "DE": (52.52, 13.41), "DK": (55.68, 12.57), "DO": (18.49, -69.93),
    "DZ": (36.75, 3.06), "EC": (-0.18, -78.47), "EE": (59.44, 24.75), "EG": (30.04, 31.24),
    "ES": (40.42, -3.70), "ET": (9.03, 38.74), "FI": (60.17, 24.94), "FJ": (-18.14, 178.44),
    "FR": (48.86, 2.35), "GB": (51.51, -0.13), "GE": (41.72, 44.78), "GH": (5.56, -0.20),
    "GR": (37.98, 23.73), "GT": (14.63, -90.51), "GY": (6.80, -58.16), "HK": (22.32, 114.17),
    "HN": (14.07, -87.19), "HR": (45.81, 15.98), "HT": (18.54, -72.34), "HU": (47.50, 19.04),
    "ID": (-6.21, 106.85), "IE": (53.35, -6.26), "IL": (31.77, 35.21), "IN": (28.61, 77.21),
    "IQ": (33.32, 44.37), "IR": (35.69, 51.39), "IS": (64.15, -21.94), "IT": (41.90, 12.50),
    "JM": (18.02, -76.79), "JO": (31.95, 35.93), "JP": (35.68, 139.69), "KE": (-1.29, 36.82),
    "KG": (42.87, 74.59), "KH": (11.56, 104.93), "KR": (37.57, 126.98), "KW": (29.38, 47.99),
    "KZ": (51.17, 71.43), "LA": (17.98, 102.63), "LB": (33.89, 35.50), "LI": (47.14, 9.52),
    "LK": (6.93, 79.85), "LT": (54.69, 25.28), "LU": (49.61, 6.13), "LV": (56.95, 24.11),
    "LY": (32.89, 13.19), "MA": (34.02, -6.84), "MC": (43.74, 7.42), "MD": (47.01, 28.86),
    "ME": (42.44, 19.26), "MK": (41.99, 21.43), "MM": (19.76, 96.08), "MN": (47.92, 106.92),
    "MT": (35.90, 14.51), "MX": (19.43, -99.13), "MY": (3.14, 101.69), "NG": (9.08, 7.40),
    "NI": (12.14, -86.25), "NL": (52.37, 4.90), "NO": (59.91, 10.75), "NP": (27.72, 85.32),
    "NZ": (-41.29, 174.78), "OM": (23.59, 58.38), "PA": (8.98, -79.52), "PE": (-12.05, -77.04),
    "PG": (-9.44, 147.18), "PH": (14.60, 120.98), "PK": (33.68, 73.04), "PL": (52.23, 21.01),
    "PR": (18.47, -66.11), "PS": (31.90, 35.20), "PT": (38.72, -9.14), "PY": (-25.26, -57.58),
    "QA": (25.29, 51.53), "RO": (44.43, 26.10), "RS": (44.82, 20.46), "RU": (55.76, 37.62),
    "SA": (24.71, 46.68), "SE": (59.33, 18.07), "SG": (1.35, 103.82), "SI": (46.05, 14.51),
    "SK": (48.15, 17.11), "SM": (43.94, 12.45), "SN": (14.69, -17.45), "SR": (5.85, -55.20),
    "SV": (13.69, -89.19), "SY": (33.51, 36.29), "TH": (13.76, 100.50), "TJ": (38.56, 68.77),
    "TM": (37.95, 58.38), "TN": (36.81, 10.18), "TR": (39.93, 32.86), "TT": (10.66, -61.51),
    "TW": (25.03, 121.57), "TZ": (-6.16, 35.75), "UA": (50.45, 30.52), "UG": (0.35, 32.58),
    "UK": (51.51, -0.13), "US": (38.91, -77.04), "UY": (-34.90, -56.19), "UZ": (41.30, 69.24),
    "VA": (41.90, 12.45), "VE": (10.48, -66.90), "VN": (21.03, 105.85), "XK": (42.66, 21.17),
    "YE": (15.37, 44.19), "ZA": (-25.75, 28.19), "ZW": (-17.83, 31.05),
}

# Same country → nearby (FI for RU) → rest of the same region → untagged → other regions.
_NEARBY_KM = 2500.0
_FIT_SAME = 0
_FIT_NEAR = 1
_FIT_REGION = 2
_FIT_UNKNOWN_PROXY = 3
_FIT_OTHER = 4
_FIT_UNKNOWN_ACCOUNT = 5

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


def _iso_country(code: str | None) -> str | None:
    text = (code or "").strip().upper()
    if not text:
        return None
    if text == "UK":
        text = "GB"
    return text


def region_for_country(code: str | None) -> str | None:
    key = _iso_country(code)
    if not key:
        return None
    return COUNTRY_REGION.get(key)


def country_from_phone(raw: Any) -> str | None:
    digits = re.sub(r"\D+", "", str(raw or ""))
    if digits.startswith("00"):
        digits = digits[2:]
    # Domestic 8XXXXXXXXXX used in RU/KZ. Mobiles 89… stay RU; 76/77 prefixes still win as KZ.
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
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


def geo_distance_km(account_country: str | None, proxy_country: str | None) -> float | None:
    left = _COUNTRY_CENTROIDS.get(_iso_country(account_country) or "")
    right = _COUNTRY_CENTROIDS.get(_iso_country(proxy_country) or "")
    if not left or not right:
        return None
    lat1, lon1 = (math.radians(left[0]), math.radians(left[1]))
    lat2, lon2 = (math.radians(right[0]), math.radians(right[1]))
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    hav = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(hav)))


def proxy_fit_key(account_country: str | None, proxy_country: str | None) -> tuple[int, int]:
    """Sort key: lower is closer. Distance km is the tie-breaker inside a rank."""
    want = _iso_country(account_country)
    have = _iso_country(proxy_country)
    if not want:
        return (_FIT_UNKNOWN_ACCOUNT, 0)
    if not have:
        return (_FIT_UNKNOWN_PROXY, 50_000)
    if want == have:
        return (_FIT_SAME, 0)
    distance = geo_distance_km(want, have)
    distance_km = int(distance) if distance is not None else 30_000
    if distance is not None and distance <= _NEARBY_KM:
        return (_FIT_NEAR, distance_km)
    want_region = region_for_country(want)
    have_region = region_for_country(have)
    if want_region and have_region and want_region == have_region:
        return (_FIT_REGION, distance_km)
    return (_FIT_OTHER, distance_km)


def proxy_fit_score(account_country: str | None, proxy_country: str | None) -> int:
    """Lower is better: same country, nearby/same region, unknown proxy, other region."""
    rank, _distance = proxy_fit_key(account_country, proxy_country)
    if rank == _FIT_SAME:
        return 0
    if rank in {_FIT_NEAR, _FIT_REGION}:
        return 1
    if rank in {_FIT_UNKNOWN_PROXY, _FIT_UNKNOWN_ACCOUNT}:
        return 2
    return 3
