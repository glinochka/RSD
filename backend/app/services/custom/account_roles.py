"""Account function (role) assignment for /custom pool accounts."""
from __future__ import annotations

from ...alembic.models import AccountClass, AccountRole, PoolAccount, SocialAccount

ACCOUNT_ROLES: tuple[str, ...] = tuple(item.value for item in AccountRole)
SHILLING_QUESTION_ROLE = AccountRole.SHILLING_QUESTION.value
SHILLING_ANSWER_ROLE = AccountRole.SHILLING_ANSWER.value
LEGACY_SHILLING_ROLE = AccountRole.SHILLING.value
ALL_SHILLING_ROLES = {LEGACY_SHILLING_ROLE, SHILLING_QUESTION_ROLE, SHILLING_ANSWER_ROLE}

ROLE_LABELS = {
    AccountRole.NEUROCOMMENTING.value: "Нейрокомментинг",
    AccountRole.LEAD_INTERCEPT.value: "Перехват заявок",
    AccountRole.SHILLING.value: "Шиллинг",
    AccountRole.SHILLING_QUESTION.value: "Шиллинг 1 (вопрос)",
    AccountRole.SHILLING_ANSWER.value: "Шиллинг 2 (ответ)",
    AccountRole.DMP.value: "DMP",
}

ACTION_ROLE = {
    "commenting": AccountRole.NEUROCOMMENTING.value,
    "dm": AccountRole.LEAD_INTERCEPT.value,
    "dmp_outreach": AccountRole.DMP.value,
    "shilling": AccountRole.SHILLING.value,
    "shilling_question": SHILLING_QUESTION_ROLE,
    "shilling_answer": SHILLING_ANSWER_ROLE,
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
WARMUP_OPEN_ACTIONS = {"inspect", "prepare_join", "discovery"}


def _expand_shilling_roles(roles: list[str]) -> list[str]:
    if LEGACY_SHILLING_ROLE not in roles:
        return roles
    expanded = [item for item in roles if item != LEGACY_SHILLING_ROLE]
    for role in (SHILLING_QUESTION_ROLE, SHILLING_ANSWER_ROLE):
        if role not in expanded:
            expanded.append(role)
    return expanded


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
    return _expand_shilling_roles(seen)


def default_roles_for_class(account_class: str | None) -> list[str]:
    return list(CLASS_DEFAULT_ROLES.get(account_class or "", ()))


def effective_roles(pool_account: PoolAccount | None, social: SocialAccount | None = None) -> set[str]:
    return set(normalize_roles(getattr(pool_account, "roles", None) if pool_account is not None else None))


def can_ask_shilling(roles: set[str] | list[str] | None) -> bool:
    values = set(roles or ())
    return SHILLING_QUESTION_ROLE in values or LEGACY_SHILLING_ROLE in values


def can_answer_shilling(roles: set[str] | list[str] | None) -> bool:
    values = set(roles or ())
    return SHILLING_ANSWER_ROLE in values or LEGACY_SHILLING_ROLE in values


def has_shilling_role(roles: set[str] | list[str] | None) -> bool:
    return bool(set(roles or ()) & ALL_SHILLING_ROLES)


def shilling_pair_ready(role_sets: list[set[str]] | list[list[str]]) -> bool:
    askers = [index for index, roles in enumerate(role_sets) if can_ask_shilling(roles)]
    answerers = [index for index, roles in enumerate(role_sets) if can_answer_shilling(roles)]
    return any(asker != answerer for asker in askers for answerer in answerers)


def is_warmup_blocked(pool_account: PoolAccount | None, action_type: str) -> bool:
    if action_type in WARMUP_OPEN_ACTIONS:
        return False
    status = (getattr(pool_account, "warmup_status", None) or "idle").strip().lower()
    return status in WARMUP_BLOCKED_STATUSES


def _matches_shilling(roles: set[str], action_type: str) -> bool:
    if action_type == "shilling_question":
        return can_ask_shilling(roles)
    if action_type == "shilling_answer":
        return can_answer_shilling(roles)
    return has_shilling_role(roles)


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
    if action_type in {"shilling", "shilling_question", "shilling_answer"}:
        return _matches_shilling(roles, action_type)
    required = ACTION_ROLE.get(action_type)
    if required is None:
        return bool(roles)
    return required in roles
