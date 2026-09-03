"""Account function (role) assignment for /custom pool accounts."""
from __future__ import annotations

from ...alembic.models import AccountClass, AccountRole, PoolAccount, SocialAccount

ACCOUNT_ROLES: tuple[str, ...] = tuple(item.value for item in AccountRole)

ROLE_LABELS = {
    AccountRole.NEUROCOMMENTING.value: "Нейрокомментинг",
    AccountRole.LEAD_INTERCEPT.value: "Перехват заявок",
    AccountRole.SHILLING.value: "Шиллинг",
    AccountRole.DMP.value: "DMP",
}

ACTION_ROLE = {
    "commenting": AccountRole.NEUROCOMMENTING.value,
    "dm": AccountRole.LEAD_INTERCEPT.value,
    "dmp_outreach": AccountRole.DMP.value,
    "shilling": AccountRole.SHILLING.value,
}

CLASS_DEFAULT_ROLES = {
    AccountClass.ONE_DAY.value: (AccountRole.NEUROCOMMENTING.value,),
    AccountClass.MID.value: (AccountRole.NEUROCOMMENTING.value, AccountRole.LEAD_INTERCEPT.value),
    AccountClass.TRUSTED.value: (
        AccountRole.NEUROCOMMENTING.value,
        AccountRole.LEAD_INTERCEPT.value,
        AccountRole.DMP.value,
    ),
    AccountClass.SHILLING.value: (AccountRole.SHILLING.value,),
}

WARMUP_BLOCKED_STATUSES = {"rest", "warming"}
WARMUP_OPEN_ACTIONS = {"inspect", "prepare_join"}


def normalize_roles(raw) -> list[str]:
    if isinstance(raw, dict):
        raw = raw.get("roles") or raw.get("items") or []
    if not isinstance(raw, (list, tuple, set)):
        return []
    seen: list[str] = []
    for item in raw:
        value = str(item or "").strip().lower()
        if value in ACCOUNT_ROLES and value not in seen:
            seen.append(value)
    return seen


def default_roles_for_class(account_class: str | None) -> list[str]:
    return list(CLASS_DEFAULT_ROLES.get(account_class or "", ()))


def effective_roles(pool_account: PoolAccount | None, social: SocialAccount | None = None) -> set[str]:
    return set(normalize_roles(getattr(pool_account, "roles", None) if pool_account is not None else None))


def is_warmup_blocked(pool_account: PoolAccount | None, action_type: str) -> bool:
    if action_type in WARMUP_OPEN_ACTIONS:
        return False
    status = (getattr(pool_account, "warmup_status", None) or "idle").strip().lower()
    return status in WARMUP_BLOCKED_STATUSES


def account_matches_action(
    pool_account: PoolAccount | None,
    social: SocialAccount | None,
    action_type: str,
) -> bool:
    if is_warmup_blocked(pool_account, action_type):
        return False
    if action_type in WARMUP_OPEN_ACTIONS:
        return True
    roles = effective_roles(pool_account, social)
    required = ACTION_ROLE.get(action_type)
    if required is None:
        return bool(roles)
    return required in roles
