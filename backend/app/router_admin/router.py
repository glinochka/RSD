import asyncio
from datetime import datetime, timezone
from html import escape
import json
from logging import getLogger
import os
import re
from secrets import compare_digest
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import httpx
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.exc import UnknownHashError
from sqlalchemy import and_, func, or_, select, tuple_
from sqlalchemy.exc import IntegrityError

from .schemas import (
    AdminCreateUserRequest,
    AdminEmailBroadcastRequest,
    AdminEmailTargetedPreviewRequest,
    AdminFreeAgentActivationRequest,
    AdminGiftSubscriptionRequest,
    AdminLoginRequest,
    AdminPartnerPayoutUpdateRequest,
    AdminPromoCodeCreateRequest,
    AdminAgentTemplatePricingUpdateRequest,
    AdminSubscriptionPlansUpdateRequest,
    ArticlePublisherAddTopicsRequest,
    ArticlePublisherGenerateTopicsRequest,
    ArticlePublisherRunNowRequest,
    ArticlePublisherSettingsUpdateRequest,
    AdminTargetedBroadcastRequest,
)
from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentAnalyticsMessage, AgentFrozenUser, ArticlePublisherImage, PromoCode, User
from ..config import get_auth_data, settings
from ..qdrant.search_service import delete_agent_vectors
from ..router_agents.dao import AgentDAO
from ..router_documents.dao import DocumentDAO
from ..router_payments.dao import PaymentTransactionDAO, PromoCodeDAO, TurnkeyAgentRequestDAO
from ..router_referrals.dao import PartnerPayoutRequestDAO, PartnerPromoCodeDAO
from ..services.partner_payouts import (
    PAYOUT_STATUS_APPROVED,
    PAYOUT_STATUS_PAID,
    PAYOUT_STATUS_PENDING,
    PAYOUT_STATUS_REJECTED,
)
from ..router_payments.router import _calculate_new_end_date
from ..router_users.dao import UserDAO, UserErrorReportDAO
from .dao import ApplicationErrorLogDAO
from ..router_users.router import _build_unique_username, _validate_email_or_422
from ..agent_template_pricing import (
    AGENT_DURATION_DISCOUNT_BY_MONTHS,
    get_all_agent_template_pricing_admin,
    update_agent_template_pricing_overrides,
)
from ..subscription_plans import (
    get_all_subscription_plans,
    get_subscription_plan,
    update_subscription_plan_overrides,
)
from ..utils.email_list_parse import parse_emails_from_raw_text
from ..utils.JWT import create_access_token
from ..utils.rate_limit import rate_limit
from ..utils.security import get_password_hash, verify_password

logger = getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])
http_bearer = HTTPBearer(auto_error=False)

MAILOPOST_RATE_LIMIT_RETRY_RE = re.compile(r"try again in (\d+)\s*seconds?", re.IGNORECASE)
MAX_TARGETED_RECIPIENTS = 10_000
MAX_ALL_VERIFIED_BROADCAST_RECIPIENTS = 500_000
_admin_mass_mail_job_lock = asyncio.Lock()
_admin_mass_mail_jobs: dict[str, dict] = {}
_current_admin_mass_mail_job_id: str | None = None


def _mailopost_rate_limit_retry_seconds(response: httpx.Response) -> int | None:
    try:
        data = response.json()
    except Exception:
        return None
    for err in data.get("errors") or []:
        detail = str(err.get("detail", ""))
        match = MAILOPOST_RATE_LIMIT_RETRY_RE.search(detail)
        if match:
            return int(match.group(1))
    return None


def _render_broadcast_html(*, subject: str, body: str) -> str:
    safe_subject = escape(subject.strip())
    safe_lines = [escape(line.strip()) for line in body.splitlines() if line.strip()]
    rendered_lines = "".join(
        f"<tr><td style='padding:0 24px 10px 24px;color:#374151;font-size:14px;line-height:1.7;'>{line}</td></tr>"
        for line in safe_lines
    )
    return (
        "<!DOCTYPE html>"
        "<html><body style='margin:0;padding:0;background:#f5f7fb;font-family:Arial,sans-serif;'>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='background:#f5f7fb;padding:24px 12px;'>"
        "<tr><td align='center'>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='max-width:640px;background:#ffffff;border:1px solid #e8ecf3;border-radius:12px;overflow:hidden;'>"
        "<tr><td style='padding:24px 24px 10px 24px;'>"
        f"<div style='font-size:22px;font-weight:700;color:#111827;'>{safe_subject}</div>"
        "</td></tr>"
        f"{rendered_lines}"
        "<tr><td style='padding:8px 24px 24px 24px;color:#9ca3af;font-size:12px;line-height:1.6;'>"
        "Вы получили это письмо, потому что зарегистрированы в RSD."
        "</td></tr>"
        "</table>"
        "</td></tr></table>"
        "</body></html>"
    )


async def _post_mailopost_email_response(
    *, recipient: str, subject: str, plain_text: str, html: str
) -> httpx.Response:
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
        "to": recipient,
        "subject": subject,
        "text": plain_text,
        "html": html,
    }
    from_name = settings.MAILOPOST_FROM_NAME.strip()
    if from_name:
        payload["from_name"] = from_name

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(settings.MAILOPOST_SEND_TIMEOUT_SECONDS, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(f"{base_url}/email/messages", json=payload, headers=headers)


def _targeted_preview_stats(payload: AdminEmailTargetedPreviewRequest) -> tuple[list[str], dict]:
    selected = set(payload.selected_titles)
    per_group: dict[str, dict[str, int]] = {}
    seen_union: set[str] = set()
    ordered: list[str] = []

    for g in payload.groups:
        title = g.title.strip()
        if title not in selected:
            continue
        emails = parse_emails_from_raw_text(g.emails_raw)
        added_here = 0
        for email in emails:
            if email not in seen_union:
                seen_union.add(email)
                ordered.append(email)
                added_here += 1
        per_group[title] = {
            "parsed_in_group": len(emails),
            "new_unique_for_campaign": added_here,
        }

    return ordered, {"per_group": per_group, "unique_total": len(ordered)}


async def _send_one_targeted_with_backoff(
    *, recipient: str, subject: str, plain_text: str, html: str
) -> bool:
    max_attempts = 12
    for attempt in range(max_attempts):
        response = await _post_mailopost_email_response(
            recipient=recipient, subject=subject, plain_text=plain_text, html=html
        )
        if response.is_success:
            return True
        if response.status_code == 429:
            wait_sec = _mailopost_rate_limit_retry_seconds(response)
            if wait_sec is not None:
                await asyncio.sleep(min(wait_sec + 1, 7200))
                continue
        logger.error(
            "Targeted broadcast MailoPost error: status=%s body=%s recipient=%s attempt=%s",
            response.status_code,
            response.text[:500],
            recipient,
            attempt,
        )
        return False
    return False


async def _run_admin_mass_mail_job(
    job_id: str,
    *,
    recipients: list[str],
    subject: str,
    body: str,
    interval_seconds: int,
) -> None:
    global _current_admin_mass_mail_job_id
    job = _admin_mass_mail_jobs.get(job_id)
    if not job:
        return
    plain_text = f"{subject}\n\n{body}"
    html = _render_broadcast_html(subject=subject, body=body)
    try:
        for i, recipient in enumerate(recipients):
            job["progress_index"] = i
            job["last_recipient"] = recipient
            ok = await _send_one_targeted_with_backoff(
                recipient=recipient,
                subject=subject,
                plain_text=plain_text,
                html=html,
            )
            if ok:
                job["sent"] = job.get("sent", 0) + 1
            else:
                job["failed"] = job.get("failed", 0) + 1
            if i + 1 < len(recipients):
                await asyncio.sleep(interval_seconds)
        job["status"] = "completed"
    except Exception as exc:
        logger.exception("Targeted broadcast job %s failed", job_id)
        job["status"] = "failed"
        job["error"] = str(exc)
    finally:
        job["finished_at"] = datetime.now(timezone.utc).isoformat()
        job["last_recipient"] = None
        async with _admin_mass_mail_job_lock:
            if _current_admin_mass_mail_job_id == job_id:
                _current_admin_mass_mail_job_id = None


def _ensure_admin_credentials_configured() -> None:
    if not settings.ADMIN_WEB_LOGIN.strip() or not settings.ADMIN_WEB_PASSWORD_HASH.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_WEB_LOGIN / ADMIN_WEB_PASSWORD_HASH are not configured",
        )


def _decode_admin_token(token: str) -> dict:
    try:
        auth_data = get_auth_data("admin")
        payload = jwt.decode(token, auth_data["secret_key"], algorithms=[auth_data["algorithm"]])
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token is invalid",
        )

    exp = payload.get("exp")
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token is invalid",
        )

    expire_time = datetime.fromtimestamp(int(exp), tz=timezone.utc)
    if expire_time < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token is expired",
        )

    if payload.get("admin_web") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token is invalid",
        )
    if payload.get("token_kind") != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token is invalid",
        )

    return payload


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authorization required",
        )
    return _decode_admin_token(credentials.credentials)


def _serialize_promo_code(item: PromoCode) -> dict:
    return {
        "id": item.id,
        "code": item.code,
        "discount_percent": item.discount_percent,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _serialize_partner_payout_for_admin(item, partner_user: User | None) -> dict:
    return {
        "id": item.id,
        "partner_user_id": item.partner_user_id,
        "partner_name": partner_user.name if partner_user else None,
        "partner_email": partner_user.email if partner_user else None,
        "amount_kopecks": item.amount_kopecks,
        "payment_details": item.payment_details,
        "status": item.status,
        "admin_note": item.admin_note,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "processed_at": item.processed_at.isoformat() if item.processed_at else None,
    }


@router.post("/login", dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60, scope="admin_login"))])
async def admin_login(payload: AdminLoginRequest):
    _ensure_admin_credentials_configured()
    login = payload.login.strip()
    password = payload.password

    is_login_valid = compare_digest(login, settings.ADMIN_WEB_LOGIN.strip())
    if not is_login_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )
    try:
        is_password_valid = verify_password(password, settings.ADMIN_WEB_PASSWORD_HASH)
    except UnknownHashError:
        logger.exception("ADMIN_WEB_PASSWORD_HASH is invalid and cannot be parsed by passlib")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_WEB_PASSWORD_HASH is misconfigured",
        )
    if not is_password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )

    access_token = create_access_token({"admin_web": True}, token_kind="admin")
    return JSONResponse(
        content={
            "access_token": access_token,
            "token_type": "bearer",
        },
        status_code=status.HTTP_200_OK,
    )


@router.get("/stats")
async def admin_stats(_admin=Depends(get_current_admin)):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        agent_dao = AgentDAO(session)
        document_dao = DocumentDAO(session)
        payment_tx_dao = PaymentTransactionDAO(session)
        async with session.begin():
            total_users = await user_dao.count_for_admin()
            total_agents = await agent_dao.count_all()
            active_agents = await agent_dao.count_active()
            total_documents = await document_dao.count_all()
            paid_users = await user_dao.count_paid_users()
            total_payments = await payment_tx_dao.count_all()
            free_users = await user_dao.count_by_subscription_type("Free")
            advanced_users = await user_dao.count_by_subscription_type("Advanced")
            pro_users = await user_dao.count_by_subscription_type("Pro")

    return JSONResponse(
        content={
            "users_total": total_users or 0,
            "agents_total": total_agents or 0,
            "agents_active": active_agents or 0,
            "documents_total": total_documents or 0,
            "paid_users_total": paid_users or 0,
            "payments_total": total_payments or 0,
            "users_by_plan": {
                "Free": free_users or 0,
                "Advanced": advanced_users or 0,
                "Pro": pro_users or 0,
            },
        },
        status_code=status.HTTP_200_OK,
    )


@router.get("/users")
async def admin_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None),
    _admin=Depends(get_current_admin),
):
    search_value = (search or "").strip()

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            total = await user_dao.count_for_admin(search_value)
            users = await user_dao.list_for_admin(
                page=page,
                page_size=page_size,
                search_value=search_value,
            )

    items = [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "email_verified": user.email_verified,
            "telegram_id": user.telegram_id,
            "subscription_type": user.subscription_type,
            "subscription_end_date": (
                user.subscription_end_date.isoformat() if user.subscription_end_date else None
            ),
            "is_banned": user.is_banned,
            "free_agent_activation": user.free_agent_activation,
            "registered": user.registered.isoformat() if user.registered else None,
        }
        for user in users
    ]
    return JSONResponse(
        content={
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total or 0,
                "total_pages": max(1, ((total or 0) + page_size - 1) // page_size),
            },
        },
        status_code=status.HTTP_200_OK,
    )


def _serialize_admin_user(user) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "email_verified": user.email_verified,
        "telegram_id": user.telegram_id,
        "subscription_type": user.subscription_type,
        "subscription_end_date": (
            user.subscription_end_date.isoformat() if user.subscription_end_date else None
        ),
        "is_banned": user.is_banned,
        "free_agent_activation": user.free_agent_activation,
        "registered": user.registered.isoformat() if user.registered else None,
    }


@router.post("/users")
async def admin_create_user(
    payload: AdminCreateUserRequest,
    _admin=Depends(get_current_admin),
):
    normalized_email = _validate_email_or_422(payload.email)
    password_hash = get_password_hash(payload.password)
    verified_fields = {
        "password": password_hash,
        "email_verified": True,
        "email_verification_code_hash": None,
        "email_verification_expires_at": None,
        "email_verification_attempts_left": 0,
        "email_verification_last_sent_at": None,
    }

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            existing_user = await user_dao.find_one_by_filter(email=normalized_email)

            if payload.telegram_id is not None:
                telegram_owner = await user_dao.find_one_by_filter(telegram_id=payload.telegram_id)
                if telegram_owner and (
                    not existing_user or telegram_owner.id != existing_user.id
                ):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Telegram ID уже привязан к другому аккаунту",
                    )

            if existing_user:
                if existing_user.email_verified:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Email уже используется",
                    )
                await user_dao.update(
                    existing_user,
                    {
                        **verified_fields,
                        "telegram_id": payload.telegram_id,
                    },
                )
                await session.flush()
                await session.refresh(existing_user)
                logger.info(
                    "Admin activated unverified user id=%d email=%s",
                    existing_user.id,
                    normalized_email,
                )
                return JSONResponse(
                    content={"item": _serialize_admin_user(existing_user), "created": False},
                    status_code=status.HTTP_200_OK,
                )

            generated_name = await _build_unique_username(user_dao, normalized_email)
            try:
                user = await user_dao.add(
                    {
                        "name": generated_name,
                        "email": normalized_email,
                        **verified_fields,
                        "telegram_id": payload.telegram_id,
                    }
                )
                await session.flush()
            except IntegrityError:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email уже используется",
                )

    logger.info("Admin created user id=%d email=%s", user.id, normalized_email)
    return JSONResponse(
        content={"item": _serialize_admin_user(user), "created": True},
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/agents")
async def admin_agents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None),
    _admin=Depends(get_current_admin),
):
    search_value = (search or "").strip()

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            total = await agent_dao.count_for_admin(search_value)
            rows = await agent_dao.list_for_admin(
                page=page,
                page_size=page_size,
                search_value=search_value,
            )

    items = [
        {
            "id": row.id,
            "bot_id": row.bot_id,
            "bot_username": row.bot_username,
            "is_active": row.is_active,
            "owner_name": row.owner_name,
            "owner_subscription_type": row.owner_subscription_type,
            "registered": row.registered.isoformat() if row.registered else None,
        }
        for row in rows
    ]
    return JSONResponse(
        content={
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total or 0,
                "total_pages": max(1, ((total or 0) + page_size - 1) // page_size),
            },
        },
        status_code=status.HTTP_200_OK,
    )


@router.get("/chats")
async def admin_chats(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None),
    agent_id: int | None = Query(default=None, ge=1),
    agent_username: str | None = Query(default=None),
    messages_per_chat: int = Query(default=50, ge=1, le=200),
    _admin=Depends(get_current_admin),
):
    search_value = (search or "").strip().lower()
    agent_username_value = (agent_username or "").strip().lower()
    supported_chat_channels = {
        "telegram",
        "telegram_userbot",
        "max_bot",
        "max_userbot",
        "whatsapp_userbot",
        "phone",
        "external_api",
    }

    async with async_session_maker() as session:
        async with session.begin():
            base_where = [
                AgentAnalyticsMessage.role == "user",
                AgentAnalyticsMessage.user_external_id.is_not(None),
                AgentAnalyticsMessage.channel.in_(supported_chat_channels),
            ]
            if search_value:
                like_pattern = f"%{search_value}%"
                base_where.append(
                    func.lower(
                        func.coalesce(AgentAnalyticsMessage.user_display_name, "")
                    ).like(like_pattern)
                    | func.lower(
                        func.coalesce(AgentAnalyticsMessage.user_external_id, "")
                    ).like(like_pattern)
                    | func.lower(func.coalesce(Agent.bot_username, "")).like(like_pattern)
                )
            if agent_id is not None:
                base_where.append(AgentAnalyticsMessage.agent_id == agent_id)
            if agent_username_value:
                base_where.append(
                    func.lower(func.coalesce(Agent.bot_username, "")).like(f"%{agent_username_value}%")
                )

            total_query = (
                select(func.count())
                .select_from(
                    select(
                        AgentAnalyticsMessage.agent_id,
                        AgentAnalyticsMessage.user_external_id,
                        AgentAnalyticsMessage.channel,
                    )
                    .join(Agent, Agent.id == AgentAnalyticsMessage.agent_id)
                    .where(*base_where)
                    .group_by(
                        AgentAnalyticsMessage.agent_id,
                        AgentAnalyticsMessage.user_external_id,
                        AgentAnalyticsMessage.channel,
                    )
                    .subquery()
                )
            )
            total = int((await session.scalar(total_query)) or 0)

            chats_query = (
                select(
                    AgentAnalyticsMessage.agent_id.label("agent_id"),
                    AgentAnalyticsMessage.bot_id.label("bot_id"),
                    AgentAnalyticsMessage.user_external_id.label("user_external_id"),
                    AgentAnalyticsMessage.channel.label("chat_channel"),
                    func.max(AgentAnalyticsMessage.user_display_name).label("user_display_name"),
                    func.count(AgentAnalyticsMessage.id).label("questions_count"),
                    func.max(AgentAnalyticsMessage.created_at).label("last_message_at"),
                    func.max(Agent.bot_username).label("agent_bot_username"),
                )
                .join(Agent, Agent.id == AgentAnalyticsMessage.agent_id)
                .where(*base_where)
                .group_by(
                    AgentAnalyticsMessage.agent_id,
                    AgentAnalyticsMessage.bot_id,
                    AgentAnalyticsMessage.user_external_id,
                    AgentAnalyticsMessage.channel,
                )
                .order_by(func.max(AgentAnalyticsMessage.created_at).desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            chat_rows = (await session.execute(chats_query)).mappings().all()

            if not chat_rows:
                return JSONResponse(
                    content={
                        "items": [],
                        "pagination": {
                            "page": page,
                            "page_size": page_size,
                            "total": total,
                            "total_pages": max(1, (total + page_size - 1) // page_size),
                        },
                    },
                    status_code=status.HTTP_200_OK,
                )

            chat_pairs = [
                (row["agent_id"], row["user_external_id"])
                for row in chat_rows
                if row["agent_id"] is not None and row["user_external_id"] is not None
            ]
            frozen_rows = await session.execute(
                select(AgentFrozenUser.agent_id, AgentFrozenUser.user_external_id).where(
                    tuple_(AgentFrozenUser.agent_id, AgentFrozenUser.user_external_id).in_(chat_pairs)
                )
            )
            frozen_pairs = {
                (agent_id, user_external_id)
                for agent_id, user_external_id in frozen_rows.all()
            }

            message_filters = [
                and_(
                    AgentAnalyticsMessage.agent_id == row["agent_id"],
                    AgentAnalyticsMessage.user_external_id == row["user_external_id"],
                    AgentAnalyticsMessage.channel.in_([row["chat_channel"], "dashboard"]),
                )
                for row in chat_rows
            ]
            messages_query = (
                select(
                    AgentAnalyticsMessage.agent_id,
                    AgentAnalyticsMessage.user_external_id,
                    AgentAnalyticsMessage.channel,
                    AgentAnalyticsMessage.role,
                    AgentAnalyticsMessage.message_text,
                    AgentAnalyticsMessage.created_at,
                )
                .where(or_(*message_filters))
                .order_by(AgentAnalyticsMessage.created_at.asc())
            )
            message_rows = (await session.execute(messages_query)).mappings().all()

    grouped_messages: dict[tuple[int, str, str], list[dict]] = {}
    for row in message_rows:
        if row["channel"] == "dashboard":
            continue
        key = (row["agent_id"], row["user_external_id"], row["channel"])
        grouped_messages.setdefault(key, []).append(
            {
                "role": row["role"],
                "channel": row["channel"],
                "text": row["message_text"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        )

    for row in message_rows:
        if row["channel"] != "dashboard":
            continue
        for chat_row in chat_rows:
            if (
                chat_row["agent_id"] == row["agent_id"]
                and chat_row["user_external_id"] == row["user_external_id"]
            ):
                key = (
                    chat_row["agent_id"],
                    chat_row["user_external_id"],
                    chat_row["chat_channel"],
                )
                grouped_messages.setdefault(key, []).append(
                    {
                        "role": row["role"],
                        "channel": row["channel"],
                        "text": row["message_text"],
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    }
                )

    items = []
    for row in chat_rows:
        key = (row["agent_id"], row["user_external_id"], row["chat_channel"])
        messages = grouped_messages.get(key, [])
        if messages_per_chat > 0 and len(messages) > messages_per_chat:
            messages = messages[-messages_per_chat:]

        items.append(
            {
                "chat_key": f"{row['agent_id']}:{row['chat_channel']}:{row['user_external_id']}",
                "agent_id": row["agent_id"],
                "agent_bot_id": row["bot_id"],
                "agent_bot_username": row["agent_bot_username"],
                "chat_channel": row["chat_channel"],
                "user_external_id": row["user_external_id"],
                "user_display_name": row["user_display_name"] or f"User {row['user_external_id']}",
                "questions_count": int(row["questions_count"] or 0),
                "last_message_at": row["last_message_at"].isoformat() if row["last_message_at"] else None,
                "is_frozen": (row["agent_id"], row["user_external_id"]) in frozen_pairs,
                "messages": messages,
            }
        )

    return JSONResponse(
        content={
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": max(1, (total + page_size - 1) // page_size),
            },
        },
        status_code=status.HTTP_200_OK,
    )


@router.get("/turnkey-requests")
async def admin_turnkey_requests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None),
    _admin=Depends(get_current_admin),
):
    search_value = (search or "").strip()

    async with async_session_maker() as session:
        turnkey_request_dao = TurnkeyAgentRequestDAO(session)
        async with session.begin():
            total = await turnkey_request_dao.count_for_admin(search_value)
            items_data = await turnkey_request_dao.list_for_admin(
                page=page,
                page_size=page_size,
                search_value=search_value,
            )

    items = [
        {
            "id": item.id,
            "phone_number": item.phone_number,
            "email": item.email,
            "requested_agent": item.requested_agent,
            "purpose": item.purpose,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in items_data
    ]

    return JSONResponse(
        content={
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total or 0,
                "total_pages": max(1, ((total or 0) + page_size - 1) // page_size),
            },
        },
        status_code=status.HTTP_200_OK,
    )


@router.get("/error-reports")
async def admin_error_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None),
    _admin=Depends(get_current_admin),
):
    search_value = (search or "").strip()

    async with async_session_maker() as session:
        report_dao = UserErrorReportDAO(session)
        async with session.begin():
            total = await report_dao.count_for_admin(search_value or None)
            rows = await report_dao.list_for_admin(
                page=page,
                page_size=page_size,
                search_value=search_value or None,
            )

    items = []
    for row in rows:
        u = row.user
        items.append(
            {
                "id": row.id,
                "description": row.description,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "user": {
                    "id": u.id,
                    "name": u.name,
                    "email": u.email,
                },
            }
        )

    return JSONResponse(
        content={
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total or 0,
                "total_pages": max(1, ((total or 0) + page_size - 1) // page_size),
            },
        },
        status_code=status.HTTP_200_OK,
    )


def _serialize_error_log_row(row) -> dict:
    user = row.user
    return {
        "id": row.id,
        "level": row.level,
        "source": row.source,
        "scenario": row.scenario,
        "error_type": row.error_type,
        "message": row.message,
        "traceback": row.traceback,
        "context": row.context_json,
        "status_code": row.status_code,
        "is_resolved": row.is_resolved,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "user": (
            {
                "id": user.id,
                "name": user.name,
                "email": user.email,
            }
            if user
            else None
        ),
    }


@router.get("/logs")
async def admin_application_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    level: str | None = Query(default=None),
    source: str | None = Query(default=None),
    is_resolved: bool | None = Query(default=None),
    _admin=Depends(get_current_admin),
):
    search_value = (search or "").strip()
    level_value = (level or "").strip() or None
    source_value = (source or "").strip() or None

    async with async_session_maker() as session:
        log_dao = ApplicationErrorLogDAO(session)
        async with session.begin():
            total = await log_dao.count_for_admin(
                search_value=search_value or None,
                level=level_value,
                source=source_value,
                is_resolved=is_resolved,
            )
            rows = await log_dao.list_for_admin(
                page=page,
                page_size=page_size,
                search_value=search_value or None,
                level=level_value,
                source=source_value,
                is_resolved=is_resolved,
            )

    items = [_serialize_error_log_row(row) for row in rows]

    return JSONResponse(
        content={
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total or 0,
                "total_pages": max(1, ((total or 0) + page_size - 1) // page_size),
            },
        },
        status_code=status.HTTP_200_OK,
    )


@router.get("/logs/{log_id}")
async def admin_application_log_detail(
    log_id: int = Path(..., ge=1),
    _admin=Depends(get_current_admin),
):
    async with async_session_maker() as session:
        log_dao = ApplicationErrorLogDAO(session)
        async with session.begin():
            row = await log_dao.get_by_id(log_id)

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found")

    return JSONResponse(content=_serialize_error_log_row(row), status_code=status.HTTP_200_OK)


@router.patch("/logs/{log_id}/resolve")
async def admin_application_log_resolve(
    log_id: int = Path(..., ge=1),
    _admin=Depends(get_current_admin),
):
    async with async_session_maker() as session:
        log_dao = ApplicationErrorLogDAO(session)
        async with session.begin():
            row = await log_dao.get_by_id(log_id)
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found")
            await log_dao.update(
                row,
                {
                    "is_resolved": True,
                    "resolved_at": datetime.now(timezone.utc).replace(tzinfo=None),
                },
            )
            await session.flush()

    return JSONResponse(content={"ok": True}, status_code=status.HTTP_200_OK)


@router.get("/plans")
async def admin_plans(_admin=Depends(get_current_admin)):
    return JSONResponse(
        content={"plans": get_all_subscription_plans()},
        status_code=status.HTTP_200_OK,
    )


@router.put("/plans")
async def admin_update_plans(
    payload: AdminSubscriptionPlansUpdateRequest,
    _admin=Depends(get_current_admin),
):
    plan_updates = [p.model_dump() for p in payload.plans]
    update_subscription_plan_overrides(plan_updates=plan_updates)
    return JSONResponse(
        content={"plans": get_all_subscription_plans()},
        status_code=status.HTTP_200_OK,
    )


@router.get("/agent-template-pricing")
async def admin_agent_template_pricing(_admin=Depends(get_current_admin)):
    return JSONResponse(
        content={
            "templates": get_all_agent_template_pricing_admin(),
            "duration_discounts": dict(AGENT_DURATION_DISCOUNT_BY_MONTHS),
        },
        status_code=status.HTTP_200_OK,
    )


@router.put("/agent-template-pricing")
async def admin_update_agent_template_pricing(
    payload: AdminAgentTemplatePricingUpdateRequest,
    _admin=Depends(get_current_admin),
):
    template_updates = [t.model_dump() for t in payload.templates]
    update_agent_template_pricing_overrides(template_updates=template_updates)
    return JSONResponse(
        content={
            "templates": get_all_agent_template_pricing_admin(),
            "duration_discounts": dict(AGENT_DURATION_DISCOUNT_BY_MONTHS),
        },
        status_code=status.HTTP_200_OK,
    )


@router.get("/promo-codes")
async def admin_list_promo_codes(_admin=Depends(get_current_admin)):
    async with async_session_maker() as session:
        promo_code_dao = PromoCodeDAO(session)
        async with session.begin():
            rows = await promo_code_dao.list_all_desc()

    return JSONResponse(
        content={"items": [_serialize_promo_code(row) for row in rows]},
        status_code=status.HTTP_200_OK,
    )


@router.post("/promo-codes")
async def admin_create_promo_code(
    payload: AdminPromoCodeCreateRequest,
    _admin=Depends(get_current_admin),
):
    code = payload.code.strip().upper()
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Promo code is required")

    async with async_session_maker() as session:
        promo_code_dao = PromoCodeDAO(session)
        partner_promo_dao = PartnerPromoCodeDAO(session)
        async with session.begin():
            existing = await promo_code_dao.find_by_code_case_insensitive(code)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Promo code already exists",
                )
            if await partner_promo_dao.find_by_code_case_insensitive(code):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Promo code already exists",
                )

            item = await promo_code_dao.add(
                {
                    "code": code,
                    "discount_percent": payload.discount_percent,
                }
            )
            await session.flush()
            await session.refresh(item)

    return JSONResponse(
        content={"item": _serialize_promo_code(item)},
        status_code=status.HTTP_201_CREATED,
    )


@router.delete("/promo-codes/{promo_code_id}")
async def admin_delete_promo_code(
    promo_code_id: int = Path(..., ge=1),
    _admin=Depends(get_current_admin),
):
    async with async_session_maker() as session:
        promo_code_dao = PromoCodeDAO(session)
        async with session.begin():
            item = await promo_code_dao.find_one_by_filter(id=promo_code_id)
            if not item:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promo code not found")
            await promo_code_dao.delete(item)

    return JSONResponse(content={"detail": "Promo code deleted"}, status_code=status.HTTP_200_OK)


@router.get("/partner-payouts")
async def admin_list_partner_payouts(
    status_filter: str | None = Query(default=None, alias="status"),
    _admin=Depends(get_current_admin),
):
    async with async_session_maker() as session:
        payout_dao = PartnerPayoutRequestDAO(session)
        user_dao = UserDAO(session)
        async with session.begin():
            rows = await payout_dao.list_for_admin(status=status_filter)
            partner_ids = {row.partner_user_id for row in rows}
            partners_by_id: dict[int, User] = {}
            for partner_id in partner_ids:
                partner = await user_dao.find_one_by_filter(id=partner_id)
                if partner:
                    partners_by_id[partner_id] = partner

    return JSONResponse(
        content={
            "items": [
                _serialize_partner_payout_for_admin(row, partners_by_id.get(row.partner_user_id))
                for row in rows
            ],
        },
        status_code=status.HTTP_200_OK,
    )


@router.patch("/partner-payouts/{payout_id}")
async def admin_update_partner_payout(
    payload: AdminPartnerPayoutUpdateRequest,
    payout_id: int = Path(..., ge=1),
    _admin=Depends(get_current_admin),
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with async_session_maker() as session:
        payout_dao = PartnerPayoutRequestDAO(session)
        user_dao = UserDAO(session)
        async with session.begin():
            item = await payout_dao.find_one_by_filter(id=payout_id)
            if not item:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")

            if payload.action == "approve":
                if item.status != PAYOUT_STATUS_PENDING:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Одобрить можно только заявку в статусе «ожидает»",
                    )
                await payout_dao.update(
                    item,
                    {
                        "status": PAYOUT_STATUS_APPROVED,
                        "admin_note": payload.admin_note or item.admin_note,
                        "updated_at": now,
                    },
                )
            elif payload.action == "reject":
                if item.status not in (PAYOUT_STATUS_PENDING, PAYOUT_STATUS_APPROVED):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Отклонить можно только необработанную заявку",
                    )
                await payout_dao.update(
                    item,
                    {
                        "status": PAYOUT_STATUS_REJECTED,
                        "admin_note": payload.admin_note,
                        "updated_at": now,
                        "processed_at": now,
                    },
                )
            elif payload.action == "mark_paid":
                if item.status != PAYOUT_STATUS_APPROVED:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Отметить выплату можно только для одобренной заявки",
                    )
                await payout_dao.update(
                    item,
                    {
                        "status": PAYOUT_STATUS_PAID,
                        "admin_note": payload.admin_note or item.admin_note,
                        "updated_at": now,
                        "processed_at": now,
                    },
                )

            partner = await user_dao.find_one_by_filter(id=item.partner_user_id)

    return JSONResponse(
        content={"item": _serialize_partner_payout_for_admin(item, partner)},
        status_code=status.HTTP_200_OK,
    )


@router.post("/users/{user_id}/ban")
async def admin_ban_user(
    user_id: int = Path(...),
    _admin=Depends(get_current_admin),
):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        agent_dao = AgentDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(load_relations=True, id=user_id)
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            if user.is_banned:
                return JSONResponse(content={"detail": "Already banned"}, status_code=status.HTTP_200_OK)

            for agent in list(user.agents or []):
                if agent.bot_id:
                    await delete_agent_vectors(agent.bot_id)
                await agent_dao.delete(agent)

            await user_dao.update(user, {"is_banned": True})
            await session.flush()

    logger.info("User %s (id=%d) banned by admin", user.name, user_id)
    return JSONResponse(content={"detail": "User banned"}, status_code=status.HTTP_200_OK)


@router.post("/users/{user_id}/unban")
async def admin_unban_user(
    user_id: int = Path(...),
    _admin=Depends(get_current_admin),
):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(id=user_id)
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            if not user.is_banned:
                return JSONResponse(content={"detail": "User is not banned"}, status_code=status.HTTP_200_OK)
            await user_dao.update(user, {"is_banned": False})
            await session.flush()

    logger.info("User %s (id=%d) unbanned by admin", user.name, user_id)
    return JSONResponse(content={"detail": "User unbanned"}, status_code=status.HTTP_200_OK)


@router.post("/users/{user_id}/free-agent-activation")
async def admin_set_free_agent_activation(
    payload: AdminFreeAgentActivationRequest,
    user_id: int = Path(...),
    _admin=Depends(get_current_admin),
):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(id=user_id)
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            await user_dao.update(user, {"free_agent_activation": payload.enabled})
            await session.flush()

    logger.info(
        "Admin set free_agent_activation=%s for user id=%d",
        payload.enabled,
        user_id,
    )
    return JSONResponse(
        content={"free_agent_activation": payload.enabled},
        status_code=status.HTTP_200_OK,
    )


@router.post("/users/{user_id}/gift-subscription")
async def admin_gift_subscription(
    payload: AdminGiftSubscriptionRequest,
    user_id: int = Path(...),
    _admin=Depends(get_current_admin),
):
    plan = get_subscription_plan(payload.plan_code)
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown plan code")

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(id=user_id)
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

            new_end = _calculate_new_end_date(user.subscription_end_date)
            await user_dao.update(user, {
                "subscription_type": payload.plan_code,
                "subscription_end_date": new_end,
            })

    logger.info(
        "Admin gifted %s subscription to user id=%d until %s",
        payload.plan_code, user_id, new_end.isoformat(),
    )
    return JSONResponse(
        content={
            "subscription_type": payload.plan_code,
            "subscription_end_date": new_end.isoformat(),
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/email-broadcast")
async def admin_email_broadcast(
    payload: AdminEmailBroadcastRequest,
    _admin=Depends(get_current_admin),
):
    subject = payload.subject.strip()
    body = payload.body.strip()

    interval_seconds = payload.interval_seconds
    if interval_seconds is None:
        interval_seconds = settings.MAILOPOST_BROADCAST_INTERVAL_SECONDS
    interval_seconds = max(30, min(int(interval_seconds), 86_400))

    async with async_session_maker() as session:
        async with session.begin():
            emails = (
                await session.scalars(
                    select(User.email).where(
                        User.email.is_not(None),
                        User.email_verified.is_(True),
                    )
                )
            ).all()

    recipients = [e for e in emails if e]
    total = len(recipients)
    if total > MAX_ALL_VERIFIED_BROADCAST_RECIPIENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Слишком много получателей (максимум {MAX_ALL_VERIFIED_BROADCAST_RECIPIENTS})",
        )

    global _current_admin_mass_mail_job_id

    async with _admin_mass_mail_job_lock:
        if _current_admin_mass_mail_job_id:
            existing = _admin_mass_mail_jobs.get(_current_admin_mass_mail_job_id)
            if existing and existing.get("status") == "running":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Уже выполняется массовая рассылка. Дождитесь окончания "
                        "или запросите статус текущей задачи."
                    ),
                )
        job_id = str(uuid.uuid4())
        _admin_mass_mail_jobs[job_id] = {
            "id": job_id,
            "kind": "all_verified",
            "status": "running",
            "total": total,
            "sent": 0,
            "failed": 0,
            "progress_index": 0,
            "last_recipient": None,
            "error": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "interval_seconds": interval_seconds,
            "subject": subject,
            "preview": None,
        }
        _current_admin_mass_mail_job_id = job_id

    asyncio.create_task(
        _run_admin_mass_mail_job(
            job_id,
            recipients=recipients,
            subject=subject,
            body=body,
            interval_seconds=interval_seconds,
        )
    )

    logger.info(
        "Admin all-verified email broadcast queued: job_id=%s total=%s interval=%ss subject=%s",
        job_id,
        total,
        interval_seconds,
        subject,
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "job_id": job_id,
            "status": "started",
            "total_recipients": total,
            "interval_seconds": interval_seconds,
            "subject": subject,
        },
    )


@router.post("/email-targeted-preview")
async def admin_email_targeted_preview(
    payload: AdminEmailTargetedPreviewRequest,
    _admin=Depends(get_current_admin),
):
    _ordered, meta = _targeted_preview_stats(payload)
    return JSONResponse(
        content={
            **meta,
            "recipient_preview": _ordered[:8],
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/email-targeted-broadcast")
async def admin_email_targeted_broadcast(
    payload: AdminTargetedBroadcastRequest,
    _admin=Depends(get_current_admin),
):
    preview_payload = AdminEmailTargetedPreviewRequest(
        groups=payload.groups,
        selected_titles=payload.selected_titles,
    )
    recipients, meta = _targeted_preview_stats(preview_payload)
    if not recipients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет ни одного корректного email в выбранных группах",
        )
    if len(recipients) > MAX_TARGETED_RECIPIENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Слишком много получателей (максимум {MAX_TARGETED_RECIPIENTS})",
        )

    interval_seconds = payload.interval_seconds
    if interval_seconds is None:
        interval_seconds = settings.MAILOPOST_BROADCAST_INTERVAL_SECONDS
    interval_seconds = max(30, min(int(interval_seconds), 86_400))

    global _current_admin_mass_mail_job_id

    async with _admin_mass_mail_job_lock:
        if _current_admin_mass_mail_job_id:
            existing = _admin_mass_mail_jobs.get(_current_admin_mass_mail_job_id)
            if existing and existing.get("status") == "running":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Уже выполняется массовая рассылка. Дождитесь окончания "
                        "или запросите статус текущей задачи."
                    ),
                )
        job_id = str(uuid.uuid4())
        subject = payload.subject.strip()
        body = payload.body.strip()
        _admin_mass_mail_jobs[job_id] = {
            "id": job_id,
            "kind": "targeted",
            "status": "running",
            "total": len(recipients),
            "sent": 0,
            "failed": 0,
            "progress_index": 0,
            "last_recipient": None,
            "error": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "interval_seconds": interval_seconds,
            "subject": subject,
            "preview": meta,
        }
        _current_admin_mass_mail_job_id = job_id

    asyncio.create_task(
        _run_admin_mass_mail_job(
            job_id,
            recipients=recipients,
            subject=subject,
            body=body,
            interval_seconds=interval_seconds,
        )
    )

    logger.info(
        "Admin targeted email broadcast queued: job_id=%s total=%s interval=%ss subject=%s",
        job_id,
        len(recipients),
        interval_seconds,
        subject,
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "job_id": job_id,
            "status": "started",
            "total_recipients": len(recipients),
            "interval_seconds": interval_seconds,
            "preview": meta,
        },
    )


@router.get("/email-targeted-broadcast/jobs/{job_id}")
async def admin_email_targeted_broadcast_job_status(
    job_id: str = Path(...),
    _admin=Depends(get_current_admin),
):
    job = _admin_mass_mail_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
    return JSONResponse(content=job, status_code=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Article Publisher endpoints
# ---------------------------------------------------------------------------

def _get_article_publisher_service():
    from ..services.article_publisher.service import get_article_publisher_service
    return get_article_publisher_service()


@router.get("/article-publisher/settings")
async def ap_get_settings(_admin=Depends(get_current_admin)):
    service = _get_article_publisher_service()
    row = await service.get_settings()
    return JSONResponse(content={"settings": service.serialize_settings(row)})


@router.put("/article-publisher/settings")
async def ap_update_settings(
    payload: ArticlePublisherSettingsUpdateRequest,
    _admin=Depends(get_current_admin),
):
    from ..utils.crypto import encrypt_token

    service = _get_article_publisher_service()
    updates: dict = {}

    for field in (
        "posting_enabled", "posting_frequency_hours",
        "vcru_enabled", "vcru_email", "vcru_subsite_id",
        "zen_enabled", "zen_login", "zen_channel_id",
        "auto_topics_enabled", "promo_ratio",
        "company_name", "company_url", "company_description",
        "article_min_words", "article_max_words",
    ):
        val = getattr(payload, field, None)
        if val is not None:
            updates[field] = val

    if payload.topic_categories is not None:
        updates["topic_categories_json"] = json.dumps(
            [t.strip() for t in payload.topic_categories if t.strip()],
            ensure_ascii=False,
        )
    if payload.vcru_password is not None and payload.vcru_password.strip():
        updates["vcru_password_enc"] = encrypt_token(payload.vcru_password.strip())
    if payload.zen_password is not None and payload.zen_password.strip():
        updates["zen_password_enc"] = encrypt_token(payload.zen_password.strip())

    row = await service.update_settings(updates)
    return JSONResponse(content={"settings": service.serialize_settings(row)})


@router.get("/article-publisher/topics")
async def ap_list_topics(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    unused_only: bool = Query(default=False),
    _admin=Depends(get_current_admin),
):
    service = _get_article_publisher_service()
    rows, total = await service.list_topics(page=page, page_size=page_size, unused_only=unused_only)
    items = [
        {
            "id": r.id,
            "topic": r.topic,
            "source": r.source,
            "used": r.used,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return JSONResponse(
        content={
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.post("/article-publisher/topics")
async def ap_add_topics(
    payload: ArticlePublisherAddTopicsRequest,
    _admin=Depends(get_current_admin),
):
    service = _get_article_publisher_service()
    valid_topics = [t.strip() for t in payload.topics if t.strip()][:100]
    if not valid_topics:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid topics provided")
    added = await service.add_topics(valid_topics, source="manual")
    return JSONResponse(
        content={"added": len(added)},
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/article-publisher/topics/generate")
async def ap_generate_topics(
    payload: ArticlePublisherGenerateTopicsRequest,
    _admin=Depends(get_current_admin),
):
    from ..services.article_publisher.topic_generator import fetch_topics_from_search

    service = _get_article_publisher_service()
    categories = payload.categories
    if not categories:
        row = await service.get_settings()
        try:
            categories = json.loads(row.topic_categories_json or "[]")
        except Exception:
            categories = ["ИИ", "IT", "Автоматизация"]
    if not categories:
        categories = ["ИИ", "IT", "Автоматизация"]

    try:
        topics = await fetch_topics_from_search(categories, count=payload.count)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Topic generation failed: {exc}",
        )

    added = await service.add_topics(topics, source="auto")
    return JSONResponse(content={"added": len(added), "topics": topics})


@router.delete("/article-publisher/topics/{topic_id}")
async def ap_delete_topic(
    topic_id: int = Path(..., ge=1),
    _admin=Depends(get_current_admin),
):
    service = _get_article_publisher_service()
    deleted = await service.delete_topic(topic_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return JSONResponse(content={"detail": "deleted"})


@router.get("/article-publisher/images")
async def ap_list_images(_admin=Depends(get_current_admin)):
    service = _get_article_publisher_service()
    images = await service.list_images()
    return JSONResponse(content={"items": images})


@router.post("/article-publisher/images")
async def ap_upload_image(
    file: UploadFile = File(...),
    _admin=Depends(get_current_admin),
):
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, WEBP, GIF images are allowed",
        )
    max_size = 10 * 1024 * 1024
    data = await file.read()
    if len(data) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image too large (max 10 MB)",
        )
    service = _get_article_publisher_service()
    result = await service.save_image(
        file_bytes=data,
        original_name=file.filename or "upload.jpg",
        mime_type=file.content_type,
    )
    return JSONResponse(content={"image": result}, status_code=status.HTTP_201_CREATED)


@router.get("/article-publisher/images/{image_id}/file")
async def ap_serve_image(
    image_id: int = Path(..., ge=1),
):
    async with async_session_maker() as session:
        async with session.begin():
            row = await session.scalar(
                select(ArticlePublisherImage).where(ArticlePublisherImage.id == image_id)
            )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    from ..services.article_publisher.service import _get_images_dir
    path = os.path.join(_get_images_dir(), row.storage_filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image file not found")
    return FileResponse(path, media_type=row.mime_type or "image/jpeg")


@router.delete("/article-publisher/images/{image_id}")
async def ap_delete_image(
    image_id: int = Path(..., ge=1),
    _admin=Depends(get_current_admin),
):
    service = _get_article_publisher_service()
    deleted = await service.delete_image(image_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    return JSONResponse(content={"detail": "deleted"})


@router.get("/article-publisher/jobs")
async def ap_list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin=Depends(get_current_admin),
):
    service = _get_article_publisher_service()
    rows, total = await service.list_jobs(page=page, page_size=page_size)
    return JSONResponse(
        content={
            "items": [service.serialize_job(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.post("/article-publisher/run-now")
async def ap_run_now(
    payload: ArticlePublisherRunNowRequest,
    _admin=Depends(get_current_admin),
):
    """Trigger an immediate article generation + publish job."""
    import asyncio
    from ..services.article_publisher.worker import get_article_publisher_worker

    service = _get_article_publisher_service()
    settings_row = await service.get_settings()

    active_platforms = []
    if settings_row.vcru_enabled and settings_row.vcru_email and settings_row.vcru_password_enc:
        active_platforms.append("vcru")
    if settings_row.zen_enabled and settings_row.zen_login and settings_row.zen_password_enc:
        active_platforms.append("yandex_zen")

    platform = payload.platform
    if platform and platform not in ("vcru", "yandex_zen"):
        raise HTTPException(status_code=400, detail="platform must be 'vcru' or 'yandex_zen'")
    if not platform:
        if not active_platforms:
            raise HTTPException(status_code=400, detail="No active platforms configured")
        import random
        platform = random.choice(active_platforms)

    topic = (payload.topic or "").strip()
    if not topic:
        from ..services.article_publisher.topic_generator import fetch_topics_from_search
        topic = await service.pick_next_topic()
        if not topic:
            if settings_row.auto_topics_enabled:
                try:
                    cats = json.loads(settings_row.topic_categories_json or "[]") or ["ИИ", "IT"]
                    new_topics = await fetch_topics_from_search(cats, count=5)
                    if new_topics:
                        await service.add_topics(new_topics, source="auto")
                        topic = await service.pick_next_topic()
                except Exception:
                    pass
        if not topic:
            raise HTTPException(status_code=400, detail="No topics available. Add topics first.")

    is_promo = await service.determine_next_is_promo(settings_row.promo_ratio)
    from datetime import datetime, timezone
    job = await service.create_job(
        platform=platform,
        topic=topic,
        is_promo=is_promo,
        scheduled_for=datetime.now(timezone.utc).replace(tzinfo=None),
    )

    worker = get_article_publisher_worker()
    asyncio.create_task(
        worker._process_job(job_id=job.id, settings=settings_row, platform=platform)
    )

    return JSONResponse(
        content={
            "job_id": job.id,
            "platform": platform,
            "topic": topic,
            "is_promo": is_promo,
            "status": "started",
        },
        status_code=status.HTTP_202_ACCEPTED,
    )


@router.post("/article-publisher/preview-article")
async def ap_preview_article(
    payload: ArticlePublisherRunNowRequest,
    _admin=Depends(get_current_admin),
):
    """Generate article content without publishing."""
    from ..services.article_publisher.content_generator import generate_article

    service = _get_article_publisher_service()
    settings_row = await service.get_settings()

    topic = (payload.topic or "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic is required for preview")

    platform = payload.platform or "vcru"
    is_promo = await service.determine_next_is_promo(settings_row.promo_ratio)

    try:
        article = await generate_article(
            topic=topic,
            is_promo=is_promo,
            company_name=settings_row.company_name or "RSD AI",
            company_url=settings_row.company_url or "",
            company_description=settings_row.company_description or "",
            min_words=settings_row.article_min_words,
            max_words=settings_row.article_max_words,
            platform=platform,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Generation failed: {exc}")

    return JSONResponse(
        content={
            "title": article.title,
            "content": article.content,
            "is_promo": article.is_promo,
            "topic": topic,
        }
    )


from .sales_admin import router as admin_sales_router  # noqa: E402

router.include_router(admin_sales_router)