from datetime import datetime, timezone
from html import escape
from logging import getLogger
from secrets import compare_digest

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import httpx
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.exc import UnknownHashError
from sqlalchemy import select

from .schemas import (
    AdminEmailBroadcastRequest,
    AdminGiftSubscriptionRequest,
    AdminLoginRequest,
    AdminPromoCodeCreateRequest,
    AdminSubscriptionPlansUpdateRequest,
)
from ..alembic.database import async_session_maker
from ..alembic.models import PromoCode, User
from ..config import get_auth_data, settings
from ..qdrant.search_service import delete_agent_vectors
from ..router_agents.dao import AgentDAO
from ..router_documents.dao import DocumentDAO
from ..router_payments.dao import PaymentTransactionDAO, PromoCodeDAO, TurnkeyAgentRequestDAO
from ..router_payments.router import _calculate_new_end_date
from ..router_users.dao import UserDAO, UserErrorReportDAO
from ..subscription_plans import (
    get_all_subscription_plans,
    get_subscription_plan,
    update_subscription_plan_overrides,
)
from ..utils.JWT import create_access_token
from ..utils.rate_limit import rate_limit
from ..utils.security import verify_password

logger = getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])
http_bearer = HTTPBearer(auto_error=False)


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


async def _send_mailopost_email(*, recipient: str, subject: str, plain_text: str, html: str) -> bool:
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
        response = await client.post(f"{base_url}/email/messages", json=payload, headers=headers)
    return response.is_success


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
            "telegram_id": user.telegram_id,
            "subscription_type": user.subscription_type,
            "subscription_end_date": (
                user.subscription_end_date.isoformat() if user.subscription_end_date else None
            ),
            "is_banned": user.is_banned,
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
        async with session.begin():
            existing = await promo_code_dao.find_by_code_case_insensitive(code)
            if existing:
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

    logger.info("User %s (id=%d) unbanned by admin", user.name, user_id)
    return JSONResponse(content={"detail": "User unbanned"}, status_code=status.HTTP_200_OK)


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
    plain_text = f"{subject}\n\n{body}"
    html = _render_broadcast_html(subject=subject, body=body)

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

    total = len(emails)
    sent = 0
    failed = 0
    for recipient in emails:
        if not recipient:
            continue
        try:
            ok = await _send_mailopost_email(
                recipient=recipient,
                subject=subject,
                plain_text=plain_text,
                html=html,
            )
            if ok:
                sent += 1
            else:
                failed += 1
        except HTTPException:
            raise
        except Exception:
            logger.exception("Admin broadcast failed for recipient=%s", recipient)
            failed += 1

    logger.info(
        "Admin email broadcast finished: total=%d sent=%d failed=%d subject=%s",
        total,
        sent,
        failed,
        subject,
    )
    return JSONResponse(
        content={
            "status": "completed",
            "total_recipients": total,
            "sent": sent,
            "failed": failed,
            "subject": subject,
        },
        status_code=status.HTTP_200_OK,
    )