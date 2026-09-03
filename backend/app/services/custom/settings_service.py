"""Settings validation and feature-flag helpers for /custom automations."""
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AccountClass, AccountRole, CustomAutomation, CustomAutomationCredential, PoolAccount, SocialAccount
from .account_roles import ACCOUNT_ROLES, effective_roles
from .lead_keywords import normalize_lead_keywords


async def count_accounts_by_class(session: AsyncSession, automation_id: int) -> dict[str, int]:
    result = await session.execute(
        select(SocialAccount.account_class, func.count(SocialAccount.id))
        .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(
            PoolAccount.custom_automation_id == automation_id,
            SocialAccount.is_active.is_(True),
            SocialAccount.is_banned.is_(False),
        )
        .group_by(SocialAccount.account_class)
    )
    counts = {cls.value: 0 for cls in AccountClass}
    for account_class, count in result.all():
        counts[account_class] = count
    return counts


async def count_accounts_by_role(session: AsyncSession, automation_id: int) -> dict[str, int]:
    result = await session.execute(
        select(PoolAccount, SocialAccount)
        .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(
            PoolAccount.custom_automation_id == automation_id,
            SocialAccount.is_active.is_(True),
            SocialAccount.is_banned.is_(False),
        )
    )
    counts = {role: 0 for role in ACCOUNT_ROLES}
    for pool_account, social in result.all():
        for role in effective_roles(pool_account, social):
            counts[role] = counts.get(role, 0) + 1
    return counts


async def count_active_accounts(session: AsyncSession, automation_id: int) -> int:
    return await session.scalar(
        select(func.count(SocialAccount.id))
        .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(
            PoolAccount.custom_automation_id == automation_id,
            SocialAccount.is_active.is_(True),
            SocialAccount.is_banned.is_(False),
        )
    ) or 0


async def validate_settings(
    session: AsyncSession,
    automation: CustomAutomation,
) -> dict[str, Any]:
    warnings: list[str] = []
    can_enable: dict[str, bool] = {}

    counts = await count_accounts_by_class(session, automation.id)
    role_counts = await count_accounts_by_role(session, automation.id)
    total_active = sum(counts.values())
    trusted = counts.get(AccountClass.TRUSTED.value, 0)
    shilling = role_counts.get(AccountRole.SHILLING.value, 0)
    intercept = role_counts.get(AccountRole.LEAD_INTERCEPT.value, 0)
    neuro = role_counts.get(AccountRole.NEUROCOMMENTING.value, 0)
    dmp = role_counts.get(AccountRole.DMP.value, 0)

    from .solution_templates import is_dmp_notify_pipeline, qualification_enabled

    can_enable["chat_monitoring"] = intercept >= 1
    can_enable["neurocommenting"] = neuro >= 1
    can_enable["discussion"] = (neuro + intercept + dmp + shilling) >= 1
    can_enable["dmp_one"] = dmp >= 1
    can_enable["amocrm"] = True
    can_enable["shilling"] = shilling >= 2

    if is_dmp_notify_pipeline(automation):
        qualify = qualification_enabled(automation)
        can_enable["dmp_one"] = True if not qualify else trusted >= 1
        if not (automation.telegram_bot_token_enc or "").strip():
            warnings.append("Укажите API-ключ Telegram-бота.")
        if not (automation.google_sheets_spreadsheet_id or "").strip():
            warnings.append("Укажите Google Таблицу.")
        if not (automation.google_sheets_credentials_enc or "").strip():
            warnings.append("Вставьте JSON сервисного аккаунта Google.")
        credential_count = await session.scalar(
            select(func.count(CustomAutomationCredential.id)).where(
                CustomAutomationCredential.custom_automation_id == automation.id,
                CustomAutomationCredential.is_active.is_(True),
            )
        ) or 0
        if credential_count == 0:
            warnings.append("Создайте логин и пароль клиента — бот спрашивает их перед уведомлениями.")
        if qualify and trusted < 1:
            warnings.append("Квалификация включена, но нет активного trusted-аккаунта.")
        return {
            "warnings": warnings,
            "can_enable": can_enable,
            "counts": counts,
        }

    if automation.is_chat_monitoring_enabled and not can_enable["chat_monitoring"]:
        warnings.append(
            "Перехват заявок включён, но нет аккаунтов с функцией «перехват заявок». "
            "Назначьте функцию в разделе Аккаунты или отключите модуль."
        )
    if automation.is_chat_monitoring_enabled:
        if not normalize_lead_keywords(getattr(automation, "lead_keywords", None)):
            warnings.append(
                "Перехват заявок включён, но нет ключевых слов — сообщения не уйдут в LLM и в ЛС."
            )
    if automation.is_neurocommenting_enabled and not can_enable["neurocommenting"]:
        warnings.append(
            "Нейрокомментинг включён, но нет аккаунтов с этой функцией. "
            "Назначьте функцию в разделе Аккаунты или отключите модуль."
        )
    if automation.is_digital_footprint_enabled and not can_enable["discussion"]:
        warnings.append(
            "Искусственная активность в чатах включена, но нет аккаунтов с назначенной функцией. "
            "Назначьте функции в разделе Аккаунты или отключите модуль."
        )
    if automation.is_dmp_one_enabled and not can_enable["dmp_one"]:
        warnings.append(
            "DMP.one включён, но нет аккаунта с функцией DMP для исходящих ЛС. "
            "Назначьте функцию DMP или отключите модуль."
        )
    if automation.is_shilling_enabled and not can_enable["shilling"]:
        warnings.append(
            "Шиллинг включён, но меньше двух аккаунтов с функцией «шиллинг». "
            "Назначьте минимум два аккаунта или отключите модуль."
        )
    if automation.max_daily_messages_per_account <= 0:
        warnings.append("Дневной лимит сообщений на аккаунт равен 0 — сообщения не будут отправляться.")
    if total_active == 0:
        warnings.append("В автоматизации нет активных аккаунтов пула — все действия будут пропущены.")
    from .proxy_service import count_active_proxies

    if total_active > 0 and await count_active_proxies(session, automation.id) == 0:
        warnings.append(
            "Нет прокси — все аккаунты ходят в Telegram с IP сервера. "
            "Залейте прокси в настройках, чтобы размазать запросы по разным адресам."
        )
    kind = (automation.solution_kind or "generic").strip()
    manager_set = bool((automation.lead_manager_contact or "").strip())
    if kind == "fulfillment" and not manager_set:
        warnings.append("Укажите Telegram МОПа — на него уйдёт уведомление после прогрева.")
    elif kind != "seo_saas" and not automation.is_amocrm_enabled and not manager_set:
        warnings.append(
            "Не указан контакт менеджера. Без AmoCRM передать лид заказчику будет нельзя."
        )

    return {
        "warnings": warnings,
        "can_enable": can_enable,
        "counts": counts,
    }


async def is_feature_enabled(
    session: AsyncSession,
    automation_id: int,
    flag_name: str,
) -> bool:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        return False
    return bool(getattr(automation, flag_name, False))
