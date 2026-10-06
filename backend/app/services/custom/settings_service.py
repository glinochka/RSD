"""Settings validation and feature-flag helpers for /custom automations.

Gating is task-based: each module runs on the accounts selected in that task.
Here we only check that live accounts exist when a global flag is on.
"""
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import CustomAutomation, CustomAutomationCredential, PoolAccount, SocialAccount
from .lead_keywords import normalize_lead_keywords


async def _live_pool_accounts(session: AsyncSession, automation_id: int) -> list[tuple[PoolAccount, SocialAccount]]:
    result = await session.execute(
        select(PoolAccount, SocialAccount)
        .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(
            PoolAccount.custom_automation_id == automation_id,
            SocialAccount.is_active.is_(True),
            SocialAccount.is_banned.is_(False),
            SocialAccount.is_frozen.is_(False),
        )
    )
    return list(result.all())


async def count_active_accounts(session: AsyncSession, automation_id: int) -> int:
    return await session.scalar(
        select(func.count(SocialAccount.id))
        .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(
            PoolAccount.custom_automation_id == automation_id,
            SocialAccount.is_active.is_(True),
            SocialAccount.is_banned.is_(False),
            SocialAccount.is_frozen.is_(False),
        )
    ) or 0


async def validate_settings(
    session: AsyncSession,
    automation: CustomAutomation,
) -> dict[str, Any]:
    warnings: list[str] = []
    can_enable: dict[str, bool] = {}

    live_accounts = await _live_pool_accounts(session, automation.id)
    total_active = len(live_accounts)
    has_live = total_active >= 1
    has_pair = total_active >= 2
    counts = {"live": total_active}

    from .solution_templates import is_dmp_notify_pipeline, qualification_enabled

    can_enable["chat_monitoring"] = has_live
    can_enable["neurocommenting"] = has_live
    can_enable["discussion"] = has_live
    can_enable["dmp_one"] = has_live
    can_enable["amocrm"] = True
    can_enable["shilling"] = has_pair

    if is_dmp_notify_pipeline(automation):
        qualify = qualification_enabled(automation)
        can_enable["dmp_one"] = True if not qualify else has_live
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
        if qualify and not has_live:
            warnings.append("Квалификация включена, но нет живых аккаунтов для исходящих ЛС.")
        return {
            "warnings": warnings,
            "can_enable": can_enable,
            "counts": counts,
        }

    if automation.is_chat_monitoring_enabled and not can_enable["chat_monitoring"]:
        warnings.append("Перехват заявок включён, но нет живых аккаунтов.")
    if automation.is_chat_monitoring_enabled:
        if not normalize_lead_keywords(getattr(automation, "lead_keywords", None)):
            warnings.append(
                "Перехват заявок включён, но нет ключевых слов — сообщения не уйдут в LLM и в ЛС."
            )
    if automation.is_neurocommenting_enabled and not can_enable["neurocommenting"]:
        warnings.append("Нейрокомментинг включён, но нет живых аккаунтов.")
    if automation.is_digital_footprint_enabled and not can_enable["discussion"]:
        warnings.append("Искусственная активность в чатах включена, но нет живых аккаунтов.")
    if automation.is_dmp_one_enabled and not can_enable["dmp_one"]:
        warnings.append("DMP.one включён, но нет живых аккаунтов для исходящих ЛС.")
    if automation.is_shilling_enabled and not can_enable["shilling"]:
        warnings.append("Шиллинг включён, но нужно минимум два живых аккаунта.")
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
    bot_set = bool((automation.telegram_bot_token_enc or "").strip())
    if bot_set and not is_dmp_notify_pipeline(automation) and not (getattr(automation, "telegram_bot_password_hash", None) or "").strip():
        warnings.append("Укажите пароль Telegram-бота — его спрашивают перед отправкой лидов.")
    if kind == "fulfillment" and not manager_set and not bot_set:
        warnings.append("Укажите Telegram МОПа или подключите Telegram-бота — на него уйдёт лид после прогрева.")
    elif kind != "seo_saas" and not automation.is_amocrm_enabled and not manager_set and not bot_set:
        warnings.append(
            "Не указан контакт менеджера. Без AmoCRM и Telegram-бота передать лид заказчику будет нельзя."
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
