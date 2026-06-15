"""Отправка outreach-писем ИИ МОП через MailoPost."""

from __future__ import annotations

import logging

import httpx

from ...config import settings
from ...router_users.router import _render_mailopost_card_html

logger = logging.getLogger(__name__)


async def send_ai_mop_outreach_email(
    *,
    to_email: str,
    subject: str,
    text: str,
    html_body: str,
) -> None:
    api_token = settings.MAILOPOST_API_TOKEN.strip()
    from_email = settings.MAILOPOST_FROM_EMAIL.strip()
    base_url = settings.MAILOPOST_API_URL.strip().rstrip("/")
    if not api_token or not from_email:
        raise RuntimeError("Mail sender is not configured")

    html = html_body.strip()
    if not html:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        html = _render_mailopost_card_html(
            title=subject,
            paragraphs=paragraphs or [text],
        )

    payload = {
        "from_email": from_email,
        "to": to_email,
        "subject": subject,
        "text": text,
        "html": html,
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

    if not response.is_success:
        logger.error(
            "AI MOP MailoPost failed: status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        raise RuntimeError(f"MailoPost error {response.status_code}")
