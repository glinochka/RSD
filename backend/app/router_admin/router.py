from datetime import datetime, timezone
from secrets import compare_digest

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import String, cast, desc, func, or_, select

from .schemas import AdminLoginRequest, AdminSubscriptionPlansUpdateRequest
from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentDocument, PaymentTransaction, User
from ..config import get_auth_data, settings
from ..subscription_plans import get_all_subscription_plans, update_subscription_plan_overrides
from ..utils.JWT import create_access_token

router = APIRouter(prefix="/api/admin", tags=["admin"])
http_bearer = HTTPBearer(auto_error=False)


def _ensure_admin_credentials_configured() -> None:
    if not settings.ADMIN_WEB_LOGIN.strip() or not settings.ADMIN_WEB_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_WEB_LOGIN / ADMIN_WEB_PASSWORD are not configured",
        )


def _decode_admin_token(token: str) -> dict:
    try:
        auth_data = get_auth_data()
        payload = jwt.decode(token, auth_data["secret_key"], algorithms=[auth_data["algorithm"]])
    except JWTError:
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


@router.post("/login")
async def admin_login(payload: AdminLoginRequest):
    _ensure_admin_credentials_configured()
    login = payload.login.strip()
    password = payload.password

    is_login_valid = compare_digest(login, settings.ADMIN_WEB_LOGIN.strip())
    is_password_valid = compare_digest(password, settings.ADMIN_WEB_PASSWORD)

    if not is_login_valid or not is_password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )

    access_token = create_access_token({"admin_web": True})
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
        total_users = await session.scalar(select(func.count(User.id)))
        total_agents = await session.scalar(select(func.count(Agent.id)))
        active_agents = await session.scalar(
            select(func.count(Agent.id)).where(Agent.is_active.is_(True))
        )
        total_documents = await session.scalar(select(func.count(AgentDocument.id)))
        paid_users = await session.scalar(
            select(func.count(User.id)).where(User.subscription_type != "Free")
        )
        total_payments = await session.scalar(select(func.count(PaymentTransaction.id)))
        free_users = await session.scalar(
            select(func.count(User.id)).where(User.subscription_type == "Free")
        )
        advanced_users = await session.scalar(
            select(func.count(User.id)).where(User.subscription_type == "Advanced")
        )
        pro_users = await session.scalar(
            select(func.count(User.id)).where(User.subscription_type == "Pro")
        )

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
    offset = (page - 1) * page_size

    async with async_session_maker() as session:
        base_count_query = select(func.count(User.id))
        base_items_query = (
            select(User)
            .order_by(desc(User.registered), desc(User.id))
            .offset(offset)
            .limit(page_size)
        )
        if search_value:
            pattern = f"%{search_value}%"
            filters = or_(
                User.name.ilike(pattern),
                cast(User.telegram_id, String).ilike(pattern),
            )
            base_count_query = base_count_query.where(filters)
            base_items_query = base_items_query.where(filters)

        total = await session.scalar(base_count_query)
        users = (await session.scalars(base_items_query)).all()

    items = [
        {
            "id": user.id,
            "name": user.name,
            "telegram_id": user.telegram_id,
            "subscription_type": user.subscription_type,
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
    offset = (page - 1) * page_size

    async with async_session_maker() as session:
        base_query = select(
            Agent.id,
            Agent.bot_id,
            Agent.bot_username,
            Agent.is_active,
            Agent.registered,
            User.name.label("owner_name"),
            User.subscription_type.label("owner_subscription_type"),
        ).join(User, User.id == Agent.user_id)
        count_query = select(func.count(Agent.id)).join(User, User.id == Agent.user_id)
        if search_value:
            pattern = f"%{search_value}%"
            filters = or_(
                Agent.bot_username.ilike(pattern),
                User.name.ilike(pattern),
                cast(Agent.bot_id, String).ilike(pattern),
            )
            base_query = base_query.where(filters)
            count_query = count_query.where(filters)

        total = await session.scalar(count_query)
        rows = (
            await session.execute(
                base_query.order_by(desc(Agent.registered), desc(Agent.id))
                .offset(offset)
                .limit(page_size)
            )
        ).all()

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
