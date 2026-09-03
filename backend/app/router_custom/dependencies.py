"""Auth dependencies for /custom endpoints."""
from typing import Optional
from logging import getLogger

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..utils.JWT import decode_access_token_payload
from ..alembic.database import async_session_maker
from ..alembic.models import CustomAdmin, CustomAutomation, CustomAutomationCredential


logger = getLogger(__name__)
http_bearer = HTTPBearer(auto_error=False)


async def _get_token_or_raise(credentials: Optional[HTTPAuthorizationCredentials]) -> str:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
        )
    return credentials.credentials


async def get_current_custom_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> CustomAdmin:
    token = await _get_token_or_raise(credentials)
    try:
        payload = decode_access_token_payload(token, "custom_admin")
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid custom admin token",
        )

    admin_id = payload.get("custom_admin_id")
    if not admin_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )

    async with async_session_maker() as session:
        admin = await session.get(CustomAdmin, int(admin_id))
        if not admin or not admin.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Custom admin access denied",
            )
        return admin


async def get_current_custom_automation(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> CustomAutomation:
    token = await _get_token_or_raise(credentials)
    path_automation_id = request.path_params.get("automation_id")

    admin_payload = None
    try:
        admin_payload = decode_access_token_payload(token, "custom_admin")
    except HTTPException:
        admin_payload = None

    if admin_payload:
        admin_id = admin_payload.get("custom_admin_id")
        if not admin_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims",
            )
        if path_automation_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="automation_id required",
            )
        async with async_session_maker() as session:
            admin = await session.get(CustomAdmin, int(admin_id))
            if not admin or not admin.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Custom admin access denied",
                )
            automation = await session.get(CustomAutomation, int(path_automation_id))
            if not automation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Automation not found",
                )
            return automation

    try:
        payload = decode_access_token_payload(token, "custom_automation")
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid custom automation token",
        )

    automation_id = payload.get("custom_automation_id")
    if not automation_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )

    if path_automation_id is not None and int(path_automation_id) != int(automation_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Automation access mismatch",
        )

    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, int(automation_id))
        if not automation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Automation not found",
            )
        return automation


async def get_current_custom_automation_credential(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> CustomAutomationCredential:
    token = await _get_token_or_raise(credentials)
    try:
        payload = decode_access_token_payload(token, "custom_automation")
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid custom automation token",
        )

    credential_id = payload.get("custom_credential_id")
    if not credential_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )

    async with async_session_maker() as session:
        credential = await session.get(CustomAutomationCredential, int(credential_id))
        if not credential or not credential.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Credential access denied",
            )
        return credential


async def optional_is_custom_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> bool:
    if not credentials or not credentials.credentials:
        return False
    try:
        decode_access_token_payload(credentials.credentials, "custom_admin")
        return True
    except HTTPException:
        return False
