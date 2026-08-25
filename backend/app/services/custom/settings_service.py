"""Settings validation and feature-flag helpers for /custom automations."""
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AccountClass, CustomAutomation, CustomAutomationCredential, PoolAccount, SocialAccount


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
    total_active = sum(counts.values())
    trusted = counts.get(AccountClass.TRUSTED.value, 0)
    mid = counts.get(AccountClass.MID.value, 0)
    one_day = counts.get(AccountClass.ONE_DAY.value, 0)
    shilling = counts.get(AccountClass.SHILLING.value, 0)

    from .solution_templates import is_dmp_notify_pipeline, qualification_enabled

    can_enable["chat_monitoring"] = trusted >= 1
    can_enable["neurocommenting"] = (one_day + mid) >= 1
    can_enable["discussion"] = (one_day + mid + trusted) >= 1
    can_enable["dmp_one"] = trusted >= 1
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
            "Перехват заявок включён, но нет активных trusted-аккаунтов для отправки ЛС. "
            "Добавьте/классифицируйте аккаунты trusted или отключите модуль."
        )
    if automation.is_neurocommenting_enabled and not can_enable["neurocommenting"]:
        warnings.append(
            "Нейрокомментинг включён, но нет активных one_day/mid-аккаунтов. "
            "Добавьте и классифицируйте аккаунты или отключите модуль."
        )
    if automation.is_digital_footprint_enabled and not can_enable["discussion"]:
        warnings.append(
            "Искусственная активность в чатах включена, но нет активных аккаунтов пула. "
            "Добавьте аккаунты или отключите модуль."
        )
    if automation.is_dmp_one_enabled and not can_enable["dmp_one"]:
        warnings.append(
            "DMP.one включён, но нет активного доверенного аккаунта для исходящих ЛС. "
            "Добавьте trusted-аккаунт или отключите модуль."
        )
    if automation.is_shilling_enabled and not can_enable["shilling"]:
        warnings.append(
            "Шиллинг включён, но в пуле меньше двух активных аккаунтов класса «шиллинг». "
            "Назначьте минимум два аккаунта или отключите модуль."
        )
    if automation.max_daily_messages_per_account <= 0:
        warnings.append("Дневной лимит сообщений на аккаунт равен 0 — сообщения не будут отправляться.")
    if total_active == 0:
        warnings.append("В автоматизации нет активных аккаунтов пула — все действия будут пропущены.")
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
