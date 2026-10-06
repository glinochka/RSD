"""Shared module picker flags: require_proxy and hide_in_work."""
from __future__ import annotations

from typing import Any


def account_has_proxy(account: Any, pool: Any = None) -> bool:
    return bool(getattr(account, "telegram_proxy", None) or (pool is not None and getattr(pool, "proxy_id", None)))


def account_is_in_work(account: Any) -> bool:
    from .rotation_service import current_daily_messages_sent

    if account is None:
        return False
    return bool(getattr(account, "is_active", False) and (current_daily_messages_sent(account) or 0) > 0)


def skip_account_for_module(cfg: dict[str, Any] | None, account: Any, pool: Any = None) -> bool:
    data = cfg if isinstance(cfg, dict) else {}
    if data.get("require_proxy") and not account_has_proxy(account, pool):
        return True
    if data.get("hide_in_work") and account_is_in_work(account):
        return True
    return False


def module_account_ids(cfg: dict[str, Any] | None) -> list[int]:
    data = cfg if isinstance(cfg, dict) else {}
    raw = data.get("account_ids") or []
    if not isinstance(raw, list):
        raw = [raw]
    ids: list[int] = []
    seen: set[int] = set()
    for item in raw:
        try:
            ident = int(item)
        except (TypeError, ValueError):
            continue
        if ident <= 0 or ident in seen:
            continue
        seen.add(ident)
        ids.append(ident)
    return ids


def no_accounts_picked(cfg: dict[str, Any] | None) -> bool:
    """Empty picker must not fall back to the whole pool for production modules."""
    return not module_account_ids(cfg)
