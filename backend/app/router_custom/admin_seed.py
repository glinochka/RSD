"""Seed /custom admin from environment variables.

Usage:
    python -m backend.app.router_custom.admin_seed
    or from project root:
    python -m app.router_custom.admin_seed

Creates the first CustomAdmin from CUSTOM_ADMIN_LOGIN / CUSTOM_ADMIN_PASSWORD_HASH.
If CUSTOM_ADMIN_PASSWORD_HASH is empty, uses CUSTOM_ADMIN_PASSWORD (plain) and hashes it.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
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


async def seed_custom_admin():
    login = settings.CUSTOM_ADMIN_LOGIN
    password_hash = settings.CUSTOM_ADMIN_PASSWORD_HASH

    if not login:
        print("CUSTOM_ADMIN_LOGIN is not set; skipping custom admin seed.")
        return None

    if not password_hash:
        plain_password = os.environ.get("CUSTOM_ADMIN_PASSWORD")
        if not plain_password:
            print("CUSTOM_ADMIN_PASSWORD_HASH is empty and CUSTOM_ADMIN_PASSWORD is not set; skipping seed.")
            return None
        password_hash = get_password_hash(plain_password)
        print("Hashed plain CUSTOM_ADMIN_PASSWORD (store hash in .env and remove plain password).")

    async with async_session_maker() as session:
        existing = await session.scalar(
            select(CustomAdmin).where(CustomAdmin.username == login)
        )
        if existing:
            print(f"CustomAdmin '{login}' already exists (id={existing.id}).")
            return existing

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
        print(f"Created CustomAdmin '{login}' (id={admin.id}).")
        return admin


async def main():
    await seed_custom_admin()


if __name__ == "__main__":
    asyncio.run(main())
