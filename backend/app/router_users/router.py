import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from logging import getLogger

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .dao import TelegramLinkChallengeDAO, UserDAO
from .schemas import *
from ..alembic.database import async_session_maker
from ..alembic.models import UserAuthSession
from ..config import settings
from ..router_agents.dao import AgentDAO
from ..utils.convert import convert_to_dict
from ..utils.internal_auth import verify_internal_key
from ..utils.JWT import create_access_token, decode_access_token_payload, get_user_from_access_token
from ..utils.rate_limit import rate_limit
from ..utils.security import get_password_hash, verify_password

logger = getLogger(__name__)

router = APIRouter(prefix="/api/users")

http_bearer = HTTPBearer(auto_error=False)
LINK_CODE_ALPHABET = "0123456789"
LINK_CODE_LENGTH = 6
LINK_CODE_TTL_MINUTES = 5
LINK_CODE_MAX_ATTEMPTS = 5
EMAIL_CODE_ALPHABET = "0123456789"
EMAIL_CODE_LENGTH = 6
EMAIL_CODE_TTL_MINUTES = 10
EMAIL_CODE_MAX_ATTEMPTS = 5
EMAIL_CODE_RESEND_COOLDOWN_SECONDS = 120
PASSWORD_RESET_CODE_ALPHABET = "0123456789"
PASSWORD_RESET_CODE_LENGTH = 6
PASSWORD_RESET_CODE_TTL_MINUTES = 10
PASSWORD_RESET_MAX_ATTEMPTS = 5
PASSWORD_RESET_RESEND_COOLDOWN_SECONDS = 120
PASSWORD_RESET_TOKEN_BYTES = 36
PASSWORD_RESET_TOKEN_TTL_MINUTES = 15
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
REFRESH_TOKEN_BYTES = 48
MAILOPOST_RATE_LIMIT_RETRY_RE = re.compile(r"try again in (\d+)\s*seconds?", re.IGNORECASE)


def _mailopost_rate_limit_retry_seconds(response: httpx.Response) -> int | None:
    """Parse 'Try again in N seconds' from MailoPost JSON error body."""
    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
    for err in data.get("errors") or []:
        detail = err.get("detail") if isinstance(err, dict) else None
        if not detail or not isinstance(detail, str):
            continue
        match = MAILOPOST_RATE_LIMIT_RETRY_RE.search(detail)
        if match:
            return int(match.group(1))
    return None


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_link_code(raw_code: str) -> str:
    return "".join(ch for ch in raw_code.upper().strip() if ch.isalnum())


def _normalize_email(raw_email: str) -> str:
    return raw_email.strip().lower()


def _validate_email_or_422(raw_email: str) -> str:
    normalized_email = _normalize_email(raw_email)
    if not EMAIL_PATTERN.match(normalized_email):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Некорректный email")
    return normalized_email


def _build_username_base_from_email(email: str) -> str:
    local_part = email.split("@", 1)[0].lower()
    normalized = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in local_part)
    normalized = normalized.strip("_")
    if not normalized:
        normalized = "user"
    if len(normalized) < 3:
        normalized = f"{normalized}_usr"
    return normalized[:32]


async def _build_unique_username(user_dao: UserDAO, normalized_email: str) -> str:
    base = _build_username_base_from_email(normalized_email)
    candidate = base
    suffix = 1
    while await user_dao.find_one_by_filter(name=candidate):
        suffix += 1
        suffix_text = f"_{suffix}"
        max_base_len = 32 - len(suffix_text)
        candidate = f"{base[:max_base_len]}{suffix_text}"
    return candidate


def _format_link_code(raw_code: str) -> str:
    return raw_code


def _generate_link_code() -> str:
    return "".join(secrets.choice(LINK_CODE_ALPHABET) for _ in range(LINK_CODE_LENGTH))


def _generate_email_code() -> str:
    return "".join(secrets.choice(EMAIL_CODE_ALPHABET) for _ in range(EMAIL_CODE_LENGTH))


def _hash_link_code(raw_code: str) -> str:
    normalized_code = _normalize_link_code(raw_code)
    peppered_code = f"{settings.SECRET_KEY}:{normalized_code}"
    return hashlib.sha256(peppered_code.encode("utf-8")).hexdigest()


def _hash_email_code(raw_code: str) -> str:
    normalized_code = "".join(ch for ch in raw_code.strip() if ch.isdigit())
    peppered_code = f"{settings.SECRET_KEY}:email_verification:{normalized_code}"
    return hashlib.sha256(peppered_code.encode("utf-8")).hexdigest()


def _generate_password_reset_code() -> str:
    return "".join(secrets.choice(PASSWORD_RESET_CODE_ALPHABET) for _ in range(PASSWORD_RESET_CODE_LENGTH))


def _hash_password_reset_code(raw_code: str) -> str:
    normalized_code = "".join(ch for ch in raw_code.strip() if ch.isdigit())
    peppered_code = f"{settings.SECRET_KEY}:password_reset:{normalized_code}"
    return hashlib.sha256(peppered_code.encode("utf-8")).hexdigest()


def _generate_password_reset_token() -> str:
    return secrets.token_urlsafe(PASSWORD_RESET_TOKEN_BYTES)


def _hash_password_reset_token(raw_token: str) -> str:
    normalized_token = raw_token.strip()
    peppered_token = f"{settings.SECRET_KEY}:password_reset_token:{normalized_token}"
    return hashlib.sha256(peppered_token.encode("utf-8")).hexdigest()


def _normalize_tg_username(username: str) -> str:
    value = username.strip()
    if value.startswith("@"):
        value = value[1:]
    return value.lower()


def _build_refresh_expiry() -> datetime:
    return _utc_now_naive() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


def _hash_refresh_token(refresh_token: str) -> str:
    jwt_secret = settings.USER_JWT_SECRET_KEY.strip()
    if not jwt_secret:
        raise RuntimeError("USER_JWT_SECRET_KEY is not configured")
    material = f"{jwt_secret}:{refresh_token.strip()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _generate_refresh_token() -> str:
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


async def _issue_user_tokens(session, user_id: int) -> tuple[str, str]:
    session_id = secrets.token_hex(16)
    refresh_token = _generate_refresh_token()
    expires_at = _build_refresh_expiry()
    session.add(
        UserAuthSession(
            id=session_id,
            user_id=user_id,
            refresh_token_hash=_hash_refresh_token(refresh_token),
            expires_at=expires_at,
        )
    )
    access_token = create_access_token({"user_id": str(user_id), "sid": session_id}, token_kind="user")
    return access_token, refresh_token


def _serialize_user_public(user) -> dict:
    user_dict = convert_to_dict(user)
    # Для JSON-сериализации удаляем неиспользуемые служебные поля.
    user_dict.pop("registered", None)
    sub_time: datetime | None = user_dict.get("subscription_end_date")
    user_dict["subscription_end_date"] = sub_time.isoformat() if sub_time else None
    user_dict.pop("password", None)
    return user_dict


async def _send_master_bot_link_prompt(telegram_id: int) -> None:
    token = settings.MASTER_BOT_TOKEN.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MASTER_BOT_TOKEN is not configured on backend",
        )

    message_text = (
        "Привязка web аккаунта с bot аккаунтом.\n"
        "Введите код, указанный на сайте (6 цифр), обычным сообщением в этот чат.\n\n"
        "Если вы не начинали привязку, проигнорируйте это сообщение."
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": telegram_id,
        "text": message_text,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        response = await client.post(url, json=payload)
    if not response.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to deliver message to Telegram user",
        )


async def _send_registration_email_code(email: str, code: str) -> None:
    api_token = settings.MAILOPOST_API_TOKEN.strip()
    from_email = settings.MAILOPOST_FROM_EMAIL.strip()
    base_url = settings.MAILOPOST_API_URL.strip().rstrip("/")
    if not api_token or not from_email:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mail sender is not configured",
        )

    payload = {
        "from_email": from_email,
        "to": email,
        "subject": "Код подтверждения регистрации",
        "text": (
            "RSD - подтверждение email\n\n"
            f"Ваш код подтверждения: {code}\n"
            f"Код действует {EMAIL_CODE_TTL_MINUTES} минут.\n\n"
            "Если вы не запрашивали регистрацию, просто проигнорируйте письмо."
        ),
        "html": (
            "<!DOCTYPE html>"
            "<html><body style='margin:0;padding:0;background:#f5f7fb;font-family:Arial,sans-serif;'>"
            "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='background:#f5f7fb;padding:24px 12px;'>"
            "<tr><td align='center'>"
            "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='max-width:560px;background:#ffffff;border:1px solid #e8ecf3;border-radius:12px;overflow:hidden;'>"
            "<tr><td style='padding:24px 24px 8px 24px;'>"
            "<div style='font-size:20px;font-weight:700;color:#111827;'>Подтверждение регистрации в RSD</div>"
            "</td></tr>"
            "<tr><td style='padding:0 24px 8px 24px;color:#374151;font-size:14px;line-height:1.6;'>"
            "Введите код ниже на странице регистрации."
            "</td></tr>"
            "<tr><td style='padding:8px 24px 8px 24px;'>"
            f"<div style='display:inline-block;background:#111827;color:#ffffff;font-size:28px;font-weight:700;letter-spacing:6px;padding:14px 18px;border-radius:10px;'>{code}</div>"
            "</td></tr>"
            "<tr><td style='padding:8px 24px 8px 24px;color:#6b7280;font-size:13px;line-height:1.6;'>"
            f"Код действует {EMAIL_CODE_TTL_MINUTES} минут."
            "</td></tr>"
            "<tr><td style='padding:0 24px 24px 24px;color:#9ca3af;font-size:12px;line-height:1.6;'>"
            "Если вы не запрашивали регистрацию, просто проигнорируйте это письмо."
            "</td></tr>"
            "</table>"
            "</td></tr></table>"
            "</body></html>"
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

    if not response.is_success:
        logger.error(
            "MailoPost send failed: status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        if response.status_code == 429:
            retry_sec = _mailopost_rate_limit_retry_seconds(response)
            if retry_sec is not None:
                minutes = max(1, (retry_sec + 59) // 60)
                detail = (
                    f"Сервис рассылки временно ограничил отправку. Повторите через ~{minutes} мин."
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=detail,
                    headers={"Retry-After": str(retry_sec)},
                )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Сервис рассылки временно ограничил отправку. Повторите позже.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось отправить код подтверждения на email",
        )


async def _send_password_reset_email_code(email: str, code: str) -> None:
    api_token = settings.MAILOPOST_API_TOKEN.strip()
    from_email = settings.MAILOPOST_FROM_EMAIL.strip()
    base_url = settings.MAILOPOST_API_URL.strip().rstrip("/")
    if not api_token or not from_email:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mail sender is not configured",
        )

    payload = {
        "from_email": from_email,
        "to": email,
        "subject": "Код восстановления пароля",
        "text": (
            "RSD - восстановление пароля\n\n"
            f"Ваш код восстановления: {code}\n"
            f"Код действует {PASSWORD_RESET_CODE_TTL_MINUTES} минут.\n\n"
            "Если вы не запрашивали восстановление, просто проигнорируйте письмо."
        ),
        "html": (
            "<!DOCTYPE html>"
            "<html><body style='margin:0;padding:0;background:#f5f7fb;font-family:Arial,sans-serif;'>"
            "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='background:#f5f7fb;padding:24px 12px;'>"
            "<tr><td align='center'>"
            "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='max-width:560px;background:#ffffff;border:1px solid #e8ecf3;border-radius:12px;overflow:hidden;'>"
            "<tr><td style='padding:24px 24px 8px 24px;'>"
            "<div style='font-size:20px;font-weight:700;color:#111827;'>Восстановление пароля в RSD</div>"
            "</td></tr>"
            "<tr><td style='padding:0 24px 8px 24px;color:#374151;font-size:14px;line-height:1.6;'>"
            "Введите код ниже на странице восстановления пароля."
            "</td></tr>"
            "<tr><td style='padding:8px 24px 8px 24px;'>"
            f"<div style='display:inline-block;background:#111827;color:#ffffff;font-size:28px;font-weight:700;letter-spacing:6px;padding:14px 18px;border-radius:10px;'>{code}</div>"
            "</td></tr>"
            "<tr><td style='padding:8px 24px 8px 24px;color:#6b7280;font-size:13px;line-height:1.6;'>"
            f"Код действует {PASSWORD_RESET_CODE_TTL_MINUTES} минут."
            "</td></tr>"
            "<tr><td style='padding:0 24px 24px 24px;color:#9ca3af;font-size:12px;line-height:1.6;'>"
            "Если вы не запрашивали восстановление, просто проигнорируйте это письмо."
            "</td></tr>"
            "</table>"
            "</td></tr></table>"
            "</body></html>"
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

    if not response.is_success:
        logger.error(
            "MailoPost password reset send failed: status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        if response.status_code == 429:
            retry_sec = _mailopost_rate_limit_retry_seconds(response)
            if retry_sec is not None:
                minutes = max(1, (retry_sec + 59) // 60)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Сервис рассылки временно ограничил отправку. Повторите через ~{minutes} мин.",
                    headers={"Retry-After": str(retry_sec)},
                )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Сервис рассылки временно ограничил отправку. Повторите позже.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось отправить код восстановления на email",
        )


async def get_current_user_required(
    http_credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
):
    if not http_credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token = http_credentials.credentials
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            return await get_user_from_access_token(token, user_dao)


@router.post("")
async def create_user(user_by_tg: User_from_tg, _internal=Depends(verify_internal_key)):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)

        async with session.begin():
            double_user = await user_dao.find_one_by_filter(name=user_by_tg.name)
            if double_user:
                logger.info(f"{user_by_tg.name} уже есть в базе данных")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Пользователь уже существует"
                )
            
            dict_new_user = user_by_tg.model_dump()
            await user_dao.add(dict_new_user)

    logger.info(f"{user_by_tg.name} был добавлен")

    return Response(status_code=status.HTTP_201_CREATED)


@router.get("/by_agentID")
async def user_by_agentID(user_by_agent: User_by_agent_or_tgID = Depends(), _internal=Depends(verify_internal_key)):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await agent_dao.find_one_by_filter(load_relations=True, bot_id=user_by_agent.id)
            
            if not agent:
                logger.error(f"бот с айди {user_by_agent.id} не найден")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found"
                )
            user = agent.user
            if not user:
                logger.error(f"пользователь владеющий ботом с айди {user_by_agent.id} не найден")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found for this agent"
                )
            user_dict = _serialize_user_public(user)

    logger.info(f"запрос с {user_by_agent.id} был обработан")
    return JSONResponse(
        content=user_dict,
        status_code=status.HTTP_200_OK
        )

@router.get("/by_tgID")
async def user_by_tgID(user_by_tg: User_by_agent_or_tgID = Depends(), _internal=Depends(verify_internal_key)):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(telegram_id=user_by_tg.id)
            
            if not user:
                logger.error(f"пользователь с tg айди {user_by_tg.id} не найден")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found for this tg ID"
                )
            user_dict = _serialize_user_public(user)


    logger.info(f"запрос с {user_by_tg.id} был обработан")
    return JSONResponse(
        content=user_dict,
        status_code=status.HTTP_200_OK
        )
@router.patch("/by_tgID")
async def UpdateUser_by_tgID(user_by_tg: Update_userSubscription, _internal=Depends(verify_internal_key)):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(telegram_id=user_by_tg.telegram_id)
            
            if not user:
                logger.error(f"пользователь с tg айди {user_by_tg.telegram_id} не найден")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found for this tg ID"
                )
            update_dict = user_by_tg.model_dump()
            del update_dict["telegram_id"]

            await user_dao.update(user, update_dict)

    logger.info(f"запрос с {user_by_tg.telegram_id} был обработан")
    return Response(
        status_code=status.HTTP_204_NO_CONTENT
        )






@router.post("/registration", dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, scope="users_registration"))])
async def user_registration(new_user: NewUser):
    normalized_email = _validate_email_or_422(new_user.email)
    verification_code = ""
    # Retry once on DB uniqueness race (parallel registration requests).
    for attempt in range(2):
        verification_code = _generate_email_code()
        verification_code_hash = _hash_email_code(verification_code)
        now_utc = _utc_now_naive()
        expires_at = now_utc + timedelta(minutes=EMAIL_CODE_TTL_MINUTES)
        try:
            async with async_session_maker() as session:
                user_dao = UserDAO(session)

                async with session.begin():
                    user_with_email = await user_dao.find_one_by_filter(email=normalized_email)

                    if user_with_email and user_with_email.email_verified:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Email уже используется"
                        )

                    if user_with_email and not user_with_email.email_verified:
                        last_sent = user_with_email.email_verification_last_sent_at
                        if last_sent is not None:
                            elapsed = (now_utc - last_sent).total_seconds()
                            if elapsed < EMAIL_CODE_RESEND_COOLDOWN_SECONDS:
                                retry_after = max(1, int(EMAIL_CODE_RESEND_COOLDOWN_SECONDS - elapsed))
                                raise HTTPException(
                                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                    detail=(
                                        f"Повторная отправка кода возможна через {retry_after} с. "
                                        "Подождите или используйте код из предыдущего письма."
                                    ),
                                    headers={"Retry-After": str(retry_after)},
                                )

                    updates = {
                        "email": normalized_email,
                        "password": get_password_hash(new_user.password),
                        "email_verified": False,
                        "email_verification_code_hash": verification_code_hash,
                        "email_verification_expires_at": expires_at,
                        "email_verification_attempts_left": EMAIL_CODE_MAX_ATTEMPTS,
                        "email_verification_last_sent_at": now_utc,
                    }
                    if user_with_email:
                        await user_dao.update(user_with_email, updates)
                    else:
                        generated_name = await _build_unique_username(user_dao, normalized_email)
                        await user_dao.add(
                            {
                                "name": generated_name,
                                **updates,
                                "telegram_id": new_user.telegram_id,
                            }
                        )
                        # Surface uniqueness races before leaving transaction block.
                        await session.flush()
            break
        except IntegrityError:
            if attempt == 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email уже используется",
                )
            continue

    try:
        await _send_registration_email_code(normalized_email, verification_code)
    except HTTPException as exc:
        # If sending failed due to transport/provider error, unlock immediate resend.
        if exc.status_code == status.HTTP_502_BAD_GATEWAY:
            async with async_session_maker() as session:
                user_dao = UserDAO(session)
                async with session.begin():
                    user = await user_dao.find_one_by_filter(email=normalized_email)
                    if user and not user.email_verified:
                        await user_dao.update(user, {"email_verification_last_sent_at": None})
        raise

    logger.info("Код подтверждения регистрации отправлен на email %s", normalized_email)

    return JSONResponse(content={
            "status": "verification_required",
            "detail": "Код подтверждения отправлен на email",
            "email": normalized_email,
            "expires_in_seconds": EMAIL_CODE_TTL_MINUTES * 60,
        },
        status_code=status.HTTP_201_CREATED)


@router.post(
    "/registration/verify",
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60, scope="users_registration_verify"))],
)
async def verify_user_registration_code(payload: VerifyRegistrationCodeRequest):
    normalized_email = _validate_email_or_422(payload.email)
    code_hash = _hash_email_code(payload.code)
    now_utc = _utc_now_naive()

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(email=normalized_email)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Пользователь не найден",
                )

            if user.email_verified:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email уже подтвержден",
                )

            if not user.email_verification_code_hash or not user.email_verification_expires_at:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Код подтверждения не запрошен",
                )

            if user.email_verification_expires_at < now_utc:
                await user_dao.update(
                    user,
                    {
                        "email_verification_code_hash": None,
                        "email_verification_expires_at": None,
                        "email_verification_attempts_left": 0,
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Код подтверждения истек",
                )

            if user.email_verification_attempts_left <= 0:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Превышено число попыток ввода кода",
                )

            if user.email_verification_code_hash != code_hash:
                attempts_left = max(0, user.email_verification_attempts_left - 1)
                await user_dao.update(user, {"email_verification_attempts_left": attempts_left})
                if attempts_left == 0:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Превышено число попыток ввода кода",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Неверный код. Осталось попыток: {attempts_left}",
                )

            await user_dao.update(
                user,
                {
                    "email_verified": True,
                    "email_verification_code_hash": None,
                    "email_verification_expires_at": None,
                    "email_verification_attempts_left": 0,
                },
            )

            access_token, refresh_token = await _issue_user_tokens(session, user.id)

    return JSONResponse(
        content={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/password-reset/request",
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, scope="users_password_reset_request"))],
)
async def request_password_reset(payload: PasswordResetRequest):
    normalized_email = _validate_email_or_422(payload.email)
    now_utc = _utc_now_naive()
    code = _generate_password_reset_code()
    code_hash = _hash_password_reset_code(code)
    code_expires_at = now_utc + timedelta(minutes=PASSWORD_RESET_CODE_TTL_MINUTES)

    user_for_email = None
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            user_for_email = await user_dao.find_one_by_filter(email=normalized_email)
            if not user_for_email:
                # Generic response to avoid email enumeration.
                return JSONResponse(
                    content={
                        "status": "code_sent_if_exists",
                        "detail": "Если email существует, код восстановления отправлен.",
                    },
                    status_code=status.HTTP_200_OK,
                )

            if user_for_email.password is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Для этого аккаунта вход по паролю недоступен",
                )

            last_sent = user_for_email.password_reset_last_sent_at
            if last_sent is not None:
                elapsed = (now_utc - last_sent).total_seconds()
                if elapsed < PASSWORD_RESET_RESEND_COOLDOWN_SECONDS:
                    retry_after = max(1, int(PASSWORD_RESET_RESEND_COOLDOWN_SECONDS - elapsed))
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=(
                            f"Повторная отправка кода возможна через {retry_after} с. "
                            "Подождите или используйте код из предыдущего письма."
                        ),
                        headers={"Retry-After": str(retry_after)},
                    )

            await user_dao.update(
                user_for_email,
                {
                    "password_reset_code_hash": code_hash,
                    "password_reset_expires_at": code_expires_at,
                    "password_reset_attempts_left": PASSWORD_RESET_MAX_ATTEMPTS,
                    "password_reset_last_sent_at": now_utc,
                    "password_reset_token_hash": None,
                    "password_reset_verified_at": None,
                },
            )

    try:
        await _send_password_reset_email_code(normalized_email, code)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_502_BAD_GATEWAY:
            async with async_session_maker() as session:
                user_dao = UserDAO(session)
                async with session.begin():
                    user = await user_dao.find_one_by_filter(email=normalized_email)
                    if user:
                        await user_dao.update(user, {"password_reset_last_sent_at": None})
        raise

    return JSONResponse(
        content={
            "status": "code_sent_if_exists",
            "detail": "Если email существует, код восстановления отправлен.",
            "expires_in_seconds": PASSWORD_RESET_CODE_TTL_MINUTES * 60,
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/password-reset/verify",
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60, scope="users_password_reset_verify"))],
)
async def verify_password_reset_code(payload: PasswordResetVerifyRequest):
    normalized_email = _validate_email_or_422(payload.email)
    code_hash = _hash_password_reset_code(payload.code)
    now_utc = _utc_now_naive()
    reset_token = _generate_password_reset_token()
    reset_token_hash = _hash_password_reset_token(reset_token)
    token_expires_at = now_utc + timedelta(minutes=PASSWORD_RESET_TOKEN_TTL_MINUTES)

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(email=normalized_email)
            if not user or not user.password_reset_code_hash or not user.password_reset_expires_at:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный код восстановления",
                )

            if user.password_reset_expires_at < now_utc:
                await user_dao.update(
                    user,
                    {
                        "password_reset_code_hash": None,
                        "password_reset_expires_at": None,
                        "password_reset_attempts_left": 0,
                        "password_reset_token_hash": None,
                        "password_reset_verified_at": None,
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Код восстановления истек",
                )

            if user.password_reset_attempts_left <= 0:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Превышено число попыток ввода кода",
                )

            if user.password_reset_code_hash != code_hash:
                attempts_left = max(0, user.password_reset_attempts_left - 1)
                await user_dao.update(user, {"password_reset_attempts_left": attempts_left})
                if attempts_left == 0:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Превышено число попыток ввода кода",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Неверный код. Осталось попыток: {attempts_left}",
                )

            await user_dao.update(
                user,
                {
                    "password_reset_code_hash": None,
                    "password_reset_attempts_left": 0,
                    "password_reset_token_hash": reset_token_hash,
                    "password_reset_verified_at": now_utc,
                    "password_reset_expires_at": token_expires_at,
                },
            )

    return JSONResponse(
        content={
            "status": "verified",
            "reset_token": reset_token,
            "expires_in_seconds": PASSWORD_RESET_TOKEN_TTL_MINUTES * 60,
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/password-reset/confirm",
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, scope="users_password_reset_confirm"))],
)
async def confirm_password_reset(payload: PasswordResetConfirmRequest):
    normalized_email = _validate_email_or_422(payload.email)
    token_hash = _hash_password_reset_token(payload.reset_token)
    now_utc = _utc_now_naive()

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(email=normalized_email)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Сессия восстановления не найдена",
                )

            if (
                not user.password_reset_token_hash
                or not user.password_reset_expires_at
                or user.password_reset_token_hash != token_hash
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный или устаревший токен восстановления",
                )

            if user.password_reset_expires_at < now_utc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Сессия восстановления истекла",
                )

            await user_dao.update(
                user,
                {
                    "password": get_password_hash(payload.new_password),
                    "password_reset_code_hash": None,
                    "password_reset_expires_at": None,
                    "password_reset_attempts_left": 0,
                    "password_reset_last_sent_at": None,
                    "password_reset_token_hash": None,
                    "password_reset_verified_at": None,
                },
            )

            sessions = (
                await session.scalars(
                    select(UserAuthSession).where(
                        UserAuthSession.user_id == user.id,
                        UserAuthSession.revoked_at.is_(None),
                    )
                )
            ).all()
            for auth_session in sessions:
                auth_session.revoked_at = now_utc

    return JSONResponse(
        content={"status": "password_updated"},
        status_code=status.HTTP_200_OK,
    )


@router.post("/login", dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, scope="users_login"))])
async def user_login(login_user: LoginUser):
    login_value = login_user.name.strip()
    async with async_session_maker() as session:
        user_dao = UserDAO(session)

        async with session.begin():
            user = await user_dao.find_one_by_filter(name=login_value)
            if not user and "@" in login_value:
                user = await user_dao.find_one_by_filter(email=_normalize_email(login_value))

    if not user or (not user.password) or (not verify_password(login_user.password, user.password)):
        logger.info("Неуспешная попытка входа для логина: %s", login_value)
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверные учетные данные"
        )
    if user.is_banned:
        logger.info("Заблокированный пользователь попытался войти: %s", login_user.name)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь заблокирован",
        )
    if user.email and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Подтвердите email перед входом",
        )

    logger.info(f"{login_user.name} вошел в систему")

    async with async_session_maker() as session:
        async with session.begin():
            access_token, refresh_token = await _issue_user_tokens(session, user.id)

    return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }


@router.post("/refresh", dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60, scope="users_refresh"))])
async def refresh_user_tokens(payload: RefreshTokenRequest):
    refresh_token = payload.refresh_token.strip()
    refresh_token_hash = _hash_refresh_token(refresh_token)
    now_utc = _utc_now_naive()

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            auth_session = await session.scalar(
                select(UserAuthSession).where(UserAuthSession.refresh_token_hash == refresh_token_hash)
            )
            if not auth_session or auth_session.revoked_at is not None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is invalid")
            if auth_session.expires_at < now_utc:
                auth_session.revoked_at = now_utc
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is expired")

            user = await user_dao.find_one_by_filter(id=auth_session.user_id)
            if not user:
                auth_session.revoked_at = now_utc
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
            if user.is_banned:
                auth_session.revoked_at = now_utc
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

            new_refresh_token = _generate_refresh_token()
            auth_session.refresh_token_hash = _hash_refresh_token(new_refresh_token)
            auth_session.expires_at = _build_refresh_expiry()
            auth_session.last_refreshed_at = now_utc

            access_token = create_access_token(
                {"user_id": str(user.id), "sid": auth_session.id},
                token_kind="user",
            )

    return JSONResponse(
        content={
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/logout")
async def user_logout(
    current_user=Depends(get_current_user_required),
    http_credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
):
    if not http_credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    payload = decode_access_token_payload(http_credentials.credentials, "user")
    session_id = payload.get("sid")
    if not session_id:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    now_utc = _utc_now_naive()
    async with async_session_maker() as session:
        async with session.begin():
            auth_session = await session.scalar(
                select(UserAuthSession).where(
                    UserAuthSession.id == str(session_id),
                    UserAuthSession.user_id == current_user.id,
                    UserAuthSession.revoked_at.is_(None),
                )
            )
            if auth_session:
                auth_session.revoked_at = now_utc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout_all")
async def user_logout_all(current_user=Depends(get_current_user_required)):
    now_utc = _utc_now_naive()
    async with async_session_maker() as session:
        async with session.begin():
            sessions = (
                await session.scalars(
                    select(UserAuthSession).where(
                        UserAuthSession.user_id == current_user.id,
                        UserAuthSession.revoked_at.is_(None),
                    )
                )
            ).all()
            for auth_session in sessions:
                auth_session.revoked_at = now_utc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
async def user_me(current_user=Depends(get_current_user_required)):
    return JSONResponse(
        content={
            "id": current_user.id,
            "name": current_user.name,
            "telegram_id": current_user.telegram_id,
            "is_telegram_linked": current_user.telegram_id is not None,
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/telegram-link/start")
async def start_telegram_link(payload: TelegramLinkStartRequest, current_user=Depends(get_current_user_required)):
    if current_user.telegram_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Telegram already linked",
        )

    normalized_tg_username = _normalize_tg_username(payload.telegram_username)
    now_utc = _utc_now_naive()
    expires_at = now_utc + timedelta(minutes=LINK_CODE_TTL_MINUTES)
    code = ""
    target_telegram_id: int | None = None

    async with async_session_maker() as session:
        challenge_dao = TelegramLinkChallengeDAO(session)
        user_dao = UserDAO(session)
        async with session.begin():
            target_user = await user_dao.find_telegram_user_by_normalized_name(normalized_tg_username)
            if not target_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Telegram user not found. Ask user to start master bot first.",
                )

            code = _generate_link_code()
            code_hash = _hash_link_code(code)
            target_telegram_id = int(target_user.telegram_id)

            stale_challenges = await challenge_dao.find_pending_by_user_id(current_user.id)
            for challenge in stale_challenges:
                await challenge_dao.update(challenge, {"status": "expired"})

            await challenge_dao.add(
                {
                    "user_id": current_user.id,
                    "target_telegram_id": target_telegram_id,
                    "code_hash": code_hash,
                    "expires_at": expires_at,
                    "attempts_left": LINK_CODE_MAX_ATTEMPTS,
                    "status": "pending",
                }
            )
    if target_telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Telegram target is not set",
        )
    await _send_master_bot_link_prompt(target_telegram_id)

    return JSONResponse(
        content={
            "code": _format_link_code(code),
            "expires_at": expires_at.replace(tzinfo=timezone.utc).isoformat(),
            "expires_in_seconds": LINK_CODE_TTL_MINUTES * 60,
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/telegram-link/confirm")
async def confirm_telegram_link(payload: TelegramLinkConfirmRequest, _internal=Depends(verify_internal_key)):
    normalized_code = _normalize_link_code(payload.code)
    code_hash = _hash_link_code(normalized_code)
    now_utc = _utc_now_naive()

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        agent_dao = AgentDAO(session)
        challenge_dao = TelegramLinkChallengeDAO(session)
        async with session.begin():
            challenge = await challenge_dao.find_pending_by_code_and_target(
                code_hash=code_hash,
                target_telegram_id=payload.telegram_id,
            )
            if not challenge:
                latest_challenge = await challenge_dao.find_latest_pending_by_target_telegram_id(
                    target_telegram_id=payload.telegram_id
                )
                if latest_challenge:
                    new_attempts = max(0, latest_challenge.attempts_left - 1)
                    new_status = "blocked" if new_attempts == 0 else "pending"
                    await challenge_dao.update(
                        latest_challenge,
                        {"attempts_left": new_attempts, "status": new_status},
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid link code",
                )

            if challenge.expires_at < now_utc:
                await challenge_dao.update(challenge, {"status": "expired"})
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Link code expired",
                )

            if challenge.attempts_left <= 0:
                await challenge_dao.update(challenge, {"status": "blocked"})
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Link code blocked",
                )

            user = await user_dao.find_one_by_filter(id=challenge.user_id)
            if not user:
                await challenge_dao.update(challenge, {"status": "expired"})
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User for link code not found",
                )

            linked_user = await user_dao.find_one_by_filter(telegram_id=payload.telegram_id)
            if linked_user and linked_user.id != challenge.user_id:
                # Auto-resolve "telegram-only" records created by master-bot bootstrap flow.
                # Those records have no password and can safely release telegram_id
                # so it can be attached to the authenticated web account.
                if linked_user.password is None:
                    # Preserve all agents created from Telegram account before linking.
                    linked_user_agents = await agent_dao.find_all_by_user_id(linked_user.id)
                    for linked_agent in linked_user_agents:
                        linked_agent.user_id = user.id
                    await user_dao.update(linked_user, {"telegram_id": None})
                    # Ensure unique index slot is released before assigning telegram_id to target user.
                    await session.flush()
                else:
                    await challenge_dao.update(
                        challenge,
                        {"attempts_left": max(0, challenge.attempts_left - 1)},
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Telegram ID already linked to another account",
                    )

            if user.telegram_id and user.telegram_id != payload.telegram_id:
                await challenge_dao.update(
                    challenge,
                    {"attempts_left": max(0, challenge.attempts_left - 1)},
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User already linked to another Telegram account",
                )

            if user.telegram_id is None:
                await user_dao.update(user, {"telegram_id": payload.telegram_id})

            await challenge_dao.update(
                challenge,
                {"status": "consumed", "consumed_at": now_utc},
            )

            stale_challenges = await challenge_dao.find_pending_by_user_id_except(
                user_id=user.id,
                challenge_id=challenge.id,
            )
            for stale in stale_challenges:
                await challenge_dao.update(stale, {"status": "expired"})

    return JSONResponse(
        content={
            "status": "linked",
            "user_id": user.id,
            "name": user.name,
            "telegram_id": payload.telegram_id,
        },
        status_code=status.HTTP_200_OK,
    )

