from datetime import datetime, timedelta, timezone
from logging import getLogger

import asyncio
import httpx
from sqlalchemy import exists, select

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, User
from ..config import settings

logger = getLogger(__name__)
INACTIVE_REMINDER_DELAY_DAYS = 3
INACTIVE_REMINDER_REPEAT_DAYS = 10


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _render_mailopost_card_html(*, title: str, paragraphs: list[str], accent_block_html: str = "") -> str:
    rendered_paragraphs = "".join(
        f"<tr><td style='padding:0 24px 8px 24px;color:#374151;font-size:14px;line-height:1.6;'>{line}</td></tr>"
        for line in paragraphs
    )
    return (
        "<!DOCTYPE html>"
        "<html><body style='margin:0;padding:0;background:#f5f7fb;font-family:Arial,sans-serif;'>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='background:#f5f7fb;padding:24px 12px;'>"
        "<tr><td align='center'>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='max-width:560px;background:#ffffff;border:1px solid #e8ecf3;border-radius:12px;overflow:hidden;'>"
        "<tr><td style='padding:24px 24px 8px 24px;'>"
        f"<div style='font-size:20px;font-weight:700;color:#111827;'>{title}</div>"
        "</td></tr>"
        f"{rendered_paragraphs}"
        f"{accent_block_html}"
        "<tr><td style='padding:8px 24px 24px 24px;color:#9ca3af;font-size:12px;line-height:1.6;'>"
        "Это письмо отправлено автоматически. Если нужна помощь, просто ответьте на него."
        "</td></tr>"
        "</table>"
        "</td></tr></table>"
        "</body></html>"
    )


async def _send_inactive_user_reminder_email(email: str) -> bool:
    api_token = settings.MAILOPOST_API_TOKEN.strip()
    from_email = settings.MAILOPOST_FROM_EMAIL.strip()
    base_url = settings.MAILOPOST_API_URL.strip().rstrip("/")
    if not api_token or not from_email:
        logger.warning("Onboarding reminder skipped: Mail sender is not configured")
        return False

    payload = {
        "from_email": from_email,
        "to": email,
        "subject": "RSD AI: поможем запустить вашего ИИ сотрудника",
        "text": (
            "Здравствуйте!\n"
            "Вы зарегистрировались на сервисе RSD AI.\n\n"
            "Хотели уточнить, получилось ли у Вас настроить ИИ сотрудника для Вашего бизнеса?\n"
            "Если у вас возникли вопросы, можете задать их в ответном письме, в чате на сайте "
            "или в Telegram: t.me/fakerebellious.\n\n"
            "Также можем реализовать автоматизацию под ключ: от настройки ИИ сотрудника до "
            "подключения каналов (Telegram, МАКС, WhatsApp) и запуска процессов."
        ),
        "html": _render_mailopost_card_html(
            title="Помочь запустить ИИ сотрудника?",
            paragraphs=[
                "Здравствуйте! Вы зарегистрировались на сервисе RSD AI.",
                "Получилось ли у вас настроить ИИ сотрудника для вашего бизнеса?",
                "Если возникли вопросы, напишите в ответ на это письмо, в чате на сайте или в Telegram: t.me/fakerebellious.",
                "Также можем сделать автоматизацию под ключ: от внедрения до сопровождения.",
            ],
            accent_block_html=(
                "<tr><td style='padding:8px 24px 8px 24px;'>"
                "<div style='display:inline-block;background:#eef2ff;color:#3730a3;font-size:13px;font-weight:600;padding:10px 14px;border-radius:10px;'>"
                "Каналы подключения: Telegram, МАКС, WhatsApp"
                "</div>"
                "</td></tr>"
            ),
        ),
    }
    from_name = settings.MAILOPOST_FROM_NAME.strip()
    if from_name:
        payload["from_name"] = from_name

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    url = f"{base_url}/email/messages"
    timeout = httpx.Timeout(settings.MAILOPOST_SEND_TIMEOUT_SECONDS, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload, headers=headers)

    if response.is_success:
        return True

    logger.error(
        "MailoPost onboarding reminder send failed: status=%s body=%s",
        response.status_code,
        response.text[:500],
    )
    return False


async def send_onboarding_inactive_user_reminders_once() -> int:
    now_utc = _utc_now_naive()
    first_reminder_cutoff = now_utc - timedelta(days=INACTIVE_REMINDER_DELAY_DAYS)
    repeat_reminder_cutoff = now_utc - timedelta(days=INACTIVE_REMINDER_REPEAT_DAYS)
    sent_count = 0

    async with async_session_maker() as session:
        async with session.begin():
            rows = (
                await session.scalars(
                    select(User).where(
                        User.email.is_not(None),
                        User.email_verified.is_(True),
                        User.registered <= first_reminder_cutoff,
                        (
                            User.onboarding_reminder_sent_at.is_(None)
                            | (User.onboarding_reminder_sent_at <= repeat_reminder_cutoff)
                        ),
                        ~exists(select(Agent.id).where(Agent.user_id == User.id)),
                    )
                )
            ).all()

        for idx, user in enumerate(rows):
            if idx > 0:
                await asyncio.sleep(settings.MAILOPOST_REMINDER_BATCH_INTERVAL_SECONDS)
            if not user.email:
                continue
            delivered = await _send_inactive_user_reminder_email(user.email)
            if not delivered:
                continue
            async with session.begin():
                db_user = await session.get(User, user.id)
                if db_user:
                    db_user.onboarding_reminder_sent_at = now_utc
                    sent_count += 1

    if sent_count:
        logger.info("Sent %s onboarding reminder emails to inactive users", sent_count)
    return sent_count
