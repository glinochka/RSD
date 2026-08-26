"""Automation (client) routes for /custom."""
from datetime import datetime, timezone
from logging import getLogger
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_, select

from .schemas import (
    AccountBulkClassifyRequest,
    AccountBulkClassifyResponse,
    AccountBulkUpdateProfilesRequest,
    AccountBulkUpdateProfilesResponse,
    AccountBanStatsResponse,
    AccountClassUpdate,
    AccountConnectResponse,
    AccountHealthCheckResponse,
    AccountHealthCheckResult,
    AccountListResponse,
    AccountQrStartRequest,
    AccountQrStartResponse,
    AccountQrStatusRequest,
    AccountQrStatusResponse,
    AccountQrVerify2faRequest,
    AccountResponse,
    AccountSmsRequest,
    AccountSmsStartResponse,
    AccountSmsVerifyRequest,
    AccountUploadResponse,
    ChatDiscoveryActionResponse,
    ChatDiscoveryApproveRequest,
    ChatDiscoveryCreate,
    ChatDiscoveryTaskListResponse,
    ChatDiscoveryTaskResponse,
    ChatImportJobListResponse,
    ChatImportJobResponse,
    ChatMessageListResponse,
    ChatMessageResponse,
    ChatTargetCreate,
    ChatTargetListResponse,
    ChatTargetResponse,
    ChatTargetUpdate,
    CustomAutomationDashboardResponse,
    CustomAutomationLoginRequest,
    CustomAutomationSettingsResponse,
    CustomAutomationSettingsValidationResponse,
    AmocrmCredentialsUpdate,
    AmocrmOAuthStartRequest,
    AmocrmOAuthStartResponse,
    AmocrmPipelineUpdate,
    AmocrmConnectionResponse,
    AmocrmTransferResponse,
    CustomAutomationSettingsUpdate,
    CustomLeadListResponse,
    CustomLeadMessageListResponse,
    CustomLeadMessageResponse,
    CustomLeadResponse,
    CustomLeadStatusUpdate,
    CustomLoginResponse,
    CustomPromptListResponse,
    CustomPromptResponse,
    CustomPromptTestRequest,
    CustomPromptTestResponse,
    CustomPromptUpdate,
    DmpOneImportCreate,
    DmpOneImportListResponse,
    DmpOneImportResponse,
    DmpOneWebhookResponse,
    GoogleSheetsSettingsUpdate,
    TelegramBotSettingsUpdate,
)
from .dependencies import get_current_custom_automation
from ..services.account_pool_service import bulk_upload_sessions, delete_pool_account
from ..services.custom.lead_keywords import normalize_lead_keywords
from ..services.custom.account_connect_service import (
    poll_account_qr,
    request_account_sms,
    start_account_qr,
    verify_account_qr_2fa,
    verify_account_sms,
)
from ..services.custom.account_health_worker import AccountHealthWorker
from ..services.telegram_userbot_auth import TelegramUserbotAuthError
from ..services.custom.bulk_profile_service import (
    BulkProfileUpdateWorker,
    _save_uploaded_avatar,
    update_account_bio,
    update_account_display_name,
)
from ..services.custom.chat_discovery_service import (
    approve_discovered_chats,
    create_discovery_task,
    list_discovery_tasks,
    reject_discovered_chats,
    run_discovery_task,
)
from ..services.custom.chat_import_service import import_chats_from_file, retry_import_errors
from ..services.custom.chat_join_service import join_pending_chats
from ..services.custom.chat_monitoring_service import scan_chats_and_process
from ..services.custom.amocrm_service import (
    build_oauth_authorization_url,
    create_oauth_state,
    deactivate_connection,
    decode_oauth_state,
    exchange_authorization_code,
    get_connection,
    get_redirect_uri,
    run_amocrm_sync_for_automation,
    safe_return_url,
    save_credentials,
    serialize_connection,
    transfer_lead_to_amocrm,
    update_pipeline_config,
)
from ..services.custom.lead_warmup_service import auto_transfer_lead
from ..services.custom.analytics_service import get_automation_dashboard
from ..services.custom.discussion_service import run_discussion_pass
from ..services.custom.settings_service import validate_settings
from ..services.custom.dmp_one_service import (
    create_order,
    dmp_webhook_secret_ok,
    ensure_dmp_webhook_secret,
    handle_webhook,
    poll_pending_imports,
    public_webhook_url,
    rotate_dmp_webhook_secret,
)
from ..services.custom.google_sheets_service import (
    encrypt_service_account_json,
    parse_spreadsheet_id,
    service_account_email,
    worksheet_name,
)
from ..services.custom.solution_templates import is_dmp_notify_pipeline, lock_dmp_bot_modules
from ..services.custom.telegram_notify_bot_service import (
    bot_webhook_secret_ok,
    connect_telegram_bot,
    count_subscribers,
    disconnect_telegram_bot,
    handle_bot_update,
    public_bot_webhook_url,
)
from ..services.custom.neurocommenting_service import run_neurocommenting_pass
from ..services.custom.prompt_service import (
    list_prompts,
    get_prompt,
    test_prompt,
    toggle_prompt,
    update_prompt,
)
from ..services.custom.shilling_service import run_shilling_pass
from ..utils.JWT import create_access_token
from ..utils.security import verify_password
from ..alembic.database import async_session_maker
from ..config import settings
from ..alembic.models import (
    AccountClass,
    AccountPool,
    ChatDiscoveryTask,
    ChatImportJob,
    ChatMessage,
    ChatTarget,
    CustomAutomation,
    CustomAutomationCredential,
    CustomLead,
    CustomLeadMessage,
    DmpOneImport,
    PoolAccount,
    SocialAccount,
)


logger = getLogger(__name__)
router = APIRouter()


async def _settings_payload(session, db_automation) -> dict:
    if (db_automation.is_dmp_one_enabled or is_dmp_notify_pipeline(db_automation)) and not db_automation.dmp_webhook_secret:
        ensure_dmp_webhook_secret(db_automation)
        await session.commit()
        await session.refresh(db_automation)
    validation = await validate_settings(session, db_automation)
    response = CustomAutomationSettingsResponse.model_validate(db_automation).model_dump()
    response["lead_keywords"] = normalize_lead_keywords(db_automation.lead_keywords)
    response["warnings"] = validation["warnings"]
    response["amocrm_redirect_uri"] = get_redirect_uri()
    if (db_automation.is_dmp_one_enabled or is_dmp_notify_pipeline(db_automation)) and db_automation.dmp_webhook_secret:
        response["dmp_webhook_secret"] = db_automation.dmp_webhook_secret
        response["dmp_webhook_url"] = public_webhook_url(db_automation.id, db_automation.dmp_webhook_secret)
    else:
        response["dmp_webhook_secret"] = None
        response["dmp_webhook_url"] = None
    response["telegram_bot_token_set"] = bool((db_automation.telegram_bot_token_enc or "").strip())
    response["telegram_bot_username"] = db_automation.telegram_bot_username
    response["telegram_bot_webhook_url"] = public_bot_webhook_url(
        db_automation.id, db_automation.telegram_bot_webhook_secret
    ) if response["telegram_bot_token_set"] else None
    response["telegram_bot_subscribers"] = await count_subscribers(session, db_automation.id)
    response["google_sheets_spreadsheet_id"] = db_automation.google_sheets_spreadsheet_id
    response["google_sheets_worksheet"] = worksheet_name(db_automation)
    response["google_sheets_credentials_set"] = bool((db_automation.google_sheets_credentials_enc or "").strip())
    response["google_sheets_service_account_email"] = (
        service_account_email(db_automation) if response["google_sheets_credentials_set"] else None
    )
    response.pop("telegram_bot_token_enc", None)
    response.pop("google_sheets_credentials_enc", None)
    return response


def _dmp_incoming_secret(request: Request, path_secret: str | None = None) -> str:
    incoming = (path_secret or "").strip()
    incoming = incoming or (
        request.headers.get("X-DMP-Webhook-Secret")
        or request.headers.get("X-Webhook-Secret")
        or ""
    ).strip()
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        incoming = incoming or auth[7:].strip()
    return incoming


@router.post("/login", response_model=CustomLoginResponse)
async def login_automation(payload: CustomAutomationLoginRequest):
    async with async_session_maker() as session:
        credential = await session.scalar(
            select(CustomAutomationCredential).where(
                CustomAutomationCredential.username == payload.username,
                CustomAutomationCredential.is_active.is_(True),
            )
        )
        if not credential:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        if not verify_password(payload.password, credential.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        credential.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()

        token = create_access_token(
            data={
                "custom_automation_id": credential.custom_automation_id,
                "custom_credential_id": credential.id,
            },
            token_kind="custom_automation",
        )

        return CustomLoginResponse(
            access_token=token,
            custom_admin=False,
            custom_automation_id=credential.custom_automation_id,
        )


@router.get("/automations/{automation_id}/dashboard", response_model=CustomAutomationDashboardResponse)
async def automation_dashboard(
    automation_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        data = await get_automation_dashboard(session, automation_id)
        return CustomAutomationDashboardResponse.model_validate(data)


@router.get("/automations/{automation_id}/settings", response_model=CustomAutomationSettingsResponse)
async def get_automation_settings(
    automation_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        db_automation = await session.get(CustomAutomation, automation_id)
        if not db_automation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
        return await _settings_payload(session, db_automation)


@router.patch("/automations/{automation_id}/settings", response_model=CustomAutomationSettingsResponse)
async def update_automation_settings(
    automation_id: int,
    payload: CustomAutomationSettingsUpdate,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        db_automation = await session.merge(automation)
        update_data = payload.model_dump(exclude_unset=True)
        if "lead_keywords" in update_data:
            update_data["lead_keywords"] = normalize_lead_keywords(update_data.get("lead_keywords"))
        for field, value in update_data.items():
            setattr(db_automation, field, value)
        if is_dmp_notify_pipeline(db_automation):
            lock_dmp_bot_modules(db_automation)
        modules_on = any([
            db_automation.is_chat_monitoring_enabled,
            db_automation.is_neurocommenting_enabled,
            db_automation.is_digital_footprint_enabled,
            db_automation.is_dmp_one_enabled,
            db_automation.is_amocrm_enabled,
            db_automation.is_shilling_enabled,
        ])
        if modules_on and db_automation.status == "draft":
            db_automation.status = "active"
        if db_automation.is_dmp_one_enabled:
            ensure_dmp_webhook_secret(db_automation)
        db_automation.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()
        await session.refresh(db_automation)
        return await _settings_payload(session, db_automation)


@router.get(
    "/automations/{automation_id}/settings/validation",
    response_model=CustomAutomationSettingsValidationResponse,
)
async def validate_automation_settings(
    automation_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        db_automation = await session.get(CustomAutomation, automation_id)
        if not db_automation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
        validation = await validate_settings(session, db_automation)
        return CustomAutomationSettingsValidationResponse(**validation)


def _session_status(social_account: SocialAccount) -> str:
    if not social_account.session_file_path:
        return "empty"
    if not social_account.is_active:
        return "revoked"
    return "active"


def _account_response(
    pool_account: PoolAccount,
    social_account: SocialAccount,
    max_daily: int = 50,
) -> AccountResponse:
    return AccountResponse(
        id=social_account.id,
        provider=social_account.provider,
        phone_number=social_account.phone_number,
        username=social_account.username,
        display_name=social_account.display_name,
        bio=social_account.current_bio or social_account.bio,
        avatar_url=social_account.avatar_url
        or (f"/media/{social_account.avatar_file_path}" if social_account.avatar_file_path else None),
        avatar_file_path=social_account.avatar_file_path,
        account_class=social_account.account_class,
        assigned_class=pool_account.assigned_class,
        status=_session_status(social_account),
        is_active=social_account.is_active,
        is_banned=social_account.is_banned,
        is_spamblocked=bool(getattr(social_account, "is_spamblocked", False)),
        auto_classified=social_account.auto_classified,
        risk_score=social_account.risk_score,
        trust_score=social_account.trust_score,
        session_file_path=social_account.session_file_path,
        daily_messages_sent=social_account.daily_messages_sent,
        daily_messages_reset_at=social_account.daily_messages_reset_at,
        last_used_at=social_account.last_used_at,
        max_daily_messages_per_account=max_daily,
        added_at=pool_account.added_at,
        last_health_check_at=social_account.last_health_check_at,
        updated_at=social_account.updated_at,
    )


def _apply_chat_target_update(chat: ChatTarget, payload: ChatTargetUpdate) -> None:
    if payload.is_active is not None:
        chat.is_active = payload.is_active
        if payload.mode is None:
            chat.mode = "monitoring" if payload.is_active else "inactive"
    if payload.mode is not None:
        chat.mode = payload.mode
        if payload.mode == "inactive":
            chat.is_active = False
        elif payload.is_active is None:
            chat.is_active = True
    if payload.neurocommenting_config is not None:
        chat.neurocommenting_config = payload.neurocommenting_config
    if payload.discussion_config is not None:
        chat.discussion_config = payload.discussion_config
    if payload.shilling_config is not None:
        chat.shilling_config = payload.shilling_config
    chat.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)


def _userbot_auth_http_error(exc: TelegramUserbotAuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _queue_account_health_check(background_tasks: BackgroundTasks, automation_id: int) -> None:
    background_tasks.add_task(AccountHealthWorker().check_all_accounts_for_automation, automation_id)


@router.get("/automations/{automation_id}/accounts", response_model=AccountListResponse)
async def list_accounts(
    automation_id: int,
    status: Optional[str] = None,
    account_class: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        pool = await session.scalar(
            select(AccountPool).where(
                AccountPool.custom_automation_id == automation_id,
                AccountPool.is_default.is_(True),
            )
        )
        if not pool:
            return AccountListResponse(items=[], total=0)

        stmt = (
            select(PoolAccount, SocialAccount)
            .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
            .where(PoolAccount.account_pool_id == pool.id)
        )
        if account_class:
            stmt = stmt.where(PoolAccount.assigned_class == account_class)
        if status == "loaded" or status == "active":
            stmt = stmt.where(
                SocialAccount.session_file_path.isnot(None),
                SocialAccount.is_active.is_(True),
            )
        elif status == "revoked":
            stmt = stmt.where(
                SocialAccount.session_file_path.isnot(None),
                SocialAccount.is_active.is_(False),
            )
        elif status == "spamblock":
            stmt = stmt.where(SocialAccount.is_spamblocked.is_(True))
        elif status == "banned":
            stmt = stmt.where(SocialAccount.is_banned.is_(True))
        elif status == "empty":
            stmt = stmt.where(SocialAccount.session_file_path.is_(None))
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    SocialAccount.phone_number.ilike(pattern),
                    SocialAccount.username.ilike(pattern),
                    SocialAccount.display_name.ilike(pattern),
                )
            )
        stmt = stmt.order_by(PoolAccount.added_at.desc()).limit(limit).offset(offset)

        result = await session.execute(stmt)
        rows = result.all()
        total = await session.scalar(
            select(func.count(PoolAccount.id)).where(PoolAccount.account_pool_id == pool.id)
        )

        max_daily = automation.max_daily_messages_per_account
        items = [_account_response(pool_account, social_account, max_daily) for pool_account, social_account in rows]
        return AccountListResponse(items=items, total=total or 0)


@router.get("/automations/{automation_id}/accounts/ban-stats", response_model=AccountBanStatsResponse)
async def account_ban_stats(
    automation_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        pool = await session.scalar(
            select(AccountPool).where(
                AccountPool.custom_automation_id == automation_id,
                AccountPool.is_default.is_(True),
            )
        )
        if not pool:
            return AccountBanStatsResponse(
                total=0, active=0, banned=0, revoked=0, spamblocked=0, banned_percent=0.0, alert=False
            )
        total = await session.scalar(
            select(func.count(PoolAccount.id)).where(PoolAccount.account_pool_id == pool.id)
        )
        banned = await session.scalar(
            select(func.count(PoolAccount.id))
            .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
            .where(
                PoolAccount.account_pool_id == pool.id,
                SocialAccount.is_banned.is_(True),
            )
        )
        active = await session.scalar(
            select(func.count(PoolAccount.id))
            .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
            .where(
                PoolAccount.account_pool_id == pool.id,
                SocialAccount.is_active.is_(True),
                SocialAccount.is_banned.is_(False),
            )
        )
        revoked = await session.scalar(
            select(func.count(PoolAccount.id))
            .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
            .where(
                PoolAccount.account_pool_id == pool.id,
                SocialAccount.is_active.is_(False),
                SocialAccount.is_banned.is_(False),
                SocialAccount.session_file_path.isnot(None),
            )
        )
        spamblocked = await session.scalar(
            select(func.count(PoolAccount.id))
            .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
            .where(
                PoolAccount.account_pool_id == pool.id,
                SocialAccount.is_spamblocked.is_(True),
            )
        )
        banned_percent = round((banned or 0) / total, 2) if total else 0.0
        alert_threshold = float(settings.CUSTOM_BAN_ALERT_THRESHOLD or 0.3)
        is_alert = banned_percent >= alert_threshold
        if is_alert:
            logger.warning(
                "High ban rate for automation %s: %s/%s (%.0f%%)",
                automation_id, banned, total, banned_percent * 100
            )
        return AccountBanStatsResponse(
            total=total or 0,
            active=active or 0,
            banned=banned or 0,
            revoked=revoked or 0,
            spamblocked=spamblocked or 0,
            banned_percent=banned_percent,
            alert_threshold=alert_threshold,
            alert=is_alert,
        )


@router.post("/automations/{automation_id}/accounts/health-check", response_model=AccountHealthCheckResponse)
async def run_account_health_check(
    automation_id: int,
    background_tasks: BackgroundTasks,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    worker = AccountHealthWorker()
    results = await worker.check_all_accounts_for_automation(automation_id)
    ok = sum(1 for r in results if r.get("status") == "ok")
    fallback = sum(1 for r in results if r.get("status") == "fallback")
    error = sum(
        1
        for r in results
        if r.get("status") in {"error", "not_found", "session_invalid", "banned", "spamblock"}
    )
    return AccountHealthCheckResponse(
        results=[AccountHealthCheckResult(**r) for r in results],
        total=len(results),
        ok=ok,
        fallback=fallback,
        error=error,
    )


@router.post("/automations/{automation_id}/accounts/qr/start", response_model=AccountQrStartResponse)
async def start_qr_account(
    automation_id: int,
    background_tasks: BackgroundTasks,
    payload: AccountQrStartRequest | None = None,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    body = payload or AccountQrStartRequest()
    async with async_session_maker() as session:
        try:
            result = await start_account_qr(session, automation_id, assign_class=body.assign_class)
        except TelegramUserbotAuthError as exc:
            raise _userbot_auth_http_error(exc) from exc
    account = None
    if result.get("pool_account") is not None and result.get("social_account") is not None:
        account = _account_response(
            result["pool_account"],
            result["social_account"],
            automation.max_daily_messages_per_account,
        )
        if result.get("created"):
            _queue_account_health_check(background_tasks, automation_id)
    return AccountQrStartResponse(
        auth_token=result["auth_token"],
        qr_url=result.get("qr_url") or "",
        qr_data_url=result.get("qr_data_url") or "",
        already_authorized=bool(result.get("already_authorized")),
        account=account,
    )


@router.post("/automations/{automation_id}/accounts/qr/status", response_model=AccountQrStatusResponse)
async def qr_account_status(
    automation_id: int,
    payload: AccountQrStatusRequest,
    background_tasks: BackgroundTasks,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            result = await poll_account_qr(session, automation_id, auth_token=payload.auth_token)
        except TelegramUserbotAuthError as exc:
            raise _userbot_auth_http_error(exc) from exc
    account = None
    if result.get("pool_account") is not None and result.get("social_account") is not None:
        account = _account_response(
            result["pool_account"],
            result["social_account"],
            automation.max_daily_messages_per_account,
        )
        if result.get("created"):
            _queue_account_health_check(background_tasks, automation_id)
    return AccountQrStatusResponse(
        status=result.get("status") or "pending",
        error=result.get("error"),
        account=account,
    )


@router.post("/automations/{automation_id}/accounts/qr/verify_2fa", response_model=AccountConnectResponse)
async def qr_account_verify_2fa(
    automation_id: int,
    payload: AccountQrVerify2faRequest,
    background_tasks: BackgroundTasks,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            pool_account, social_account = await verify_account_qr_2fa(
                session,
                automation_id,
                auth_token=payload.auth_token,
                password=payload.password,
            )
        except TelegramUserbotAuthError as exc:
            raise _userbot_auth_http_error(exc) from exc
    _queue_account_health_check(background_tasks, automation_id)
    return AccountConnectResponse(
        account=_account_response(pool_account, social_account, automation.max_daily_messages_per_account)
    )


@router.post("/automations/{automation_id}/accounts/sms/request", response_model=AccountSmsStartResponse)
async def sms_account_request(
    automation_id: int,
    payload: AccountSmsRequest,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    result = await request_account_sms(
        automation_id,
        phone_number=payload.phone_number,
        assign_class=payload.assign_class,
    )
    return AccountSmsStartResponse(auth_token=result["auth_token"])


@router.post("/automations/{automation_id}/accounts/sms/verify", response_model=AccountConnectResponse)
async def sms_account_verify(
    automation_id: int,
    payload: AccountSmsVerifyRequest,
    background_tasks: BackgroundTasks,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        pool_account, social_account = await verify_account_sms(
            session,
            automation_id,
            auth_token=payload.auth_token,
            code=payload.code,
            password=payload.password,
        )
    _queue_account_health_check(background_tasks, automation_id)
    return AccountConnectResponse(
        account=_account_response(pool_account, social_account, automation.max_daily_messages_per_account)
    )


@router.get("/automations/{automation_id}/accounts/{account_id}", response_model=AccountResponse)
async def get_account(
    automation_id: int,
    account_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        row = await session.execute(
            select(PoolAccount, SocialAccount)
            .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
            .join(AccountPool, PoolAccount.account_pool_id == AccountPool.id)
            .where(
                AccountPool.custom_automation_id == automation_id,
                SocialAccount.id == account_id,
            )
        )
        result = row.one_or_none()
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        pool_account, social_account = result
        return _account_response(pool_account, social_account, automation.max_daily_messages_per_account)


@router.post("/automations/{automation_id}/accounts/bulk-upload", response_model=AccountUploadResponse)
async def bulk_upload_accounts(
    automation_id: int,
    background_tasks: BackgroundTasks,
    archive: UploadFile = File(...),
    assign_class: str = Form(AccountClass.ONE_DAY.value),
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        result = await bulk_upload_sessions(session, automation_id, archive, assign_class)
    background_tasks.add_task(AccountHealthWorker().check_all_accounts_for_automation, automation_id)
    return AccountUploadResponse(**result)


@router.post("/automations/{automation_id}/accounts/bulk-classify", response_model=AccountBulkClassifyResponse)
async def bulk_classify(
    automation_id: int,
    payload: AccountBulkClassifyRequest,
    background_tasks: BackgroundTasks,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        pool = await session.scalar(
            select(AccountPool).where(
                AccountPool.custom_automation_id == automation_id,
                AccountPool.is_default.is_(True),
            )
        )
        if not pool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Default pool not found",
            )

        if payload.account_ids:
            account_ids = list(payload.account_ids)
        else:
            result = await session.execute(
                select(PoolAccount.social_account_id).where(
                    PoolAccount.account_pool_id == pool.id
                )
            )
            account_ids = [row[0] for row in result.all()]

        if not account_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No accounts to classify",
            )

    worker = AccountHealthWorker()
    background_tasks.add_task(worker.process_accounts, automation_id, account_ids)
    return AccountBulkClassifyResponse(queued=len(account_ids))


@router.post("/automations/{automation_id}/accounts/bulk-update-profiles", response_model=AccountBulkUpdateProfilesResponse)
async def bulk_update_profiles(
    automation_id: int,
    background_tasks: BackgroundTasks,
    avatar: UploadFile | None = File(None),
    payload: str = Form("{}"),
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    data = AccountBulkUpdateProfilesRequest.model_validate_json(payload)

    avatar_relative_path = None
    if avatar:
        content = await avatar.read()
        if content:
            avatar_relative_path = await _save_uploaded_avatar(
                automation_id, avatar.filename or "avatar.jpg", content
            )

    async with async_session_maker() as session:
        pool = await session.scalar(
            select(AccountPool).where(
                AccountPool.custom_automation_id == automation_id,
                AccountPool.is_default.is_(True),
            )
        )
        if not pool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Default pool not found",
            )

        stmt = (
            select(PoolAccount.social_account_id)
            .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
            .where(PoolAccount.account_pool_id == pool.id)
        )
        if data.account_ids:
            stmt = stmt.where(SocialAccount.id.in_(data.account_ids))
        if data.account_class:
            stmt = stmt.where(PoolAccount.assigned_class == data.account_class)
        if data.status == "loaded":
            stmt = stmt.where(SocialAccount.session_file_path.isnot(None))
        elif data.status == "empty":
            stmt = stmt.where(SocialAccount.session_file_path.is_(None))

        result = await session.execute(stmt)
        account_ids = [row[0] for row in result.all()]

        if not account_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No accounts to update",
            )

    worker = BulkProfileUpdateWorker()
    job_kwargs = {
        "avatar_relative_path": avatar_relative_path,
        "bio_template": data.bio_template,
        "generate_unique": data.generate_unique,
    }
    if len(account_ids) <= 5:
        results = await worker.process_accounts(automation_id, account_ids, **job_kwargs)
        return AccountBulkUpdateProfilesResponse(queued=len(account_ids), results=results)
    background_tasks.add_task(worker.process_accounts, automation_id, account_ids, **job_kwargs)
    return AccountBulkUpdateProfilesResponse(queued=len(account_ids))


@router.patch("/automations/{automation_id}/accounts/{account_id}", response_model=AccountResponse)
async def update_account(
    automation_id: int,
    account_id: int,
    payload: AccountClassUpdate,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    if payload.assigned_class is None and payload.display_name is None and payload.bio is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update")
    async with async_session_maker() as session:
        row = await session.execute(
            select(PoolAccount, SocialAccount)
            .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
            .join(AccountPool, PoolAccount.account_pool_id == AccountPool.id)
            .where(
                AccountPool.custom_automation_id == automation_id,
                SocialAccount.id == account_id,
            )
        )
        result = row.one_or_none()
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        pool_account, social_account = result
        if payload.assigned_class is not None:
            pool_account.assigned_class = payload.assigned_class
            social_account.account_class = payload.assigned_class
            social_account.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if payload.display_name is not None:
            try:
                await update_account_display_name(session, automation_id, social_account, payload.display_name)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)[:255]) from exc
        if payload.bio is not None:
            try:
                await update_account_bio(session, automation_id, social_account, payload.bio)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)[:255]) from exc
        await session.commit()
        await session.refresh(pool_account)
        await session.refresh(social_account)
        return _account_response(pool_account, social_account)


@router.delete("/automations/{automation_id}/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    automation_id: int,
    account_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            await delete_pool_account(session, automation_id, account_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found") from None


# --- Chat targets ---

@router.get("/automations/{automation_id}/chats", response_model=ChatTargetListResponse)
async def list_chats(
    automation_id: int,
    join_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        stmt = select(ChatTarget).where(ChatTarget.custom_automation_id == automation_id)
        if join_status:
            stmt = stmt.where(ChatTarget.join_status == join_status)
        stmt = stmt.order_by(ChatTarget.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        items = result.scalars().all()
        total = await session.scalar(
            select(func.count(ChatTarget.id)).where(ChatTarget.custom_automation_id == automation_id)
        )
        return ChatTargetListResponse(
            items=[ChatTargetResponse.model_validate(c) for c in items],
            total=total or 0,
        )


@router.post("/automations/{automation_id}/chats", response_model=ChatTargetResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    automation_id: int,
    payload: ChatTargetCreate,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        chat = ChatTarget(
            custom_automation_id=automation_id,
            provider=payload.provider,
            external_chat_id=payload.external_chat_id,
            invite_link=payload.invite_link,
            title=payload.title,
            description=payload.description,
            chat_type=payload.chat_type,
            mode=payload.mode,
            join_status="pending",
            join_attempts=0,
            is_active=True,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(chat)
        await session.commit()
        await session.refresh(chat)
        return ChatTargetResponse.model_validate(chat)


@router.patch("/automations/{automation_id}/chats/{chat_id}/neurocommenting-config", response_model=ChatTargetResponse)
async def update_chat_neurocommenting_config(
    automation_id: int,
    chat_id: int,
    payload: ChatTargetUpdate,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        chat = await session.get(ChatTarget, chat_id)
        if not chat or chat.custom_automation_id != automation_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        _apply_chat_target_update(chat, payload)
        await session.commit()
        await session.refresh(chat)
        return ChatTargetResponse.model_validate(chat)


@router.post("/automations/{automation_id}/chats/neurocommenting")
async def run_neurocommenting(
    automation_id: int,
    background_tasks: BackgroundTasks,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    background_tasks.add_task(run_neurocommenting_pass, automation_id)
    return {"status": "started"}


@router.patch("/automations/{automation_id}/chats/{chat_id}/discussion-config", response_model=ChatTargetResponse)
async def update_chat_discussion_config(
    automation_id: int,
    chat_id: int,
    payload: ChatTargetUpdate,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        chat = await session.get(ChatTarget, chat_id)
        if not chat or chat.custom_automation_id != automation_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        _apply_chat_target_update(chat, payload)
        await session.commit()
        await session.refresh(chat)
        return ChatTargetResponse.model_validate(chat)


@router.post("/automations/{automation_id}/chats/discussion")
async def run_discussion(
    automation_id: int,
    background_tasks: BackgroundTasks,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    background_tasks.add_task(run_discussion_pass, automation_id)
    return {"status": "started"}


@router.patch("/automations/{automation_id}/chats/{chat_id}/shilling-config", response_model=ChatTargetResponse)
async def update_chat_shilling_config(
    automation_id: int,
    chat_id: int,
    payload: ChatTargetUpdate,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        chat = await session.get(ChatTarget, chat_id)
        if not chat or chat.custom_automation_id != automation_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        _apply_chat_target_update(chat, payload)
        await session.commit()
        await session.refresh(chat)
        return ChatTargetResponse.model_validate(chat)


@router.post("/automations/{automation_id}/chats/shilling")
async def run_shilling(
    automation_id: int,
    background_tasks: BackgroundTasks,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    background_tasks.add_task(run_shilling_pass, automation_id)
    return {"status": "started"}


@router.delete("/automations/{automation_id}/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    automation_id: int,
    chat_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        chat = await session.get(ChatTarget, chat_id)
        if not chat or chat.custom_automation_id != automation_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        await session.delete(chat)
        await session.commit()
        return None


@router.get("/automations/{automation_id}/chats/{chat_id}/messages", response_model=ChatMessageListResponse)
async def list_chat_messages(
    automation_id: int,
    chat_id: int,
    limit: int = 50,
    offset: int = 0,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.custom_automation_id == automation_id, ChatMessage.chat_target_id == chat_id)
            .order_by(ChatMessage.sent_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        items = result.scalars().all()
        total = await session.scalar(
            select(func.count(ChatMessage.id)).where(
                ChatMessage.custom_automation_id == automation_id, ChatMessage.chat_target_id == chat_id
            )
        )
        return ChatMessageListResponse(
            items=[ChatMessageResponse.model_validate(m) for m in items],
            total=total or 0,
        )


@router.post("/automations/{automation_id}/chats/bulk-import", response_model=ChatImportJobResponse)
async def bulk_import_chats(
    automation_id: int,
    archive: UploadFile = File(...),
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    content = await archive.read()
    async with async_session_maker() as session:
        job = await import_chats_from_file(
            session,
            automation_id=automation_id,
            filename=archive.filename or "import.csv",
            content=content,
        )
        return ChatImportJobResponse.model_validate(job)


@router.get("/automations/{automation_id}/chats/import-jobs", response_model=ChatImportJobListResponse)
async def list_import_jobs(
    automation_id: int,
    limit: int = 50,
    offset: int = 0,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        stmt = (
            select(ChatImportJob)
            .where(ChatImportJob.custom_automation_id == automation_id)
            .order_by(ChatImportJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        items = result.scalars().all()
        total = await session.scalar(
            select(func.count(ChatImportJob.id)).where(ChatImportJob.custom_automation_id == automation_id)
        )
        return ChatImportJobListResponse(
            items=[ChatImportJobResponse.model_validate(j) for j in items],
            total=total or 0,
        )


@router.post("/automations/{automation_id}/chats/import-jobs/{job_id}/retry", response_model=ChatImportJobResponse)
async def retry_import_job(
    automation_id: int,
    job_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        job = await retry_import_errors(session, job_id)
        if not job or job.custom_automation_id != automation_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
        return ChatImportJobResponse.model_validate(job)


@router.post("/automations/{automation_id}/chats/join")
async def run_join_chats(
    automation_id: int,
    background_tasks: BackgroundTasks,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    background_tasks.add_task(_join_chats_background, automation_id)
    return {"status": "started"}


async def _join_chats_background(automation_id: int) -> None:
    async with async_session_maker() as session:
        await join_pending_chats(session, automation_id)


async def _run_discovery_background(automation_id: int, task_id: int) -> None:
    async with async_session_maker() as session:
        try:
            await run_discovery_task(session, task_id)
        except Exception as exc:
            logger.exception("Discovery task %s failed for automation %s: %s", task_id, automation_id, exc)


@router.post("/automations/{automation_id}/chats/discovery", response_model=ChatDiscoveryTaskResponse, status_code=status.HTTP_201_CREATED)
async def start_chat_discovery(
    automation_id: int,
    payload: ChatDiscoveryCreate,
    background_tasks: BackgroundTasks,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        task = await create_discovery_task(
            session,
            automation_id=automation_id,
            query=payload.query,
            mode=payload.mode or "monitoring",
            max_chats=payload.max_chats,
            require_approval=payload.require_approval,
            relevance_threshold=payload.relevance_threshold,
        )
        task_id = task.id
    background_tasks.add_task(_run_discovery_background, automation_id, task_id)
    async with async_session_maker() as session:
        task = await session.get(ChatDiscoveryTask, task_id)
        return ChatDiscoveryTaskResponse.model_validate(task)


@router.get("/automations/{automation_id}/chats/discovery", response_model=ChatDiscoveryTaskListResponse)
async def list_chat_discovery_tasks(
    automation_id: int,
    limit: int = 50,
    offset: int = 0,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        items = await list_discovery_tasks(session, automation_id, limit=limit, offset=offset)
        total = await session.scalar(
            select(func.count(ChatDiscoveryTask.id)).where(
                ChatDiscoveryTask.custom_automation_id == automation_id
            )
        )
        return ChatDiscoveryTaskListResponse(
            items=[ChatDiscoveryTaskResponse.model_validate(i) for i in items],
            total=total or 0,
        )


@router.get("/automations/{automation_id}/chats/discovery/{task_id}", response_model=ChatDiscoveryTaskResponse)
async def get_chat_discovery_task(
    automation_id: int,
    task_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        task = await session.get(ChatDiscoveryTask, task_id)
        if not task or task.custom_automation_id != automation_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery task not found")
        return ChatDiscoveryTaskResponse.model_validate(task)


@router.post("/automations/{automation_id}/chats/discovery/{task_id}/approve", response_model=ChatDiscoveryActionResponse)
async def approve_discovery_task(
    automation_id: int,
    task_id: int,
    payload: ChatDiscoveryApproveRequest,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        result = await approve_discovered_chats(
            session,
            automation_id=automation_id,
            task_id=task_id,
            indices=payload.indices,
            mode=payload.mode,
        )
        return ChatDiscoveryActionResponse(**result)


@router.post("/automations/{automation_id}/chats/discovery/{task_id}/reject", response_model=ChatDiscoveryActionResponse)
async def reject_discovery_task(
    automation_id: int,
    task_id: int,
    payload: ChatDiscoveryApproveRequest,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        result = await reject_discovered_chats(
            session,
            automation_id=automation_id,
            task_id=task_id,
            indices=payload.indices,
        )
        return ChatDiscoveryActionResponse(created=0, rejected=result.get("rejected", 0))


@router.post("/automations/{automation_id}/chats/monitor")
async def run_chat_monitoring(
    automation_id: int,
    background_tasks: BackgroundTasks,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    background_tasks.add_task(scan_chats_and_process, automation_id)
    return {"status": "started"}


@router.get("/automations/{automation_id}/leads", response_model=CustomLeadListResponse)
async def list_leads(
    automation_id: int,
    status: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        stmt = select(CustomLead).where(CustomLead.custom_automation_id == automation_id)
        if status:
            stmt = stmt.where(CustomLead.status == status)
        if source:
            stmt = stmt.where(CustomLead.source == source)
        stmt = stmt.order_by(CustomLead.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        items = result.scalars().all()
        total = await session.scalar(
            select(func.count(CustomLead.id)).where(CustomLead.custom_automation_id == automation_id)
        )
        return CustomLeadListResponse(
            items=[CustomLeadResponse.model_validate(l) for l in items],
            total=total or 0,
        )


@router.get("/automations/{automation_id}/leads/{lead_id}", response_model=CustomLeadResponse)
async def get_lead(
    automation_id: int,
    lead_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        lead = await session.get(CustomLead, lead_id)
        if not lead or lead.custom_automation_id != automation_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
        return CustomLeadResponse.model_validate(lead)


@router.get("/automations/{automation_id}/leads/{lead_id}/messages", response_model=CustomLeadMessageListResponse)
async def list_lead_messages(
    automation_id: int,
    lead_id: int,
    limit: int = 100,
    offset: int = 0,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        lead = await session.get(CustomLead, lead_id)
        if not lead or lead.custom_automation_id != automation_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
        stmt = (
            select(CustomLeadMessage)
            .where(CustomLeadMessage.custom_lead_id == lead_id)
            .order_by(CustomLeadMessage.sent_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        items = result.scalars().all()
        total = await session.scalar(
            select(func.count(CustomLeadMessage.id)).where(CustomLeadMessage.custom_lead_id == lead_id)
        )
        return CustomLeadMessageListResponse(
            items=[CustomLeadMessageResponse.model_validate(m) for m in items],
            total=total or 0,
        )


@router.patch("/automations/{automation_id}/leads/{lead_id}/status", response_model=CustomLeadResponse)
async def update_lead_status(
    automation_id: int,
    lead_id: int,
    payload: CustomLeadStatusUpdate,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        lead = await session.get(CustomLead, lead_id)
        if not lead or lead.custom_automation_id != automation_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
        lead.status = payload.status
        lead.status_history = (lead.status_history or []) + [{"status": payload.status, "changed_at": datetime.now(timezone.utc).isoformat()}]
        lead.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(lead)
        return CustomLeadResponse.model_validate(lead)


@router.post("/automations/{automation_id}/leads/{lead_id}/transfer", response_model=AmocrmTransferResponse)
async def transfer_lead(
    automation_id: int,
    lead_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        lead = await session.get(CustomLead, lead_id)
        if not lead or lead.custom_automation_id != automation_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

        result = await auto_transfer_lead(session, automation_id, lead)
        if not result.get("transferred"):
            reason = result.get("reason") or "unknown"
            status_code = (
                status.HTTP_502_BAD_GATEWAY
                if reason not in {"no_manager_contact", "invalid_contact", "unsupported_contact_type", "automation_not_found"}
                else status.HTTP_400_BAD_REQUEST
            )
            raise HTTPException(status_code=status_code, detail=f"Lead transfer failed: {reason}")

        await session.refresh(lead)
        return AmocrmTransferResponse(
            lead_id=lead.id,
            status=lead.status,
            transferred_at=lead.transferred_at,
            amocrm_lead_id=lead.amocrm_lead_id,
            amocrm_contact_id=lead.amocrm_contact_id,
            reason=result.get("reason"),
        )


@router.get("/automations/{automation_id}/dmp/imports", response_model=DmpOneImportListResponse)
async def list_dmp_imports(
    automation_id: int,
    limit: int = 50,
    offset: int = 0,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        stmt = (
            select(DmpOneImport)
            .where(DmpOneImport.custom_automation_id == automation_id)
            .order_by(DmpOneImport.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        items = result.scalars().all()
        total = await session.scalar(
            select(func.count(DmpOneImport.id)).where(DmpOneImport.custom_automation_id == automation_id)
        )
        return DmpOneImportListResponse(
            items=[DmpOneImportResponse.model_validate(i) for i in items],
            total=total or 0,
        )


@router.post("/automations/{automation_id}/dmp/orders", response_model=DmpOneImportResponse)
async def create_dmp_order(
    automation_id: int,
    payload: DmpOneImportCreate,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            dmp_import = await create_order(
                session,
                automation_id,
                import_type=payload.import_type,
                source_url=payload.source_url,
                requested_count=payload.requested_count,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        return DmpOneImportResponse.model_validate(dmp_import)


@router.post("/automations/{automation_id}/dmp/poll")
async def run_dmp_poll(
    automation_id: int,
    background_tasks: BackgroundTasks,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    background_tasks.add_task(poll_pending_imports, automation_id)
    return {"status": "started"}


async def _accept_dmp_webhook(automation_id: int, payload: Any, incoming_secret: str) -> DmpOneWebhookResponse:
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
        if not dmp_webhook_secret_ok(automation, incoming_secret):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid DMP webhook secret")
        result = await handle_webhook(session, automation_id, payload)
        return DmpOneWebhookResponse(
            created_leads=result.get("created_leads") or 0,
            received_count=result.get("received_count") or 0,
            purchased_count=result.get("purchased_count") or 0,
        )


@router.post("/webhooks/dmp/{automation_id}/{secret}", response_model=DmpOneWebhookResponse)
async def dmp_public_webhook_with_secret(
    automation_id: int,
    secret: str,
    request: Request,
    payload: Any = Body(default=None),
):
    return await _accept_dmp_webhook(automation_id, payload, secret or _dmp_incoming_secret(request))


@router.post("/webhooks/dmp/{automation_id}", response_model=DmpOneWebhookResponse)
async def dmp_public_webhook(
    automation_id: int,
    request: Request,
    payload: Any = Body(default=None),
):
    return await _accept_dmp_webhook(automation_id, payload, _dmp_incoming_secret(request))


@router.post("/automations/{automation_id}/dmp/webhook", response_model=DmpOneWebhookResponse)
async def dmp_webhook(
    automation_id: int,
    request: Request,
    payload: Any = Body(default=None),
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        result = await handle_webhook(session, automation_id, payload)
        return DmpOneWebhookResponse(
            created_leads=result.get("created_leads") or 0,
            received_count=result.get("received_count") or 0,
            purchased_count=result.get("purchased_count") or 0,
        )


@router.post("/automations/{automation_id}/dmp/webhook-secret/rotate")
async def rotate_automation_dmp_webhook_secret(
    automation_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        db_automation = await session.get(CustomAutomation, automation_id)
        if not db_automation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
        secret = rotate_dmp_webhook_secret(db_automation)
        await session.commit()
        return {
            "dmp_webhook_secret": secret,
            "dmp_webhook_url": public_webhook_url(automation_id, secret),
        }


@router.post("/automations/{automation_id}/telegram-bot", response_model=CustomAutomationSettingsResponse)
async def save_telegram_bot(
    automation_id: int,
    payload: TelegramBotSettingsUpdate,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        db_automation = await session.get(CustomAutomation, automation_id)
        if not db_automation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
        try:
            if payload.disconnect:
                await disconnect_telegram_bot(db_automation)
            elif (payload.bot_token or "").strip():
                await connect_telegram_bot(db_automation, payload.bot_token or "")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        await session.commit()
        await session.refresh(db_automation)
        return await _settings_payload(session, db_automation)


@router.post("/automations/{automation_id}/google-sheets", response_model=CustomAutomationSettingsResponse)
async def save_google_sheets(
    automation_id: int,
    payload: GoogleSheetsSettingsUpdate,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        db_automation = await session.get(CustomAutomation, automation_id)
        if not db_automation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
        if payload.spreadsheet is not None:
            db_automation.google_sheets_spreadsheet_id = parse_spreadsheet_id(payload.spreadsheet) or None
        if payload.worksheet is not None:
            name = (payload.worksheet or "").strip()
            db_automation.google_sheets_worksheet = name or None
        raw_json = (payload.service_account_json or "").strip()
        if raw_json:
            try:
                db_automation.google_sheets_credentials_enc = encrypt_service_account_json(raw_json)
            except (ValueError, TypeError) as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        db_automation.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()
        await session.refresh(db_automation)
        return await _settings_payload(session, db_automation)


@router.post("/webhooks/telegram/{automation_id}/{secret}")
async def telegram_bot_public_webhook(
    automation_id: int,
    secret: str,
    request: Request,
    payload: Any = Body(default=None),
):
    header_token = (request.headers.get("X-Telegram-Bot-Api-Secret-Token") or "").strip()
    try:
        async with async_session_maker() as session:
            automation = await session.get(CustomAutomation, automation_id)
            if not automation or not bot_webhook_secret_ok(automation, secret, header_token):
                return {"ok": True}
            await handle_bot_update(session, automation, payload if isinstance(payload, dict) else {})
    except Exception:
        logger.exception("Telegram bot webhook failed for automation %s", automation_id)
    return {"ok": True}


@router.get("/automations/{automation_id}/amocrm/connection", response_model=AmocrmConnectionResponse)
async def get_amocrm_connection(
    automation_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        connection = await get_connection(session, automation_id)
        return AmocrmConnectionResponse.model_validate(serialize_connection(connection))


@router.post("/automations/{automation_id}/amocrm/credentials", response_model=AmocrmConnectionResponse)
async def save_amocrm_credentials(
    automation_id: int,
    payload: AmocrmCredentialsUpdate,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            connection = await save_credentials(
                session,
                automation_id,
                subdomain=payload.subdomain,
                client_id=payload.client_id,
                client_secret=payload.client_secret,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return AmocrmConnectionResponse.model_validate(serialize_connection(connection))


@router.post("/automations/{automation_id}/amocrm/oauth/start", response_model=AmocrmOAuthStartResponse)
async def start_amocrm_oauth(
    automation_id: int,
    payload: AmocrmOAuthStartRequest,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        connection = await get_connection(session, automation_id)
        if not connection or not connection.client_id or not connection.client_secret_enc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Сначала сохраните client_id и client_secret",
            )
        redirect_uri = get_redirect_uri()
        if not redirect_uri:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="AMOCRM_REDIRECT_URI не задан",
            )
        return_url = safe_return_url(payload.return_url, automation_id)
        state = create_oauth_state(automation_id=automation_id, return_url=return_url)
        return AmocrmOAuthStartResponse(
            auth_url=build_oauth_authorization_url(connection.client_id, state),
            redirect_uri=redirect_uri,
        )


@router.get("/amocrm/oauth/callback")
async def amocrm_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    referer: str | None = None,
    error: str | None = None,
):
    fallback = f"{(settings.BASE_URL or '').rstrip('/')}/custom"
    if error or not code or not state:
        return RedirectResponse(url=f"{fallback}?amocrm=error", status_code=302)
    try:
        data = decode_oauth_state(state)
        automation_id = int(data["automation_id"])
        return_url = safe_return_url(data.get("return_url"), automation_id)
        async with async_session_maker() as session:
            await exchange_authorization_code(
                session,
                automation_id,
                code=code,
                referer=referer,
            )
        separator = "&" if "?" in return_url else "?"
        return RedirectResponse(url=f"{return_url}{separator}amocrm=connected", status_code=302)
    except Exception:
        logger.exception("AmoCRM OAuth callback failed")
        return RedirectResponse(url=f"{fallback}?amocrm=error", status_code=302)


@router.post("/automations/{automation_id}/amocrm/connection", response_model=AmocrmConnectionResponse)
async def save_amocrm_pipeline(
    automation_id: int,
    payload: AmocrmPipelineUpdate,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            connection = await update_pipeline_config(
                session,
                automation_id,
                pipeline_id=payload.pipeline_id,
                responsible_user_id=payload.responsible_user_id,
                lead_status_id=payload.lead_status_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return AmocrmConnectionResponse.model_validate(serialize_connection(connection))


@router.delete("/automations/{automation_id}/amocrm/connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_amocrm_connection(
    automation_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        await deactivate_connection(session, automation_id)
        return None


@router.post("/automations/{automation_id}/amocrm/sync")
async def run_amocrm_sync(
    automation_id: int,
    background_tasks: BackgroundTasks,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    background_tasks.add_task(run_amocrm_sync_for_automation, automation_id)
    return {"status": "started"}


@router.get("/automations/{automation_id}/prompts", response_model=CustomPromptListResponse)
async def list_automation_prompts(
    automation_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        items = await list_prompts(session, automation_id)
        return CustomPromptListResponse(
            items=[CustomPromptResponse.model_validate(p) for p in items],
        )


@router.get("/automations/{automation_id}/prompts/{prompt_id}", response_model=CustomPromptResponse)
async def get_automation_prompt(
    automation_id: int,
    prompt_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        prompt = await get_prompt(session, automation_id, prompt_id)
        if not prompt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")
        return CustomPromptResponse.model_validate(prompt)


@router.patch("/automations/{automation_id}/prompts/{prompt_id}", response_model=CustomPromptResponse)
async def update_automation_prompt(
    automation_id: int,
    prompt_id: int,
    payload: CustomPromptUpdate,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            prompt = await update_prompt(
                session,
                automation_id,
                prompt_id,
                content=payload.content,
                model=payload.model,
                temperature=payload.temperature,
                max_tokens=payload.max_tokens,
                is_active=payload.is_active,
            )
            return CustomPromptResponse.model_validate(prompt)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/automations/{automation_id}/prompts/{prompt_id}/toggle", response_model=CustomPromptResponse)
async def toggle_automation_prompt(
    automation_id: int,
    prompt_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            prompt = await toggle_prompt(session, automation_id, prompt_id)
            return CustomPromptResponse.model_validate(prompt)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/automations/{automation_id}/prompts/{prompt_id}/test", response_model=CustomPromptTestResponse)
async def test_automation_prompt(
    automation_id: int,
    prompt_id: int,
    payload: CustomPromptTestRequest,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        try:
            result = await test_prompt(session, automation_id, prompt_id, payload.variables)
            return CustomPromptTestResponse(**result)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
