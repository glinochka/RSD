"""Seed /custom admin from environment variables.

Usage:
    python -m backend.app.router_custom.admin_seed
    or from project root:
    python -m app.router_custom.admin_seed

Creates the first CustomAdmin from CUSTOM_ADMIN_LOGIN / CUSTOM_ADMIN_PASSWORD_HASH.
If CUSTOM_ADMIN_PASSWORD_HASH is empty, uses CUSTOM_ADMIN_PASSWORD (plain) and hashes it.
Also updates the stored hash when .env changes, so a restart applies a new password.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path

# Ensure project root is on sys.path when run as script
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from app.alembic.database import async_session_maker
from app.alembic.models import CustomAdmin
from app.utils.security import get_password_hash
from app.config import settings

logger = getLogger(__name__)


def looks_like_bcrypt(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith(("$2a$", "$2b$", "$2y$")) and len(value) >= 59


async def seed_custom_admin():
    login = (settings.CUSTOM_ADMIN_LOGIN or "").strip()
    password_hash = settings.CUSTOM_ADMIN_PASSWORD_HASH or ""

    if not login:
        logger.warning("CUSTOM_ADMIN_LOGIN is not set; skipping custom admin seed.")
        return None

    if not password_hash:
        plain_password = os.environ.get("CUSTOM_ADMIN_PASSWORD")
        if not plain_password:
            logger.warning(
                "CUSTOM_ADMIN_PASSWORD_HASH is empty and CUSTOM_ADMIN_PASSWORD is not set; skipping seed."
            )
            return None
        password_hash = get_password_hash(plain_password)
        logger.info("Hashed plain CUSTOM_ADMIN_PASSWORD for custom admin seed.")

    if not looks_like_bcrypt(password_hash):
        logger.error(
            "CUSTOM_ADMIN_PASSWORD_HASH is not a bcrypt hash (prefix=%r len=%s). "
            "Docker Compose likely ate `$...` — use `$$` for each `$` in .env.",
            password_hash[:12],
            len(password_hash),
        )
        return None

    async with async_session_maker() as session:
        existing = await session.scalar(
            select(CustomAdmin).where(CustomAdmin.username == login)
        )
        if existing:
            changed = False
            if existing.password_hash != password_hash:
                existing.password_hash = password_hash
                changed = True
            if not existing.is_active:
                existing.is_active = True
                changed = True
            if changed:
                existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await session.commit()
                await session.refresh(existing)
                logger.info("Updated CustomAdmin '%s' (id=%s) from .env.", login, existing.id)
            else:
                logger.info("CustomAdmin '%s' already in sync (id=%s).", login, existing.id)
            admin = existing
        else:
            admin = CustomAdmin(
                username=login,
                password_hash=password_hash,
                is_active=True,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            session.add(admin)
            await session.commit()
            await session.refresh(admin)
            logger.info("Created CustomAdmin '%s' (id=%s).", login, admin.id)

    try:
        from app.services.custom.solution_templates import ensure_builtin_solutions

        async with async_session_maker() as session:
            ids = await ensure_builtin_solutions(session)
            logger.info("Built-in custom solutions ready: %s", ids)
    except Exception as exc:
        logger.exception("Failed to seed built-in custom solutions: %s", exc)

    return admin


async def main():
    await seed_custom_admin()


if __name__ == "__main__":
    asyncio.run(main())
