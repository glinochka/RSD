"""Helpers for /custom automation account pools and session uploads."""
import asyncio
import base64
import csv
import hashlib
import io
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import AccountClass, AccountPool, CustomAutomation, PoolAccount, SocialAccount
from ..config import settings


_SQLITE_MAGIC = b"SQLite format 3\x00"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _automation_sessions_dir(automation_id: int) -> Path:
    return _media_root() / "sessions" / str(automation_id)


def _derive_cipher_key() -> bytes:
    source = settings.CUSTOM_AUTOMATION_JWT_SECRET_KEY.strip() or settings.SECRET_KEY.strip()
    if not source:
        raise RuntimeError("No secret key available for session encryption")
    digest = hashlib.sha256(source.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_session_bytes(data: bytes) -> str:
    from cryptography.fernet import Fernet

    return f"fernet1:{Fernet(_derive_cipher_key()).encrypt(data).decode()}"


def decrypt_session_bytes(payload: str) -> bytes:
    from cryptography.fernet import Fernet, InvalidToken

    if not payload.startswith("fernet1:"):
        raise ValueError("Unsupported session encryption format")
    token = payload.split(":", 1)[1]
    try:
        return Fernet(_derive_cipher_key()).decrypt(token.encode())
    except InvalidToken as exc:
        raise ValueError("Invalid session encryption token") from exc


def _safe_filename(name: str) -> str:
    name = Path(name).name
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    if not name or name in {".", ".."}:
        name = "session.session"
    return name


def _write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def _is_valid_telegram_session(data: bytes) -> bool:
    """Check the SQLite magic header used by Telethon/Pyrogram .session files."""
    return len(data) >= 16 and data.startswith(_SQLITE_MAGIC)


def _parse_csv_accounts(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        cleaned = {k.strip().lower(): (v.strip() if v else None) for k, v in row.items()}
        rows.append(cleaned)
    return rows


async def get_or_create_default_pool(session: AsyncSession, automation_id: int) -> AccountPool:
    pool = await session.scalar(
        select(AccountPool).where(
            AccountPool.custom_automation_id == automation_id,
            AccountPool.is_default.is_(True),
        )
    )
    if pool:
        return pool

    pool = AccountPool(
        custom_automation_id=automation_id,
        name="Default",
        description="Default pool created automatically",
        is_default=True,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    session.add(pool)
    await session.flush()
    await session.refresh(pool)
    return pool


async def _create_social_account(
    session: AsyncSession,
    automation_id: int,
    pool_id: int,
    *,
    provider: str,
    phone_number: str | None,
    username: str | None,
    display_name: str | None,
    account_class: str,
    encrypted_session: str,
    session_file_path: str | None,
) -> SocialAccount:
    social_account = SocialAccount(
        provider=provider,
        phone_number=phone_number,
        username=username,
        display_name=display_name,
        encrypted_session=encrypted_session,
        session_file_path=session_file_path,
        account_class=account_class,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    session.add(social_account)
    await session.flush()
    await session.refresh(social_account)

    pool_account = PoolAccount(
        custom_automation_id=automation_id,
        account_pool_id=pool_id,
        social_account_id=social_account.id,
        assigned_class=account_class,
        added_at=_utc_now(),
    )
    session.add(pool_account)
    await session.flush()
    automation = await session.get(CustomAutomation, automation_id)
    from .custom.account_warmup_service import enroll_pool_account

    enroll_pool_account(automation, pool_account)
    return social_account


async def _save_session_file(
    session: AsyncSession,
    automation_id: int,
    pool_id: int,
    archive_name: str,
    data: bytes,
    assign_class: str,
    *,
    phone_number: str | None = None,
    username: str | None = None,
    display_name: str | None = None,
) -> SocialAccount:
    sessions_dir = _automation_sessions_dir(automation_id)
    safe_name = _safe_filename(archive_name)
    target_path = sessions_dir / safe_name
    await asyncio.to_thread(_write_file, target_path, data)

    encrypted = encrypt_session_bytes(data)
    relative_path = str(target_path.relative_to(_media_root()))
    return await _create_social_account(
        session,
        automation_id,
        pool_id,
        provider="telegram",
        phone_number=phone_number,
        username=username,
        display_name=display_name,
        account_class=assign_class,
        encrypted_session=encrypted,
        session_file_path=relative_path,
    )


def string_session_to_sqlite_bytes(session_string: str) -> bytes:
    """Convert a Telethon StringSession into SQLite .session file bytes."""
    import tempfile

    from telethon.sessions import SQLiteSession, StringSession

    raw = (session_string or "").strip()
    if not raw:
        raise ValueError("Пустая строка сессии")
    src = StringSession(raw)
    if not getattr(src, "auth_key", None):
        raise ValueError("В сессии нет ключа авторизации")
    with tempfile.TemporaryDirectory() as tmp:
        stem = str(Path(tmp) / "account")
        dest = SQLiteSession(stem)
        dest.set_dc(src.dc_id, src.server_address, src.port)
        dest.auth_key = src.auth_key
        dest.save()
        dest.close()
        path = Path(f"{stem}.session")
        if not path.is_file():
            raise ValueError("Не удалось записать файл сессии")
        data = path.read_bytes()
    if not _is_valid_telegram_session(data):
        raise ValueError("Полученный файл сессии повреждён")
    return data


async def _find_existing_pool_account(
    session: AsyncSession,
    automation_id: int,
    pool_id: int,
    *,
    phone_number: str | None,
    username: str | None,
) -> tuple[PoolAccount, SocialAccount] | None:
    from .custom.telegram_account_client import normalize_telegram_phone

    phone = normalize_telegram_phone(phone_number) or (phone_number or "").strip() or None
    uname = (username or "").strip().lstrip("@") or None
    if not phone and not uname:
        return None

    stmt = (
        select(PoolAccount, SocialAccount)
        .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(
            PoolAccount.custom_automation_id == automation_id,
            PoolAccount.account_pool_id == pool_id,
        )
    )
    rows = (await session.execute(stmt)).all()
    for pool_account, social in rows:
        existing_phone = normalize_telegram_phone(social.phone_number) or (social.phone_number or "").strip() or None
        existing_user = (social.username or "").strip().lstrip("@") or None
        if phone and existing_phone and phone == existing_phone:
            return pool_account, social
        if uname and existing_user and uname.lower() == existing_user.lower():
            return pool_account, social
    return None


async def add_account_from_session_string(
    session: AsyncSession,
    automation_id: int,
    *,
    session_string: str,
    assign_class: str,
    phone_number: str | None = None,
    username: str | None = None,
    display_name: str | None = None,
    telegram_id: int | None = None,
) -> tuple[PoolAccount, SocialAccount]:
    """Persist an authorized StringSession as a pool .session account."""
    data = await asyncio.to_thread(string_session_to_sqlite_bytes, session_string)
    pool = await get_or_create_default_pool(session, automation_id)
    existing = await _find_existing_pool_account(
        session,
        automation_id,
        pool.id,
        phone_number=phone_number,
        username=username,
    )
    if existing:
        pool_account, social = existing
        if social.session_file_path:
            target_path = _media_root() / social.session_file_path
        else:
            filename = _safe_filename(f"tg_{telegram_id or social.id}.session")
            target_path = _automation_sessions_dir(automation_id) / filename
            social.session_file_path = str(target_path.relative_to(_media_root()))
        await asyncio.to_thread(_write_file, target_path, data)
        social.encrypted_session = encrypt_session_bytes(data)
        social.phone_number = phone_number or social.phone_number
        social.username = username or social.username
        social.display_name = display_name or social.display_name
        social.is_active = True
        social.updated_at = _utc_now()
        await session.flush()
        await session.commit()
        await session.refresh(social)
        await session.refresh(pool_account)
        return pool_account, social

    filename = _safe_filename(f"tg_{telegram_id or uuid_like_name()}.session")
    social = await _save_session_file(
        session,
        automation_id,
        pool.id,
        filename,
        data,
        assign_class,
        phone_number=phone_number,
        username=username,
        display_name=display_name,
    )
    pool_account = await session.scalar(
        select(PoolAccount).where(
            PoolAccount.custom_automation_id == automation_id,
            PoolAccount.social_account_id == social.id,
        )
    )
    await session.commit()
    await session.refresh(social)
    if pool_account:
        await session.refresh(pool_account)
    if pool_account is None:
        raise RuntimeError("Pool account was not created")
    return pool_account, social


def uuid_like_name() -> str:
    import uuid

    return uuid.uuid4().hex[:12]


async def bulk_upload_sessions(
    session: AsyncSession,
    automation_id: int,
    upload_file: UploadFile,
    assign_class: str = AccountClass.ONE_DAY.value,
) -> dict[str, Any]:
    """Accept .zip, .csv or a single .session file and create SocialAccount/PoolAccount records."""
    pool = await get_or_create_default_pool(session, automation_id)

    filename = (upload_file.filename or "upload").lower()
    content_type = (upload_file.content_type or "").lower()
    content = await upload_file.read()

    created = 0
    skipped = 0
    errors: list[str] = []

    if filename.endswith(".zip") or content_type.startswith("application/zip"):
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist():
                if name.startswith("__MACOSX") or name.startswith(".") or not name.lower().endswith(".session"):
                    continue
                data = zf.read(name)
                if not _is_valid_telegram_session(data):
                    skipped += 1
                    errors.append(f"{name}: not a valid SQLite session file")
                    continue
                try:
                    await _save_session_file(session, automation_id, pool.id, name, data, assign_class)
                    created += 1
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
    elif filename.endswith(".csv") or content_type.startswith("text/csv"):
        rows = _parse_csv_accounts(content)
        for row in rows:
            phone_number = row.get("phone_number") or row.get("phone") or None
            username = row.get("username") or None
            display_name = row.get("display_name") or row.get("name") or None
            account_class = row.get("account_class") or assign_class
            try:
                await _create_social_account(
                    session,
                    automation_id,
                    pool.id,
                    provider="telegram",
                    phone_number=phone_number,
                    username=username,
                    display_name=display_name,
                    account_class=account_class,
                    encrypted_session="",
                    session_file_path=None,
                )
                created += 1
            except Exception as exc:
                errors.append(f"csv row {row}: {exc}")
    elif filename.endswith(".session"):
        if not _is_valid_telegram_session(content):
            skipped += 1
            errors.append(f"{filename}: not a valid SQLite session file")
        else:
            try:
                await _save_session_file(session, automation_id, pool.id, filename, content, assign_class)
                created += 1
            except Exception as exc:
                errors.append(f"{filename}: {exc}")
    else:
        errors.append("Unsupported file format. Use .zip, .csv or .session")

    await session.commit()
    total = created + skipped + len(errors)
    return {
        "total": total,
        "created": created,
        "skipped": skipped,
        "errors": errors,
    }


async def delete_pool_account(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
) -> None:
    row = await session.execute(
        select(PoolAccount, SocialAccount)
        .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(
            PoolAccount.custom_automation_id == automation_id,
            SocialAccount.id == account_id,
        )
    )
    result = row.one_or_none()
    if not result:
        raise ValueError("Account not found")
    pool_account, social_account = result
    session_rel = social_account.session_file_path
    avatar_rel = social_account.avatar_file_path
    await session.delete(pool_account)
    await session.delete(social_account)
    await session.commit()
    media_root = _media_root()
    for relative in (session_rel, avatar_rel):
        if not relative:
            continue
        path = media_root / relative
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
