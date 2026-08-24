"""Admin routes for /custom."""
from datetime import datetime, timezone
from logging import getLogger

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from .schemas import (
    CustomAdminLoginRequest,
    CustomLoginResponse,
    CustomAdminDashboardResponse,
    CustomAutomationCreate,
    CustomAutomationUpdate,
    CustomAutomationListResponse,
    CustomAutomationResponse,
    CustomAutomationCredentialCreate,
    CustomAutomationCredentialListResponse,
    CustomAutomationCredentialResponse,
)
from .dependencies import get_current_custom_admin
from ..utils.JWT import create_access_token
from ..utils.security import get_password_hash, verify_password
from ..alembic.database import async_session_maker
from ..alembic.models import CustomAdmin, CustomAutomation, CustomAutomationCredential
from ..services.account_pool_service import get_or_create_default_pool
from ..services.custom.prompt_service import create_default_prompts
from ..services.custom.analytics_service import get_admin_dashboard


logger = getLogger(__name__)
router = APIRouter(prefix="/admin")


@router.post("/login", response_model=CustomLoginResponse)
async def login_admin(payload: CustomAdminLoginRequest):
    async with async_session_maker() as session:
        admin = await session.scalar(
            select(CustomAdmin).where(
                CustomAdmin.username == payload.username,
                CustomAdmin.is_active.is_(True),
            )
        )
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        if not verify_password(payload.password, admin.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        admin.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()

        token = create_access_token(
            data={"custom_admin_id": admin.id, "custom_admin": True},
            token_kind="custom_admin",
        )

        return CustomLoginResponse(
            access_token=token,
            custom_admin=True,
            custom_automation_id=None,
        )


@router.get("/dashboard", response_model=CustomAdminDashboardResponse)
async def admin_dashboard(admin: CustomAdmin = Depends(get_current_custom_admin)):
    async with async_session_maker() as session:
        data = await get_admin_dashboard(session)
        return CustomAdminDashboardResponse.model_validate(data)


@router.get("/automations", response_model=CustomAutomationListResponse)
async def list_automations(admin: CustomAdmin = Depends(get_current_custom_admin)):
    async with async_session_maker() as session:
        result = await session.execute(
            select(CustomAutomation).order_by(CustomAutomation.created_at.desc())
        )
        items = result.scalars().all()
        total = await session.scalar(select(func.count(CustomAutomation.id)))
        return CustomAutomationListResponse(
            items=[CustomAutomationResponse.model_validate(a) for a in items],
            total=total or 0,
        )


@router.post("/automations", response_model=CustomAutomationResponse, status_code=status.HTTP_201_CREATED)
async def create_automation(
    payload: CustomAutomationCreate,
    admin: CustomAdmin = Depends(get_current_custom_admin),
):
    async with async_session_maker() as session:
        automation = CustomAutomation(
            name=payload.name,
            client_name=payload.client_name,
            industry=payload.industry,
            description=payload.description,
            status="draft",
            created_by_admin_id=admin.id,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(automation)
        await session.flush()
        await get_or_create_default_pool(session, automation.id)
        await create_default_prompts(session, automation.id)
        await session.commit()
        await session.refresh(automation)
        return CustomAutomationResponse.model_validate(automation)


@router.get("/automations/{automation_id}", response_model=CustomAutomationResponse)
async def get_automation(
    automation_id: int,
    admin: CustomAdmin = Depends(get_current_custom_admin),
):
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
        return CustomAutomationResponse.model_validate(automation)


@router.patch("/automations/{automation_id}", response_model=CustomAutomationResponse)
async def update_automation(
    automation_id: int,
    payload: CustomAutomationUpdate,
    admin: CustomAdmin = Depends(get_current_custom_admin),
):
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(automation, field, value)

        automation.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()
        await session.refresh(automation)
        return CustomAutomationResponse.model_validate(automation)


@router.delete("/automations/{automation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_automation(
    automation_id: int,
    admin: CustomAdmin = Depends(get_current_custom_admin),
):
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
        await session.delete(automation)
        await session.commit()
        return None


@router.get(
    "/automations/{automation_id}/credentials",
    response_model=CustomAutomationCredentialListResponse,
)
async def list_credentials(
    automation_id: int,
    admin: CustomAdmin = Depends(get_current_custom_admin),
):
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")

        result = await session.execute(
            select(CustomAutomationCredential)
            .where(CustomAutomationCredential.custom_automation_id == automation_id)
            .order_by(CustomAutomationCredential.created_at.desc())
        )
        items = result.scalars().all()
        total = await session.scalar(
            select(func.count(CustomAutomationCredential.id))
            .where(CustomAutomationCredential.custom_automation_id == automation_id)
        )
        return CustomAutomationCredentialListResponse(
            items=[CustomAutomationCredentialResponse.model_validate(c) for c in items],
            total=total or 0,
        )


@router.post(
    "/automations/{automation_id}/credentials",
    response_model=CustomAutomationCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_credential(
    automation_id: int,
    payload: CustomAutomationCredentialCreate,
    admin: CustomAdmin = Depends(get_current_custom_admin),
):
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")

        existing = await session.scalar(
            select(CustomAutomationCredential).where(
                CustomAutomationCredential.username == payload.username
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )

        credential = CustomAutomationCredential(
            custom_automation_id=automation_id,
            username=payload.username,
            password_hash=get_password_hash(payload.password),
            is_active=True,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(credential)
        await session.commit()
        await session.refresh(credential)
        return CustomAutomationCredentialResponse.model_validate(credential)


@router.delete("/automations/{automation_id}/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    automation_id: int,
    credential_id: int,
    admin: CustomAdmin = Depends(get_current_custom_admin),
):
    async with async_session_maker() as session:
        credential = await session.scalar(
            select(CustomAutomationCredential).where(
                CustomAutomationCredential.id == credential_id,
                CustomAutomationCredential.custom_automation_id == automation_id,
            )
        )
        if not credential:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")
        await session.delete(credential)
        await session.commit()
        return None
