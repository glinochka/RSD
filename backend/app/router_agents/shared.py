"""Shared helpers, constants, and dependencies for agent routers."""
import asyncio
import base64
import json
import math
import re
from logging import getLogger
from urllib.parse import quote
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import HTTPError, URLError
from datetime import date, datetime, timedelta, timezone
from collections import defaultdict
from typing import Any

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy import Date, and_, cast, func, select
from sqlalchemy.exc import IntegrityError

from .dao import AgentChannelConnectionDAO, AgentCrmConnectionDAO, AgentDAO, AgentHttpIntegrationDAO
from .schemas import *
from ..alembic.database import async_session_maker
from ..alembic.models import (
    AdminApplication,
    AdminAppointment,
    AdminAppointmentReminderLog,
    AdminClientProfile,
    AdminQuickReplyTemplate,
    AdminResource,
    AdminScheduleSlot,
    AdminService,
    AdminStaff,
    AdminWaitlistEntry,
    Agent,
    AgentAnalyticsMessage,
    AgentChannelConnection,
    AgentContentJob,
    AgentCrmConnection,
    AgentFrozenUser,
    AgentHttpIntegration,
    AgentSalesContact,
    AgentSalesImportedContact,
)
from ..config import settings
from ..qdrant.search_service import delete_agent_vectors
from ..router_users.dao import UserDAO
from ..channels.message_processor import (
    Channel as RuntimeChannel,
    MessageRequest as RuntimeMessageRequest,
    ProcessingStatus as RuntimeProcessingStatus,
    get_message_processor,
)
from ..services.agent_availability import normalize_agent_availability_for_storage
from ..prompts.system_prompts import DEFAULT_AGENT_SYSTEM_PROMPT, SALES_TRIGGER_WORDS_INSTRUCTION
from ..services.ai_authoring import ai_client, generate_welcome_with_ai, improve_prompt_with_ai
from ..services.admin_booking import get_admin_booking_service
from ..services.admin_booking.payment_service import get_admin_booking_payment_service
from ..services.admin_booking.domains import DOMAIN_REGISTRY as _DOMAIN_REGISTRY
from ..services.admin_applications import get_admin_application_service
from ..services.website_public_forms import WEBSITE_UNIFIED_LEAD_FIELDS
from ..services.voice_transcription import is_voice_stt_configured, transcribe_voice_bytes
from ..services.http_integration.errors import HttpIntegrationValidationError
from ..services.http_integration.tool_registry import validate_integration_config_dict
from ..services.qa_handoff_service import EscalationType as QAEscalationType, get_qa_handoff_service
from ..services.template_runtime import EscalationType, get_template_runtime
from ..services.crm import build_provider
from ..telephony.agent_guards import is_user_frozen
from ..services.telegram_userbot_auth import (
    TelegramUserbotAuthError,
    complete_qr_2fa,
    create_telegram_client,
    get_qr_status,
    import_session_file,
    resolve_api_credentials,
    start_qr_login,
)
from ..services.max_userbot_auth import (
    MaxUserbotAuthError,
    complete_qr_2fa as max_complete_qr_2fa,
    get_qr_status as max_get_qr_status,
    import_session_file as max_import_session_file,
    request_sms_code as max_request_sms_code,
    start_qr_login as max_start_qr_login,
    verify_sms_code as max_verify_sms_code,
)
from ..services.max_userbot_session import (
    MaxUserbotSessionError,
    bundle_from_credentials,
    normalize_bundle,
    parse_session_payload,
    send_message_once as max_send_message_once,
    validate_session_bundle,
)
from ..services.youtube_client import get_youtube_client
from ..utils.api_keys import generate_agent_external_api_key, hash_agent_external_api_key
from ..utils.JWT import get_user_from_access_token
from ..utils.convert import convert_to_dict
from ..utils.crypto import (
    decrypt_booking_payment_secret,
    decrypt_crm_credentials,
    decrypt_token,
    encrypt_booking_payment_secret,
    encrypt_crm_credentials,
    encrypt_token,
)
from ..utils.internal_auth import is_internal_request, is_request_secure, verify_internal_signature
from ..utils.pii import redact_pii_text
from ..utils.rate_limit import rate_limit
from ..utils.whatsapp_session import decode_whatsapp_session_bundle
from ..telephony.credentials import (
    TELEPHONY_CHANNEL_PROVIDER,
    TelephonyCredentialsV1,
    parse_telephony_credentials,
)
from ..telephony.routing import (
    clear_channel_routes,
    scan_extension_conflict_in_db,
    sync_channel_routes,
    telephony_routing_public_fields,
)
from ..services.voximplant_client import (
    VoximplantApiError,
    deactivate_voximplant_inbound_rule,
    validate_voximplant_account,
    validate_voximplant_channel_setup,
)
from ..telephony.platform_config import platform_telephony_public_fields, require_platform_telephony_config
from ..telephony.webhook_urls import build_telephony_webhook_url
from .telephony_channel import (
    build_encrypted_telephony_bundle,
    telephony_connect_response_extra,
    telephony_external_id,
    validate_telephony_credentials_input,
)
from .telephony_analytics import list_agent_telephony_calls
from ..utils.scoped_auth_token import (
    max_userbot_auth_token,
    userbot_auth_token,
    userbot_qr_auth_token,
    whatsapp_userbot_auth_token,
)
from ..utils.whatsapp_jid import WhatsAppJidError, bridge_post, external_id_to_jid

logger = getLogger(__name__)

http_bearer = HTTPBearer(auto_error=False)
MAX_INT32 = 2_147_483_647
LEGACY_TEMPLATE_TYPE_ALIASES = {
    "function_calling": "crm_admin",
}
SUPPORTED_TEMPLATE_TYPES = {
    "qa",
    "crm_admin",
    "lead_generation",
    "content_factory",
    "sales_manager",
    "ai_logist",
    "ai_manager",
}
CRM_PROVIDERS = {"amocrm", "bitrix24"}
CRM_CONFIRMATION_POLICIES = {"always_confirm", "confirm_risky", "never_confirm"}
CRM_FALLBACK_MODES = {"ask_clarifying_question", "text_only"}
CRM_DOMAIN_TYPES = set(_DOMAIN_REGISTRY.keys())
CRM_MODES = {"disabled", "optional", "required"}
CRM_BOOKING_BACKENDS = {"local", "crm", "auto"}
DEFAULT_CRM_ALLOWED_TOOLS = [
    "find_contact",
    "create_contact",
    "find_lead",
    "create_lead",
    "update_lead",
    "add_note",
    "create_task",
    "assign_owner",
]
DEFAULT_BOOKING_ALLOWED_TOOLS = [
    "check_availability",
    "find_next_available",
    "list_appointments",
    "create_appointment",
    "reschedule_appointment",
    "cancel_appointment",
    "list_staff",
    "list_services",
]
CRM_WORKFLOW_MODES = {"booking", "applications"}
DEFAULT_APPLICATION_ALLOWED_TOOLS = [
    "get_application_schema",
    "create_application",
    "list_client_applications",
]
SALES_MODES = {"draft_only", "semi_auto", "auto"}
SALES_ALLOWED_LANGUAGES = {"ru", "en"}
SALES_CONFIRMATION_POLICIES = {"always_confirm", "confirm_risky", "never_confirm"}
SALES_WORKFLOW_COMPLETION_MODES = {"auto_finish_on_signal", "continue_dialog"}
SALES_SCORE_SCALES = {10, 100}
SALES_DEFAULT_ALLOWED_TOOLS = [
    "schedule_dm",
    "skip_lead",
    "record_lead_signal",
    "create_crm_lead",
    "mark_contacted",
]
SALES_DEFAULT_CONFIG = {
    "mode": "auto",
    "qualification_model": "deepseek-chat",
    "generation_model": "deepseek-chat",
    "min_confidence": 0.75,
    "sales_product_name": "",
    "sales_offer_type": "",
    "sales_usp": "",
    "workflow_completion_mode": "auto_finish_on_signal",
    "lead_score_scale": 100,
    "lead_generation_enabled": True,
    "contacts_pool_only": False,
    "neuro_commenting_enabled": False,
    "live_chat_simulation_enabled": False,
    "scan_scope": {
        "include_chat_ids": [],
        "exclude_chat_ids": [],
    },
    "dm_limits": {
        "per_minute": 3,
        "per_hour": 25,
        "per_day": 120,
        "per_source_chat_per_day": 40,
    },
    "cooldown_days": 14,
    "dedup_window_days": 30,
    "allowed_languages": ["ru", "en"],
    "quiet_hours_local": "22:00-09:00",
    "offer_profile_id": None,
    "confirmation_policy": "never_confirm",
    "allowed_tools": list(SALES_DEFAULT_ALLOWED_TOOLS),
    "trigger_words": ["купить"],
}
YOUTUBE_OAUTH_STATE_TTL_SECONDS = 15 * 60
YOUTUBE_OAUTH_STATE_SCOPE = "youtube_oauth_connect"
CONTENT_FACTORY_DEFAULT_CONFIG = {
    "content_language": "ru",
    "daily_posting_enabled": True,
    "daily_post_time": "10:00",
    "timezone": "UTC",
    "video_duration_seconds": 8,
    "kling_model": "kling-v1",
}
CONTENT_FACTORY_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
CONTENT_FACTORY_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,16}(?:-[a-z]{2,16})?$")
CONTENT_FACTORY_TIMEZONE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_+\-]*/?[A-Za-z0-9_+\-]*$")
WIDGET_ALLOWED_TEMPLATE_TYPES = {"qa", "crm_admin"}


def _normalize_sales_trigger_words(raw_value: Any) -> list[str]:
    from ..services.sales.trigger_words import normalize_sales_trigger_words

    return normalize_sales_trigger_words(raw_value)


async def _generate_sales_trigger_words_via_llm(
    *,
    system_prompt: str,
    template_config: dict[str, Any],
) -> list[str]:
    product = str(template_config.get("sales_product_name") or "").strip()
    offer_type = str(template_config.get("sales_offer_type") or "").strip()
    usp = str(template_config.get("sales_usp") or "").strip()
    instruction = SALES_TRIGGER_WORDS_INSTRUCTION.format(
        product=product or "не указан",
        offer_type=offer_type or "не указан",
        usp=usp or "не указано",
        system_prompt=system_prompt or "не указан",
    )
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": instruction}],
        temperature=0.2,
        max_tokens=250,
    )
    from ..services.sales.trigger_words import parse_llm_trigger_words_response

    raw = str(response.choices[0].message.content or "").strip()
    parsed = parse_llm_trigger_words_response(raw)
    return _normalize_sales_trigger_words(parsed)


async def _run_sales_manager_excel_outreach(*, agent_id: int, import_batch_id: str) -> None:
    from ..services.sales.agent_outreach_service import schedule_outreach_for_import_batch

    max_batches = 25
    total_queued = 0
    try:
        for _ in range(max_batches):
            result = await schedule_outreach_for_import_batch(
                agent_id=agent_id,
                import_batch_id=import_batch_id,
            )
            if result.get("error"):
                logger.warning(
                    "sales_manager excel outreach stopped agent_id=%s batch=%s: %s",
                    agent_id,
                    import_batch_id,
                    result.get("error"),
                )
                break
            queued = int(result.get("queued") or 0)
            total_queued += queued
            if queued == 0:
                break
            await asyncio.sleep(2)
        logger.info(
            "sales_manager excel outreach finished agent_id=%s batch=%s total_queued=%s",
            agent_id,
            import_batch_id,
            total_queued,
        )
    except Exception:
        logger.exception(
            "sales_manager excel outreach failed agent_id=%s batch=%s",
            agent_id,
            import_batch_id,
        )


async def _schedule_sales_trigger_words_generation(
    *,
    agent_id: int,
    system_prompt: str,
    template_config_json: str | None,
) -> None:
    try:
        cfg_raw = json.loads(template_config_json or "{}")
        cfg = cfg_raw if isinstance(cfg_raw, dict) else {}
    except Exception:
        cfg = {}
    trigger_words = await _generate_sales_trigger_words_via_llm(
        system_prompt=system_prompt,
        template_config=cfg,
    )
    cfg["trigger_words"] = _normalize_sales_trigger_words(trigger_words)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await agent_dao.find_one_by_filter(id=agent_id)
            if not agent:
                return
            try:
                current_cfg_raw = json.loads(agent.template_config or "{}")
                current_cfg = current_cfg_raw if isinstance(current_cfg_raw, dict) else {}
            except Exception:
                current_cfg = {}
            current_cfg["trigger_words"] = _normalize_sales_trigger_words(cfg.get("trigger_words"))
            await agent_dao.update(
                agent,
                {"template_config": json.dumps(current_cfg, ensure_ascii=False)},
            )

WIDGET_CSS = """
.rsd-widget-root{position:fixed;z-index:2147483000;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
.rsd-widget-root[data-position="bottom-right"]{right:20px;bottom:20px}
.rsd-widget-root[data-position="bottom-left"]{left:20px;bottom:20px}
.rsd-widget-toggle{width:56px;height:56px;border-radius:50%;border:none;cursor:pointer;background:#111827;color:#fff;box-shadow:0 10px 30px rgba(17,24,39,.35);font-size:22px;transition:transform .15s,box-shadow .15s}
.rsd-widget-toggle:hover{transform:scale(1.08);box-shadow:0 14px 36px rgba(17,24,39,.45)}
.rsd-widget-panel{position:absolute;bottom:70px;right:0;width:min(400px,calc(100vw - 24px));height:540px;max-height:calc(100vh - 110px);background:#fff;border-radius:16px;box-shadow:0 24px 60px rgba(15,23,42,.25);display:flex;flex-direction:column;overflow:hidden;border:1px solid #e5e7eb}
.rsd-widget-root[data-position="bottom-left"] .rsd-widget-panel{right:auto;left:0}
.rsd-widget-header{padding:14px 16px;background:#111827;color:#fff;font-weight:600;font-size:14px;display:flex;align-items:center;justify-content:space-between}
.rsd-widget-header-close{background:none;border:none;color:rgba(255,255,255,.65);cursor:pointer;font-size:18px;line-height:1;padding:0 0 0 8px;flex-shrink:0}
.rsd-widget-header-close:hover{color:#fff}
.rsd-widget-messages{flex:1;overflow:auto;padding:14px;background:#f8fafc;display:flex;flex-direction:column;gap:8px}
.rsd-widget-msg{max-width:86%;padding:10px 12px;border-radius:14px;line-height:1.35;font-size:14px;white-space:pre-wrap;word-break:break-word}
.rsd-widget-msg--agent{background:#fff;border:1px solid #e5e7eb;align-self:flex-start}
.rsd-widget-msg--user{background:#111827;color:#fff;align-self:flex-end}
.rsd-widget-msg--error{background:#fee2e2;color:#991b1b;align-self:flex-start}
.rsd-widget-form{display:flex;gap:8px;padding:12px;border-top:1px solid #e5e7eb;background:#fff}
.rsd-widget-input{flex:1;border:1px solid #d1d5db;border-radius:10px;padding:10px 12px;font-size:14px;outline:none;background:#fff;color:#111827}
.rsd-widget-input:focus{border-color:#6b7280}
.rsd-widget-send{border:none;border-radius:10px;padding:10px 14px;background:#111827;color:#fff;cursor:pointer;font-size:14px}
.rsd-widget-send:disabled{opacity:.55;cursor:not-allowed}
.rsd-widget-bubbles{position:absolute;bottom:70px;right:0;display:flex;flex-direction:column;align-items:flex-end;gap:8px;max-width:min(420px,calc(100vw - 24px));pointer-events:none}
.rsd-widget-root[data-position="bottom-left"] .rsd-widget-bubbles{right:auto;left:0;align-items:flex-start}
.rsd-widget-bubble{position:relative;width:fit-content;max-width:min(420px,calc(100vw - 24px));background:#fff;border:1px solid #e5e7eb;border-radius:14px 14px 4px 14px;padding:12px 38px 12px 14px;box-shadow:0 8px 24px rgba(15,23,42,.18);font-size:14px;line-height:1.4;color:#111827;cursor:pointer;animation:rsd-in .3s ease;pointer-events:auto;transition:transform .28s ease,opacity .22s ease}
.rsd-widget-root[data-position="bottom-left"] .rsd-widget-bubble{border-radius:14px 14px 14px 4px}
@keyframes rsd-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.rsd-widget-bubble-close{position:absolute;top:7px;right:8px;background:none;border:none;cursor:pointer;font-size:16px;color:#9ca3af;line-height:1;padding:2px 4px}
.rsd-widget-bubble-close:hover{color:#374151}
.rsd-widget-bubble p{margin:0;pointer-events:none}
.rsd-widget-root[data-theme="light"] .rsd-widget-toggle{background:#6b7280;box-shadow:0 10px 30px rgba(107,114,128,.35)}
.rsd-widget-root[data-theme="light"] .rsd-widget-header{background:#6b7280}
.rsd-widget-root[data-theme="light"] .rsd-widget-msg--user{background:#6b7280}
.rsd-widget-root[data-theme="light"] .rsd-widget-send{background:#6b7280}
.rsd-widget-root[data-theme="light"] .rsd-widget-input:focus{border-color:#6b7280}
.rsd-widget-root[data-theme="ocean"] .rsd-widget-toggle{background:#0369a1;box-shadow:0 10px 30px rgba(3,105,161,.35)}
.rsd-widget-root[data-theme="ocean"] .rsd-widget-header{background:#0369a1}
.rsd-widget-root[data-theme="ocean"] .rsd-widget-messages{background:#f0f9ff}
.rsd-widget-root[data-theme="ocean"] .rsd-widget-msg--agent{border-color:#bae6fd}
.rsd-widget-root[data-theme="ocean"] .rsd-widget-msg--user{background:#0369a1}
.rsd-widget-root[data-theme="ocean"] .rsd-widget-panel{border-color:#bae6fd}
.rsd-widget-root[data-theme="ocean"] .rsd-widget-send{background:#0369a1}
.rsd-widget-root[data-theme="ocean"] .rsd-widget-input:focus{border-color:#0369a1}
.rsd-widget-root[data-theme="forest"] .rsd-widget-toggle{background:#166534;box-shadow:0 10px 30px rgba(22,101,52,.35)}
.rsd-widget-root[data-theme="forest"] .rsd-widget-header{background:#166534}
.rsd-widget-root[data-theme="forest"] .rsd-widget-messages{background:#f0fdf4}
.rsd-widget-root[data-theme="forest"] .rsd-widget-msg--agent{border-color:#bbf7d0}
.rsd-widget-root[data-theme="forest"] .rsd-widget-msg--user{background:#166534}
.rsd-widget-root[data-theme="forest"] .rsd-widget-panel{border-color:#bbf7d0}
.rsd-widget-root[data-theme="forest"] .rsd-widget-send{background:#166534}
.rsd-widget-root[data-theme="forest"] .rsd-widget-input:focus{border-color:#166534}
.rsd-widget-root[data-theme="sunset"] .rsd-widget-toggle{background:#c2410c;box-shadow:0 10px 30px rgba(194,65,12,.35)}
.rsd-widget-root[data-theme="sunset"] .rsd-widget-header{background:#c2410c}
.rsd-widget-root[data-theme="sunset"] .rsd-widget-messages{background:#fff7ed}
.rsd-widget-root[data-theme="sunset"] .rsd-widget-msg--agent{border-color:#fed7aa}
.rsd-widget-root[data-theme="sunset"] .rsd-widget-msg--user{background:#c2410c}
.rsd-widget-root[data-theme="sunset"] .rsd-widget-panel{border-color:#fed7aa}
.rsd-widget-root[data-theme="sunset"] .rsd-widget-send{background:#c2410c}
.rsd-widget-root[data-theme="sunset"] .rsd-widget-input:focus{border-color:#c2410c}
.rsd-widget-root[data-theme="darkmode"] .rsd-widget-toggle{background:#4f46e5;box-shadow:0 10px 30px rgba(79,70,229,.35)}
.rsd-widget-root[data-theme="darkmode"] .rsd-widget-panel{background:#1f2937;border-color:#374151}
.rsd-widget-root[data-theme="darkmode"] .rsd-widget-header{background:#111827}
.rsd-widget-root[data-theme="darkmode"] .rsd-widget-messages{background:#111827}
.rsd-widget-root[data-theme="darkmode"] .rsd-widget-msg--agent{background:#374151;border-color:#4b5563;color:#f9fafb}
.rsd-widget-root[data-theme="darkmode"] .rsd-widget-msg--user{background:#4f46e5}
.rsd-widget-root[data-theme="darkmode"] .rsd-widget-form{background:#1f2937;border-top-color:#374151}
.rsd-widget-root[data-theme="darkmode"] .rsd-widget-input{background:#374151;border-color:#4b5563;color:#f9fafb}
.rsd-widget-root[data-theme="darkmode"] .rsd-widget-input:focus{border-color:#6366f1}
.rsd-widget-root[data-theme="darkmode"] .rsd-widget-send{background:#4f46e5}
.rsd-widget-root[data-theme="darkmode"] .rsd-widget-bubble{background:#1f2937;border-color:#374151;color:#f9fafb}
@media (max-width:480px){.rsd-widget-root[data-position="bottom-right"]{right:12px;bottom:12px;left:auto}.rsd-widget-root[data-position="bottom-left"]{left:12px;bottom:12px;right:auto}.rsd-widget-panel{width:min(calc(100vw - 24px),400px);left:auto;right:0;max-height:calc(100vh - 94px)}.rsd-widget-root[data-position="bottom-left"] .rsd-widget-panel{left:0;right:auto}.rsd-widget-bubbles,.rsd-widget-bubble{max-width:calc(100vw - 24px)}}
""".strip()

WIDGET_JS = """
(function () {
  if (window.RSDChatWidgetInitialized) return;
  window.RSDChatWidgetInitialized = true;

  function pickScript() {
    var scripts = document.querySelectorAll("script[data-rsd-widget]");
    return scripts[scripts.length - 1] || document.currentScript;
  }

  function ensureCss(href) {
    if (document.querySelector('link[data-rsd-widget-css="1"]')) return;
    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    link.setAttribute("data-rsd-widget-css", "1");
    document.head.appendChild(link);
  }

  function uid(key) {
    try {
      var v = localStorage.getItem(key);
      if (v) return v;
      v = "web_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem(key, v);
      return v;
    } catch (e) {
      return "web_" + Math.random().toString(36).slice(2);
    }
  }

  var script = pickScript();
  if (!script) return;

  var apiBase = (script.dataset.apiBase || "").replace(/\\/$/, "");
  var apiKey = script.dataset.apiKey || "";
  if (!apiBase || !apiKey) {
    console.error("[RSD widget] Missing data-api-base or data-api-key");
    return;
  }

  var title = script.dataset.title || "Онлайн-консультант";
  var greeting = script.dataset.greeting || "Здравствуйте! Чем могу помочь?";
  var placeholder = script.dataset.placeholder || "Напишите сообщение...";
  var position = script.dataset.position === "bottom-left" ? "bottom-left" : "bottom-right";
  var theme = (script.dataset.theme || "dark").trim();
  var providedUserId = script.dataset.userId || "";
  var userName = script.dataset.userName || "";
  var openOnStart = script.dataset.open === "true";

  var proactiveMsg1 = (script.dataset.proactiveMessage || "").trim();
  var proactiveMsg2 = (script.dataset.proactiveMessage2 || "").trim();
  var delay1Sec = parseFloat(script.dataset.proactiveDelay || "0");
  var legacyDelayMs = Number(script.dataset.proactiveDelayMs || "0");
  var delay1Ms = delay1Sec > 0 ? delay1Sec * 1000 : (legacyDelayMs > 0 ? legacyDelayMs : 3000);
  var delay2Sec = parseFloat(script.dataset.proactiveDelay2 || "0");
  var delay2Ms = delay2Sec > 0 ? delay2Sec * 1000 : 1000;

  ensureCss(apiBase + "/api/agents/external/widget.css");
  var userId = providedUserId || uid("rsd_uid_" + apiKey.slice(-8));

  var histKey = "rsd_hist_" + apiKey.slice(-8) + "_" + userId.slice(-8);
  function loadHistory() {
    try { var r = localStorage.getItem(histKey); return r ? JSON.parse(r) : null; } catch (e) { return null; }
  }
  function saveHistory(arr) {
    try {
      var trimmed = arr.length > 100 ? arr.slice(arr.length - 100) : arr;
      localStorage.setItem(histKey, JSON.stringify(trimmed));
    } catch (e) {}
  }
  var chatHistory = [];

  var root = document.createElement("div");
  root.className = "rsd-widget-root";
  root.setAttribute("data-position", position);
  root.setAttribute("data-theme", theme);
  root.innerHTML =
    '<button type="button" class="rsd-widget-toggle" aria-label="Открыть чат">💬</button>' +
    '<section class="rsd-widget-panel" style="display:none;">' +
    '<header class="rsd-widget-header">' +
    '<span class="rsd-widget-header-title"></span>' +
    '<button type="button" class="rsd-widget-header-close" aria-label="Закрыть">✕</button>' +
    '</header>' +
    '<div class="rsd-widget-messages"></div>' +
    '<form class="rsd-widget-form">' +
    '<input class="rsd-widget-input" type="text" maxlength="4000" />' +
    '<button class="rsd-widget-send" type="submit">Отправить</button>' +
    "</form></section>";
  document.body.appendChild(root);

  var toggle = root.querySelector(".rsd-widget-toggle");
  var panel = root.querySelector(".rsd-widget-panel");
  var headerTitle = root.querySelector(".rsd-widget-header-title");
  var headerClose = root.querySelector(".rsd-widget-header-close");
  var messages = root.querySelector(".rsd-widget-messages");
  var form = root.querySelector(".rsd-widget-form");
  var input = root.querySelector(".rsd-widget-input");
  var sendBtn = root.querySelector(".rsd-widget-send");
  headerTitle.textContent = title;
  input.placeholder = placeholder;

  function pushMessage(role, text, persist) {
    var el = document.createElement("div");
    el.className = "rsd-widget-msg " + (role === "user" ? "rsd-widget-msg--user" : role === "error" ? "rsd-widget-msg--error" : "rsd-widget-msg--agent");
    el.textContent = text;
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    if (persist !== false && role !== "error") {
      chatHistory.push({ role: role, text: text });
      saveHistory(chatHistory);
    }
  }

  var stored = loadHistory();
  if (stored && stored.length > 0) {
    chatHistory = stored;
    stored.forEach(function (m) { pushMessage(m.role, m.text, false); });
  } else {
    pushMessage("agent", greeting);
  }

  function setLoading(flag) {
    sendBtn.disabled = !!flag;
    input.disabled = !!flag;
  }

  async function sendMessage(text) {
    setLoading(true);
    try {
      var response = await fetch(apiBase + "/api/agents/external/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Agent-API-Key": apiKey },
        body: JSON.stringify({ message: text, external_user_id: userId, external_user_name: userName || null })
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
      var payload = await response.json();
      if (payload.reply === false) return;
      var answer = (payload.answer || "").trim();
      if (!answer) return;
      pushMessage("agent", answer);
    } catch (err) {
      pushMessage("error", "Не удалось отправить сообщение. Попробуйте еще раз.");
    } finally {
      setLoading(false);
    }
  }

  var bubbleContainer = document.createElement("div");
  bubbleContainer.className = "rsd-widget-bubbles";
  root.insertBefore(bubbleContainer, panel);

  function dismissBubble(target) {
    var items = target ? [target] : Array.prototype.slice.call(bubbleContainer.querySelectorAll(".rsd-widget-bubble"));
    items.forEach(function (b) {
      b.style.opacity = "0";
      b.style.transform = "translateY(6px)";
      setTimeout(function () { if (b.parentNode) b.parentNode.removeChild(b); }, 220);
    });
  }

  function openPanel() {
    if (panel.style.display !== "none") return;
    panel.style.display = "flex";
    dismissBubble();
    setTimeout(function () { input.focus(); }, 50);
  }

  function closePanel() {
    panel.style.display = "none";
  }

  function showBubble(text) {
    var existing = Array.prototype.slice.call(bubbleContainer.querySelectorAll(".rsd-widget-bubble"));
    var before = existing.map(function (node) { return { node: node, top: node.getBoundingClientRect().top }; });
    var bubble = document.createElement("div");
    bubble.className = "rsd-widget-bubble";
    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "rsd-widget-bubble-close";
    closeBtn.setAttribute("aria-label", "Закрыть");
    closeBtn.textContent = "✕";
    closeBtn.addEventListener("click", function (e) { e.stopPropagation(); dismissBubble(bubble); });
    var p = document.createElement("p");
    p.textContent = text;
    bubble.appendChild(closeBtn);
    bubble.appendChild(p);
    bubble.addEventListener("click", function () { openPanel(); });
    bubbleContainer.appendChild(bubble);

    before.forEach(function (entry) {
      var delta = entry.top - entry.node.getBoundingClientRect().top;
      if (!delta) return;
      entry.node.style.transform = "translateY(" + delta + "px)";
      entry.node.getBoundingClientRect();
      entry.node.style.transform = "";
    });

    var all = bubbleContainer.querySelectorAll(".rsd-widget-bubble");
    if (all.length > 2) {
      dismissBubble(all[0]);
    }
  }

  toggle.addEventListener("click", function () {
    if (panel.style.display !== "none") { closePanel(); } else { openPanel(); }
  });

  headerClose.addEventListener("click", closePanel);

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var text = (input.value || "").trim();
    if (!text) return;
    input.value = "";
    pushMessage("user", text);
    sendMessage(text);
  });

  if (openOnStart) openPanel();

  if (proactiveMsg1) {
    setTimeout(function () {
      if (panel.style.display !== "none") return;
      showBubble(proactiveMsg1);
      if (proactiveMsg2) {
        setTimeout(function () {
          if (panel.style.display !== "none") { dismissBubble(); return; }
          showBubble(proactiveMsg2);
        }, delay2Ms);
      }
    }, delay1Ms);
  }
})();
""".strip()


def _assert_https_for_sensitive_endpoint(request: Request) -> None:
    if not is_request_secure(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HTTPS is required for this endpoint",
        )


def _summarize_tool_event_for_log(event: dict) -> str:
    tool_name = str(event.get("tool_name") or "unknown")
    tool_status = str(event.get("tool_status") or "unknown")
    latency_ms = int(event.get("latency_ms") or 0)
    provider = str(event.get("crm_provider") or "unknown")
    replay = bool(event.get("idempotent_replay"))
    error = redact_pii_text(str(event.get("error") or "")).strip()
    parts = [
        f"tool={tool_name}",
        f"status={tool_status}",
        f"latency_ms={latency_ms}",
        f"crm_provider={provider}",
        f"idempotent_replay={str(replay).lower()}",
    ]
    if error:
        parts.append(f"error={error}")
    return " ".join(parts)


def _initial_agent_billing_fields(template_type: str, *, user=None) -> dict[str, object]:
    from ..agent_template_pricing import (
        get_agent_template_pricing,
        initial_maintenance_paid_until_for_template,
        user_has_free_agent_activation,
    )

    pricing = get_agent_template_pricing(template_type)
    if not pricing:
        return {}
    fields: dict[str, object] = {}
    if pricing.setup_rub_min <= 0 or user_has_free_agent_activation(user):
        fields["activation_paid_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
    grace_until = initial_maintenance_paid_until_for_template(template_type)
    if grace_until is not None:
        fields["maintenance_paid_until"] = grace_until
    return fields


def _normalize_template_type(template_type: str | None, *, allow_legacy: bool = False) -> str:
    from ..agent_template_pricing import (
        TEMPLATE_TYPES_IN_DEVELOPMENT,
        assert_template_selectable,
        get_agent_template_pricing,
    )

    raw = (template_type or "qa").strip().lower()
    normalized = LEGACY_TEMPLATE_TYPE_ALIASES.get(raw, raw)
    if normalized not in SUPPORTED_TEMPLATE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported template_type: {template_type}",
        )
    if not allow_legacy and normalized in TEMPLATE_TYPES_IN_DEVELOPMENT:
        pricing = get_agent_template_pricing(normalized)
        title = pricing.title if pricing else normalized
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Шаблон «{title}» находится в разработке и недоступен для создания",
        )
    if not allow_legacy:
        try:
            assert_template_selectable(normalized)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
    return normalized


def _default_crm_admin_config() -> dict[str, object]:
    return {
        "workflow_mode": "booking",
        "domain_type": "beauty_salon",
        "application_fields": [],
        "crm_mode": "optional",
        # Keep runtime-compatible behavior for current implementation.
        "booking_backend": "crm",
        "crm_provider": "amocrm",
        "allowed_tools": list(DEFAULT_CRM_ALLOWED_TOOLS),
        "allowed_booking_tools": list(DEFAULT_BOOKING_ALLOWED_TOOLS),
        "allowed_application_tools": list(DEFAULT_APPLICATION_ALLOWED_TOOLS),
        "confirmation_policy": "confirm_risky",
        "fallback_mode": "ask_clarifying_question",
        "waitlist_enabled": True,
        "reminder_enabled": True,
        "reminder_offsets_hours": [24, 2],
        "paid_booking_enabled": False,
        "appointment_confirmation_enabled": True,
        "field_mapping": None,
        "resources_enabled": True,
        "resource_linked_to_staff": True,
        "custom_staff_role": None,
        "custom_staff_label": None,
        "custom_resource_types": None,
        "custom_domain_instruction": None,
        "http_integrations_enabled": True,
        "http_integration_names": None,
    }


def _migrate_crm_admin_config(raw_config: dict | None) -> dict[str, object]:
    raw = raw_config if isinstance(raw_config, dict) else {}
    defaults = _default_crm_admin_config()

    # Legacy compatibility: support both `crm_mode` and older aliases if they ever appear.
    crm_mode_raw = raw.get("crm_mode", raw.get("integration_mode", defaults["crm_mode"]))
    workflow_mode = str(raw.get("workflow_mode") or defaults["workflow_mode"]).strip().lower()
    domain_type = str(raw.get("domain_type") or defaults["domain_type"]).strip().lower()
    crm_mode = str(crm_mode_raw or defaults["crm_mode"]).strip().lower()
    booking_backend = str(raw.get("booking_backend") or defaults["booking_backend"]).strip().lower()
    crm_provider = str(raw.get("crm_provider") or defaults["crm_provider"]).strip().lower()
    confirmation_policy = str(raw.get("confirmation_policy") or defaults["confirmation_policy"]).strip().lower()
    fallback_mode = str(raw.get("fallback_mode") or defaults["fallback_mode"]).strip().lower()

    if domain_type not in CRM_DOMAIN_TYPES:
        valid = ", ".join(sorted(CRM_DOMAIN_TYPES))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"template_config.domain_type must be one of: {valid}",
        )
    if workflow_mode not in CRM_WORKFLOW_MODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.workflow_mode must be one of: booking, applications",
        )
    if crm_mode not in CRM_MODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.crm_mode must be one of: disabled, optional, required",
        )
    if booking_backend not in CRM_BOOKING_BACKENDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.booking_backend must be one of: local, crm, auto",
        )
    if crm_provider not in CRM_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.crm_provider must be one of: amocrm, bitrix24",
        )
    if confirmation_policy not in CRM_CONFIRMATION_POLICIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.confirmation_policy is invalid",
        )
    if fallback_mode not in CRM_FALLBACK_MODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.fallback_mode is invalid",
        )

    allowed_booking_tools_raw = raw.get("allowed_booking_tools")
    if allowed_booking_tools_raw is None:
        allowed_booking_tools = list(DEFAULT_BOOKING_ALLOWED_TOOLS)
    elif isinstance(allowed_booking_tools_raw, list):
        allowed_booking_tools = []
        for item in allowed_booking_tools_raw:
            tool = str(item or "").strip()
            if tool and tool not in allowed_booking_tools:
                allowed_booking_tools.append(tool)
        if not allowed_booking_tools:
            allowed_booking_tools = list(DEFAULT_BOOKING_ALLOWED_TOOLS)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.allowed_booking_tools must be an array of strings",
        )

    allowed_application_tools_raw = raw.get("allowed_application_tools")
    if allowed_application_tools_raw is None:
        allowed_application_tools = list(DEFAULT_APPLICATION_ALLOWED_TOOLS)
    elif isinstance(allowed_application_tools_raw, list):
        allowed_application_tools = []
        for item in allowed_application_tools_raw:
            tool = str(item or "").strip()
            if tool and tool not in allowed_application_tools:
                allowed_application_tools.append(tool)
        if not allowed_application_tools:
            allowed_application_tools = list(DEFAULT_APPLICATION_ALLOWED_TOOLS)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.allowed_application_tools must be an array of strings",
        )

    from ..services.admin_applications.fields import normalize_application_fields

    application_fields_raw = raw.get("application_fields", defaults["application_fields"])
    try:
        application_fields = normalize_application_fields(application_fields_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    if workflow_mode == "applications" and not application_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.application_fields must contain at least one field when workflow_mode is applications",
        )

    waitlist_enabled = bool(raw.get("waitlist_enabled", defaults["waitlist_enabled"]))
    reminder_enabled = bool(raw.get("reminder_enabled", defaults["reminder_enabled"]))
    appointment_confirmation_enabled = bool(
        raw.get("appointment_confirmation_enabled", defaults["appointment_confirmation_enabled"])
    )
    paid_booking_enabled = bool(raw.get("paid_booking_enabled", defaults["paid_booking_enabled"]))
    reminder_offsets_raw = raw.get("reminder_offsets_hours", defaults["reminder_offsets_hours"])
    if not isinstance(reminder_offsets_raw, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.reminder_offsets_hours must be an array of integers",
        )
    reminder_offsets_hours: list[int] = []
    for item in reminder_offsets_raw:
        try:
            value = int(item)
        except Exception:
            continue
        if 1 <= value <= 72 and value not in reminder_offsets_hours:
            reminder_offsets_hours.append(value)
    if not reminder_offsets_hours:
        reminder_offsets_hours = [24, 2]

    allowed_tools_raw = raw.get("allowed_tools")
    if allowed_tools_raw is None:
        allowed_tools = list(DEFAULT_CRM_ALLOWED_TOOLS)
    elif isinstance(allowed_tools_raw, list):
        allowed_tools = []
        for item in allowed_tools_raw:
            tool = str(item or "").strip()
            if tool and tool not in allowed_tools:
                allowed_tools.append(tool)
        if not allowed_tools:
            allowed_tools = list(DEFAULT_CRM_ALLOWED_TOOLS)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.allowed_tools must be an array of strings",
        )

    field_mapping_raw = raw.get("field_mapping")
    field_mapping = None
    if field_mapping_raw is not None:
        if not isinstance(field_mapping_raw, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.field_mapping must be an object",
            )
        normalized_mapping = {}
        for key, value in field_mapping_raw.items():
            k = str(key or "").strip()
            v = str(value or "").strip()
            if k and v:
                normalized_mapping[k] = v
        field_mapping = normalized_mapping or None

    resources_enabled = bool(raw.get("resources_enabled", defaults["resources_enabled"]))
    resource_linked_to_staff = bool(raw.get("resource_linked_to_staff", defaults["resource_linked_to_staff"]))

    custom_staff_role_raw = raw.get("custom_staff_role")
    custom_staff_role = str(custom_staff_role_raw).strip()[:32] if custom_staff_role_raw else None

    custom_staff_label_raw = raw.get("custom_staff_label")
    custom_staff_label = str(custom_staff_label_raw).strip()[:64] if custom_staff_label_raw else None

    custom_resource_types_raw = raw.get("custom_resource_types")
    if custom_resource_types_raw is None:
        custom_resource_types = None
    elif isinstance(custom_resource_types_raw, list):
        custom_resource_types = [str(t).strip()[:32] for t in custom_resource_types_raw if str(t).strip()] or None
    else:
        custom_resource_types = None

    custom_domain_instruction_raw = raw.get("custom_domain_instruction")
    custom_domain_instruction = str(custom_domain_instruction_raw).strip()[:4000] if custom_domain_instruction_raw else None

    http_integrations_enabled = bool(raw.get("http_integrations_enabled", defaults["http_integrations_enabled"]))
    http_integration_names_raw = raw.get("http_integration_names")
    if http_integration_names_raw is None:
        http_integration_names = defaults["http_integration_names"]
    elif isinstance(http_integration_names_raw, list):
        http_integration_names = []
        for item in http_integration_names_raw:
            slug = str(item or "").strip().lower()
            if slug and slug not in http_integration_names:
                http_integration_names.append(slug)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.http_integration_names must be an array of strings or null",
        )

    return {
        "workflow_mode": workflow_mode,
        "domain_type": domain_type,
        "application_fields": application_fields,
        "crm_mode": crm_mode,
        "booking_backend": booking_backend,
        "crm_provider": crm_provider,
        "allowed_tools": allowed_tools,
        "allowed_booking_tools": allowed_booking_tools,
        "allowed_application_tools": allowed_application_tools,
        "confirmation_policy": confirmation_policy,
        "fallback_mode": fallback_mode,
        "waitlist_enabled": waitlist_enabled,
        "reminder_enabled": reminder_enabled,
        "reminder_offsets_hours": reminder_offsets_hours,
        "paid_booking_enabled": paid_booking_enabled,
        "appointment_confirmation_enabled": appointment_confirmation_enabled,
        "field_mapping": field_mapping,
        "resources_enabled": resources_enabled,
        "resource_linked_to_staff": resource_linked_to_staff,
        "custom_staff_role": custom_staff_role,
        "custom_staff_label": custom_staff_label,
        "custom_resource_types": custom_resource_types,
        "custom_domain_instruction": custom_domain_instruction,
        "http_integrations_enabled": http_integrations_enabled,
        "http_integration_names": http_integration_names,
    }


def _normalize_template_config(template_type: str, template_config: dict | None) -> str | None:
    raw = template_config or {}
    if not isinstance(raw, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config must be a JSON object",
        )
    common_config: dict[str, object] = {}
    if "enable_chat_portrait" in raw:
        common_config["enable_chat_portrait"] = bool(raw.get("enable_chat_portrait"))
    if "enable_phone_portrait" in raw:
        common_config["enable_phone_portrait"] = bool(raw.get("enable_phone_portrait"))
    if "enable_smart_search" in raw:
        common_config["enable_smart_search"] = bool(raw.get("enable_smart_search"))
    if "enable_human_delay" in raw:
        common_config["enable_human_delay"] = bool(raw.get("enable_human_delay"))
    if "enable_chat_history" in raw:
        common_config["enable_chat_history"] = bool(raw.get("enable_chat_history"))
    # Chat freeze feature is available only for QA template.
    if template_type == "qa" and "enable_chat_freeze" in raw:
        common_config["enable_chat_freeze"] = bool(raw.get("enable_chat_freeze"))
    if "agent_availability" in raw:
        common_config["agent_availability"] = normalize_agent_availability_for_storage(
            raw.get("agent_availability")
        )
    if "portrait_model" in raw:
        portrait_model = str(raw.get("portrait_model") or "").strip()
        if portrait_model:
            common_config["portrait_model"] = portrait_model

    if template_type == "content_factory":
        company_name = str(raw.get("company_name") or "").strip()
        company_activity = str(raw.get("company_activity") or "").strip()
        if not company_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.company_name is required for content_factory",
            )
        if not company_activity:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.company_activity is required for content_factory",
            )
        if len(company_name) > 255 or len(company_activity) > 2000:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.company_name/company_activity are too long",
            )

        brand_tone = str(raw.get("brand_tone") or "").strip() or None
        if brand_tone and len(brand_tone) > 500:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.brand_tone is too long",
            )

        content_language = str(
            raw.get("content_language") or CONTENT_FACTORY_DEFAULT_CONFIG["content_language"]
        ).strip().lower()
        if not CONTENT_FACTORY_LANGUAGE_PATTERN.fullmatch(content_language):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.content_language must be an IETF-like tag (e.g. ru, en, pt-br)",
            )

        daily_posting_enabled_raw = raw.get(
            "daily_posting_enabled",
            CONTENT_FACTORY_DEFAULT_CONFIG["daily_posting_enabled"],
        )
        if not isinstance(daily_posting_enabled_raw, bool):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.daily_posting_enabled must be a boolean",
            )
        daily_posting_enabled = daily_posting_enabled_raw

        daily_post_time = str(
            raw.get("daily_post_time") or CONTENT_FACTORY_DEFAULT_CONFIG["daily_post_time"]
        ).strip()
        if not CONTENT_FACTORY_TIME_PATTERN.fullmatch(daily_post_time):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.daily_post_time must be in HH:MM format",
            )

        timezone_name = str(raw.get("timezone") or CONTENT_FACTORY_DEFAULT_CONFIG["timezone"]).strip()
        if not timezone_name:
            timezone_name = str(CONTENT_FACTORY_DEFAULT_CONFIG["timezone"])
        if not CONTENT_FACTORY_TIMEZONE_PATTERN.fullmatch(timezone_name):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.timezone format is invalid",
            )

        video_duration_raw = raw.get(
            "video_duration_seconds",
            CONTENT_FACTORY_DEFAULT_CONFIG["video_duration_seconds"],
        )
        try:
            video_duration_seconds = int(video_duration_raw)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.video_duration_seconds must be an integer",
            ) from None
        if video_duration_seconds < 1 or video_duration_seconds > 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.video_duration_seconds must be between 1 and 8 for MVP",
            )

        kling_model = str(raw.get("kling_model") or CONTENT_FACTORY_DEFAULT_CONFIG["kling_model"]).strip()
        if not kling_model:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.kling_model must be non-empty",
            )
        if len(kling_model) > 128:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.kling_model is too long",
            )

        normalized_config = {
            "company_name": company_name,
            "company_activity": company_activity,
            "brand_tone": brand_tone,
            "content_language": content_language,
            "daily_posting_enabled": daily_posting_enabled,
            "daily_post_time": daily_post_time,
            "timezone": timezone_name,
            "video_duration_seconds": video_duration_seconds,
            "kling_model": kling_model,
            **common_config,
        }
        return json.dumps(normalized_config, ensure_ascii=False)

    if template_type == "sales_manager":
        mode = str(raw.get("mode") or SALES_DEFAULT_CONFIG["mode"]).strip().lower()
        if mode not in SALES_MODES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.mode must be one of: draft_only, semi_auto, auto",
            )

        qualification_model = str(
            raw.get("qualification_model") or SALES_DEFAULT_CONFIG["qualification_model"]
        ).strip()
        generation_model = str(
            raw.get("generation_model") or SALES_DEFAULT_CONFIG["generation_model"]
        ).strip()
        if not qualification_model or not generation_model:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config qualification_model/generation_model must be non-empty",
            )

        min_confidence_raw = raw.get("min_confidence", SALES_DEFAULT_CONFIG["min_confidence"])
        try:
            min_confidence = float(min_confidence_raw)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.min_confidence must be a number",
            ) from None
        if min_confidence < 0.0 or min_confidence > 1.0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.min_confidence must be between 0 and 1",
            )

        sales_product_name = str(raw.get("sales_product_name") or SALES_DEFAULT_CONFIG["sales_product_name"]).strip()
        sales_offer_type = str(raw.get("sales_offer_type") or SALES_DEFAULT_CONFIG["sales_offer_type"]).strip()
        sales_usp = str(raw.get("sales_usp") or SALES_DEFAULT_CONFIG["sales_usp"]).strip()
        workflow_completion_mode = str(
            raw.get("workflow_completion_mode") or SALES_DEFAULT_CONFIG["workflow_completion_mode"]
        ).strip().lower()
        if workflow_completion_mode not in SALES_WORKFLOW_COMPLETION_MODES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.workflow_completion_mode must be one of: auto_finish_on_signal, continue_dialog",
            )
        lead_score_scale_raw = raw.get("lead_score_scale", SALES_DEFAULT_CONFIG["lead_score_scale"])
        try:
            lead_score_scale = int(lead_score_scale_raw)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.lead_score_scale must be an integer",
            ) from None
        if lead_score_scale not in SALES_SCORE_SCALES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.lead_score_scale must be one of: 10, 100",
            )
        if len(sales_product_name) > 255 or len(sales_offer_type) > 128 or len(sales_usp) > 2000:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config sales fields are too long",
            )
        lead_generation_enabled = bool(
            raw.get("lead_generation_enabled", SALES_DEFAULT_CONFIG["lead_generation_enabled"])
        )
        contacts_pool_only = bool(
            raw.get("contacts_pool_only", SALES_DEFAULT_CONFIG["contacts_pool_only"])
        )
        neuro_commenting_enabled = bool(
            raw.get("neuro_commenting_enabled", SALES_DEFAULT_CONFIG["neuro_commenting_enabled"])
        )
        live_chat_simulation_enabled = bool(
            raw.get(
                "live_chat_simulation_enabled",
                SALES_DEFAULT_CONFIG["live_chat_simulation_enabled"],
            )
        )

        scan_scope_raw = raw.get("scan_scope")
        if scan_scope_raw is None:
            scan_scope_raw = SALES_DEFAULT_CONFIG["scan_scope"]
        if not isinstance(scan_scope_raw, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.scan_scope must be an object",
            )

        def _normalize_chat_ids(value: list | None) -> list[int]:
            if value is None:
                return []
            if not isinstance(value, list):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="scan_scope chat ids must be arrays",
                )
            normalized_ids: list[int] = []
            for item in value:
                try:
                    chat_id = int(str(item).strip())
                except (TypeError, ValueError):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="scan_scope chat ids must contain integers",
                    ) from None
                if chat_id not in normalized_ids:
                    normalized_ids.append(chat_id)
            return normalized_ids

        include_chat_ids = _normalize_chat_ids(scan_scope_raw.get("include_chat_ids"))
        exclude_chat_ids = _normalize_chat_ids(scan_scope_raw.get("exclude_chat_ids"))
        scan_scope = {
            "include_chat_ids": include_chat_ids,
            "exclude_chat_ids": exclude_chat_ids,
        }

        dm_limits_raw = raw.get("dm_limits")
        if dm_limits_raw is None:
            dm_limits_raw = SALES_DEFAULT_CONFIG["dm_limits"]
        if not isinstance(dm_limits_raw, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.dm_limits must be an object",
            )

        def _normalize_positive_int(name: str, default_value: int, max_value: int) -> int:
            value = dm_limits_raw.get(name, default_value)
            try:
                normalized = int(value)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"template_config.dm_limits.{name} must be an integer",
                ) from None
            if normalized < 1 or normalized > max_value:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"template_config.dm_limits.{name} must be between 1 and {max_value}",
                )
            return normalized

        dm_limits = {
            "per_minute": _normalize_positive_int("per_minute", 3, 60),
            "per_hour": _normalize_positive_int("per_hour", 25, 600),
            "per_day": _normalize_positive_int("per_day", 120, 5000),
            "per_source_chat_per_day": _normalize_positive_int("per_source_chat_per_day", 40, 2000),
        }

        cooldown_days_raw = raw.get("cooldown_days", SALES_DEFAULT_CONFIG["cooldown_days"])
        dedup_window_days_raw = raw.get("dedup_window_days", SALES_DEFAULT_CONFIG["dedup_window_days"])
        try:
            cooldown_days = int(cooldown_days_raw)
            dedup_window_days = int(dedup_window_days_raw)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.cooldown_days/dedup_window_days must be integers",
            ) from None
        if cooldown_days < 1 or cooldown_days > 365:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.cooldown_days must be between 1 and 365",
            )
        if dedup_window_days < 1 or dedup_window_days > 365:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.dedup_window_days must be between 1 and 365",
            )

        allowed_languages_raw = raw.get("allowed_languages")
        if allowed_languages_raw is None:
            allowed_languages = list(SALES_DEFAULT_CONFIG["allowed_languages"])
        elif isinstance(allowed_languages_raw, list):
            allowed_languages = []
            for item in allowed_languages_raw:
                lang = str(item or "").strip().lower()
                if lang in SALES_ALLOWED_LANGUAGES and lang not in allowed_languages:
                    allowed_languages.append(lang)
            if not allowed_languages:
                allowed_languages = list(SALES_DEFAULT_CONFIG["allowed_languages"])
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.allowed_languages must be an array of strings",
            )

        quiet_hours_local = str(raw.get("quiet_hours_local") or SALES_DEFAULT_CONFIG["quiet_hours_local"]).strip()
        if quiet_hours_local != "22:00-09:00":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.quiet_hours_local currently supports only: 22:00-09:00",
            )

        offer_profile_raw = raw.get("offer_profile_id")
        offer_profile_id = None
        if offer_profile_raw is not None:
            offer_profile_value = str(offer_profile_raw).strip()
            offer_profile_id = offer_profile_value or None

        confirmation_policy = str(
            raw.get("confirmation_policy") or SALES_DEFAULT_CONFIG["confirmation_policy"]
        ).strip().lower()
        if confirmation_policy not in SALES_CONFIRMATION_POLICIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.confirmation_policy must be one of: always_confirm, confirm_risky, never_confirm",
            )

        allowed_tools_raw = raw.get("allowed_tools")
        if allowed_tools_raw is None:
            allowed_tools = list(SALES_DEFAULT_ALLOWED_TOOLS)
        elif isinstance(allowed_tools_raw, list):
            allowed_tools = []
            for item in allowed_tools_raw:
                tool = str(item or "").strip()
                if tool and tool in SALES_DEFAULT_ALLOWED_TOOLS and tool not in allowed_tools:
                    allowed_tools.append(tool)
            if not allowed_tools:
                allowed_tools = list(SALES_DEFAULT_ALLOWED_TOOLS)
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.allowed_tools must be an array of strings",
            )
        trigger_words = _normalize_sales_trigger_words(raw.get("trigger_words"))

        normalized_config = {
            "mode": mode,
            "qualification_model": qualification_model,
            "generation_model": generation_model,
            "min_confidence": min_confidence,
            "sales_product_name": sales_product_name,
            "sales_offer_type": sales_offer_type,
            "sales_usp": sales_usp,
            "workflow_completion_mode": workflow_completion_mode,
            "lead_score_scale": lead_score_scale,
            "lead_generation_enabled": lead_generation_enabled,
            "contacts_pool_only": contacts_pool_only,
            "neuro_commenting_enabled": neuro_commenting_enabled,
            "live_chat_simulation_enabled": live_chat_simulation_enabled,
            "scan_scope": scan_scope,
            "dm_limits": dm_limits,
            "cooldown_days": cooldown_days,
            "dedup_window_days": dedup_window_days,
            "allowed_languages": allowed_languages,
            "quiet_hours_local": quiet_hours_local,
            "offer_profile_id": offer_profile_id,
            "confirmation_policy": confirmation_policy,
            "allowed_tools": allowed_tools,
            "trigger_words": trigger_words,
            **common_config,
        }
        return json.dumps(normalized_config, ensure_ascii=False)

    if template_type != "crm_admin":
        return json.dumps(common_config, ensure_ascii=False) if common_config else None

    normalized_config = _migrate_crm_admin_config(raw)
    normalized_config.update(common_config)
    return json.dumps(normalized_config, ensure_ascii=False)


async def get_current_user_optional(
    http_credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
):
    if not http_credentials:
        return None

    token = http_credentials.credentials
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            user = await get_user_from_access_token(token, user_dao)
            return await user_dao.find_one_by_filter(load_relations=True, id=user.id)


async def get_current_user_required(
    current_user=Depends(get_current_user_optional),
):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return current_user


def _assert_access(current_user, internal: bool) -> None:
    if current_user is None and not internal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )


async def _ensure_external_api_key(agent, agent_dao: AgentDAO) -> str:
    if agent.encrypted_external_api_key and agent.external_api_key_hash:
        return decrypt_token(agent.encrypted_external_api_key)

    raw_key = generate_agent_external_api_key()
    await agent_dao.update(
        agent,
        {
            "encrypted_external_api_key": encrypt_token(raw_key),
            "external_api_key_hash": hash_agent_external_api_key(raw_key),
        },
    )
    return raw_key


async def _regenerate_external_api_key(agent, agent_dao: AgentDAO) -> str:
    raw_key = generate_agent_external_api_key()
    await agent_dao.update(
        agent,
        {
            "encrypted_external_api_key": encrypt_token(raw_key),
            "external_api_key_hash": hash_agent_external_api_key(raw_key),
        },
    )
    return raw_key


async def _resolve_billing_user(session, agent, current_user=None):
    billing_user = current_user
    if billing_user is None or getattr(billing_user, "id", None) != agent.user_id:
        user_dao = UserDAO(session)
        billing_user = await user_dao.find_one_by_filter(id=agent.user_id)
    return billing_user


def _serialize_agent(
    agent,
    *,
    user=None,
    include_external_api_key: bool = False,
    include_encrypted_token: bool = False,
) -> dict:
    from ..agent_template_pricing import build_agent_billing_state

    data = convert_to_dict(agent)
    for key, value in list(data.items()):
        if isinstance(value, (date, datetime)):
            data[key] = _safe_iso(value)
    data.pop("registered", None)
    data.pop("encrypted_external_api_key", None)
    data.pop("encrypted_booking_payment_api_key", None)
    data.pop("external_api_key_hash", None)
    try:
        data["template_type"] = _normalize_template_type(data.get("template_type"), allow_legacy=True)
    except HTTPException:
        data["template_type"] = "qa"
    raw_template_config = data.get("template_config")
    if isinstance(raw_template_config, str) and raw_template_config.strip():
        try:
            decoded_config = json.loads(raw_template_config)
            if data["template_type"] == "crm_admin" and isinstance(decoded_config, dict):
                decoded_config = _migrate_crm_admin_config(decoded_config)
            data["template_config"] = decoded_config
        except Exception:
            data["template_config"] = None
    else:
        data["template_config"] = None
    if not include_encrypted_token:
        data.pop("encrypted_token", None)
    if include_external_api_key:
        if agent.encrypted_external_api_key:
            data["external_api_key"] = decrypt_token(agent.encrypted_external_api_key)
        else:
            data["external_api_key"] = None
    data["has_booking_payment_api_key"] = bool(getattr(agent, "encrypted_booking_payment_api_key", None))
    data["billing"] = build_agent_billing_state(agent, user=user)
    return data


def _serialize_channel_connection(connection: AgentChannelConnection) -> dict:
    data = {
        "id": connection.id,
        "provider": connection.provider,
        "connection_type": connection.connection_type,
        "external_id": connection.external_id,
        "is_primary": bool(connection.is_primary),
        "is_active": bool(connection.is_active),
        "created_at": _safe_iso(connection.created_at),
        "updated_at": _safe_iso(connection.updated_at),
    }
    if connection.provider == TELEPHONY_CHANNEL_PROVIDER:
        data["telephony_webhook_url"] = build_telephony_webhook_url(int(connection.id))
        if connection.encrypted_credentials:
            try:
                creds = parse_telephony_credentials(decrypt_token(connection.encrypted_credentials))
                data["telephony_routing"] = telephony_routing_public_fields(creds)
            except Exception:
                data["telephony_routing"] = None
    return data


def _serialize_crm_connection(connection: AgentCrmConnection) -> dict:
    return {
        "id": connection.id,
        "provider": connection.provider,
        "external_id": connection.external_id,
        "is_active": bool(connection.is_active),
        "last_checked_at": _safe_iso(connection.last_checked_at),
        "created_at": _safe_iso(connection.created_at),
        "updated_at": _safe_iso(connection.updated_at),
    }


_HTTP_INTEGRATION_NAME_RE = re.compile(r"^[a-z0-9](?:[-a-z0-9_]{0,61}[a-z0-9])?$")


def _normalize_http_integration_slug(name: str) -> str:
    raw = str(name or "").strip().lower()
    if len(raw) > 64 or not _HTTP_INTEGRATION_NAME_RE.fullmatch(raw):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="integration_name must be a lowercase slug (a-z / digits / hyphen / underscore, max 64 chars)",
        )
    return raw


def _bundle_auth_payload_to_dict(auth_model: HttpIntegrationAuthPayload) -> dict[str, object]:
    mode = auth_model.type
    if mode == "none":
        return {"type": "none"}
    if mode == "bearer":
        token = (auth_model.token or "").strip()
        if not token:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Bearer token is required")
        return {"type": "bearer", "token": token}
    if mode == "header":
        hn = (auth_model.header_name or "").strip()
        if not hn:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="header_name is required")
        return {"type": "header", "name": hn, "value": (auth_model.header_value or "").strip()}
    if mode == "basic":
        user = (auth_model.username or "").strip()
        if not user:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="username is required for basic auth")
        return {
            "type": "basic",
            "username": user,
            "password": auth_model.password or "",
        }
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Unsupported authentication type",
    )


def _http_integration_manifest_for_api(bundle: dict[str, object]) -> dict[str, object]:
    tools = bundle.get("tools") if isinstance(bundle.get("tools"), list) else []
    summarized = []
    for item in tools:
        if isinstance(item, dict):
            summarized.append(
                {
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "method": item.get("method"),
                    "path": item.get("path"),
                }
            )
    auth_raw = bundle.get("auth") if isinstance(bundle.get("auth"), dict) else {}
    return {
        "base_url": bundle.get("base_url"),
        "timeout_seconds": bundle.get("timeout_seconds"),
        "default_headers": sorted((bundle.get("default_headers") or {}).keys())
        if isinstance(bundle.get("default_headers"), dict)
        else [],
        "auth_type": auth_raw.get("type"),
        "tools": summarized,
    }


def _serialize_http_integration(connection: AgentHttpIntegration) -> dict:
    preview: dict[str, object] | None = None
    try:
        decrypted, _ = decrypt_crm_credentials(connection.encrypted_config)
        loaded = json.loads(decrypted)
        if isinstance(loaded, dict):
            validated = validate_integration_config_dict(loaded)
            preview = _http_integration_manifest_for_api(validated)
    except HttpIntegrationValidationError:
        preview = {"error": "invalid_stored_integration"}
    except Exception:
        preview = {"error": "manifest_unreadable"}
    return {
        "id": connection.id,
        "name": connection.name,
        "is_active": bool(connection.is_active),
        "created_at": _safe_iso(connection.created_at),
        "updated_at": _safe_iso(connection.updated_at),
        "manifest": preview or {},
    }


def _parse_content_job_metadata(raw_metadata: str | None) -> dict:
    if not raw_metadata or not str(raw_metadata).strip():
        return {}
    try:
        loaded = json.loads(raw_metadata)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _serialize_content_job(row: AgentContentJob) -> dict:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "status": row.status,
        "scheduled_for": _safe_iso(row.scheduled_for),
        "started_at": _safe_iso(row.started_at),
        "finished_at": _safe_iso(row.finished_at),
        "script_text": row.script_text,
        "script_model": row.script_model,
        "kling_task_id": row.kling_task_id,
        "video_url": row.video_url,
        "youtube_video_id": row.youtube_video_id,
        "youtube_video_url": row.youtube_video_url,
        "retry_count": int(row.retry_count or 0),
        "max_retries": int(row.max_retries or 0),
        "last_error": row.last_error,
        "metadata": _parse_content_job_metadata(row.metadata_json),
        "created_at": _safe_iso(row.created_at),
        "updated_at": _safe_iso(row.updated_at),
    }


def _normalize_crm_base_url(value: str) -> str:
    raw = (value or "").strip().rstrip("/")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="account_base_url is required",
        )
    if not (raw.startswith("http://") or raw.startswith("https://")):
        raw = f"https://{raw}"
    return raw


def _decode_template_config(
    raw_template_config: str | None,
    *,
    template_type: str | None = None,
) -> dict | None:
    if not raw_template_config or not str(raw_template_config).strip():
        return None
    try:
        loaded = json.loads(raw_template_config)
        if isinstance(loaded, dict):
            normalized_type = None
            if template_type is not None:
                try:
                    normalized_type = _normalize_template_type(template_type)
                except Exception:
                    normalized_type = None
            if normalized_type == "crm_admin":
                return _migrate_crm_admin_config(loaded)
            return loaded
    except Exception:
        return None
    return None


def _normalize_external_webhook_url(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if len(raw) > 1024:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="external_webhook_url must be at most 1024 chars",
        )
    if not (raw.startswith("http://") or raw.startswith("https://")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="external_webhook_url must start with http:// or https://",
        )
    return raw


async def _send_external_webhook_message(
    *,
    webhook_url: str,
    agent,
    user_external_id: str,
    message_text: str,
) -> dict:
    body = json.dumps(
        {
            "event": "owner_message",
            "channel": "external_api",
            "agent_id": agent.id,
            "bot_id": agent.bot_id,
            "user_external_id": user_external_id,
            "message": message_text,
            "sent_at": datetime.utcnow().isoformat() + "Z",
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = UrlRequest(
        webhook_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    def _call():
        with urlopen(request, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw.strip():
                return {"ok": True}
            try:
                decoded = json.loads(raw)
                if isinstance(decoded, dict):
                    return decoded
            except Exception:
                pass
            return {"ok": True, "raw": raw}

    try:
        return await asyncio.get_running_loop().run_in_executor(None, _call)
    except HTTPError as exc:
        detail_text = ""
        try:
            detail_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail_text = ""
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"External webhook returned HTTP {exc.code}: {detail_text[:500]}",
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"External webhook is unreachable: {exc.reason}",
        ) from exc


async def _list_agent_channels(session, agent_id: int) -> list[AgentChannelConnection]:
    rows = await session.scalars(
        select(AgentChannelConnection)
        .where(AgentChannelConnection.agent_id == agent_id)
        .order_by(AgentChannelConnection.created_at.asc(), AgentChannelConnection.id.asc())
    )
    return list(rows.all())


async def _list_agent_crm_connections(session, agent_id: int) -> list[AgentCrmConnection]:
    rows = await session.scalars(
        select(AgentCrmConnection)
        .where(AgentCrmConnection.agent_id == agent_id)
        .order_by(AgentCrmConnection.created_at.asc(), AgentCrmConnection.id.asc())
    )
    return list(rows.all())


async def _list_agent_http_integrations(session, agent_id: int) -> list[AgentHttpIntegration]:
    rows = await session.scalars(
        select(AgentHttpIntegration)
        .where(AgentHttpIntegration.agent_id == agent_id)
        .order_by(AgentHttpIntegration.created_at.asc(), AgentHttpIntegration.id.asc())
    )
    return list(rows.all())


async def _sync_agent_primary_fields(
    *,
    agent,
    agent_dao: AgentDAO,
    session,
):
    channels = await _list_agent_channels(session, agent.id)
    if not channels:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="У агента должен быть минимум один канал подключения",
        )
    primary = next((item for item in channels if item.is_primary), None) or channels[0]
    now = datetime.utcnow()
    for item in channels:
        should_be_primary = item.id == primary.id
        if bool(item.is_primary) != should_be_primary:
            item.is_primary = should_be_primary
            item.updated_at = now

    updates = {"primary_provider": primary.provider}
    primary_external_id = (primary.external_id or "").strip()
    if primary_external_id.isdigit():
        updates["bot_id"] = int(primary_external_id)
    elif primary.provider == "telegram_bot":
        updates["bot_id"] = None
    # Keep legacy field in sync for Telegram bot flow used by webhook and bot service.
    if primary.provider == "telegram_bot" and primary.encrypted_credentials:
        updates["encrypted_token"] = primary.encrypted_credentials
    await agent_dao.update(agent, updates)
    return primary


async def _ensure_single_primary_flag(
    *,
    session,
    agent_id: int,
):
    channels = await _list_agent_channels(session, agent_id)
    if not channels:
        return
    now = datetime.utcnow()
    primary = next((item for item in channels if item.is_primary), None) or channels[0]
    for item in channels:
        target = item.id == primary.id
        if bool(item.is_primary) != target:
            item.is_primary = target
            item.updated_at = now


async def _set_primary_channel(
    *,
    session,
    agent_id: int,
    connection_id: int,
):
    rows = await session.scalars(
        select(AgentChannelConnection).where(AgentChannelConnection.agent_id == agent_id)
    )
    now = datetime.utcnow()
    for row in rows.all():
        row.is_primary = row.id == connection_id
        row.updated_at = now


async def _get_telegram_bot_channel_for_agent(session, agent_id: int) -> AgentChannelConnection | None:
    return await session.scalar(
        select(AgentChannelConnection).where(
            AgentChannelConnection.agent_id == agent_id,
            AgentChannelConnection.provider == "telegram_bot",
            AgentChannelConnection.connection_type == "bot",
            AgentChannelConnection.is_active.is_(True),
            AgentChannelConnection.encrypted_credentials.is_not(None),
        )
    )


async def _get_telegram_userbot_channel_for_agent(session, agent_id: int) -> AgentChannelConnection | None:
    return await session.scalar(
        select(AgentChannelConnection).where(
            AgentChannelConnection.agent_id == agent_id,
            AgentChannelConnection.provider == "telegram_userbot",
            AgentChannelConnection.connection_type == "userbot",
            AgentChannelConnection.is_active.is_(True),
            AgentChannelConnection.encrypted_credentials.is_not(None),
        )
    )


async def _get_whatsapp_userbot_channel_for_agent(session, agent_id: int) -> AgentChannelConnection | None:
    return await session.scalar(
        select(AgentChannelConnection).where(
            AgentChannelConnection.agent_id == agent_id,
            AgentChannelConnection.provider == "whatsapp_userbot",
            AgentChannelConnection.connection_type == "userbot",
            AgentChannelConnection.is_active.is_(True),
            AgentChannelConnection.encrypted_credentials.is_not(None),
        )
    )


async def _get_max_userbot_channel_for_agent(session, agent_id: int) -> AgentChannelConnection | None:
    return await session.scalar(
        select(AgentChannelConnection).where(
            AgentChannelConnection.agent_id == agent_id,
            AgentChannelConnection.provider == "max_userbot",
            AgentChannelConnection.connection_type == "userbot",
            AgentChannelConnection.is_active.is_(True),
            AgentChannelConnection.encrypted_credentials.is_not(None),
        )
    )


async def _get_youtube_oauth_channel_for_agent(session, agent_id: int) -> AgentChannelConnection | None:
    return await session.scalar(
        select(AgentChannelConnection).where(
            AgentChannelConnection.agent_id == agent_id,
            AgentChannelConnection.provider == "youtube",
            AgentChannelConnection.connection_type == "oauth",
            AgentChannelConnection.is_active.is_(True),
            AgentChannelConnection.encrypted_credentials.is_not(None),
        )
    )


def _whatsapp_user_external_to_jid(user_external_id: str) -> str:
    """Полный JID из аналитики (предпочтительно) или только цифры номера (старые записи)."""
    try:
        return external_id_to_jid(user_external_id)
    except WhatsAppJidError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


async def _ensure_whatsapp_userbot_session(connection_id: int, encrypted_credentials: str) -> None:
    """Убедиться, что wa_bridge имеет активную runtime сессию для данного connection_id.

    Менеджер (whatsapp_userbot_manager.py) обычно поддерживает сессию через polling,
    но если он не запущен или перезапускался, сессии может не быть в runtimeSessions Map.
    Эта функция вызывает session/connect чтобы гарантировать наличие сессии перед отправкой.
    """
    if not encrypted_credentials:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Отсутствуют credentials для WhatsApp канала",
        )
    try:
        bundle = json.loads(decrypt_token(encrypted_credentials))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось расшифровать credentials WhatsApp: {exc}",
        ) from exc
    session_string = str(bundle.get("session_string") or "").strip()
    if not session_string:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Отсутствует session_string в credentials WhatsApp",
        )
    # Вызываем session/connect для установки/восстановления сессии в wa_bridge
    await _wa_userbot_bridge_post(
        "session/connect",
        {
            "connection_id": str(connection_id),
            "session_string": session_string,
        },
    )


async def _max_userbot_send_message(encrypted_credentials: str, text: str, *, chat_id: str | None = None) -> None:
    max_chat_id = str(chat_id or "").strip()
    if not max_chat_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="MAX chat id (user_external_id) обязателен для отправки",
        )
    try:
        bundle = bundle_from_credentials(encrypted_credentials)
    except MaxUserbotSessionError as exc:
        raise _max_userbot_session_http_error(exc) from exc
    try:
        await max_send_message_once(bundle, max_chat_id, text)
    except MaxUserbotSessionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Не удалось отправить сообщение в MAX: {exc}",
        ) from exc


async def _validate_max_userbot_session_payload(
    session_payload: str,
    *,
    require_live_check: bool = False,
) -> dict[str, Any]:
    try:
        parsed = parse_session_payload(session_payload)
    except MaxUserbotSessionError as exc:
        raise _max_userbot_session_http_error(exc) from exc

    account_id = str(parsed.get("account_id") or parsed.get("max_account_id") or "").strip()
    if account_id and not require_live_check:
        return parsed

    try:
        validated = await validate_session_bundle(parsed["bundle"])
    except MaxUserbotSessionError as exc:
        raise _max_userbot_session_http_error(exc) from exc
    return validated


async def _list_whatsapp_userbot_broadcast_recipients(session, analytics_namespace_id: int) -> list[dict]:
    rows = (
        (
            await session.execute(
                select(
                    AgentAnalyticsMessage.user_external_id.label("uid"),
                    func.max(AgentAnalyticsMessage.created_at).label("last_at"),
                )
                .where(
                    AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                    AgentAnalyticsMessage.role == "user",
                    AgentAnalyticsMessage.channel == "whatsapp_userbot",
                    AgentAnalyticsMessage.user_external_id.is_not(None),
                )
                .group_by(AgentAnalyticsMessage.user_external_id)
                .order_by(func.max(AgentAnalyticsMessage.created_at).desc())
            )
        )
        .mappings()
        .all()
    )
    recipients: list[dict] = []
    for row in rows:
        uid = row.get("uid")
        if not uid:
            continue
        uid_s = str(uid).strip()
        if not uid_s:
            continue
        recipients.append({"user_external_id": uid_s, "channel": "whatsapp_userbot"})
    return recipients


def _normalize_public_base_url(base_url: str | None) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BASE_URL не задан — без него нельзя настроить webhook Telegram",
        )
    if not normalized.lower().startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BASE_URL должен начинаться с https:// — Telegram принимает только HTTPS для webhook",
        )
    return normalized


def _extract_telegram_api_error(exc: HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8")
        payload = json.loads(raw)
        if isinstance(payload, dict):
            description = payload.get("description")
            if description:
                return str(description)
        if raw:
            return raw[:500]
    except Exception:
        pass
    return exc.reason or f"HTTP {exc.code}"


async def _telegram_bot_api_json(
    bot_token: str,
    method: str,
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{quote(bot_token, safe='')}/{method}"
    body = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = UrlRequest(url, data=body, headers=headers, method="POST")

    def _fetch():
        try:
            with urlopen(request, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Telegram API ({method}): {_extract_telegram_api_error(exc)}",
            ) from exc
        except URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Не удалось связаться с Telegram ({method}): {exc.reason}",
            ) from exc

    return await asyncio.get_running_loop().run_in_executor(None, _fetch)


async def _telegram_get_me(bot_token: str) -> dict:
    url = f"https://api.telegram.org/bot{quote(bot_token, safe='')}/getMe"

    def _fetch():
        with urlopen(url, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return await asyncio.get_running_loop().run_in_executor(None, _fetch)


def _raise_telegram_token_check_http_exception(exc: Exception) -> None:
    if isinstance(exc, HTTPError):
        if exc.code == status.HTTP_401_UNAUTHORIZED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Некорректный API ключ Telegram бота",
            ) from exc
        if exc.code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Telegram не распознал токен бота (HTTP 404). "
                    "Проверьте, что токен полностью скопирован из BotFather и не содержит лишних символов."
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Telegram вернул ошибку HTTP {exc.code} при проверке токена",
        ) from exc

    if isinstance(exc, URLError):
        nested_http_error = exc.reason if isinstance(exc.reason, HTTPError) else None
        if nested_http_error is not None:
            _raise_telegram_token_check_http_exception(nested_http_error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Не удалось связаться с Telegram при проверке токена. "
                "Проверьте интернет-соединение и повторите попытку."
            ),
        ) from exc

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Ошибка при проверке токена Telegram: {exc}",
    ) from exc


async def _max_bot_get_me(bot_token: str) -> dict:
    request = UrlRequest(
        "https://platform-api.max.ru/me",
        headers={
            "Authorization": bot_token,
            "Accept": "application/json",
        },
    )

    def _fetch():
        with urlopen(request, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return await asyncio.get_running_loop().run_in_executor(None, _fetch)


async def _sync_telegram_bot_webhook(bot_token: str, bot_id: int, enabled: bool) -> None:
    base_url = _normalize_public_base_url(settings.BASE_URL)
    if enabled:
        webhook_url = f"{base_url}/webhook/{bot_id}"
        result = await _telegram_bot_api_json(
            bot_token,
            "setWebhook",
            payload={"url": webhook_url, "drop_pending_updates": True},
        )
    else:
        result = await _telegram_bot_api_json(bot_token, "deleteWebhook")

    if not result or result.get("ok") is not True:
        description = result.get("description") if isinstance(result, dict) else None
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=description or f"Не удалось синхронизировать webhook Telegram: {result}",
        )


async def _waba_get_phone_number_info(phone_number_id: str, access_token: str) -> dict:
    request_url = (
        f"https://graph.facebook.com/v22.0/{quote(phone_number_id, safe='')}"
        "?fields=id,display_phone_number,verified_name,quality_rating"
    )
    request = UrlRequest(
        request_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )

    def _fetch():
        with urlopen(request, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return await asyncio.get_running_loop().run_in_executor(None, _fetch)


async def _map_telegram_userbot_access_hashes(
    session,
    *,
    analytics_namespace_id: int,
    user_external_ids: list[str],
) -> dict[str, int]:
    """Latest known access_hash per user for Telethon InputPeerUser (backend session has no entity cache)."""
    if not user_external_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(
                    AgentAnalyticsMessage.user_external_id,
                    AgentAnalyticsMessage.telegram_peer_access_hash,
                    AgentAnalyticsMessage.created_at,
                )
                .where(
                    AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                    AgentAnalyticsMessage.channel == "telegram_userbot",
                    AgentAnalyticsMessage.user_external_id.in_(user_external_ids),
                    AgentAnalyticsMessage.telegram_peer_access_hash.is_not(None),
                    AgentAnalyticsMessage.telegram_peer_access_hash > 0,
                )
                .order_by(AgentAnalyticsMessage.created_at.desc())
            )
        )
        .all()
    )
    out: dict[str, int] = {}
    for uid, h, _ in rows:
        if not uid or h is None:
            continue
        key = str(uid)
        if key not in out:
            out[key] = int(h)
    return out


async def _latest_telegram_userbot_access_hash(
    session,
    *,
    analytics_namespace_id: int,
    user_external_id: str,
) -> int | None:
    ids = [user_external_id.strip()] if (user_external_id or "").strip() else []
    m = await _map_telegram_userbot_access_hashes(
        session, analytics_namespace_id=analytics_namespace_id, user_external_ids=ids
    )
    return m.get(ids[0]) if ids else None


async def _telegram_userbot_send_message(
    encrypted_bundle: str,
    chat_id: int,
    text: str,
    *,
    access_hash: int | None = None,
) -> None:
    from telethon.tl.types import InputPeerUser

    try:
        raw = decrypt_token(encrypted_bundle)
        data = json.loads(raw)
        api_id = int(data.get("api_id"))
        api_hash = str(data.get("api_hash") or "").strip()
        session_string = str(data.get("session_string") or "").strip()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Некорректные credentials userbot-канала: {exc}",
        )

    if not api_id or not api_hash or not session_string:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="В userbot-канале отсутствуют api_id/api_hash/session_string",
        )

    client = _create_telethon_client(api_id=api_id, api_hash=api_hash, session_string=session_string)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Userbot session не авторизована",
            )
        if access_hash is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Нет telegram_peer_access_hash для этого пользователя. "
                    "Пусть пользователь снова напишет агенту в userbot (после обновления сервера), "
                    "чтобы сохранился access_hash для отправки."
                ),
            )
        peer = InputPeerUser(user_id=int(chat_id), access_hash=int(access_hash))
        await client.send_message(peer, text)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Telegram userbot send_message: {exc}",
        )
    finally:
        await client.disconnect()


async def _terminate_telegram_userbot_session(encrypted_bundle: str) -> None:
    if not encrypted_bundle:
        return
    try:
        raw = decrypt_token(encrypted_bundle)
        data = json.loads(raw)
        api_id = int(data.get("api_id"))
        api_hash = str(data.get("api_hash") or "").strip()
        session_string = str(data.get("session_string") or "").strip()
    except Exception:
        logger.warning("telegram_userbot: failed to decode credentials for session termination", exc_info=True)
        return
    if not api_id or not api_hash or not session_string:
        return

    client = _create_telethon_client(api_id=api_id, api_hash=api_hash, session_string=session_string)
    try:
        await client.connect()
        if await client.is_user_authorized():
            await client.log_out()
    except Exception:
        logger.warning("telegram_userbot: failed to terminate session", exc_info=True)
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def _terminate_whatsapp_userbot_session(connection_id: int) -> None:
    try:
        await _wa_userbot_bridge_post("session/disconnect", {"connection_id": str(connection_id)})
    except Exception:
        logger.warning("whatsapp_userbot: failed to disconnect runtime session connection_id=%s", connection_id, exc_info=True)
    try:
        await _wa_userbot_bridge_post("session/logout", {"connection_id": str(connection_id)})
    except Exception:
        logger.debug("whatsapp_userbot: session/logout is unavailable for connection_id=%s", connection_id, exc_info=True)


async def _deactivate_telephony_channel_if_supported(channel: AgentChannelConnection) -> None:
    if (channel.provider or "").strip() != TELEPHONY_CHANNEL_PROVIDER:
        return
    if not channel.encrypted_credentials:
        return
    try:
        creds = parse_telephony_credentials(decrypt_token(channel.encrypted_credentials))
    except Exception:
        logger.warning("telephony: skip CPaaS deactivation — invalid credentials connection_id=%s", channel.id)
        return
    await clear_channel_routes(creds, connection_id=int(channel.id))
    await deactivate_voximplant_inbound_rule(
        account_id=creds.account_id,
        api_key=creds.api_key,
        application_id=creds.application_id,
        rule_id=creds.rule_id,
    )


async def _terminate_channel_session_if_supported(channel: AgentChannelConnection) -> None:
    await _deactivate_telephony_channel_if_supported(channel)
    provider = (channel.provider or "").strip().lower()
    connection_type = (channel.connection_type or "").strip().lower()
    if connection_type != "userbot":
        return
    if provider == "telegram_userbot":
        await _terminate_telegram_userbot_session(str(channel.encrypted_credentials or ""))
    elif provider == "whatsapp_userbot":
        await _terminate_whatsapp_userbot_session(int(channel.id))


async def _find_agent_with_access(
    agent_dao: AgentDAO,
    *,
    agent_id: int | None = None,
    bot_id: int | None = None,
    session=None,
    current_user,
    internal: bool,
):
    agent = None
    if agent_id is not None:
        agent = await agent_dao.find_one_by_filter(id=agent_id)
    elif bot_id is not None:
        if session is not None:
            agent, _ = await _find_agent_by_lookup_id(
                session=session,
                agent_dao=agent_dao,
                lookup_id=bot_id,
            )
        else:
            agent = await agent_dao.find_one_by_filter(bot_id=bot_id)
            if not agent and 0 < bot_id <= MAX_INT32:
                agent = await agent_dao.find_one_by_filter(id=bot_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if current_user and agent.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if current_user is None and not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return agent


async def _find_agent_by_lookup_id(
    *,
    session,
    agent_dao: AgentDAO,
    lookup_id: int,
):
    agent = await agent_dao.find_one_by_filter(bot_id=lookup_id)
    resolved_channel: AgentChannelConnection | None = None
    if not agent and 0 < lookup_id <= MAX_INT32:
        agent = await agent_dao.find_one_by_filter(id=lookup_id)
    if not agent:
        resolved_channel = await session.scalar(
            select(AgentChannelConnection).where(
                AgentChannelConnection.provider == "telegram_bot",
                AgentChannelConnection.connection_type == "bot",
                AgentChannelConnection.external_id == str(lookup_id),
                AgentChannelConnection.is_active.is_(True),
            )
        )
        if resolved_channel:
            agent = await agent_dao.find_one_by_filter(id=resolved_channel.agent_id)
    return agent, resolved_channel


def _resolve_lookup(agent_lookup: AgentLookup) -> tuple[int | None, int | None]:
    return agent_lookup.agent_id, agent_lookup.bot_id


def _safe_iso(value):
    if not value:
        return None
    try:
        return value.isoformat(sep=" ", timespec="seconds")
    except Exception:
        return str(value)


def _parse_iso_datetime(raw_value: str, *, field_name: str) -> datetime:
    value = str(raw_value or "").strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} is required",
        )
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must be ISO datetime",
        )
    if parsed.tzinfo is not None:
        return parsed.astimezone(tz=None).replace(tzinfo=None)
    return parsed


def _parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        loaded = json.loads(raw)
    except Exception:
        return []
    if not isinstance(loaded, list):
        return []
    return [str(item).strip() for item in loaded if str(item).strip()]


async def _find_admin_template_agent(
    *,
    session,
    agent_dao: AgentDAO,
    current_user,
    payload: AgentLookup | None = None,
    agent_id: int | None = None,
    bot_id: int | None = None,
    domain_type: str | None = None,
) -> tuple[Agent, dict]:
    lookup_agent_id = agent_id
    lookup_bot_id = bot_id
    if payload is not None:
        lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
    agent = await _find_agent_with_access(
        agent_dao,
        agent_id=lookup_agent_id,
        bot_id=lookup_bot_id,
        session=session,
        current_user=current_user,
        internal=False,
    )
    normalized_type = _normalize_template_type(agent.template_type)
    if normalized_type != "crm_admin":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Admin template API is available only for crm_admin agents",
        )
    cfg = _decode_template_config(agent.template_config, template_type=agent.template_type) or {}
    normalized_domain = str(cfg.get("domain_type") or "").strip().lower()
    if domain_type:
        requested = str(domain_type).strip().lower()
        if requested and requested not in CRM_DOMAIN_TYPES:
            valid = ", ".join(sorted(CRM_DOMAIN_TYPES))
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"domain_type must be one of: {valid}",
            )
        if requested and normalized_domain and requested != normalized_domain:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"domain_type mismatch for this agent: expected {normalized_domain}",
            )
    return agent, cfg


def _serialize_admin_schedule_slot_row(row: AdminScheduleSlot) -> dict:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "staff_id": row.staff_id,
        "resource_id": row.resource_id,
        "slot_kind": row.slot_kind,
        "starts_at": _safe_iso(row.starts_at),
        "ends_at": _safe_iso(row.ends_at),
        "is_active": bool(row.is_active),
        "created_at": _safe_iso(row.created_at),
        "updated_at": _safe_iso(row.updated_at),
    }


def _serialize_admin_appointment_row(row: AdminAppointment) -> dict:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "staff_id": row.staff_id,
        "resource_id": row.resource_id,
        "service_id": row.service_id,
        "client_external_id": row.client_external_id,
        "client_name": row.client_name,
        "starts_at": _safe_iso(row.starts_at),
        "ends_at": _safe_iso(row.ends_at),
        "status": row.status,
        "source_channel": row.source_channel,
        "notes": row.notes,
        "created_at": _safe_iso(row.created_at),
        "updated_at": _safe_iso(row.updated_at),
    }


def _safe_json_load(raw: str | None) -> dict | list:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    if isinstance(parsed, (dict, list)):
        return parsed
    return {}


def _safe_json_dump(value: object) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return None


def _serialize_admin_waitlist_row(row: AdminWaitlistEntry) -> dict:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "client_external_id": row.client_external_id,
        "client_name": row.client_name,
        "service_id": row.service_id,
        "desired_staff_id": row.desired_staff_id,
        "desired_resource_id": row.desired_resource_id,
        "earliest_starts_at": _safe_iso(row.earliest_starts_at),
        "latest_ends_at": _safe_iso(row.latest_ends_at),
        "notes": row.notes,
        "status": row.status,
        "matched_appointment_id": row.matched_appointment_id,
        "created_at": _safe_iso(row.created_at),
        "updated_at": _safe_iso(row.updated_at),
    }


def _serialize_admin_client_profile_row(row: AdminClientProfile) -> dict:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "client_external_id": row.client_external_id,
        "client_name": row.client_name,
        "tags": _parse_json_list(row.tags_json),
        "preferences": _safe_json_load(row.preferences_json),
        "history": _parse_json_list(row.history_json),
        "last_visit_at": _safe_iso(row.last_visit_at),
        "created_at": _safe_iso(row.created_at),
        "updated_at": _safe_iso(row.updated_at),
    }


def _serialize_admin_quick_reply_row(row: AdminQuickReplyTemplate) -> dict:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "title": row.title,
        "body": row.body,
        "category": row.category,
        "is_active": bool(row.is_active),
        "created_at": _safe_iso(row.created_at),
        "updated_at": _safe_iso(row.updated_at),
    }


def _create_userbot_auth_token(
    *,
    api_id: int,
    api_hash: str,
    phone_number: str,
    phone_code_hash: str,
    encrypted_pending_session: str,
) -> str:
    return userbot_auth_token.create(
        api_id=api_id,
        encrypted_api_hash=encrypt_token(api_hash),
        phone_number=phone_number,
        phone_code_hash=phone_code_hash,
        encrypted_pending_session=encrypted_pending_session,
    )


def _decode_userbot_auth_token(auth_token: str) -> dict:
    return userbot_auth_token.decode(auth_token)


def _create_userbot_qr_auth_token(
    *,
    api_id: int,
    api_hash: str,
    auth_id: str,
    encrypted_pending_session: str,
) -> str:
    return userbot_qr_auth_token.create(
        api_id=api_id,
        encrypted_api_hash=encrypt_token(api_hash),
        auth_id=auth_id,
        encrypted_pending_session=encrypted_pending_session,
    )


def _decode_userbot_qr_auth_token(auth_token: str) -> dict:
    return userbot_qr_auth_token.decode(auth_token, required_keys=["auth_id"])


def _userbot_auth_http_error(exc: TelegramUserbotAuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _max_userbot_auth_http_error(exc: MaxUserbotAuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _max_userbot_session_http_error(exc: MaxUserbotSessionError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _create_max_userbot_auth_token(auth_id: str) -> str:
    return max_userbot_auth_token.create(auth_id=auth_id)


def _decode_max_userbot_auth_token(auth_token: str) -> str:
    data = max_userbot_auth_token.decode(auth_token, required_keys=["auth_id"])
    return str(data["auth_id"]).strip()


def _resolve_userbot_api_pair(
    api_id: int | None,
    api_hash: str | None,
    *,
    prefer_desktop: bool = True,
) -> tuple[int, str]:
    try:
        return resolve_api_credentials(api_id, api_hash, prefer_desktop=prefer_desktop)
    except TelegramUserbotAuthError as exc:
        raise _userbot_auth_http_error(exc) from exc


def _create_whatsapp_userbot_auth_token(
    *,
    user_id: int,
    phone_number: str,
    bridge_auth_id: str,
) -> str:
    return whatsapp_userbot_auth_token.create(
        user_id=int(user_id),
        phone_number=phone_number,
        encrypted_bridge_auth_id=encrypt_token(bridge_auth_id),
    )


def _decode_whatsapp_userbot_auth_token(auth_token: str) -> dict:
    data = whatsapp_userbot_auth_token.decode(auth_token)
    token_user_id = data.get("user_id")
    if not isinstance(token_user_id, int) or token_user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен подтверждения WhatsApp userbot не привязан к пользователю",
        )
    return data


def _create_youtube_oauth_state(*, user_id: int, agent_id: int, redirect_uri: str) -> str:
    now = datetime.utcnow()
    payload = {
        "scope": YOUTUBE_OAUTH_STATE_SCOPE,
        "user_id": int(user_id),
        "agent_id": int(agent_id),
        "redirect_uri": redirect_uri,
        "exp": now + timedelta(seconds=YOUTUBE_OAUTH_STATE_TTL_SECONDS),
        "iat": now,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _decode_youtube_oauth_state(state_token: str) -> dict:
    try:
        data = jwt.decode(state_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный или просроченный OAuth state токен YouTube",
        )
    if data.get("scope") != YOUTUBE_OAUTH_STATE_SCOPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный scope OAuth state токена YouTube",
        )
    if not isinstance(data.get("user_id"), int) or not isinstance(data.get("agent_id"), int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OAuth state токен YouTube не содержит корректные идентификаторы",
        )
    redirect_uri = str(data.get("redirect_uri") or "").strip()
    if not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OAuth state токен YouTube не содержит redirect_uri",
        )
    return data


async def _wa_userbot_bridge_post(path: str, payload: dict) -> dict:
    try:
        return await bridge_post(path, payload)
    except RuntimeError as exc:
        message = str(exc)
        if "WHATSAPP_USERBOT_BRIDGE_URL" in message:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WhatsApp userbot bridge не настроен на сервере",
            ) from exc
        if "WHATSAPP_USERBOT_BRIDGE_API_KEY" in message:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WhatsApp userbot bridge API key не настроен на сервере",
            ) from exc
        if "HTTP" in message:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"WhatsApp userbot bridge {message}",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"WhatsApp userbot bridge transport error: {message}",
        ) from exc


def _wa_userbot_bridge_http_status(exc: HTTPException) -> int | None:
    """Extract upstream wa_bridge HTTP status from a 502 wrapper, if present."""
    if exc.status_code != status.HTTP_502_BAD_GATEWAY:
        return None
    detail = str(exc.detail or "")
    marker = "WhatsApp userbot bridge HTTP "
    if marker not in detail:
        return None
    tail = detail.split(marker, 1)[1]
    code_part = tail.split(":", 1)[0].strip()
    try:
        return int(code_part)
    except ValueError:
        return None


def _validate_whatsapp_session_string(
    *,
    session_string: str,
    expected_phone: str | None = None,
) -> tuple[str, dict]:
    normalized = (session_string or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Сессия WhatsApp userbot пуста",
        )
    try:
        bundle = decode_whatsapp_session_bundle(normalized, settings.WA_USERBOT_SESSION_SECRET)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Некорректная сессия WhatsApp userbot: {exc}",
        ) from exc

    bundle_phone = str(bundle.get("phone_number") or "").strip()
    if expected_phone and bundle_phone and bundle_phone != expected_phone.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Номер телефона в сессии не совпадает с указанным",
        )
    return bundle_phone or (expected_phone or "").strip(), bundle


def _create_telethon_client(api_id: int, api_hash: str, session_string: str = ""):
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    return TelegramClient(StringSession(session_string), api_id, api_hash)


async def _validate_userbot_session(api_id: int, api_hash: str, session_string: str):
    try:
        import telethon  # noqa: F401
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Telethon не установлен на сервере: {exc}",
        )

    client = _create_telethon_client(api_id=api_id, api_hash=api_hash, session_string=session_string)
    try:
        await client.connect()
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="StringSession не авторизована. Сначала подтвердите вход через код Telegram.",
            )
        me = await client.get_me()
        if not me:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Telethon не смог получить профиль пользователя",
            )
        return me
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось проверить userbot-сессию через Telethon: {exc}",
        )
    finally:
        await client.disconnect()


async def _telegram_api_send_message(bot_token: str, chat_id: int, text: str) -> None:
    """Send a plain text message via Telegram Bot API (sync urllib in thread pool)."""
    url = f"https://api.telegram.org/bot{quote(bot_token, safe='')}/sendMessage"
    payload_bytes = json.dumps({"chat_id": chat_id, "text": text}, ensure_ascii=False).encode("utf-8")

    def _post():
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        req = Request(
            url,
            data=payload_bytes,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = str(exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Telegram sendMessage HTTP {exc.code}: {body}",
            ) from exc
        except URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Telegram sendMessage transport error: {exc}",
            ) from exc

    try:
        result = await asyncio.get_running_loop().run_in_executor(None, _post)
    except HTTPException:
        raise
    if not result or result.get("ok") is not True:
        detail = (result or {}).get("description") or str(result)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Telegram sendMessage: {detail}",
        )


async def _log_analytics_message_for_agent_ids(
    *,
    session,
    agent_id: int,
    telegram_bot_id: int,
    role: str,
    message_text: str,
    channel: str = "telegram",
    user_external_id: str | None = None,
    user_display_name: str | None = None,
    telegram_peer_access_hash: int | None = None,
    tool_name: str | None = None,
    tool_args_hash: str | None = None,
    tool_status: str | None = None,
    latency_ms: int | None = None,
    crm_provider: str | None = None,
) -> None:
    normalized_text = (message_text or "").strip()
    if not normalized_text:
        return
    normalized_role = (role or "").strip().lower()
    if normalized_role not in {"user", "agent", "operator"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="role must be one of: user, agent, operator",
        )
    normalized_channel = (channel or "telegram").strip().lower()
    if normalized_channel not in {
        "telegram",
        "external_api",
        "web",
        "dashboard",
        "telegram_userbot",
        "max_bot",
        "max_userbot",
        "whatsapp_userbot",
        "whatsapp_business_api",
        "phone",
        "instagram",
        "tiktok",
        "pinterest",
    }:
        normalized_channel = "web"

    row = AgentAnalyticsMessage(
        agent_id=agent_id,
        bot_id=telegram_bot_id,
        role=normalized_role,
        channel=normalized_channel,
        user_external_id=(user_external_id or None),
        user_display_name=(user_display_name or None),
        telegram_peer_access_hash=telegram_peer_access_hash,
        tool_name=tool_name,
        tool_args_hash=tool_args_hash,
        tool_status=tool_status,
        latency_ms=latency_ms,
        crm_provider=crm_provider,
        message_text=normalized_text,
    )
    session.add(row)


async def _log_analytics_message(
    *,
    session,
    agent,
    role: str,
    message_text: str,
    channel: str = "telegram",
    user_external_id: str | None = None,
    user_display_name: str | None = None,
    telegram_peer_access_hash: int | None = None,
    tool_name: str | None = None,
    tool_args_hash: str | None = None,
    tool_status: str | None = None,
    latency_ms: int | None = None,
    crm_provider: str | None = None,
) -> None:
    resolved_channel_id = agent.bot_id if agent.bot_id is not None else agent.id
    await _log_analytics_message_for_agent_ids(
        session=session,
        agent_id=agent.id,
        telegram_bot_id=resolved_channel_id,
        role=role,
        message_text=message_text,
        channel=channel,
        user_external_id=user_external_id,
        user_display_name=user_display_name,
        telegram_peer_access_hash=telegram_peer_access_hash,
        tool_name=tool_name,
        tool_args_hash=tool_args_hash,
        tool_status=tool_status,
        latency_ms=latency_ms,
        crm_provider=crm_provider,
    )


async def _list_telegram_broadcast_recipient_ids(session, telegram_bot_id: int) -> list[dict]:
    rows = (
        (
            await session.execute(
                select(
                    AgentAnalyticsMessage.user_external_id.label("uid"),
                    AgentAnalyticsMessage.channel.label("channel"),
                    func.max(AgentAnalyticsMessage.created_at).label("last_at"),
                )
                .where(
                    AgentAnalyticsMessage.bot_id == telegram_bot_id,
                    AgentAnalyticsMessage.role == "user",
                    AgentAnalyticsMessage.channel.in_(["telegram", "telegram_userbot"]),
                    AgentAnalyticsMessage.user_external_id.is_not(None),
                )
                .group_by(AgentAnalyticsMessage.user_external_id, AgentAnalyticsMessage.channel)
                .order_by(func.max(AgentAnalyticsMessage.created_at).desc())
            )
        )
        .mappings()
        .all()
    )
    recipients = []
    for row in rows:
        uid = row.get("uid")
        channel = (row.get("channel") or "").strip().lower()
        if not uid or not str(uid).isdigit():
            continue
        if channel not in {"telegram", "telegram_userbot"}:
            continue
        recipients.append({"user_external_id": str(uid), "channel": channel})
    return recipients


async def get_agent_by_external_api_key(
    x_agent_api_key: str | None = Header(default=None, alias="X-Agent-API-Key"),
):
    if not x_agent_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-Agent-API-Key is required")
    api_key_hash = hash_agent_external_api_key(x_agent_api_key.strip())
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await agent_dao.find_one_by_filter(external_api_key_hash=api_key_hash)
            if not agent:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
            return agent


