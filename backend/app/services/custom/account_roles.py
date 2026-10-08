"""Warmup-only eligibility for /custom pool accounts.

Account classes and roles are gone: a task uses the accounts selected in its
module. This helper only blocks target actions while an account is warming.
"""
from __future__ import annotations

from ...alembic.models import PoolAccount, SocialAccount

WARMUP_BLOCKED_STATUSES = {"rest", "warming"}
WARMUP_OPEN_ACTIONS = {"inspect", "prepare_join", "discovery"}

# Kept so existing tests that construct PoolAccount rows still import cleanly.
SHILLING_QUESTION_ROLE = "shilling_question"
SHILLING_ANSWER_ROLE = "shilling_answer"


def default_roles_for_class(_account_class=None) -> list[str]:
    return []


def is_warmup_blocked(
    pool_account: PoolAccount | None,
    action_type: str,
    social: SocialAccount | None = None,
) -> bool:
    if action_type in WARMUP_OPEN_ACTIONS:
        return False
    from .account_pacing import SETTLE_HOURS, account_may_do_work

    if social is not None and not account_may_do_work(social):
        return True
    status = (getattr(pool_account, "warmup_status", None) or "idle").strip().lower()
    if status not in WARMUP_BLOCKED_STATUSES:
        return False
    # Production day 3+: work may start even if the warmup card still says warming.
    if social is not None and SETTLE_HOURS > 0 and account_may_do_work(social):
        return False
    return True


def account_matches_action(
    pool_account: PoolAccount | None,
    social: SocialAccount | None,
    action_type: str,
) -> bool:
    """True unless warmup / upload calendar is blocking this target action."""
    return not is_warmup_blocked(pool_account, action_type, social)


def account_is_live(social: SocialAccount | None) -> bool:
    if social is None:
        return False
    if not social.is_active or social.is_banned or getattr(social, "is_frozen", False):
        return False
    from .account_pacing import account_is_flood_quarantined

    if account_is_flood_quarantined(social):
        return False
    if not (social.session_file_path or getattr(social, "encrypted_session", None)):
        return False
    return True


def account_is_task_ready(
    pool_account: PoolAccount | None,
    social: SocialAccount | None,
    action_type: str = "commenting",
    *,
    exclude_spamblocked: bool = False,
) -> bool:
    if not account_is_live(social):
        return False
    from .account_pacing import account_may_do_work

    if action_type not in WARMUP_OPEN_ACTIONS and not account_may_do_work(social):
        return False
    from .account_restriction import restriction_blocks_action

    if restriction_blocks_action(social, action_type):
        return False
    if exclude_spamblocked and action_type in {
        "dm",
        "dmp",
        "dmp_outreach",
        "warmup_dm",
        "lead_warmup",
        "peer_dialog",
        "account_warmup",
    }:
        if getattr(social, "is_spamblocked", False):
            return False
    return account_matches_action(pool_account, social, action_type)
