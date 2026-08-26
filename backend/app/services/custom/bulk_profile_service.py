"""Bulk profile update (bio + avatar) for Telegram accounts."""
import json
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .telegram_account_client import SESSION_RECONNECT_HINT, TelegramAccountClient
from .telegram_error_handler import SessionInvalidError, execute_with_telegram_retry
from ...alembic.models import AutomationActionLog, CustomPrompt, PromptType, SocialAccount
from ...config import settings
from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)


_DEFAULT_BIO_PROMPT = (
    "Напиши короткое нейтральное описание профиля Telegram на русском языке "
    "(1-2 предложения, без ссылок, телефонов и хештегов). "
    "Уникальность: {seed}"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


async def _load_bio_prompt(session: AsyncSession, automation_id: int) -> str:
    prompt = await session.scalar(
        select(CustomPrompt).where(
            CustomPrompt.custom_automation_id == automation_id,
            CustomPrompt.prompt_type == PromptType.PROFILE_BIO.value,
            CustomPrompt.is_active.is_(True),
        ).order_by(CustomPrompt.created_at.desc())
    )
    if prompt:
        return str(prompt.content or "").strip() or _DEFAULT_BIO_PROMPT
    return _DEFAULT_BIO_PROMPT


async def _generate_unique_bio(
    session: AsyncSession,
    automation_id: int,
    *,
    variables: dict[str, Any],
) -> str:
    prompt = await _load_bio_prompt(session, automation_id)
    try:
        prompt = prompt.format(**variables)
    except KeyError as exc:
        logger.warning("Bio prompt contains unknown variable: %s", exc)

    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.9,
        )
        text = (response.choices[0].message.content or "").strip()
        # Telegram bio limit is around 70 characters; keep a safety margin.
        return text[:140]
    except Exception as exc:
        logger.warning("LLM bio generation failed: %s", exc)
        return ""


def _render_bio_template(template: str, variables: dict[str, Any]) -> str:
    if not template:
        return ""
    try:
        return template.format(**variables)
    except KeyError as exc:
        logger.warning("Bio template contains unknown variable: %s", exc)
        return template


async def _save_uploaded_avatar(automation_id: int, filename: str, data: bytes) -> str:
    root = _media_root()
    avatars_dir = root / "avatars" / str(automation_id)
    avatars_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"bulk_{int(time.time())}_{filename.replace(' ', '_')}"
    target = avatars_dir / safe_name
    target.write_bytes(data)
    return str(target.relative_to(root))


async def _log_action(
    session: AsyncSession,
    *,
    automation_id: int,
    social_account_id: int,
    action_type: str,
    result: str,
    payload: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    log = AutomationActionLog(
        custom_automation_id=automation_id,
        social_account_id=social_account_id,
        action_type=action_type,
        result=result,
        target_type="profile",
        payload=payload or {},
        error_message=error_message,
        created_at=_utc_now(),
    )
    session.add(log)
    await session.commit()


class BulkProfileUpdateWorker:
    """Apply bio and avatar changes to a batch of Telegram accounts."""

    async def update_account(
        self,
        session: AsyncSession,
        automation_id: int,
        account_id: int,
        *,
        avatar_relative_path: str | None,
        bio_template: str,
        generate_unique: bool,
    ) -> dict[str, Any]:
        social_account = await session.get(SocialAccount, account_id)
        if not social_account:
            return {"account_id": account_id, "status": "skipped", "reason": "not_found"}
        if not social_account.session_file_path:
            return {"account_id": account_id, "status": "skipped", "reason": "no_session"}

        session_path = _media_root() / social_account.session_file_path
        if not session_path.exists():
            from .telegram_account_client import restore_encrypted_session_file

            restore_encrypted_session_file(social_account.encrypted_session, session_path)
        if not session_path.exists():
            await _log_action(
                session,
                automation_id=automation_id,
                social_account_id=account_id,
                action_type="profile_update",
                result="error",
                error_message="Session file missing",
            )
            return {"account_id": account_id, "status": "error", "error": "Session file missing"}

        variables = {
            "username": social_account.username or "",
            "phone_number": social_account.phone_number or "",
            "display_name": social_account.display_name or "",
            "account_class": social_account.account_class or "",
            "account_id": str(account_id),
            "seed": f"{account_id}-{int(time.time())}",
        }

        bio = ""
        if generate_unique:
            bio = await _generate_unique_bio(session, automation_id, variables=variables)
        if not bio and bio_template:
            bio = _render_bio_template(bio_template, variables)

        applied_avatar = False
        applied_bio = False
        try:
            async with TelegramAccountClient.for_account(social_account) as client:
                if bio:
                    await execute_with_telegram_retry(
                        session,
                        social_account,
                        lambda: client.set_bio(bio),
                        action_type="profile_update",
                        target_id=f"account:{account_id}",
                        target_type="profile",
                        payload={"bio": bio},
                        automation_id=automation_id,
                    )
                    applied_bio = True
                if avatar_relative_path:
                    avatar_path = _media_root() / avatar_relative_path
                    if avatar_path.exists():
                        avatar_bytes = avatar_path.read_bytes()
                        await execute_with_telegram_retry(
                            session,
                            social_account,
                            lambda: client.set_avatar(avatar_bytes),
                            action_type="profile_update",
                            target_id=f"account:{account_id}",
                            target_type="profile",
                            payload={"avatar": avatar_relative_path},
                            automation_id=automation_id,
                        )
                        applied_avatar = True
                        dest = _media_root() / "avatars" / str(automation_id) / f"{account_id}.jpg"
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(avatar_path, dest)
                        social_account.avatar_file_path = str(dest.relative_to(_media_root()))
                        social_account.avatar_url = f"/media/{social_account.avatar_file_path}"
        except SessionInvalidError as exc:
            error_message = str(exc) or SESSION_RECONNECT_HINT
            await _log_action(
                session,
                automation_id=automation_id,
                social_account_id=account_id,
                action_type="profile_update",
                result="error",
                payload={"bio": bio, "avatar": avatar_relative_path},
                error_message=error_message,
            )
            return {"account_id": account_id, "status": "error", "error": error_message}
        except Exception as exc:
            error_message = str(exc)
            await _log_action(
                session,
                automation_id=automation_id,
                social_account_id=account_id,
                action_type="profile_update",
                result="error",
                payload={"bio": bio, "avatar": avatar_relative_path},
                error_message=error_message,
            )
            return {"account_id": account_id, "status": "error", "error": error_message}

        if applied_bio:
            social_account.bio = bio
            social_account.current_bio = bio
        social_account.is_active = True
        social_account.updated_at = _utc_now()
        await session.commit()

        await _log_action(
            session,
            automation_id=automation_id,
            social_account_id=account_id,
            action_type="profile_update",
            result="success",
            payload={"bio": bio, "avatar": avatar_relative_path, "applied_bio": applied_bio, "applied_avatar": applied_avatar},
        )
        return {
            "account_id": account_id,
            "status": "success",
            "applied_bio": applied_bio,
            "applied_avatar": applied_avatar,
        }

    async def process_accounts(
        self,
        automation_id: int,
        account_ids: list[int],
        *,
        avatar_relative_path: str | None,
        bio_template: str,
        generate_unique: bool,
    ) -> list[dict[str, Any]]:
        from ...alembic.database import async_session_maker

        results = []
        async with async_session_maker() as session:
            for account_id in account_ids:
                try:
                    result = await self.update_account(
                        session,
                        automation_id,
                        account_id,
                        avatar_relative_path=avatar_relative_path,
                        bio_template=bio_template,
                        generate_unique=generate_unique,
                    )
                    results.append(result)
                except Exception as exc:
                    logger.exception("Bulk profile update failed for account %s: %s", account_id, exc)
                    results.append({"account_id": account_id, "status": "error", "error": str(exc)})
        return results


async def _require_session_path(social_account: SocialAccount) -> Path:
    if not social_account.session_file_path:
        raise ValueError("no session")
    session_path = _media_root() / social_account.session_file_path
    if not session_path.exists():
        raise ValueError("Session file missing")
    return session_path


async def update_account_display_name(
    session: AsyncSession,
    automation_id: int,
    social_account: SocialAccount,
    display_name: str,
) -> str:
    name = (display_name or "").strip()
    if not name:
        raise ValueError("empty display name")
    session_path = await _require_session_path(social_account)
    async with TelegramAccountClient.for_account(social_account) as client:
        stored = await execute_with_telegram_retry(
            session,
            social_account,
            lambda: client.set_display_name(name),
            action_type="profile_update",
            target_id=f"account:{social_account.id}",
            target_type="profile",
            payload={"display_name": name},
            automation_id=automation_id,
        )
    social_account.display_name = stored or name
    social_account.is_active = True
    social_account.updated_at = _utc_now()
    await session.commit()
    return social_account.display_name


async def update_account_bio(
    session: AsyncSession,
    automation_id: int,
    social_account: SocialAccount,
    bio: str,
) -> str:
    text = (bio or "").strip()[:140]
    session_path = await _require_session_path(social_account)
    async with TelegramAccountClient.for_account(social_account) as client:
        await execute_with_telegram_retry(
            session,
            social_account,
            lambda: client.set_bio(text),
            action_type="profile_update",
            target_id=f"account:{social_account.id}",
            target_type="profile",
            payload={"bio": text},
            automation_id=automation_id,
        )
    social_account.bio = text
    social_account.current_bio = text
    social_account.is_active = True
    social_account.updated_at = _utc_now()
    await session.commit()
    return text
