"""Telegram userbot auth: QR + 2FA, phone code, session file (opentele/Telethon)."""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import random
import shutil
import tempfile
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import settings

logger = logging.getLogger(__name__)

# Official public client keys (opentele API.TelegramDesktop / Android / iOS).
_TELEGRAM_DESKTOP_API_ID = 2040
_TELEGRAM_DESKTOP_API_HASH = "b18441a1ff607e10a989891a5462e627"
_TELEGRAM_ANDROID_API_ID = 6
_TELEGRAM_ANDROID_API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"
_TELEGRAM_IOS_API_ID = 8
_TELEGRAM_IOS_API_HASH = "7245de8e747a0d6fbe11b8ca67533405"

QR_WAIT_TIMEOUT_SECONDS = 180
_QR_TTL_SECONDS = 600
DEVICE_MODEL_MAIN = "RSD Platform"
DEVICE_MODEL_SPARE = "RSD Spare"
_LEGACY_DEVICE_MODELS = frozenset({DEVICE_MODEL_MAIN, DEVICE_MODEL_SPARE})

FAMILY_DESKTOP = "desktop"
FAMILY_ANDROID = "android"
FAMILY_IOS = "ios"
_FAMILY_WEIGHTS = (FAMILY_DESKTOP, FAMILY_ANDROID, FAMILY_IOS)
_FAMILY_WEIGHT_VALUES = (40, 35, 25)

# Realistic Telegram fingerprints. "RSD Platform" is a farm tell.
# device_model + api_id family must match: iPhone never rides Desktop api 2040.
# Locale is NOT stored here — it comes from the phone country at mint/normalize time.
_DEVICE_PROFILES: tuple[dict[str, str], ...] = (
    {"family": FAMILY_DESKTOP, "device_model": "PC 64bit", "system_version": "Windows 10", "app_version": "4.16.8 x64"},
    {"family": FAMILY_DESKTOP, "device_model": "Desktop", "system_version": "Windows 10", "app_version": "4.16.30 x64"},
    {"family": FAMILY_DESKTOP, "device_model": "PC 64bit", "system_version": "Windows 11", "app_version": "5.4.1 x64"},
    {"family": FAMILY_DESKTOP, "device_model": "Desktop", "system_version": "Windows 11", "app_version": "5.7.3 x64"},
    {"family": FAMILY_DESKTOP, "device_model": "PC 64bit", "system_version": "Windows 10", "app_version": "5.3.0 x64"},
    {"family": FAMILY_DESKTOP, "device_model": "Laptop", "system_version": "Windows 11", "app_version": "5.6.1 x64"},
    {"family": FAMILY_DESKTOP, "device_model": "Desktop", "system_version": "Windows 10", "app_version": "5.8.2 x64"},
    {"family": FAMILY_DESKTOP, "device_model": "PC 64bit", "system_version": "Windows 11", "app_version": "4.14.13 x64"},
    {"family": FAMILY_DESKTOP, "device_model": "Laptop", "system_version": "Windows 10", "app_version": "5.5.5 x64"},
    {"family": FAMILY_DESKTOP, "device_model": "Desktop", "system_version": "Windows 11", "app_version": "5.9.0 x64"},
    {"family": FAMILY_DESKTOP, "device_model": "PC 64bit", "system_version": "macOS 14.5", "app_version": "5.6.3 x64"},
    {"family": FAMILY_DESKTOP, "device_model": "MacBook Pro", "system_version": "macOS 15.0", "app_version": "5.8.1 x64"},
    {"family": FAMILY_ANDROID, "device_model": "Samsung SM-S941B", "system_version": "SDK 36", "app_version": "11.14.1"},
    {"family": FAMILY_ANDROID, "device_model": "Samsung SM-S946B", "system_version": "SDK 36", "app_version": "11.13.2"},
    {"family": FAMILY_ANDROID, "device_model": "Samsung SM-S938B", "system_version": "SDK 35", "app_version": "11.12.0"},
    {"family": FAMILY_ANDROID, "device_model": "Samsung SM-S936B", "system_version": "SDK 35", "app_version": "11.11.4"},
    {"family": FAMILY_ANDROID, "device_model": "Google Pixel 9", "system_version": "SDK 35", "app_version": "11.12.3"},
    {"family": FAMILY_ANDROID, "device_model": "Google Pixel 10", "system_version": "SDK 36", "app_version": "11.14.0"},
    {"family": FAMILY_ANDROID, "device_model": "Xiaomi 15", "system_version": "SDK 35", "app_version": "11.11.1"},
    {"family": FAMILY_ANDROID, "device_model": "POCO F7", "system_version": "SDK 35", "app_version": "11.10.2"},
    {"family": FAMILY_IOS, "device_model": "iPhone 16", "system_version": "18.5", "app_version": "11.12.1"},
    {"family": FAMILY_IOS, "device_model": "iPhone 16 Pro", "system_version": "18.6.2", "app_version": "11.13.0"},
    {"family": FAMILY_IOS, "device_model": "iPhone 16 Pro Max", "system_version": "18.6.1", "app_version": "11.14.1"},
    {"family": FAMILY_IOS, "device_model": "iPhone 17", "system_version": "26.0", "app_version": "11.14.0"},
    {"family": FAMILY_IOS, "device_model": "iPhone 17 Pro", "system_version": "26.0.1", "app_version": "11.14.1"},
    {"family": FAMILY_IOS, "device_model": "iPhone 17 Pro Max", "system_version": "26.1", "app_version": "11.14.2"},
)

# Official client lang packs. Empty lang_pack is a Telethon tell.
_LANG_PACK = {
    FAMILY_DESKTOP: "tdesktop",
    FAMILY_ANDROID: "android",
    FAMILY_IOS: "ios",
}
_DEFAULT_LANG = "en"
_DEFAULT_SYSTEM_LANG = "en-US"
_DEFAULT_TZ = "UTC"
# lang_code, system_lang_code, IANA timezone — typical phone locale, not "ru-RU everywhere".
_COUNTRY_LOCALE: dict[str, tuple[str, str, str]] = {
    "RU": ("ru", "ru-RU", "Europe/Moscow"),
    "BY": ("ru", "ru-BY", "Europe/Minsk"),
    "KZ": ("ru", "ru-KZ", "Asia/Almaty"),
    "KG": ("ru", "ru-KG", "Asia/Bishkek"),
    "UZ": ("uz", "uz-UZ", "Asia/Tashkent"),
    "TJ": ("ru", "ru-TJ", "Asia/Dushanbe"),
    "TM": ("ru", "ru-TM", "Asia/Ashgabat"),
    "AM": ("hy", "hy-AM", "Asia/Yerevan"),
    "AZ": ("az", "az-AZ", "Asia/Baku"),
    "GE": ("ka", "ka-GE", "Asia/Tbilisi"),
    "UA": ("uk", "uk-UA", "Europe/Kyiv"),
    "MD": ("ro", "ro-MD", "Europe/Chisinau"),
    "US": ("en", "en-US", "America/New_York"),
    "CA": ("en", "en-CA", "America/Toronto"),
    "GB": ("en", "en-GB", "Europe/London"),
    "IE": ("en", "en-IE", "Europe/Dublin"),
    "AU": ("en", "en-AU", "Australia/Sydney"),
    "NZ": ("en", "en-NZ", "Pacific/Auckland"),
    "SG": ("en", "en-SG", "Asia/Singapore"),
    "IN": ("en", "en-IN", "Asia/Kolkata"),
    "PH": ("en", "en-PH", "Asia/Manila"),
    "NG": ("en", "en-NG", "Africa/Lagos"),
    "ZA": ("en", "en-ZA", "Africa/Johannesburg"),
    "DE": ("de", "de-DE", "Europe/Berlin"),
    "AT": ("de", "de-AT", "Europe/Vienna"),
    "CH": ("de", "de-CH", "Europe/Zurich"),
    "FR": ("fr", "fr-FR", "Europe/Paris"),
    "BE": ("fr", "fr-BE", "Europe/Brussels"),
    "ES": ("es", "es-ES", "Europe/Madrid"),
    "MX": ("es", "es-MX", "America/Mexico_City"),
    "AR": ("es", "es-AR", "America/Argentina/Buenos_Aires"),
    "CO": ("es", "es-CO", "America/Bogota"),
    "CL": ("es", "es-CL", "America/Santiago"),
    "PE": ("es", "es-PE", "America/Lima"),
    "VE": ("es", "es-VE", "America/Caracas"),
    "IT": ("it", "it-IT", "Europe/Rome"),
    "PT": ("pt", "pt-PT", "Europe/Lisbon"),
    "BR": ("pt", "pt-BR", "America/Sao_Paulo"),
    "PL": ("pl", "pl-PL", "Europe/Warsaw"),
    "NL": ("nl", "nl-NL", "Europe/Amsterdam"),
    "TR": ("tr", "tr-TR", "Europe/Istanbul"),
    "RO": ("ro", "ro-RO", "Europe/Bucharest"),
    "HU": ("hu", "hu-HU", "Europe/Budapest"),
    "CZ": ("cs", "cs-CZ", "Europe/Prague"),
    "SK": ("sk", "sk-SK", "Europe/Bratislava"),
    "BG": ("bg", "bg-BG", "Europe/Sofia"),
    "GR": ("el", "el-GR", "Europe/Athens"),
    "RS": ("sr", "sr-RS", "Europe/Belgrade"),
    "HR": ("hr", "hr-HR", "Europe/Zagreb"),
    "SI": ("sl", "sl-SI", "Europe/Ljubljana"),
    "LT": ("lt", "lt-LT", "Europe/Vilnius"),
    "LV": ("lv", "lv-LV", "Europe/Riga"),
    "EE": ("et", "et-EE", "Europe/Tallinn"),
    "FI": ("fi", "fi-FI", "Europe/Helsinki"),
    "SE": ("sv", "sv-SE", "Europe/Stockholm"),
    "NO": ("nb", "nb-NO", "Europe/Oslo"),
    "DK": ("da", "da-DK", "Europe/Copenhagen"),
    "IL": ("he", "he-IL", "Asia/Jerusalem"),
    "AE": ("ar", "ar-AE", "Asia/Dubai"),
    "SA": ("ar", "ar-SA", "Asia/Riyadh"),
    "EG": ("ar", "ar-EG", "Africa/Cairo"),
    "IQ": ("ar", "ar-IQ", "Asia/Baghdad"),
    "JO": ("ar", "ar-JO", "Asia/Amman"),
    "LB": ("ar", "ar-LB", "Asia/Beirut"),
    "KW": ("ar", "ar-KW", "Asia/Kuwait"),
    "QA": ("ar", "ar-QA", "Asia/Qatar"),
    "BH": ("ar", "ar-BH", "Asia/Bahrain"),
    "OM": ("ar", "ar-OM", "Asia/Muscat"),
    "MA": ("ar", "ar-MA", "Africa/Casablanca"),
    "DZ": ("ar", "ar-DZ", "Africa/Algiers"),
    "TN": ("ar", "ar-TN", "Africa/Tunis"),
    "IR": ("fa", "fa-IR", "Asia/Tehran"),
    "CN": ("zh", "zh-CN", "Asia/Shanghai"),
    "TW": ("zh", "zh-TW", "Asia/Taipei"),
    "HK": ("zh", "zh-HK", "Asia/Hong_Kong"),
    "JP": ("ja", "ja-JP", "Asia/Tokyo"),
    "KR": ("ko", "ko-KR", "Asia/Seoul"),
    "VN": ("vi", "vi-VN", "Asia/Ho_Chi_Minh"),
    "TH": ("th", "th-TH", "Asia/Bangkok"),
    "ID": ("id", "id-ID", "Asia/Jakarta"),
    "MY": ("ms", "ms-MY", "Asia/Kuala_Lumpur"),
    "PK": ("ur", "ur-PK", "Asia/Karachi"),
    "BD": ("bn", "bn-BD", "Asia/Dhaka"),
}


def lang_pack_for_family(family: str | None) -> str:
    resolved = normalize_device_family(family) or FAMILY_DESKTOP
    return _LANG_PACK.get(resolved) or _LANG_PACK[FAMILY_DESKTOP]


def locale_for_country(country: str | None) -> tuple[str, str, str]:
    """Return (lang_code, system_lang_code, tz_name) for an ISO country."""
    code = str(country or "").strip().upper()
    if code == "UK":
        code = "GB"
    if code in _COUNTRY_LOCALE:
        return _COUNTRY_LOCALE[code]
    if len(code) == 2 and code.isalpha():
        return (_DEFAULT_LANG, f"{_DEFAULT_LANG}-{code}", _DEFAULT_TZ)
    return (_DEFAULT_LANG, _DEFAULT_SYSTEM_LANG, _DEFAULT_TZ)


def locale_for_phone(phone: Any) -> tuple[str, str, str]:
    from .custom.proxy_geo import country_from_phone

    return locale_for_country(country_from_phone(phone))


def tz_offset_seconds(tz_name: str | None) -> int:
    name = str(tz_name or "").strip() or _DEFAULT_TZ
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        delta = datetime.now(ZoneInfo(name)).utcoffset()
        if delta is None:
            return 0
        return int(delta.total_seconds())
    except Exception:
        return 0


def _looks_like_forced_ru_locale(lang_code: str, system_lang_code: str) -> bool:
    lang = (lang_code or "").strip().lower()
    system = (system_lang_code or "").strip().replace("_", "-")
    return lang in {"", "ru"} and system.lower() in {"", "ru", "ru-ru"}


def _apply_phone_locale(
    data: dict[str, Any],
    family: str,
    *,
    phone: Any = None,
    country: str | None = None,
) -> tuple[str, str, str]:
    """Pick interface language from the SIM country, not a hardcoded ru-RU."""
    if country:
        wanted_lang, wanted_system, tz_name = locale_for_country(country)
    elif phone:
        wanted_lang, wanted_system, tz_name = locale_for_phone(phone)
    else:
        stored_tz = str(data.get("tz_name") or "").strip()
        stored_lang = str(data.get("lang_code") or "").strip()
        stored_system = str(data.get("system_lang_code") or "").strip()
        if stored_lang and stored_system:
            return stored_lang, stored_system, stored_tz or _DEFAULT_TZ
        return _DEFAULT_LANG, _DEFAULT_SYSTEM_LANG, stored_tz or _DEFAULT_TZ

    stored_lang = str(data.get("lang_code") or "").strip()
    stored_system = str(data.get("system_lang_code") or "").strip()
    stored_tz = str(data.get("tz_name") or "").strip()
    if stored_lang and stored_system and not _looks_like_forced_ru_locale(stored_lang, stored_system):
        return stored_lang, stored_system, stored_tz or tz_name
    if (
        stored_lang
        and stored_system
        and _looks_like_forced_ru_locale(stored_lang, stored_system)
        and wanted_lang == "ru"
        and wanted_system.lower() == "ru-ru"
    ):
        return "ru", "ru-RU", stored_tz or tz_name
    return wanted_lang, wanted_system, tz_name


def normalize_device_family(value: Any) -> str | None:
    name = str(value or "").strip().lower()
    if name in {FAMILY_DESKTOP, FAMILY_ANDROID, FAMILY_IOS}:
        return name
    if name in {"macos", "mac", "windows", "linux", "tdesktop"}:
        return FAMILY_DESKTOP
    return None


def family_for_api_id(api_id: int | None) -> str | None:
    try:
        value = int(api_id or 0)
    except (TypeError, ValueError):
        return None
    if value == _TELEGRAM_ANDROID_API_ID:
        return FAMILY_ANDROID
    if value == _TELEGRAM_IOS_API_ID:
        return FAMILY_IOS
    if value == _TELEGRAM_DESKTOP_API_ID:
        return FAMILY_DESKTOP
    if value > 0:
        return FAMILY_DESKTOP
    return None


def infer_device_family(device_model: str | None, *, api_id: int | None = None) -> str:
    name = str(device_model or "").strip().lower()
    if "iphone" in name or "ipad" in name or name.startswith("ios"):
        return FAMILY_IOS
    android_hints = (
        "sm-", "samsung", "pixel", "xiaomi", "redmi", "poco", "huawei",
        "honor", "oneplus", "oppo", "vivo", "realme", "motorola", "nokia", "sdk",
    )
    if any(hint in name for hint in android_hints):
        return FAMILY_ANDROID
    return family_for_api_id(api_id) or FAMILY_DESKTOP


def _family_defaults(family: str | None) -> dict[str, str]:
    resolved = normalize_device_family(family) or FAMILY_DESKTOP
    if resolved == FAMILY_ANDROID:
        return {"device_model": "Samsung SM-S938B", "system_version": "SDK 35", "app_version": "11.12.0"}
    if resolved == FAMILY_IOS:
        return {"device_model": "iPhone 16", "system_version": "18.6.1", "app_version": "11.14.1"}
    return {"device_model": "PC 64bit", "system_version": "Windows 10", "app_version": "5.8.2 x64"}


def device_family_of(profile: dict[str, str] | None, *, api_id: int | None = None) -> str:
    payload = profile or {}
    return (
        normalize_device_family(payload.get("family"))
        or infer_device_family(str(payload.get("device_model") or ""), api_id=api_id)
    )


def normalize_device_profile(
    raw: dict[str, Any] | None,
    *,
    api_id: int | None = None,
    phone: Any = None,
    country: str | None = None,
) -> dict[str, str]:
    data = raw if isinstance(raw, dict) else {}
    family = device_family_of(data, api_id=api_id)
    defaults = _family_defaults(family)
    lang_code, system_lang_code, tz_name = _apply_phone_locale(
        data, family, phone=phone, country=country
    )
    return {
        "family": family,
        "device_model": str(data.get("device_model") or defaults["device_model"]),
        "system_version": str(data.get("system_version") or defaults["system_version"]),
        "app_version": str(data.get("app_version") or defaults["app_version"]),
        "lang_code": lang_code,
        "system_lang_code": system_lang_code,
        "lang_pack": str(data.get("lang_pack") or lang_pack_for_family(family)),
        "tz_name": tz_name,
    }


def _usable_device(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    model = str(payload.get("device_model") or "").strip()
    return bool(model) and model not in _LEGACY_DEVICE_MODELS


def pick_device_profile(
    *,
    seed: str,
    family: str | None = None,
    mix: bool = False,
    exclude: dict[str, str] | None = None,
    phone: Any = None,
    country: str | None = None,
) -> dict[str, str]:
    rng = random.Random(str(seed))
    wanted = normalize_device_family(family)
    if wanted is None:
        wanted = rng.choices(_FAMILY_WEIGHTS, weights=_FAMILY_WEIGHT_VALUES, k=1)[0] if mix else FAMILY_DESKTOP
    pool = [item for item in _DEVICE_PROFILES if item["family"] == wanted]
    if not pool:
        pool = [item for item in _DEVICE_PROFILES if item["family"] == FAMILY_DESKTOP]
    excluded = (exclude or {}).get("device_model"), (exclude or {}).get("app_version")
    filtered = [item for item in pool if (item["device_model"], item["app_version"]) != excluded]
    return normalize_device_profile(
        rng.choice(filtered or pool),
        phone=phone,
        country=country,
    )


def ensure_account_device(
    account: Any,
    *,
    spare: bool = False,
    api_id: int | None = None,
    mix: bool = False,
) -> dict[str, str]:
    field = "spare_telegram_device" if spare else "telegram_device"
    phone = getattr(account, "phone_number", None)
    existing = getattr(account, field, None)
    if _usable_device(existing):
        profile = normalize_device_profile(existing, api_id=api_id, phone=phone)
        if profile != existing:
            try:
                setattr(account, field, profile)
            except Exception:
                pass
        return profile
    main = getattr(account, "telegram_device", None) if spare else None
    profile = pick_device_profile(
        seed=f"{'spare' if spare else 'main'}:{getattr(account, 'id', 0)}:{phone or ''}",
        family=family_for_api_id(api_id),
        mix=mix and family_for_api_id(api_id) is None,
        exclude=main if isinstance(main, dict) else None,
        phone=phone,
    )
    try:
        setattr(account, field, profile)
    except Exception:
        pass
    return profile

_qr_lock = asyncio.Lock()
_qr_states: dict[str, "_QrAuthState"] = {}


@dataclass
class _QrAuthState:
    status: str = "pending"
    session_string: str = ""
    api_id: int = 0
    api_hash: str = ""
    error: str = ""
    me: dict[str, Any] | None = None
    client: Any = field(default=None, repr=False)
    updated_at: float = field(default_factory=time.time)


class TelegramUserbotAuthError(Exception):
    def __init__(self, message: str, *, status_code: int = 422, extra: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.extra = extra or {}


def opentele_available() -> bool:
    try:
        import opentele  # noqa: F401

        return True
    except BaseException:
        return False


def _official_desktop_api():
    from opentele.api import API

    return API.TelegramDesktop.Generate(unique_id="rsd_userbot")


def _official_android_api():
    from opentele.api import API

    return API.TelegramAndroid.Generate(unique_id="rsd_userbot_phone")


def _official_ios_api():
    from opentele.api import API

    spec = getattr(API, "TelegramIOS", None)
    if spec is None:
        raise AttributeError("opentele has no TelegramIOS")
    return spec.Generate(unique_id="rsd_userbot_ios")


def _official_api_for_family(family: str | None):
    resolved = normalize_device_family(family) or FAMILY_DESKTOP
    if resolved == FAMILY_ANDROID:
        return _official_android_api()
    if resolved == FAMILY_IOS:
        return _official_ios_api()
    return _official_desktop_api()


def _builtin_api_credentials(*, prefer_desktop: bool = True, family: str | None = None) -> tuple[int, str]:
    resolved = normalize_device_family(family) or (FAMILY_DESKTOP if prefer_desktop else FAMILY_ANDROID)
    if resolved == FAMILY_ANDROID:
        return _TELEGRAM_ANDROID_API_ID, _TELEGRAM_ANDROID_API_HASH
    if resolved == FAMILY_IOS:
        return _TELEGRAM_IOS_API_ID, _TELEGRAM_IOS_API_HASH
    return _TELEGRAM_DESKTOP_API_ID, _TELEGRAM_DESKTOP_API_HASH


def resolve_api_credentials(
    api_id: int | None = None,
    api_hash: str | None = None,
    *,
    prefer_desktop: bool = True,
    family: str | None = None,
) -> tuple[int, str]:
    """Resolve MTProto app credentials (custom > env > opentele > Telethon builtin)."""
    custom_id = int(api_id) if api_id is not None and int(api_id) > 0 else 0
    custom_hash = str(api_hash or "").strip()
    if custom_id > 0 and custom_hash:
        return custom_id, custom_hash

    env_id = int(getattr(settings, "TELEGRAM_USERBOT_API_ID", 0) or 0)
    env_hash = str(getattr(settings, "TELEGRAM_USERBOT_API_HASH", "") or "").strip()
    if env_id > 0 and env_hash:
        return env_id, env_hash

    resolved_family = normalize_device_family(family) or (FAMILY_DESKTOP if prefer_desktop else FAMILY_ANDROID)
    if opentele_available():
        try:
            api = _official_api_for_family(resolved_family)
            return int(api.api_id), str(api.api_hash)
        except Exception as exc:
            logger.warning("opentele API resolve failed, using Telethon builtin: %s", exc)

    creds = _builtin_api_credentials(prefer_desktop=prefer_desktop, family=resolved_family)
    logger.debug("telegram userbot: using builtin %s API (opentele not installed)", resolved_family)
    return creds


def official_api_hash_for_id(api_id: int | None) -> str | None:
    """Return the public hash for a known official Telegram client id."""
    try:
        value = int(api_id or 0)
    except (TypeError, ValueError):
        return None
    if value == _TELEGRAM_DESKTOP_API_ID:
        return _TELEGRAM_DESKTOP_API_HASH
    if value == _TELEGRAM_ANDROID_API_ID:
        return _TELEGRAM_ANDROID_API_HASH
    if value == _TELEGRAM_IOS_API_ID:
        return _TELEGRAM_IOS_API_HASH
    return None


def iter_api_credential_candidates(
    api_id: int | None = None,
    api_hash: str | None = None,
    *,
    extra_api_id: int | None = None,
    prefer_desktop: bool = True,
    family: str | None = None,
) -> list[tuple[int, str]]:
    """Ordered unique (api_id, api_hash) pairs to try for a purchased session.

    When the device family is known, do not hop Desktop ↔ Android ↔ iOS on a
    live auth key. Cross-family fallback is only for unidentified sessions.
    """
    seen: set[int] = set()
    pairs: list[tuple[int, str]] = []
    resolved_family = normalize_device_family(family)
    extra_family = family_for_api_id(extra_api_id)

    def add(candidate_id: int | None, candidate_hash: str | None) -> None:
        try:
            resolved_id = int(candidate_id or 0)
        except (TypeError, ValueError):
            return
        resolved_hash = str(candidate_hash or "").strip() or (official_api_hash_for_id(resolved_id) or "")
        if resolved_id <= 0 or not resolved_hash or resolved_id in seen:
            return
        seen.add(resolved_id)
        pairs.append((resolved_id, resolved_hash))

    add(api_id, api_hash)
    add(extra_api_id, official_api_hash_for_id(extra_api_id))
    known_family = resolved_family or extra_family
    if known_family:
        add(*resolve_api_credentials(prefer_desktop=prefer_desktop, family=known_family))
        if extra_family and extra_family != known_family:
            add(*_builtin_api_credentials(family=extra_family))
        return pairs
    add(*resolve_api_credentials(prefer_desktop=prefer_desktop, family=FAMILY_DESKTOP if prefer_desktop else FAMILY_ANDROID))
    add(_TELEGRAM_DESKTOP_API_ID, _TELEGRAM_DESKTOP_API_HASH)
    add(_TELEGRAM_ANDROID_API_ID, _TELEGRAM_ANDROID_API_HASH)
    add(_TELEGRAM_IOS_API_ID, _TELEGRAM_IOS_API_HASH)
    return pairs


def _build_api_data(api_id: int, api_hash: str, *, profile: dict[str, str] | None = None, device_model: str | None = None):
    from opentele.api import APIData

    data = normalize_device_profile(profile)
    defaults = _family_defaults(data["family"])
    kwargs = {
        "api_id": int(api_id),
        "api_hash": str(api_hash).strip(),
        "device_model": device_model or data.get("device_model") or defaults["device_model"],
        "system_version": str(data.get("system_version") or defaults["system_version"]),
        "app_version": str(data.get("app_version") or defaults["app_version"]),
        "lang_code": str(data.get("lang_code") or _DEFAULT_LANG),
        "system_lang_code": str(data.get("system_lang_code") or _DEFAULT_SYSTEM_LANG),
    }
    lang_pack = str(data.get("lang_pack") or lang_pack_for_family(data["family"]))
    try:
        return APIData(**kwargs, lang_pack=lang_pack)
    except TypeError:
        return APIData(**kwargs)


def stamp_init_connection(client: Any, profile: dict[str, str] | None) -> Any:
    """Fill official-client InitConnection fields Telethon leaves empty."""
    req = getattr(client, "_init_request", None)
    data = profile or {}
    if req is None:
        return client
    family = device_family_of(data)
    lang_pack = str(data.get("lang_pack") or lang_pack_for_family(family))
    lang_code = str(data.get("lang_code") or _DEFAULT_LANG)
    system_lang = str(data.get("system_lang_code") or _DEFAULT_SYSTEM_LANG)
    try:
        req.lang_pack = lang_pack
        req.lang_code = lang_code
        req.system_lang_code = system_lang
    except Exception:
        logger.debug("Could not stamp InitConnection locale")
    tz_name = str(data.get("tz_name") or "").strip()
    try:
        from telethon.tl.types import JsonNumber, JsonObject, JsonObjectValue

        req.params = JsonObject(
            value=[
                JsonObjectValue(
                    key="tz_offset",
                    value=JsonNumber(value=float(tz_offset_seconds(tz_name))),
                )
            ]
        )
    except Exception:
        logger.debug("Could not stamp InitConnection tz_offset")
    return client


def create_telegram_client(
    *,
    api_id: int | None = None,
    api_hash: str | None = None,
    session_string: str = "",
    session_path: str | None = None,
    prefer_desktop: bool = True,
    family: str | None = None,
    proxy: dict | None = None,
    device_model: str | None = None,
    device_profile: dict[str, str] | None = None,
):
    """TelegramClient with opentele when installed, otherwise Telethon."""
    profile = dict(device_profile or {})
    if device_model:
        profile["device_model"] = device_model
    resolved_family = (
        normalize_device_family(family)
        or device_family_of(profile)
        or (FAMILY_DESKTOP if prefer_desktop else FAMILY_ANDROID)
    )
    if not str(profile.get("device_model") or "").strip():
        profile = pick_device_profile(
            seed=session_path or session_string or str(uuid.uuid4()),
            family=resolved_family,
        )
    else:
        profile = normalize_device_profile(profile)
        resolved_family = profile["family"]
    resolved_id, resolved_hash = resolve_api_credentials(
        api_id, api_hash, prefer_desktop=prefer_desktop, family=resolved_family
    )
    model = str(profile["device_model"])
    defaults = _family_defaults(resolved_family)
    if session_path:
        session = session_path
    else:
        from telethon.sessions import StringSession

        session = StringSession((session_string or "").strip())
    client_kwargs: dict[str, Any] = {
        "system_version": str(profile.get("system_version") or defaults["system_version"]),
        "app_version": str(profile.get("app_version") or defaults["app_version"]),
        "lang_code": str(profile.get("lang_code") or _DEFAULT_LANG),
        "system_lang_code": str(profile.get("system_lang_code") or _DEFAULT_SYSTEM_LANG),
    }
    if proxy:
        client_kwargs["proxy"] = proxy
    if opentele_available():
        from opentele.tl import TelegramClient

        api = _build_api_data(resolved_id, resolved_hash, profile=profile, device_model=model)
        extra = {key: value for key, value in client_kwargs.items() if key == "proxy"}
        client = TelegramClient(session, api=api, **extra)
    else:
        from telethon import TelegramClient

        client = TelegramClient(session, resolved_id, resolved_hash, device_model=model, **client_kwargs)
    stamp_init_connection(client, profile)
    return client, resolved_id, resolved_hash


def qr_url_to_data_url(qr_url: str) -> str:
    import qrcode

    qr = qrcode.QRCode(border=2, box_size=6)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _profile_from_me(me: Any) -> dict[str, Any]:
    return {
        "telegram_id": getattr(me, "id", None),
        "username": getattr(me, "username", None),
        "first_name": getattr(me, "first_name", None),
        "last_name": getattr(me, "last_name", None),
        "phone_number": getattr(me, "phone", None),
    }


def _success_payload(*, session_string: str, api_id: int, api_hash: str, me: Any) -> dict[str, Any]:
    profile = _profile_from_me(me)
    return {
        "session_string": session_string,
        "api_id": api_id,
        "api_hash": api_hash,
        **profile,
    }


async def _disconnect_qr_client(client: Any) -> None:
    if client is None:
        return
    try:
        await client.disconnect()
    except Exception:
        pass


async def _purge_stale_qr_states() -> None:
    now = time.time()
    stale_clients: list[Any] = []
    async with _qr_lock:
        stale = [k for k, v in _qr_states.items() if now - v.updated_at > _QR_TTL_SECONDS]
        for key in stale:
            state = _qr_states.pop(key, None)
            if state is not None and state.client is not None:
                stale_clients.append(state.client)
                state.client = None
    for client in stale_clients:
        await _disconnect_qr_client(client)


async def _set_qr_state(auth_id: str, **kwargs: Any) -> None:
    async with _qr_lock:
        state = _qr_states.get(auth_id)
        if state is None:
            state = _QrAuthState()
            _qr_states[auth_id] = state
        for key, value in kwargs.items():
            setattr(state, key, value)
        state.updated_at = time.time()


async def _run_qr_wait(
    auth_id: str,
    client: Any,
    qr_login: Any,
    *,
    api_id: int,
    api_hash: str,
) -> None:
    from telethon.errors import SessionPasswordNeededError

    keep_client = False
    try:
        await qr_login.wait(timeout=QR_WAIT_TIMEOUT_SECONDS)
        if await client.is_user_authorized():
            me = await client.get_me()
            session_string = client.session.save()
            await _set_qr_state(
                auth_id,
                status="success",
                session_string=session_string,
                api_id=api_id,
                api_hash=api_hash,
                me=_profile_from_me(me) if me else None,
                error="",
                client=None,
            )
        else:
            await _set_qr_state(auth_id, status="error", error="Сессия не авторизована после сканирования QR", client=None)
    except SessionPasswordNeededError:
        # 2FA must be signed on THIS live connection. Disconnecting unregisters the QR auth key.
        await _set_qr_state(
            auth_id,
            status="need_2fa",
            session_string=client.session.save(),
            api_id=api_id,
            api_hash=api_hash,
            error="",
            client=client,
        )
        keep_client = True
    except asyncio.TimeoutError:
        await _set_qr_state(auth_id, status="expired", error="Время ожидания сканирования QR истекло", client=None)
    except Exception as exc:
        logger.warning("telegram userbot QR wait failed auth_id=%s: %s", auth_id, exc, exc_info=True)
        await _set_qr_state(auth_id, status="error", error=str(exc), client=None)
    finally:
        if not keep_client:
            await _disconnect_qr_client(client)


async def start_qr_login(
    *,
    api_id: int | None = None,
    api_hash: str | None = None,
    proxy: dict | None = None,
) -> dict[str, Any]:
    await _purge_stale_qr_states()
    auth_id = uuid.uuid4().hex
    profile = pick_device_profile(seed=f"qr:{auth_id}", mix=True)
    client, resolved_id, resolved_hash = create_telegram_client(
        api_id=api_id,
        api_hash=api_hash,
        family=profile["family"],
        device_profile=profile,
        proxy=proxy,
    )
    try:
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            session_string = client.session.save()
            await _set_qr_state(
                auth_id,
                status="success",
                session_string=session_string,
                api_id=resolved_id,
                api_hash=resolved_hash,
                me=_profile_from_me(me) if me else None,
            )
            await client.disconnect()
            return {
                "auth_id": auth_id,
                "qr_url": "",
                "qr_data_url": "",
                "pending_session_string": session_string,
                "already_authorized": True,
                "api_id": resolved_id,
                "api_hash": resolved_hash,
            }
        qr_login = await client.qr_login()
        qr_url = str(getattr(qr_login, "url", "") or "").strip()
        if not qr_url:
            raise TelegramUserbotAuthError("Telegram не вернул URL для QR-входа")
        pending_session_string = client.session.save()
        await _set_qr_state(
            auth_id,
            status="pending",
            session_string=pending_session_string,
            api_id=resolved_id,
            api_hash=resolved_hash,
        )
        asyncio.create_task(
            _run_qr_wait(
                auth_id,
                client,
                qr_login,
                api_id=resolved_id,
                api_hash=resolved_hash,
            )
        )
        return {
            "auth_id": auth_id,
            "qr_url": qr_url,
            "qr_data_url": qr_url_to_data_url(qr_url),
            "pending_session_string": pending_session_string,
            "already_authorized": False,
            "api_id": resolved_id,
            "api_hash": resolved_hash,
        }
    except TelegramUserbotAuthError:
        await client.disconnect()
        raise
    except Exception as exc:
        await client.disconnect()
        raise TelegramUserbotAuthError(f"Не удалось начать QR-вход: {exc}") from exc


async def get_qr_status(*, auth_id: str) -> dict[str, Any]:
    await _purge_stale_qr_states()
    async with _qr_lock:
        state = _qr_states.get(auth_id)
    if state is None:
        return {"status": "expired", "error": "Сессия QR-входа не найдена или истекла"}
    payload: dict[str, Any] = {
        "status": state.status,
        "error": state.error or None,
        "api_id": state.api_id or None,
        "api_hash": state.api_hash or None,
    }
    if state.status == "success":
        payload.update(
            {
                "session_string": state.session_string,
                "me": state.me,
            }
        )
    elif state.status == "need_2fa" and state.session_string:
        payload["session_string"] = state.session_string
        payload["pending_session_string"] = state.session_string
    return payload


async def complete_qr_2fa(
    *,
    api_id: int,
    api_hash: str,
    session_string: str,
    password: str,
    proxy: dict | None = None,
    auth_id: str | None = None,
) -> dict[str, Any]:
    from telethon.errors import AuthKeyUnregisteredError, PasswordHashInvalidError

    try:
        from telethon.errors import AuthKeyInvalidError
    except Exception:
        AuthKeyInvalidError = type("AuthKeyInvalidError", (Exception,), {})

    pwd = (password or "").strip()
    if not pwd:
        raise TelegramUserbotAuthError("Укажите пароль 2FA", status_code=422)

    live_client = None
    if auth_id:
        async with _qr_lock:
            state = _qr_states.get(auth_id)
            if state is not None:
                live_client = state.client
                if state.api_id:
                    api_id = int(state.api_id)
                if state.api_hash:
                    api_hash = str(state.api_hash)

    owns_client = live_client is None
    if live_client is not None:
        client = live_client
        resolved_id, resolved_hash = int(api_id), str(api_hash)
    else:
        profile = pick_device_profile(seed=f"qr:{auth_id}", mix=True) if auth_id else pick_device_profile(seed=session_string or "qr", mix=True)
        client, resolved_id, resolved_hash = create_telegram_client(
            api_id=api_id,
            api_hash=api_hash,
            session_string=session_string,
            family=profile["family"],
            device_profile=profile,
            proxy=proxy,
        )
        await client.connect()

    keep_alive = False
    try:
        try:
            await client.sign_in(password=pwd)
        except PasswordHashInvalidError:
            keep_alive = not owns_client
            raise TelegramUserbotAuthError("Неверный пароль 2FA", status_code=422) from None
        except (AuthKeyUnregisteredError, AuthKeyInvalidError):
            raise TelegramUserbotAuthError(
                "QR-сессия истекла. Покажите новый QR-код и сразу введите пароль 2FA.",
                status_code=422,
            ) from None
        if not await client.is_user_authorized():
            raise TelegramUserbotAuthError("Не удалось авторизовать сессию с паролем 2FA")
        me = await client.get_me()
        final_session = client.session.save()
        if auth_id:
            await _set_qr_state(
                auth_id,
                status="success",
                session_string=final_session,
                me=_profile_from_me(me) if me else None,
                error="",
                client=None,
            )
        return _success_payload(
            session_string=final_session,
            api_id=resolved_id,
            api_hash=resolved_hash,
            me=me,
        )
    except TelegramUserbotAuthError:
        raise
    except Exception as exc:
        raise TelegramUserbotAuthError(f"Не удалось подтвердить 2FA Telegram: {exc}", status_code=422) from exc
    finally:
        if not keep_alive:
            await _disconnect_qr_client(client)
            if auth_id:
                async with _qr_lock:
                    state = _qr_states.get(auth_id)
                    if state is not None and state.client is client:
                        state.client = None


def _find_tdata_dir(root: Path) -> Path | None:
    if not root.is_dir():
        return None
    markers = ("key_datas", "map", "settings", "usertag")
    if any((root / name).exists() for name in markers):
        return root
    nested = root / "tdata"
    if nested.is_dir() and any((nested / name).exists() for name in markers):
        return nested
    for child in sorted(root.iterdir()):
        if child.is_dir():
            found = _find_tdata_dir(child)
            if found is not None:
                return found
    return None


async def _import_from_tdata_dir(tdata_dir: Path) -> dict[str, Any]:
    if not opentele_available():
        raise TelegramUserbotAuthError(
            "Импорт архива tdata (Telegram Desktop) требует пакет opentele на сервере. "
            "Пересоберите Docker-образ backend или используйте вход по QR / .session / .txt",
            status_code=503,
        )
    from opentele.api import UseCurrentSession
    from opentele.td import TDesktop

    tdesk = TDesktop(str(tdata_dir))
    if not tdesk.isLoaded():
        raise TelegramUserbotAuthError("Не удалось загрузить папку tdata Telegram Desktop")

    api = _official_desktop_api()
    api_id, api_hash = int(api.api_id), str(api.api_hash)
    tmp_session = tempfile.NamedTemporaryFile(prefix="rsd_tg_", suffix=".session", delete=False)
    tmp_session.close()
    session_path = tmp_session.name
    client = None
    try:
        client = await tdesk.ToTelethon(session_path, UseCurrentSession, api)
        await client.connect()
        if not await client.is_user_authorized():
            raise TelegramUserbotAuthError("tdata не содержит авторизованной сессии Telegram Desktop")
        me = await client.get_me()
        from telethon.sessions import StringSession

        session_string = StringSession.save(client.session)
        return _success_payload(
            session_string=session_string,
            api_id=api_id,
            api_hash=api_hash,
            me=me,
        )
    finally:
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass
        try:
            Path(session_path).unlink(missing_ok=True)
        except Exception:
            pass


async def _import_from_telethon_session_file(
    session_path: Path,
    *,
    api_id: int | None,
    api_hash: str | None,
) -> dict[str, Any]:
    resolved_id, resolved_hash = resolve_api_credentials(api_id, api_hash, prefer_desktop=True)
    if opentele_available():
        from opentele.tl import TelegramClient

        api = _build_api_data(resolved_id, resolved_hash)
        client = TelegramClient(str(session_path), api=api)
    else:
        from telethon import TelegramClient

        client = TelegramClient(str(session_path), resolved_id, resolved_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise TelegramUserbotAuthError("Файл .session не авторизован в Telegram")
        me = await client.get_me()
        from telethon.sessions import StringSession

        session_string = StringSession.save(client.session)
        return _success_payload(
            session_string=session_string,
            api_id=resolved_id,
            api_hash=resolved_hash,
            me=me,
        )
    finally:
        await client.disconnect()


async def _import_from_string_text(
    text: str,
    *,
    api_id: int | None,
    api_hash: str | None,
) -> dict[str, Any]:
    session_string = text.strip()
    if len(session_string) < 10:
        raise TelegramUserbotAuthError("Слишком короткая строка сессии")
    client, resolved_id, resolved_hash = create_telegram_client(
        api_id=api_id,
        api_hash=api_hash,
        session_string=session_string,
    )
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise TelegramUserbotAuthError("StringSession не авторизована")
        me = await client.get_me()
        final = client.session.save()
        return _success_payload(
            session_string=final,
            api_id=resolved_id,
            api_hash=resolved_hash,
            me=me,
        )
    finally:
        await client.disconnect()


async def import_session_file(
    *,
    api_id: int | None,
    api_hash: str | None,
    filename: str,
    content: bytes,
) -> dict[str, Any]:
    name = (filename or "").strip().lower()
    if not content:
        raise TelegramUserbotAuthError("Файл сессии пуст")

    tmp_root = Path(tempfile.mkdtemp(prefix="rsd_tg_import_"))
    try:
        if name.endswith(".zip"):
            zip_path = tmp_root / "upload.zip"
            zip_path.write_bytes(content)
            extract_dir = tmp_root / "extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
            tdata_dir = _find_tdata_dir(extract_dir)
            if tdata_dir is None:
                raise TelegramUserbotAuthError(
                    "В архиве не найдена папка tdata Telegram Desktop"
                )
            return await _import_from_tdata_dir(tdata_dir)

        if name.endswith(".session"):
            session_path = tmp_root / "upload.session"
            session_path.write_bytes(content)
            return await _import_from_telethon_session_file(
                session_path, api_id=api_id, api_hash=api_hash
            )

        text = content.decode("utf-8", errors="ignore").strip()
        if text:
            return await _import_from_string_text(text, api_id=api_id, api_hash=api_hash)

        raise TelegramUserbotAuthError(
            "Поддерживаются: .zip (tdata), .session (Telethon), .txt (StringSession)"
        )
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
