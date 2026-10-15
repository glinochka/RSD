"""AI content factory routes for /custom automations."""
import json
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from .dependencies import get_current_custom_automation
from .schemas import (
    ContentFactoryAccountConnectRequest,
    ContentFactoryAccountUpdateRequest,
    ContentFactorySettingsUpdate,
    ContentFactoryYoutubeOauthStartRequest,
)
from ..alembic.database import async_session_maker
from ..alembic.models import CustomAutomation
from ..config import settings as app_settings
from ..services.custom.content_factory_antifraud import factory_return_url
from ..services.custom.content_factory_pipeline import generate_now, tick
from ..services.custom.content_factory_publishers import (
    oauth_configured,
    youtube_exchange_code,
    youtube_oauth_url,
)
from ..services.custom.content_factory_service import (
    apply_settings_update,
    connect_account,
    dashboard_snapshot,
    delete_account,
    get_or_create_settings,
    get_video,
    list_accounts,
    list_token_usage,
    list_videos,
    recent_warmup_events_map,
    retry_video,
    serialize_account,
    serialize_settings,
    serialize_video,
    skip_video,
    sync_module_flag,
    update_account,
)
from ..services.youtube_client import get_youtube_client
from ..utils.crypto import decrypt_token, encrypt_token

logger = getLogger(__name__)
router = APIRouter()


@router.get("/automations/{automation_id}/content-factory")
async def get_content_factory(
    automation_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        snapshot = await dashboard_snapshot(session, automation.id)
        await session.commit()
        return snapshot


@router.get("/automations/{automation_id}/content-factory/settings")
async def get_content_factory_settings(
    automation_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        row = await get_or_create_settings(session, automation.id)
        await session.commit()
        return serialize_settings(row)


@router.put("/automations/{automation_id}/content-factory/settings")
async def update_content_factory_settings(
    automation_id: int,
    payload: ContentFactorySettingsUpdate,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        db_automation = await session.get(CustomAutomation, automation.id)
        row = await get_or_create_settings(session, automation.id)
        apply_settings_update(row, payload.model_dump(exclude_unset=True))
        if db_automation is not None:
            sync_module_flag(db_automation, row.enabled)
        await session.commit()
        await session.refresh(row)
        return serialize_settings(row)


@router.get("/automations/{automation_id}/content-factory/accounts")
async def get_content_factory_accounts(
    automation_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        settings = await get_or_create_settings(session, automation.id)
        accounts = await list_accounts(session, automation.id)
        events_map = await recent_warmup_events_map(session, [item.id for item in accounts])
        await session.commit()
        return {
            "items": [
                serialize_account(item, settings, warmup_events=events_map.get(item.id) or [])
                for item in accounts
            ],
            "youtube_oauth_ready": oauth_configured(),
        }


@router.post("/automations/{automation_id}/content-factory/accounts", status_code=status.HTTP_201_CREATED)
async def create_content_factory_account(
    automation_id: int,
    payload: ContentFactoryAccountConnectRequest,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            account = await connect_account(
                session,
                automation_id=automation.id,
                platform=payload.platform.strip().lower(),
                display_name=payload.display_name,
                handle=payload.handle,
                external_id=payload.external_id,
                credentials=payload.credentials,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        settings = await get_or_create_settings(session, automation.id)
        await session.commit()
        await session.refresh(account)
        return serialize_account(account, settings)


@router.patch("/automations/{automation_id}/content-factory/accounts/{account_id}")
async def patch_content_factory_account(
    automation_id: int,
    account_id: int,
    payload: ContentFactoryAccountUpdateRequest,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            account = await update_account(
                session,
                automation_id=automation.id,
                account_id=account_id,
                payload=payload.model_dump(exclude_unset=True),
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
        settings = await get_or_create_settings(session, automation.id)
        await session.commit()
        await session.refresh(account)
        return serialize_account(account, settings)


@router.delete("/automations/{automation_id}/content-factory/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_content_factory_account(
    automation_id: int,
    account_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            await delete_account(session, automation_id=automation.id, account_id=account_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
        await session.commit()
    return None


@router.post("/automations/{automation_id}/content-factory/accounts/youtube/oauth-start")
async def start_youtube_oauth(
    automation_id: int,
    payload: ContentFactoryYoutubeOauthStartRequest,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    if not oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="YouTube OAuth не настроен на сервере. Вставьте refresh_token вручную.",
        )
    state_payload = {
        "automation_id": automation.id,
        "return_url": factory_return_url(
            payload.return_url,
            automation.id,
            base_url=app_settings.BASE_URL or "",
        ),
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=20)).timestamp(),
    }
    state = encrypt_token(json.dumps(state_payload, ensure_ascii=False))
    redirect_uri = (app_settings.YOUTUBE_OAUTH_REDIRECT_URI or "").strip() or None
    try:
        auth_url = youtube_oauth_url(state=state, redirect_uri=redirect_uri)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"auth_url": auth_url}


@router.get("/content-factory/youtube/callback")
async def youtube_oauth_callback(
    code: str = Query(""),
    state: str = Query(""),
    error: Optional[str] = Query(None),
):
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    try:
        data = json.loads(decrypt_token(state))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Некорректный OAuth state: {exc}")
    automation_id = int(data.get("automation_id") or 0)
    if not automation_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="В state нет automation_id")
    exp = data.get("exp")
    try:
        if exp is not None and float(exp) < datetime.now(timezone.utc).timestamp():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state истёк, запустите подключение снова")
    except HTTPException:
        raise
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный OAuth state")
    try:
        tokens = await youtube_exchange_code(code=code)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    display_name = "YouTube"
    external_id = str(tokens.get("channel_id") or "")
    try:
        health = await get_youtube_client().health_check(token_bundle=tokens)
        if health.get("ok"):
            display_name = str((health.get("details") or {}).get("title") or display_name)
            external_id = str(health.get("external_id") or external_id)
        if isinstance(health.get("token_bundle"), dict):
            tokens = {**tokens, **health["token_bundle"]}
    except Exception as exc:
        logger.info("YouTube health_check after OAuth failed: %s", exc)
    async with async_session_maker() as session:
        account = await connect_account(
            session,
            automation_id=automation_id,
            platform="youtube",
            display_name=display_name,
            handle="",
            external_id=external_id,
            credentials={
                "access_token": str(tokens.get("access_token") or ""),
                "refresh_token": str(tokens.get("refresh_token") or ""),
                "expires_at": str(tokens.get("expires_at") or ""),
                "token_type": str(tokens.get("token_type") or "Bearer"),
            },
        )
        await session.commit()
        account_id = account.id
    return_url = factory_return_url(
        str(data.get("return_url") or "").strip() or None,
        automation_id,
        base_url=app_settings.BASE_URL or "",
    )
    sep = "&" if "?" in return_url else "?"
    return RedirectResponse(f"{return_url}{sep}youtube=connected&account_id={account_id}")


@router.get("/automations/{automation_id}/content-factory/videos")
async def get_content_factory_videos(
    automation_id: int,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(40, ge=1, le=100),
    offset: int = Query(0, ge=0),
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        items, total = await list_videos(
            session,
            automation.id,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
        return {"items": [serialize_video(item) for item in items], "total": total, "limit": limit, "offset": offset}


@router.get("/automations/{automation_id}/content-factory/videos/{video_id}")
async def get_content_factory_video(
    automation_id: int,
    video_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            video = await get_video(session, automation.id, video_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
        return serialize_video(video)


@router.get("/automations/{automation_id}/content-factory/tokens")
async def get_content_factory_tokens(
    automation_id: int,
    limit: int = Query(80, ge=1, le=200),
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        rows = await list_token_usage(session, automation.id, limit=limit)
        return {
            "items": [
                {
                    "id": row.id,
                    "video_id": row.video_id,
                    "provider": row.provider,
                    "model": row.model,
                    "operation": row.operation,
                    "prompt_tokens": row.prompt_tokens,
                    "completion_tokens": row.completion_tokens,
                    "cost_usd": row.cost_usd,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
        }


@router.post("/automations/{automation_id}/content-factory/videos/{video_id}/retry")
async def retry_content_factory_video(
    automation_id: int,
    video_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            video = await retry_video(session, automation.id, video_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        await session.commit()
        video = await get_video(session, automation.id, video.id)
        return serialize_video(video)


@router.post("/automations/{automation_id}/content-factory/videos/{video_id}/skip")
async def skip_content_factory_video(
    automation_id: int,
    video_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            video = await skip_video(session, automation.id, video_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        await session.commit()
        return serialize_video(video)


@router.post("/automations/{automation_id}/content-factory/generate")
async def generate_content_factory_video(
    automation_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            video = await generate_now(session, automation.id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        await session.commit()
        video = await get_video(session, automation.id, video.id)
        return serialize_video(video)


@router.post("/automations/{automation_id}/content-factory/run")
async def run_content_factory_tick(
    automation_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        result = await tick(session, automation.id)
        await session.commit()
        return {"ok": True, **result}
