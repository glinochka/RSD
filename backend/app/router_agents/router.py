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
from ..services.voice_transcription import is_voice_stt_configured, transcribe_voice_bytes
from ..services.http_integration.errors import HttpIntegrationValidationError
from ..services.http_integration.tool_registry import validate_integration_config_dict
from ..services.qa_handoff_service import EscalationType as QAEscalationType, get_qa_handoff_service
from ..services.template_runtime import EscalationType, get_template_runtime
from ..services.telegram_userbot_auth import (
    TelegramUserbotAuthError,
    complete_qr_2fa,
    create_telegram_client,
    get_qr_status,
    import_session_file,
    resolve_api_credentials,
    start_qr_login,
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

logger = getLogger(__name__)
router = APIRouter(prefix="/api/agents")
http_bearer = HTTPBearer(auto_error=False)
MAX_INT32 = 2_147_483_647
USERBOT_AUTH_TOKEN_TTL_MINUTES = 10
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
    if not isinstance(raw_value, list):
        return ["купить"]
    normalized: list[str] = []
    for item in raw_value:
        word = str(item or "").strip().lower()
        if not word:
            continue
        if len(word) > 64:
            word = word[:64]
        if word not in normalized:
            normalized.append(word)
        if len(normalized) >= 30:
            break
    return normalized or ["купить"]


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
    raw = str(response.choices[0].message.content or "").strip()
    parsed: Any = []
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = [segment.strip() for segment in raw.split(",") if segment.strip()]
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
      pushMessage("agent", payload.answer || "Нет ответа");
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
        "domain_type": "beauty_salon",
        "crm_mode": "optional",
        # Keep runtime-compatible behavior for current implementation.
        "booking_backend": "crm",
        "crm_provider": "amocrm",
        "allowed_tools": list(DEFAULT_CRM_ALLOWED_TOOLS),
        "allowed_booking_tools": list(DEFAULT_BOOKING_ALLOWED_TOOLS),
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
        "domain_type": domain_type,
        "crm_mode": crm_mode,
        "booking_backend": booking_backend,
        "crm_provider": crm_provider,
        "allowed_tools": allowed_tools,
        "allowed_booking_tools": allowed_booking_tools,
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
    raw = (user_external_id or "").strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Пустой идентификатор получателя WhatsApp",
        )
    if "@" in raw:
        return raw
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный номер или JID WhatsApp (нужны цифры номера или полный JID)",
        )
    return f"{digits}@s.whatsapp.net"


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
            "connection_id": connection_id,
            "session_string": session_string,
        },
    )


async def _max_userbot_send_message(encrypted_credentials: str, text: str, *, chat_id: str | None = None) -> None:
    try:
        from ..channels.max_userbot_manager import MaxWsClient
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"MAX runtime недоступен: {exc}",
        ) from exc

    try:
        bundle = json.loads(decrypt_token(encrypted_credentials))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Не удалось декодировать MAX userbot credentials",
        ) from exc

    max_token = str(bundle.get("max_token") or "").strip()
    max_chat_id = str(chat_id or "").strip()
    if not max_token:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="MAX token отсутствует в сохраненных credentials",
        )
    if not max_chat_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="MAX chat id (user_external_id) обязателен для отправки",
        )

    def _send_once():
        client = MaxWsClient(max_token)
        try:
            client.connect()
            client.auth()
            client.send_message(max_chat_id, text)
        finally:
            client.close()

    try:
        await asyncio.get_running_loop().run_in_executor(None, _send_once)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Не удалось отправить сообщение в MAX: {exc}",
        ) from exc


async def _max_userbot_resolve_account_id(max_token: str) -> str:
    try:
        from ..channels.max_userbot_manager import MaxWsClient
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"MAX runtime недоступен: {exc}",
        ) from exc

    def _resolve() -> str:
        client = MaxWsClient(max_token)
        try:
            client.connect()
            client.auth()
            account_id = str((((client.me or {}).get("profile") or {}).get("contact") or {}).get("id") or "").strip()
            return account_id
        finally:
            client.close()

    try:
        account_id = await asyncio.get_running_loop().run_in_executor(None, _resolve)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось авторизовать MAX token: {exc}",
        ) from exc
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="MAX не вернул id аккаунта для token",
        )
    return account_id


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
        await _wa_userbot_bridge_post("session/disconnect", {"connection_id": connection_id})
    except Exception:
        logger.warning("whatsapp_userbot: failed to disconnect runtime session connection_id=%s", connection_id, exc_info=True)
    try:
        await _wa_userbot_bridge_post("session/logout", {"connection_id": connection_id})
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
    now = datetime.utcnow()
    payload = {
        "scope": "userbot_auth",
        "api_id": api_id,
        "encrypted_api_hash": encrypt_token(api_hash),
        "phone_number": phone_number,
        "phone_code_hash": phone_code_hash,
        "encrypted_pending_session": encrypted_pending_session,
        "exp": now + timedelta(minutes=USERBOT_AUTH_TOKEN_TTL_MINUTES),
        "iat": now,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _decode_userbot_auth_token(auth_token: str) -> dict:
    try:
        data = jwt.decode(auth_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный или просроченный токен подтверждения userbot",
        )
    if data.get("scope") != "userbot_auth":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный scope токена подтверждения userbot",
        )
    return data


def _create_userbot_qr_auth_token(
    *,
    api_id: int,
    api_hash: str,
    auth_id: str,
    encrypted_pending_session: str,
) -> str:
    now = datetime.utcnow()
    payload = {
        "scope": "userbot_qr_auth",
        "api_id": api_id,
        "encrypted_api_hash": encrypt_token(api_hash),
        "auth_id": auth_id,
        "encrypted_pending_session": encrypted_pending_session,
        "exp": now + timedelta(minutes=USERBOT_AUTH_TOKEN_TTL_MINUTES),
        "iat": now,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _decode_userbot_qr_auth_token(auth_token: str) -> dict:
    try:
        data = jwt.decode(auth_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный или просроченный токен QR-входа userbot",
        )
    if data.get("scope") != "userbot_qr_auth":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный scope токена QR-входа userbot",
        )
    auth_id = str(data.get("auth_id") or "").strip()
    if not auth_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен QR-входа userbot не содержит auth_id",
        )
    return data


def _userbot_auth_http_error(exc: TelegramUserbotAuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


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
    now = datetime.utcnow()
    payload = {
        "scope": "whatsapp_userbot_auth",
        "user_id": int(user_id),
        "phone_number": phone_number,
        "encrypted_bridge_auth_id": encrypt_token(bridge_auth_id),
        "exp": now + timedelta(minutes=USERBOT_AUTH_TOKEN_TTL_MINUTES),
        "iat": now,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _decode_whatsapp_userbot_auth_token(auth_token: str) -> dict:
    try:
        data = jwt.decode(auth_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный или просроченный токен подтверждения WhatsApp userbot",
        )
    if data.get("scope") != "whatsapp_userbot_auth":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный scope токена подтверждения WhatsApp userbot",
        )
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
    base = (settings.WHATSAPP_USERBOT_BRIDGE_URL or "").strip().rstrip("/")
    if not base:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp userbot bridge не настроен на сервере",
        )

    url = f"{base}/{path.lstrip('/')}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }
    bridge_api_key = (settings.WHATSAPP_USERBOT_BRIDGE_API_KEY or "").strip()
    if not bridge_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp userbot bridge API key не настроен на сервере",
        )
    headers["X-API-Key"] = bridge_api_key
    request = UrlRequest(url, data=body, headers=headers, method="POST")

    def _post():
        from urllib.error import HTTPError, URLError

        try:
            with urlopen(request, timeout=float(settings.WHATSAPP_USERBOT_BRIDGE_TIMEOUT_SECONDS)) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")
            except Exception:
                detail = str(exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"WhatsApp userbot bridge HTTP {exc.code}: {detail}",
            ) from exc
        except URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"WhatsApp userbot bridge transport error: {exc}",
            ) from exc

    result = await asyncio.get_running_loop().run_in_executor(None, _post)
    if not isinstance(result, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="WhatsApp userbot bridge вернул неожиданный ответ",
        )
    return result


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


@router.get("/internal/userbot_clients")
async def list_userbot_clients(request: Request, internal: bool = Depends(is_internal_request)):
    """List active userbot channel configs for bot service (internal only)."""
    if not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Internal API key required")
    await verify_internal_signature(request)

    async with async_session_maker() as session:
        async with session.begin():
            rows = (
                (
                    await session.execute(
                        select(
                            Agent.id.label("agent_id"),
                            Agent.bot_id,
                            Agent.system_prompt,
                            Agent.welcome_message,
                            Agent.process_start_with_llm,
                            AgentChannelConnection.encrypted_credentials,
                        )
                        .join(AgentChannelConnection, AgentChannelConnection.agent_id == Agent.id)
                        .where(
                            Agent.is_active.is_(True),
                            AgentChannelConnection.provider == "telegram_userbot",
                            AgentChannelConnection.connection_type == "userbot",
                            AgentChannelConnection.is_active.is_(True),
                            AgentChannelConnection.encrypted_credentials.is_not(None),
                        )
                    )
                )
                .mappings()
                .all()
            )

    payload = []
    for row in rows:
        resolved_lookup_id = row["bot_id"] if row["bot_id"] is not None else row["agent_id"]
        payload.append(
            {
                "agent_id": int(row["agent_id"]),
                "bot_id": int(resolved_lookup_id),
                "system_prompt": row["system_prompt"] or "",
                "welcome_message": row["welcome_message"],
                "process_start_with_llm": bool(row["process_start_with_llm"]),
                "encrypted_userbot_bundle": row["encrypted_credentials"],
            }
        )

    return JSONResponse(content=payload, status_code=status.HTTP_200_OK)


@router.get("/internal/whatsapp_userbot_clients")
async def list_whatsapp_userbot_clients(request: Request, internal: bool = Depends(is_internal_request)):
    """List active WhatsApp userbot channel configs for bot service (internal only)."""
    if not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Internal API key required")
    await verify_internal_signature(request)

    async with async_session_maker() as session:
        async with session.begin():
            rows = (
                (
                    await session.execute(
                        select(
                            Agent.id.label("agent_id"),
                            Agent.bot_id,
                            Agent.system_prompt,
                            Agent.welcome_message,
                            Agent.process_start_with_llm,
                            AgentChannelConnection.id.label("connection_id"),
                            AgentChannelConnection.external_id.label("phone_number"),
                            AgentChannelConnection.encrypted_credentials,
                        )
                        .join(AgentChannelConnection, AgentChannelConnection.agent_id == Agent.id)
                        .where(
                            Agent.is_active.is_(True),
                            AgentChannelConnection.provider == "whatsapp_userbot",
                            AgentChannelConnection.connection_type == "userbot",
                            AgentChannelConnection.is_active.is_(True),
                            AgentChannelConnection.encrypted_credentials.is_not(None),
                        )
                    )
                )
                .mappings()
                .all()
            )

    payload = []
    for row in rows:
        resolved_lookup_id = row["bot_id"] if row["bot_id"] is not None else row["agent_id"]
        payload.append(
            {
                "agent_id": int(row["agent_id"]),
                "bot_id": int(resolved_lookup_id),
                "connection_id": int(row["connection_id"]),
                "phone_number": row["phone_number"] or "",
                "system_prompt": row["system_prompt"] or "",
                "welcome_message": row["welcome_message"],
                "process_start_with_llm": bool(row["process_start_with_llm"]),
                "encrypted_credentials": row["encrypted_credentials"],
            }
        )

    return JSONResponse(content=payload, status_code=status.HTTP_200_OK)


@router.post("/internal/process_message")
async def internal_process_message(
    http_request: Request,
    payload: InternalProcessMessageRequest,
    internal: bool = Depends(is_internal_request),
):
    if not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Internal API key required")
    await verify_internal_signature(http_request)

    try:
        channel = RuntimeChannel(payload.channel)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported channel",
        )

    query_text = (payload.query or "").strip()
    runtime_ctx: dict[str, object] = {}

    if payload.voice_base64:
        raw_voice = (payload.voice_base64 or "").strip()
        try:
            audio_bytes = base64.b64decode(raw_voice, validate=True)
        except Exception:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid voice_base64")
        if len(audio_bytes) > int(settings.VOICE_MAX_BYTES):
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="voice payload too large")
        if is_voice_stt_configured():
            transcript = await transcribe_voice_bytes(
                audio_bytes,
                mime_type=(payload.voice_mime_type or "audio/ogg"),
            )
            if transcript:
                query_text = (
                    f"{query_text}\n\nТекст голосового сообщения: {transcript}".strip()
                    if query_text
                    else f"Текст голосового сообщения: {transcript}"
                )
            elif not query_text:
                query_text = "Пользователь прислал голосовое сообщение, но текст распознать не удалось."
        elif not query_text:
            return JSONResponse(
                content={
                    "text": (
                        "Голосовые сообщения недоступны: не настроено распознавание речи "
                        "(установите faster-whisper и модель, либо задайте OPENAI_API_KEY; DeepSeek аудио не принимает). "
                        "Напишите, пожалуйста, текстом."
                    ),
                    "status": RuntimeProcessingStatus.SUCCESS.value,
                },
                status_code=status.HTTP_200_OK,
            )

    query_text = query_text.strip()
    if not query_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty query after processing")

    runtime_request = RuntimeMessageRequest(
        bot_id=payload.bot_id,
        query=query_text,
        user_external_id=payload.user_external_id.strip(),
        channel=channel,
        system_prompt=(payload.system_prompt or "").strip(),
        welcome_message=payload.welcome_message,
        process_start_with_llm=bool(payload.process_start_with_llm),
        user_display_name=(payload.user_display_name or "").strip() or None,
        telegram_peer_access_hash=payload.telegram_peer_access_hash,
        runtime_context=runtime_ctx or None,
    )
    response = await get_message_processor().process(runtime_request)
    return JSONResponse(
        content={
            "text": response.text,
            "status": response.status.value,
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/crm/connect")
async def connect_crm(
    request: Request,
    payload: AgentCrmConnectPayload,
    current_user=Depends(get_current_user_required),
):
    _assert_https_for_sensitive_endpoint(request)
    provider_name = (payload.provider or "").strip().lower()
    base_url = _normalize_crm_base_url(payload.account_base_url)
    access_token = payload.access_token.strip()

    provider = build_provider(provider_name, base_url=base_url, access_token=access_token)
    try:
        health = await provider.validate_connection()
    except Exception:
        logger.exception("CRM credentials validation failed during connect (provider=%s)", provider_name)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CRM credentials validation failed",
        )

    now = datetime.utcnow()
    external_id = (health.external_id or "").strip() or base_url
    encrypted_credentials = encrypt_crm_credentials(
        json.dumps(
            {
                "base_url": base_url,
                "access_token": access_token,
                "account_external_id": external_id,
            },
            ensure_ascii=False,
        )
    )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        crm_connection_dao = AgentCrmConnectionDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )

            existing_for_agent = await crm_connection_dao.find_one_by_filter(
                agent_id=agent.id,
                provider=provider_name,
            )
            existing_global = await crm_connection_dao.find_one_by_filter(
                provider=provider_name,
                external_id=external_id,
            )
            if existing_global and existing_global.agent_id != agent.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот CRM аккаунт уже подключен к другому агенту",
                )

            if existing_for_agent:
                await crm_connection_dao.update(
                    existing_for_agent,
                    {
                        "external_id": external_id,
                        "encrypted_credentials": encrypted_credentials,
                        "is_active": True,
                        "last_checked_at": now,
                        "updated_at": now,
                    },
                )
                connection = existing_for_agent
            else:
                connection = await crm_connection_dao.add(
                    {
                        "agent_id": agent.id,
                        "provider": provider_name,
                        "external_id": external_id,
                        "encrypted_credentials": encrypted_credentials,
                        "is_active": True,
                        "last_checked_at": now,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                await session.flush()

            if _normalize_template_type(agent.template_type) == "crm_admin":
                current_config = _decode_template_config(
                    agent.template_config,
                    template_type=agent.template_type,
                ) or {}
                current_config["crm_provider"] = provider_name
                await agent_dao.update(
                    agent,
                    {
                        "template_config": _normalize_template_config("crm_admin", current_config),
                    },
                )

            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "crm_connection": _serialize_crm_connection(connection),
                    "health": {
                        "ok": health.ok,
                        "provider": health.provider,
                        "external_id": health.external_id,
                        "details": health.details,
                    },
                },
                status_code=status.HTTP_200_OK,
            )


@router.post("/http_integration/connect")
async def http_integration_connect(
    request: Request,
    payload: HttpIntegrationConnectPayload,
    current_user=Depends(get_current_user_required),
):
    _assert_https_for_sensitive_endpoint(request)
    slug = _normalize_http_integration_slug(payload.integration_name)
    tools_manifest = []
    for item in payload.tools:
        tools_manifest.append(
            {
                "name": item.name.strip(),
                "description": item.description.strip(),
                "method": item.method,
                "path": item.path.strip(),
                "requires_confirmation": item.requires_confirmation,
                "parameters": item.parameters,
            }
        )

    bundle: dict[str, object] = {
        "base_url": payload.base_url.strip().rstrip("/"),
        "timeout_seconds": float(payload.timeout_seconds),
        "default_headers": {str(k): str(v) for k, v in (payload.default_headers or {}).items() if str(k)},
        "auth": _bundle_auth_payload_to_dict(payload.auth),
        "tools": tools_manifest,
    }
    try:
        validated = validate_integration_config_dict(bundle)
    except HttpIntegrationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    encrypted_config = encrypt_crm_credentials(json.dumps(validated, ensure_ascii=False))

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        hid = AgentHttpIntegrationDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            if _normalize_template_type(agent.template_type) != "crm_admin":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Интеграции доступны только для шаблона ИИ‑администратора (crm_admin)",
                )

            existing = await hid.find_one_by_filter(agent_id=agent.id, name=slug)
            now = datetime.utcnow()
            if existing:
                await hid.update(
                    existing,
                    {
                        "encrypted_config": encrypted_config,
                        "is_active": True,
                        "updated_at": now,
                    },
                )
                row = existing
            else:
                row = await hid.add(
                    {
                        "agent_id": agent.id,
                        "name": slug,
                        "encrypted_config": encrypted_config,
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                await session.flush()

            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "http_integration": _serialize_http_integration(row),
                },
                status_code=status.HTTP_200_OK,
            )


@router.post("/http_integration/deactivate")
async def http_integration_deactivate(
    request: Request,
    payload: HttpIntegrationDeactivatePayload,
    current_user=Depends(get_current_user_required),
):
    _assert_https_for_sensitive_endpoint(request)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        hid = AgentHttpIntegrationDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            row = await hid.find_one_by_filter(agent_id=agent.id, id=payload.integration_id)
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
            now = datetime.utcnow()
            await hid.update(
                row,
                {
                    "is_active": False,
                    "updated_at": now,
                },
            )
            return JSONResponse(
                content={"http_integration": _serialize_http_integration(row)},
                status_code=status.HTTP_200_OK,
            )


@router.post("/crm/validate")
async def validate_crm_connection(
    request: Request,
    payload: AgentCrmValidatePayload,
    current_user=Depends(get_current_user_required),
):
    _assert_https_for_sensitive_endpoint(request)
    provider_name = (payload.provider or "").strip().lower()
    base_url = _normalize_crm_base_url(payload.account_base_url)
    access_token = payload.access_token.strip()

    try:
        provider = build_provider(provider_name, base_url=base_url, access_token=access_token)
        health = await provider.validate_connection()
    except Exception:
        logger.exception("CRM credentials validation failed (provider=%s)", provider_name)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CRM credentials validation failed",
        )

    return JSONResponse(
        content={
            "ok": bool(health.ok),
            "provider": health.provider,
            "external_id": health.external_id,
            "details": health.details,
        },
        status_code=status.HTTP_200_OK,
    )


@router.get("/crm/health")
async def crm_health(
    request: Request,
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    provider: str | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    _assert_https_for_sensitive_endpoint(request)
    if agent_id is None and bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'agent_id' or 'bot_id' is required",
        )

    provider_filter = (provider or "").strip().lower() or None
    if provider_filter and provider_filter not in CRM_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Supported providers: amocrm, bitrix24",
        )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=agent_id,
                bot_id=bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            rows = (
                (
                    await session.execute(
                        select(AgentCrmConnection).where(
                            AgentCrmConnection.agent_id == agent.id,
                            AgentCrmConnection.is_active.is_(True),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if provider_filter:
                rows = [row for row in rows if (row.provider or "").strip().lower() == provider_filter]
            if not rows:
                return JSONResponse(
                    content={
                        "agent_id": agent.id,
                        "bot_id": agent.bot_id,
                        "connections": [],
                    },
                    status_code=status.HTTP_200_OK,
                )

            now = datetime.utcnow()
            results = []
            for row in rows:
                try:
                    decrypted_payload, needs_rotation = decrypt_crm_credentials(row.encrypted_credentials)
                    bundle = json.loads(decrypted_payload)
                    if needs_rotation:
                        row.encrypted_credentials = encrypt_crm_credentials(
                            json.dumps(bundle, ensure_ascii=False)
                        )
                    provider_impl = build_provider(
                        row.provider,
                        base_url=str(bundle.get("base_url") or ""),
                        access_token=str(bundle.get("access_token") or ""),
                    )
                    health = await provider_impl.validate_connection()
                    row.last_checked_at = now
                    row.updated_at = now
                    results.append(
                        {
                            "connection": _serialize_crm_connection(row),
                            "health": {
                                "ok": health.ok,
                                "provider": health.provider,
                                "external_id": health.external_id,
                                "details": health.details,
                            },
                        }
                    )
                except Exception as exc:
                    logger.exception("CRM health check failed for connection_id=%s", row.id)
                    results.append(
                        {
                            "connection": _serialize_crm_connection(row),
                            "health": {
                                "ok": False,
                                "provider": row.provider,
                                "external_id": row.external_id,
                                "details": {"error": redact_pii_text(str(exc))},
                            },
                        }
                    )
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "connections": results,
                },
                status_code=status.HTTP_200_OK,
            )


@router.post("/crm/rotate_secret")
async def rotate_crm_secret(
    request: Request,
    payload: AgentCrmRotateSecretPayload,
    current_user=Depends(get_current_user_required),
):
    _assert_https_for_sensitive_endpoint(request)
    provider_filter = (payload.provider or "").strip().lower() or None

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        crm_connection_dao = AgentCrmConnectionDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            rows = (
                (
                    await session.execute(
                        select(AgentCrmConnection).where(
                            AgentCrmConnection.agent_id == agent.id,
                            AgentCrmConnection.is_active.is_(True),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if provider_filter:
                rows = [row for row in rows if (row.provider or "").strip().lower() == provider_filter]

            now = datetime.utcnow()
            rotated_count = 0
            for row in rows:
                try:
                    decrypted_payload, _ = decrypt_crm_credentials(row.encrypted_credentials)
                    row.encrypted_credentials = encrypt_crm_credentials(decrypted_payload)
                    row.updated_at = now
                    await crm_connection_dao.update(
                        row,
                        {
                            "encrypted_credentials": row.encrypted_credentials,
                            "updated_at": row.updated_at,
                        },
                    )
                    rotated_count += 1
                except Exception:
                    logger.exception("CRM secret rotation failed for connection_id=%s", row.id)

            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "provider": provider_filter,
                    "rotated": rotated_count,
                    "total_candidates": len(rows),
                },
                status_code=status.HTTP_200_OK,
            )


@router.get("")
async def read_agent(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    if agent_id is None and bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'agent_id' or 'bot_id' is required",
        )
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            resolved_channel = None
            if agent_id is not None:
                found_agent = await agent_dao.find_one_by_filter(id=agent_id)
            else:
                found_agent, resolved_channel = await _find_agent_by_lookup_id(
                    session=session,
                    agent_dao=agent_dao,
                    lookup_id=bot_id,
                )
            if not found_agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            if current_user and found_agent.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            await _ensure_external_api_key(found_agent, agent_dao)
            await _ensure_single_primary_flag(session=session, agent_id=found_agent.id)
            from ..services.agent_billing import enforce_expired_maintenance

            await enforce_expired_maintenance(agent_dao, found_agent)
            channels = await _list_agent_channels(session, found_agent.id)
            crm_connections = await _list_agent_crm_connections(session, found_agent.id)
            http_integrations = await _list_agent_http_integrations(session, found_agent.id)
            billing_user = await _resolve_billing_user(session, found_agent, current_user)
            payload = _serialize_agent(
                found_agent,
                user=billing_user,
                include_external_api_key=True,
                include_encrypted_token=internal,
            )
            payload["channels"] = [_serialize_channel_connection(item) for item in channels]
            payload["crm_connections"] = [_serialize_crm_connection(item) for item in crm_connections]
            payload["http_integrations"] = [_serialize_http_integration(item) for item in http_integrations]
            if internal and resolved_channel and resolved_channel.encrypted_credentials:
                # Internal webhook lookup by Telegram Bot ID must return that bot token.
                payload["encrypted_token"] = resolved_channel.encrypted_credentials
            return JSONResponse(
                content=payload,
                status_code=status.HTTP_200_OK,
            )


@router.get("/allBy_tgID")
async def read_all_agents(
    tg_id: int | None = Query(default=None, alias="id"),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            if current_user:
                user = await user_dao.find_one_by_filter(load_relations=True, id=current_user.id)
            else:
                if tg_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Query parameter 'id' is required for internal requests",
                    )
                user = await user_dao.find_one_by_filter(load_relations=True, telegram_id=tg_id)
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            from ..services.agent_billing import enforce_expired_maintenance

            agent_dao = AgentDAO(session)
            serialized_agents = []
            for agent in user.agents or []:
                await enforce_expired_maintenance(agent_dao, agent)
                serialized_agents.append(
                    _serialize_agent(agent, user=user, include_encrypted_token=internal)
                )
            return JSONResponse(
                content=serialized_agents,
                status_code=status.HTTP_200_OK,
            )


@router.post("")
async def create_empty_agent(
    payload: CreateEmptyAgent,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user_required),
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            template_type = _normalize_template_type(payload.template_type)
            template_config = _normalize_template_config(template_type, payload.template_config)
            external_api_key = generate_agent_external_api_key()
            created_agent = await agent_dao.add(
                {
                    "user_id": current_user.id,
                    "bot_id": None,
                    "primary_provider": "none",
                    "template_type": template_type,
                    "template_config": template_config,
                    "encrypted_token": encrypt_token(f"agent:{current_user.id}:{datetime.utcnow().timestamp()}"),
                    "encrypted_external_api_key": encrypt_token(external_api_key),
                    "external_api_key_hash": hash_agent_external_api_key(external_api_key),
                    "bot_username": None,
                    "system_prompt": payload.system_prompt.strip(),
                    "is_active": True,
                    **_initial_agent_billing_fields(template_type, user=current_user),
                }
            )
            await session.flush()
            if template_type == "sales_manager":
                background_tasks.add_task(
                    _schedule_sales_trigger_words_generation,
                    agent_id=int(created_agent.id),
                    system_prompt=str(payload.system_prompt or "").strip(),
                    template_config_json=template_config,
                )
            return JSONResponse(
                content=_serialize_agent(created_agent, user=current_user, include_external_api_key=True),
                status_code=status.HTTP_201_CREATED,
            )


@router.post("/ByUserWith_tgID")
async def create_agent_by_tg_id(
    new_agent: NewAgent_byUserWith_tgID,
    background_tasks: BackgroundTasks,
    internal: bool = Depends(is_internal_request),
):
    if not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Internal API key required")

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        user_dao = UserDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(telegram_id=new_agent.tg_id)
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            if user.is_banned:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

            duplicate_agent = await agent_dao.find_one_by_filter(bot_id=new_agent.bot_id)
            if duplicate_agent:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот Telegram бот уже зарегистрирован",
                )

            payload = new_agent.model_dump()
            payload["template_type"] = _normalize_template_type(payload.get("template_type"))
            payload["template_config"] = _normalize_template_config(
                payload["template_type"],
                payload.get("template_config"),
            )
            payload["user_id"] = user.id
            del payload["tg_id"]
            payload["primary_provider"] = "telegram_bot"
            external_api_key = generate_agent_external_api_key()
            payload["encrypted_external_api_key"] = encrypt_token(external_api_key)
            payload["external_api_key_hash"] = hash_agent_external_api_key(external_api_key)
            created_agent = await agent_dao.add(payload)
            await session.flush()
            if payload["template_type"] == "sales_manager":
                background_tasks.add_task(
                    _schedule_sales_trigger_words_generation,
                    agent_id=int(created_agent.id),
                    system_prompt=str(payload.get("system_prompt") or "").strip(),
                    template_config_json=payload.get("template_config"),
                )
            await channel_connection_dao.add(
                {
                    "agent_id": created_agent.id,
                    "provider": "telegram_bot",
                    "connection_type": "bot",
                    "external_id": str(created_agent.bot_id),
                    "encrypted_credentials": created_agent.encrypted_token,
                    "is_primary": True,
                    "is_active": True,
                }
            )
    return Response(status_code=status.HTTP_201_CREATED)


@router.post("/by_token")
async def create_agent_by_token(
    new_agent: NewAgent_byToken,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user_required),
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    token_value = new_agent.bot_token.strip()

    try:
        me = await _telegram_get_me(token_value)
    except Exception as exc:
        _raise_telegram_token_check_http_exception(exc)

    if not me or me.get("ok") is not True:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный API ключ Telegram бота",
        )

    result = me.get("result") or {}
    bot_id = result.get("id")
    bot_username = result.get("username")
    if bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Telegram не вернул bot id по указанному токену",
        )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            template_type = _normalize_template_type(new_agent.template_type)
            template_config = _normalize_template_config(template_type, new_agent.template_config)
            duplicate_agent = await agent_dao.find_one_by_filter(bot_id=bot_id)
            if duplicate_agent:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот Telegram бот уже зарегистрирован",
                )
            external_api_key = generate_agent_external_api_key()
            created_agent = await agent_dao.add(
                {
                    "user_id": current_user.id,
                    "bot_id": bot_id,
                    "primary_provider": "telegram_bot",
                    "template_type": template_type,
                    "template_config": template_config,
                    "encrypted_token": encrypt_token(token_value),
                    "encrypted_external_api_key": encrypt_token(external_api_key),
                    "external_api_key_hash": hash_agent_external_api_key(external_api_key),
                    "bot_username": bot_username,
                    "system_prompt": new_agent.system_prompt.strip(),
                    # New agents should be immediately usable via Telegram webhook.
                    "is_active": True,
                }
            )
            await session.flush()
            if template_type == "sales_manager":
                background_tasks.add_task(
                    _schedule_sales_trigger_words_generation,
                    agent_id=int(created_agent.id),
                    system_prompt=str(new_agent.system_prompt or "").strip(),
                    template_config_json=template_config,
                )
            await channel_connection_dao.add(
                {
                    "agent_id": created_agent.id,
                    "provider": "telegram_bot",
                    "connection_type": "bot",
                    "external_id": str(bot_id),
                    "encrypted_credentials": created_agent.encrypted_token,
                    "is_primary": True,
                    "is_active": True,
                }
            )

    try:
        await _sync_telegram_bot_webhook(token_value, bot_id, enabled=True)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return JSONResponse(content={"bot_id": bot_id}, status_code=status.HTTP_201_CREATED)


@router.post("/by_userbot_session")
async def create_agent_by_userbot_session(
    new_agent: NewAgent_byUserbotSession,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user_required),
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    api_id, api_hash = _resolve_userbot_api_pair(new_agent.api_id, new_agent.api_hash)
    session_string = new_agent.session_string.strip()
    me = await _validate_userbot_session(api_id=api_id, api_hash=api_hash, session_string=session_string)

    telegram_user_id = getattr(me, "id", None)
    if telegram_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Telethon не вернул идентификатор userbot",
        )

    username = getattr(me, "username", None)
    if username:
        bot_username = username
    else:
        first_name = (getattr(me, "first_name", "") or "").strip()
        last_name = (getattr(me, "last_name", "") or "").strip()
        fallback_name = " ".join(part for part in [first_name, last_name] if part).strip()
        bot_username = fallback_name or f"user_{telegram_user_id}"

    userbot_bundle = encrypt_token(
        json.dumps(
            {
                "api_id": api_id,
                "api_hash": api_hash,
                "session_string": session_string,
                "phone_number": None,
                "telegram_user_id": telegram_user_id,
            },
            ensure_ascii=False,
        )
    )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            template_type = _normalize_template_type(new_agent.template_type)
            template_config = _normalize_template_config(template_type, new_agent.template_config)
            duplicate_agent = await agent_dao.find_one_by_filter(bot_id=telegram_user_id)
            if duplicate_agent:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот Telegram userbot уже зарегистрирован",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider="telegram_userbot",
                external_id=str(telegram_user_id),
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот Telegram userbot уже подключен к другому агенту",
                )

            external_api_key = generate_agent_external_api_key()
            created_agent = await agent_dao.add(
                {
                    "user_id": current_user.id,
                    "bot_id": telegram_user_id,
                    "primary_provider": "telegram_userbot",
                    "template_type": template_type,
                    "template_config": template_config,
                    "encrypted_token": encrypt_token(session_string),
                    "encrypted_external_api_key": encrypt_token(external_api_key),
                    "external_api_key_hash": hash_agent_external_api_key(external_api_key),
                    "bot_username": bot_username,
                    "system_prompt": new_agent.system_prompt.strip(),
                    "is_active": True,
                }
            )
            await session.flush()
            if template_type == "sales_manager":
                background_tasks.add_task(
                    _schedule_sales_trigger_words_generation,
                    agent_id=int(created_agent.id),
                    system_prompt=str(new_agent.system_prompt or "").strip(),
                    template_config_json=template_config,
                )
            await channel_connection_dao.add(
                {
                    "agent_id": created_agent.id,
                    "provider": "telegram_userbot",
                    "connection_type": "userbot",
                    "external_id": str(telegram_user_id),
                    "encrypted_credentials": userbot_bundle,
                    "is_primary": True,
                    "is_active": True,
                }
            )

    return JSONResponse(
        content={"bot_id": telegram_user_id, "connection_type": "telegram_userbot"},
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/userbot/request_code")
async def request_userbot_code(
    payload: UserbotRequestCode, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    phone_number = payload.phone_number.strip()

    try:
        from telethon.errors import FloodWaitError
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Telethon не установлен на сервере: {exc}",
        )

    client, api_id, api_hash = create_telegram_client(
        api_id=payload.api_id,
        api_hash=payload.api_hash.strip() if payload.api_hash else None,
        prefer_desktop=True,
    )
    phone_code_hash = None
    pending_session_string = ""
    try:
        await client.connect()
        sent = await client.send_code_request(phone=phone_number)
        phone_code_hash = getattr(sent, "phone_code_hash", None)
        if not phone_code_hash:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Telegram не вернул phone_code_hash",
            )
        pending_session_string = client.session.save()
    except FloodWaitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Слишком много попыток. Подождите {exc.seconds} сек",
        )
    except HTTPException:
        raise
    except Exception as exc:
        detail = f"Не удалось отправить код подтверждения Telegram: {exc}"
        if "api_id/api_hash combination is invalid" in str(exc).lower():
            detail = (
                "Telegram отклонил API-ключи. Попробуйте вход по QR-код "
                "или задайте TELEGRAM_USERBOT_API_ID и TELEGRAM_USERBOT_API_HASH в .env "
                "(пара с my.telegram.org)."
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )
    finally:
        await client.disconnect()

    auth_token = _create_userbot_auth_token(
        api_id=api_id,
        api_hash=api_hash,
        phone_number=phone_number,
        phone_code_hash=phone_code_hash,
        encrypted_pending_session=encrypt_token(pending_session_string),
    )
    return JSONResponse(content={"auth_token": auth_token}, status_code=status.HTTP_200_OK)


@router.post("/userbot/verify_code")
async def verify_userbot_code(
    payload: UserbotVerifyCode, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    token_data = _decode_userbot_auth_token(payload.auth_token.strip())
    api_id = int(token_data["api_id"])
    api_hash = decrypt_token(token_data["encrypted_api_hash"])
    phone_number = token_data["phone_number"]
    phone_code_hash = token_data["phone_code_hash"]
    pending_session_enc = token_data.get("encrypted_pending_session")
    pending_session = decrypt_token(pending_session_enc) if pending_session_enc else ""

    code = "".join(ch for ch in payload.code.strip() if ch.isdigit())
    password = payload.password.strip() if payload.password else None
    if not code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Введите код подтверждения (цифры из Telegram)",
        )

    try:
        from telethon.errors import (
            PhoneCodeExpiredError,
            PhoneCodeInvalidError,
            SessionPasswordNeededError,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Telethon не установлен на сервере: {exc}",
        )

    client, api_id, api_hash = create_telegram_client(
        api_id=api_id,
        api_hash=api_hash,
        session_string=pending_session or "",
        prefer_desktop=True,
    )
    try:
        await client.connect()
        try:
            await client.sign_in(phone=phone_number, code=code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            if not password:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Для этого аккаунта включен пароль 2FA. Передайте поле password.",
                )
            await client.sign_in(password=password)
        except PhoneCodeInvalidError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Неверный код подтверждения Telegram",
            )
        except PhoneCodeExpiredError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Код подтверждения Telegram истек. Запросите новый код.",
            )

        me = await client.get_me()
        if not me:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Telethon не смог получить профиль пользователя после входа",
            )
        session_string = client.session.save()
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("userbot verify_code failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось подтвердить код Telegram: {exc}",
        )
    finally:
        await client.disconnect()

    return JSONResponse(
        content={
            "session_string": session_string,
            "api_id": api_id,
            "api_hash": api_hash,
            "phone_number": phone_number,
            "telegram_id": getattr(me, "id", None),
            "username": getattr(me, "username", None),
            "first_name": getattr(me, "first_name", None),
            "last_name": getattr(me, "last_name", None),
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/userbot/qr/start")
async def userbot_qr_start(
    payload: UserbotQrStart, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    api_id, api_hash = _resolve_userbot_api_pair(
        payload.api_id,
        payload.api_hash.strip() if payload.api_hash else None,
        prefer_desktop=True,
    )
    try:
        result = await start_qr_login(api_id=api_id, api_hash=api_hash)
    except TelegramUserbotAuthError as exc:
        raise _userbot_auth_http_error(exc) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось начать QR-вход Telegram: {exc}",
        ) from exc

    auth_token = _create_userbot_qr_auth_token(
        api_id=api_id,
        api_hash=api_hash,
        auth_id=str(result["auth_id"]),
        encrypted_pending_session=encrypt_token(str(result.get("pending_session_string") or "")),
    )
    content: dict[str, Any] = {
        "auth_token": auth_token,
        "qr_url": result.get("qr_url") or "",
        "qr_data_url": result.get("qr_data_url") or "",
        "already_authorized": bool(result.get("already_authorized")),
    }
    if result.get("already_authorized"):
        content["session_string"] = str(result.get("pending_session_string") or "")
        content["api_id"] = result.get("api_id", api_id)
        content["api_hash"] = result.get("api_hash", api_hash)
    return JSONResponse(content=content, status_code=status.HTTP_200_OK)


@router.post("/userbot/qr/status")
async def userbot_qr_status(
    payload: UserbotQrStatus, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    token_data = _decode_userbot_qr_auth_token(payload.auth_token.strip())
    api_id = int(token_data["api_id"])
    api_hash = decrypt_token(token_data["encrypted_api_hash"])
    auth_id = str(token_data["auth_id"])
    qr_state = await get_qr_status(auth_id=auth_id)

    response: dict[str, Any] = {
        "status": qr_state.get("status") or "pending",
        "error": qr_state.get("error"),
        "api_id": api_id,
        "api_hash": api_hash,
    }
    if qr_state.get("status") == "success":
        session_string = str(qr_state.get("session_string") or "").strip()
        if not session_string:
            pending_enc = token_data.get("encrypted_pending_session")
            if pending_enc:
                session_string = decrypt_token(pending_enc)
        if qr_state.get("api_id"):
            response["api_id"] = int(qr_state["api_id"])
        if qr_state.get("api_hash"):
            response["api_hash"] = str(qr_state["api_hash"])
        me = qr_state.get("me") if isinstance(qr_state.get("me"), dict) else {}
        response.update(
            {
                "session_string": session_string,
                "telegram_id": me.get("telegram_id"),
                "username": me.get("username"),
                "first_name": me.get("first_name"),
                "last_name": me.get("last_name"),
                "phone_number": me.get("phone_number"),
            }
        )
    elif qr_state.get("status") == "need_2fa":
        pending_enc = token_data.get("encrypted_pending_session")
        if qr_state.get("session_string"):
            response["pending_session_string"] = qr_state.get("session_string")
        elif pending_enc:
            response["pending_session_string"] = decrypt_token(pending_enc)
    return JSONResponse(content=response, status_code=status.HTTP_200_OK)


@router.post("/userbot/qr/verify_2fa")
async def userbot_qr_verify_2fa(
    payload: UserbotQrVerify2fa, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    token_data = _decode_userbot_qr_auth_token(payload.auth_token.strip())
    api_id = int(token_data["api_id"])
    api_hash = decrypt_token(token_data["encrypted_api_hash"])
    pending_enc = token_data.get("encrypted_pending_session")
    pending_session = decrypt_token(pending_enc) if pending_enc else ""

    qr_state = await get_qr_status(auth_id=str(token_data["auth_id"]))
    if qr_state.get("session_string"):
        pending_session = str(qr_state["session_string"])

    try:
        result = await complete_qr_2fa(
            api_id=api_id,
            api_hash=api_hash,
            session_string=pending_session,
            password=payload.password,
        )
    except TelegramUserbotAuthError as exc:
        raise _userbot_auth_http_error(exc) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось подтвердить 2FA Telegram: {exc}",
        ) from exc

    return JSONResponse(content=result, status_code=status.HTTP_200_OK)


@router.post("/userbot/import_session")
async def userbot_import_session(
    session_file: UploadFile = File(...),
    api_id: int | None = Form(default=None),
    api_hash: str | None = Form(default=None),
    current_user=Depends(get_current_user_required),
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    raw = await session_file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Файл сессии слишком большой (макс. 25 МБ)",
        )
    try:
        custom_hash = api_hash.strip() if api_hash else None
        custom_id = int(api_id) if api_id is not None and int(api_id) > 0 else None
        result = await import_session_file(
            api_id=custom_id,
            api_hash=custom_hash,
            filename=session_file.filename or "upload",
            content=raw,
        )
    except TelegramUserbotAuthError as exc:
        raise _userbot_auth_http_error(exc) from exc
    except Exception as exc:
        logger.warning("userbot import_session failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось импортировать сессию: {exc}",
        ) from exc

    return JSONResponse(content=result, status_code=status.HTTP_200_OK)


@router.post("/whatsapp_userbot/request_code")
async def request_whatsapp_userbot_code(
    payload: WhatsAppUserbotRequestCode, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    phone_number = payload.phone_number.strip()
    if len([ch for ch in phone_number if ch.isdigit()]) < 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный номер WhatsApp",
        )

    result = await _wa_userbot_bridge_post(
        "auth/request_code",
        {
            "phone_number": phone_number,
        },
    )
    bridge_auth_id = str(result.get("auth_id") or result.get("session_id") or "").strip()
    if not bridge_auth_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="WhatsApp userbot bridge не вернул auth_id",
        )

    auth_token = _create_whatsapp_userbot_auth_token(
        user_id=current_user.id,
        phone_number=phone_number,
        bridge_auth_id=bridge_auth_id,
    )
    return JSONResponse(
        content={
            "auth_token": auth_token,
            "phone_number": phone_number,
            "delivery": result.get("delivery"),
            "hint": result.get("hint"),
            "qr_data_url": result.get("qr_data_url"),
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/whatsapp_userbot/verify_code")
async def verify_whatsapp_userbot_code(
    payload: WhatsAppUserbotVerifyCode, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    token_data = _decode_whatsapp_userbot_auth_token(payload.auth_token.strip())
    if int(token_data["user_id"]) != int(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Токен подтверждения WhatsApp userbot принадлежит другому пользователю",
        )
    phone_number = str(token_data.get("phone_number") or "").strip()
    bridge_auth_id = decrypt_token(token_data["encrypted_bridge_auth_id"])
    code = payload.code.strip() if payload.code else ""

    result = await _wa_userbot_bridge_post(
        "auth/verify_code",
        {
            "auth_id": bridge_auth_id,
            "phone_number": phone_number,
            "code": code or None,
        },
    )
    session_string = str(result.get("session_string") or "").strip()
    normalized_phone = str(result.get("phone_number") or phone_number).strip()
    normalized_phone, _ = _validate_whatsapp_session_string(
        session_string=session_string,
        expected_phone=normalized_phone,
    )

    return JSONResponse(
        content={
            "session_string": session_string,
            "phone_number": normalized_phone,
            "external_user_id": result.get("external_user_id"),
            "display_name": result.get("display_name"),
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/whatsapp_userbot/auth_status")
async def whatsapp_userbot_auth_status(
    payload: WhatsAppUserbotAuthStatus, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    token_data = _decode_whatsapp_userbot_auth_token(payload.auth_token.strip())
    if int(token_data["user_id"]) != int(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Токен подтверждения WhatsApp userbot принадлежит другому пользователю",
        )
    bridge_auth_id = decrypt_token(token_data["encrypted_bridge_auth_id"])
    result = await _wa_userbot_bridge_post(
        "auth/status",
        {
            "auth_id": bridge_auth_id,
        },
    )
    return JSONResponse(
        content={
            "status": result.get("status") or "pending",
            "qr_data_url": result.get("qr_data_url"),
            "last_error": result.get("last_error"),
            "last_disconnect_code": result.get("last_disconnect_code"),
        },
        status_code=status.HTTP_200_OK,
    )


@router.get("/channels")
async def list_agent_channels(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    if agent_id is None and bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'agent_id' or 'bot_id' is required",
        )
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=agent_id,
                bot_id=bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            await _ensure_single_primary_flag(session=session, agent_id=agent.id)
            channels = await _list_agent_channels(session, agent.id)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                },
                status_code=status.HTTP_200_OK,
            )


@router.post("/channels/by_youtube_oauth_start")
async def start_agent_youtube_oauth(
    payload: YouTubeOAuthStartPayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            redirect_uri = str(payload.redirect_uri or settings.YOUTUBE_OAUTH_REDIRECT_URI or "").strip()
            if not redirect_uri:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="YouTube OAuth redirect_uri не настроен",
                )
            state = _create_youtube_oauth_state(
                user_id=current_user.id,
                agent_id=agent.id,
                redirect_uri=redirect_uri,
            )
            auth_url = get_youtube_client().build_oauth_authorization_url(
                state=state,
                redirect_uri=redirect_uri,
            )
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "auth_url": auth_url,
                    "state": state,
                    "redirect_uri": redirect_uri,
                },
                status_code=status.HTTP_200_OK,
            )


@router.post("/channels/by_youtube_oauth_callback")
async def complete_agent_youtube_oauth(payload: YouTubeOAuthCallbackPayload):
    code = payload.code.strip()
    state = payload.state.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Пустой OAuth code YouTube")
    token_data = _decode_youtube_oauth_state(state)
    agent_id = int(token_data["agent_id"])
    user_id = int(token_data["user_id"])
    redirect_uri = str(token_data.get("redirect_uri") or "").strip()

    youtube_client = get_youtube_client()
    token_bundle = await youtube_client.exchange_code_for_tokens(code=code, redirect_uri=redirect_uri)
    health = await youtube_client.health_check(token_bundle=token_bundle)
    effective_bundle = health.get("token_bundle") or token_bundle
    external_id = str(health.get("external_id") or "").strip() or "youtube"

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            agent = await session.scalar(
                select(Agent).where(
                    Agent.id == agent_id,
                    Agent.user_id == user_id,
                )
            )
            if not agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found for OAuth state")

            duplicate_connection = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.provider == "youtube",
                    AgentChannelConnection.external_id == external_id,
                    AgentChannelConnection.agent_id != agent.id,
                )
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот YouTube канал уже подключен к другому агенту",
                )

            encrypted_bundle = encrypt_token(json.dumps(effective_bundle, ensure_ascii=False))
            existing = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == "youtube",
                    AgentChannelConnection.connection_type == "oauth",
                )
            )
            now = datetime.utcnow()
            if existing:
                existing.external_id = external_id
                existing.encrypted_credentials = encrypted_bundle
                existing.is_active = True
                existing.updated_at = now
            else:
                await channel_connection_dao.add(
                    {
                        "agent_id": agent.id,
                        "provider": "youtube",
                        "connection_type": "oauth",
                        "external_id": external_id,
                        "encrypted_credentials": encrypted_bundle,
                        "is_primary": False,
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    }
                )

            await _sync_agent_primary_fields(agent=agent, agent_dao=agent_dao, session=session)
            channels = await _list_agent_channels(session, agent.id)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                    "youtube_health": {
                        "ok": bool(health.get("ok")),
                        "provider": "youtube",
                        "external_id": external_id,
                        "details": health.get("details") or {},
                    },
                },
                status_code=status.HTTP_200_OK,
            )


@router.get("/channels/youtube/health")
async def youtube_health(
    payload: YouTubeHealthPayload = Depends(),
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            channel = await _get_youtube_oauth_channel_for_agent(session, agent.id)
            if not channel or not channel.encrypted_credentials:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="YouTube OAuth канал не подключен",
                )
            try:
                bundle_raw = decrypt_token(channel.encrypted_credentials)
                bundle = json.loads(bundle_raw)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Поврежденный bundle YouTube OAuth в канале",
                )
            health = await get_youtube_client().health_check(token_bundle=bundle)
            updated_bundle = health.get("token_bundle") or bundle
            channel.encrypted_credentials = encrypt_token(json.dumps(updated_bundle, ensure_ascii=False))
            channel.external_id = str(health.get("external_id") or channel.external_id or "youtube")
            channel.updated_at = datetime.utcnow()
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "connection": _serialize_channel_connection(channel),
                    "health": {
                        "ok": bool(health.get("ok")),
                        "provider": "youtube",
                        "external_id": channel.external_id,
                        "details": health.get("details") or {},
                    },
                },
                status_code=status.HTTP_200_OK,
            )


@router.post("/channels/by_token")
async def add_agent_telegram_bot_channel(
    payload: AddTelegramBotChannel,
    current_user=Depends(get_current_user_required),
):
    token_value = payload.bot_token.strip()
    try:
        me = await _telegram_get_me(token_value)
    except Exception as exc:
        _raise_telegram_token_check_http_exception(exc)
    if not me or me.get("ok") is not True:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный API ключ Telegram бота",
        )
    result = me.get("result") or {}
    telegram_bot_id = result.get("id")
    bot_username = result.get("username")
    if telegram_bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Telegram не вернул bot id по указанному токену",
        )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            existing_bot_channel = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == "telegram_bot",
                    AgentChannelConnection.connection_type == "bot",
                )
            )
            if existing_bot_channel:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключен Telegram бот-канал",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider="telegram_bot",
                external_id=str(telegram_bot_id),
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот Telegram бот уже подключен к другому агенту",
                )

            now = datetime.utcnow()
            created_connection = await channel_connection_dao.add(
                {
                    "agent_id": agent.id,
                    "provider": "telegram_bot",
                    "connection_type": "bot",
                    "external_id": str(telegram_bot_id),
                    "encrypted_credentials": encrypt_token(token_value),
                    "is_primary": bool(payload.make_primary),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            await session.flush()
            if payload.make_primary:
                await _set_primary_channel(
                    session=session,
                    agent_id=agent.id,
                    connection_id=created_connection.id,
                )
                await agent_dao.update(agent, {"bot_username": bot_username or agent.bot_username})
            await _sync_agent_primary_fields(agent=agent, agent_dao=agent_dao, session=session)

            if agent.is_active:
                await _sync_telegram_bot_webhook(token_value, int(created_connection.external_id), enabled=True)

            channels = await _list_agent_channels(session, agent.id)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                },
                status_code=status.HTTP_201_CREATED,
            )


@router.post("/channels/by_userbot_session")
async def add_agent_userbot_channel(
    payload: AddTelegramUserbotChannel,
    current_user=Depends(get_current_user_required),
):
    api_id, api_hash = _resolve_userbot_api_pair(
        payload.api_id,
        payload.api_hash.strip() if payload.api_hash else None,
    )
    session_string = payload.session_string.strip()
    me = await _validate_userbot_session(api_id=api_id, api_hash=api_hash, session_string=session_string)

    telegram_user_id = getattr(me, "id", None)
    if telegram_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Telethon не вернул идентификатор userbot",
        )

    userbot_bundle = encrypt_token(
        json.dumps(
            {
                "api_id": api_id,
                "api_hash": api_hash,
                "session_string": session_string,
                "phone_number": None,
                "telegram_user_id": telegram_user_id,
            },
            ensure_ascii=False,
        )
    )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            existing_userbot_channel = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == "telegram_userbot",
                    AgentChannelConnection.connection_type == "userbot",
                )
            )
            if existing_userbot_channel:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключен Telegram userbot-канал",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider="telegram_userbot",
                external_id=str(telegram_user_id),
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот Telegram userbot уже подключен к другому агенту",
                )

            now = datetime.utcnow()
            created_connection = await channel_connection_dao.add(
                {
                    "agent_id": agent.id,
                    "provider": "telegram_userbot",
                    "connection_type": "userbot",
                    "external_id": str(telegram_user_id),
                    "encrypted_credentials": userbot_bundle,
                    "is_primary": bool(payload.make_primary),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            await session.flush()
            if payload.make_primary:
                await _set_primary_channel(
                    session=session,
                    agent_id=agent.id,
                    connection_id=created_connection.id,
                )
            await _sync_agent_primary_fields(agent=agent, agent_dao=agent_dao, session=session)
            channels = await _list_agent_channels(session, agent.id)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                },
                status_code=status.HTTP_201_CREATED,
            )


@router.post("/channels/by_max_bot")
async def add_agent_max_bot_channel(
    payload: AddMaxBotChannel,
    current_user=Depends(get_current_user_required),
):
    bot_token = payload.bot_token.strip()
    try:
        me = await _max_bot_get_me(bot_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Не удалось связаться с MAX API для проверки токена: {exc}",
        )

    max_bot_id = me.get("user_id")
    if max_bot_id is None or not str(max_bot_id).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="MAX API не вернул user_id бота",
        )
    is_bot = me.get("is_bot")
    if is_bot is not None and not bool(is_bot):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Переданный токен не принадлежит чат-боту MAX",
        )
    bot_username = (
        str(me.get("username") or "").strip()
        or str(me.get("first_name") or "").strip()
        or str(me.get("name") or "").strip()
        or f"max_bot_{max_bot_id}"
    )

    encrypted_bundle = encrypt_token(
        json.dumps(
            {
                "max_bot_token": bot_token,
                "max_bot_user_id": str(max_bot_id).strip(),
            },
            ensure_ascii=False,
        )
    )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            existing_max_bot_channel = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == "max_bot",
                    AgentChannelConnection.connection_type == "bot",
                )
            )
            if existing_max_bot_channel:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключен MAX bot-канал",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider="max_bot",
                external_id=str(max_bot_id),
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот MAX бот уже подключен к другому агенту",
                )

            now = datetime.utcnow()
            created_connection = await channel_connection_dao.add(
                {
                    "agent_id": agent.id,
                    "provider": "max_bot",
                    "connection_type": "bot",
                    "external_id": str(max_bot_id),
                    "encrypted_credentials": encrypted_bundle,
                    "is_primary": bool(payload.make_primary),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            await session.flush()
            if payload.make_primary:
                await _set_primary_channel(
                    session=session,
                    agent_id=agent.id,
                    connection_id=created_connection.id,
                )
                await agent_dao.update(agent, {"bot_username": bot_username or agent.bot_username})
            await _sync_agent_primary_fields(agent=agent, agent_dao=agent_dao, session=session)
            channels = await _list_agent_channels(session, agent.id)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                },
                status_code=status.HTTP_201_CREATED,
            )


@router.post("/channels/by_whatsapp_business_api")
async def add_agent_whatsapp_business_api_channel(
    payload: AddWhatsAppBusinessApiChannel,
    current_user=Depends(get_current_user_required),
):
    phone_number_id = payload.phone_number_id.strip()
    access_token = payload.access_token.strip()
    business_account_id = payload.business_account_id.strip() if payload.business_account_id else None
    verify_token = payload.verify_token.strip() if payload.verify_token else None
    if not phone_number_id.isdigit():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Phone Number ID должен содержать только цифры",
        )
    try:
        waba_phone_info = await _waba_get_phone_number_info(phone_number_id, access_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось проверить доступ к WhatsApp Business API. Проверьте access token и phone_number_id",
        )
    resolved_phone_number_id = str(waba_phone_info.get("id") or "").strip()
    if not resolved_phone_number_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Meta Graph API не вернул id номера. Проверьте access token и phone_number_id",
        )
    phone_number_id = resolved_phone_number_id

    encrypted_bundle = encrypt_token(
        json.dumps(
            {
                "phone_number_id": phone_number_id,
                "access_token": access_token,
                "business_account_id": business_account_id,
                "verify_token": verify_token,
                "display_phone_number": waba_phone_info.get("display_phone_number"),
                "verified_name": waba_phone_info.get("verified_name"),
                "quality_rating": waba_phone_info.get("quality_rating"),
            },
            ensure_ascii=False,
        )
    )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            existing_whatsapp_channel = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == "whatsapp_business_api",
                    AgentChannelConnection.connection_type == "api",
                )
            )
            if existing_whatsapp_channel:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключен канал WhatsApp Business API",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider="whatsapp_business_api",
                external_id=phone_number_id,
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот WhatsApp phone_number_id уже подключен к другому агенту",
                )

            now = datetime.utcnow()
            created_connection = await channel_connection_dao.add(
                {
                    "agent_id": agent.id,
                    "provider": "whatsapp_business_api",
                    "connection_type": "api",
                    "external_id": phone_number_id,
                    "encrypted_credentials": encrypted_bundle,
                    "is_primary": bool(payload.make_primary),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            await session.flush()
            if payload.make_primary:
                await _set_primary_channel(
                    session=session,
                    agent_id=agent.id,
                    connection_id=created_connection.id,
                )
            await _sync_agent_primary_fields(agent=agent, agent_dao=agent_dao, session=session)
            channels = await _list_agent_channels(session, agent.id)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                },
                status_code=status.HTTP_201_CREATED,
            )


@router.post("/channels/by_whatsapp_userbot")
async def add_agent_whatsapp_userbot_channel(
    payload: AddWhatsAppUserbotChannel,
    current_user=Depends(get_current_user_required),
):
    normalized_phone = payload.phone_number.strip()
    session_string = payload.session_string.strip()
    client_label = payload.client_label.strip() if payload.client_label else None
    if len([ch for ch in normalized_phone if ch.isdigit()]) < 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный номер WhatsApp userbot",
        )

    normalized_phone, _ = _validate_whatsapp_session_string(
        session_string=session_string,
        expected_phone=normalized_phone,
    )
    encrypted_bundle = encrypt_token(
        json.dumps(
            {
                "phone_number": normalized_phone,
                "session_string": session_string,
                "client_label": client_label,
            },
            ensure_ascii=False,
        )
    )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            existing_whatsapp_userbot_channel = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == "whatsapp_userbot",
                    AgentChannelConnection.connection_type == "userbot",
                )
            )
            if existing_whatsapp_userbot_channel:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключен WhatsApp userbot-канал",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider="whatsapp_userbot",
                external_id=normalized_phone,
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот WhatsApp userbot уже подключен к другому агенту",
                )

            now = datetime.utcnow()
            created_connection = await channel_connection_dao.add(
                {
                    "agent_id": agent.id,
                    "provider": "whatsapp_userbot",
                    "connection_type": "userbot",
                    "external_id": normalized_phone,
                    "encrypted_credentials": encrypted_bundle,
                    "is_primary": bool(payload.make_primary),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            await session.flush()
            if payload.make_primary:
                await _set_primary_channel(
                    session=session,
                    agent_id=agent.id,
                    connection_id=created_connection.id,
                )
            await _sync_agent_primary_fields(agent=agent, agent_dao=agent_dao, session=session)
            channels = await _list_agent_channels(session, agent.id)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                },
                status_code=status.HTTP_201_CREATED,
            )


@router.get("/channels/telephony/platform")
async def get_telephony_platform_config(
    current_user=Depends(get_current_user_required),
):
    """Публичные настройки общего номера (без секретов Voximplant)."""
    _ = current_user
    return platform_telephony_public_fields()


@router.post("/channels/add-telephony")
async def add_agent_telephony_channel(
    payload: AddTelephonyChannel,
    current_user=Depends(get_current_user_required),
):
    if not settings.TELEPHONY_WEBHOOK_BASE_URL.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TELEPHONY_WEBHOOK_BASE_URL не настроен на сервере",
        )
    require_platform_telephony_config()
    creds = await validate_telephony_credentials_input(payload)
    external_id = telephony_external_id(creds.phone_number_e164, creds.routing_extension)
    encrypted_bundle = build_encrypted_telephony_bundle(creds, encrypt_token)

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            if creds.routing_extension:
                conflict = await scan_extension_conflict_in_db(
                    session,
                    creds.routing_extension,
                )
                if conflict is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Добавочный {creds.routing_extension} уже занят",
                    )
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            existing = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == TELEPHONY_CHANNEL_PROVIDER,
                )
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключена телефония",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider=TELEPHONY_CHANNEL_PROVIDER,
                external_id=external_id,
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Добавочный {creds.routing_extension} уже занят другим агентом",
                )

            now = datetime.utcnow()
            created_connection = await channel_connection_dao.add(
                {
                    "agent_id": agent.id,
                    "provider": TELEPHONY_CHANNEL_PROVIDER,
                    "connection_type": "api",
                    "external_id": external_id,
                    "encrypted_credentials": encrypted_bundle,
                    "is_primary": bool(payload.make_primary),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            await session.flush()
            await sync_channel_routes(
                connection_id=int(created_connection.id),
                agent_id=int(agent.id),
                creds=creds,
            )
            if payload.make_primary:
                await _set_primary_channel(
                    session=session,
                    agent_id=agent.id,
                    connection_id=created_connection.id,
                )
            await _sync_agent_primary_fields(agent=agent, agent_dao=agent_dao, session=session)
            channels = await _list_agent_channels(session, agent.id)
            extra = telephony_connect_response_extra(int(created_connection.id))
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                    "telephony_routing": telephony_routing_public_fields(creds),
                    "telephony_platform": platform_telephony_public_fields(),
                    **extra,
                },
                status_code=status.HTTP_201_CREATED,
            )


@router.patch("/channels/telephony/routing")
async def update_agent_telephony_routing(
    payload: UpdateTelephonyRouting,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            connection = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == TELEPHONY_CHANNEL_PROVIDER,
                    AgentChannelConnection.is_active.is_(True),
                )
            )
            if connection is None or not connection.encrypted_credentials:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Телефонный канал не найден",
                )
            previous = parse_telephony_credentials(decrypt_token(connection.encrypted_credentials))
            updated = previous.model_copy(
                update={
                    "routing_extension": payload.routing_extension.strip(),
                    "inbound_numbers": [],
                }
            )
            if updated.routing_extension:
                conflict = await scan_extension_conflict_in_db(
                    session,
                    updated.routing_extension,
                    exclude_connection_id=int(connection.id),
                )
                if conflict is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Добавочный {updated.routing_extension} уже занят",
                    )
            connection.encrypted_credentials = encrypt_token(updated.to_encrypted_payload())
            connection.updated_at = datetime.utcnow()
            await sync_channel_routes(
                connection_id=int(connection.id),
                agent_id=int(agent.id),
                creds=updated,
                previous=previous,
            )
            channels = await _list_agent_channels(session, agent.id)
            return {
                "agent_id": agent.id,
                "telephony_routing": telephony_routing_public_fields(updated),
                "channels": [_serialize_channel_connection(item) for item in channels],
            }


@router.post("/channels/telephony/validate")
async def validate_agent_telephony_channel(
    payload: ValidateTelephonyChannel,
    current_user=Depends(get_current_user_required),
):
    _ = current_user
    if not settings.TELEPHONY_WEBHOOK_BASE_URL.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TELEPHONY_WEBHOOK_BASE_URL не настроен на сервере",
        )
    platform = require_platform_telephony_config()
    try:
        await validate_voximplant_channel_setup(
            account_id=platform.account_id,
            api_key=platform.api_key,
            phone_number_e164=platform.shared_pool_e164,
            application_id=platform.application_id,
            rule_id=platform.rule_id,
        )
    except VoximplantApiError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    ext = (payload.routing_extension or "").strip()
    if ext:
        async with async_session_maker() as session:
            conflict = await scan_extension_conflict_in_db(session, ext)
            if conflict is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Добавочный {ext} уже занят",
                )

    return {
        "ok": True,
        "provider": TELEPHONY_CHANNEL_PROVIDER,
        "phone_number_e164": platform.shared_pool_e164,
        "routing_extension": ext or None,
        "message": "Общий номер Voximplant доступен",
        **platform_telephony_public_fields(),
    }


@router.post("/channels/by_max_userbot")
async def add_agent_max_userbot_channel(
    payload: AddMaxUserbotChannel,
    current_user=Depends(get_current_user_required),
):
    max_token = payload.max_token.strip()
    max_account_id = await _max_userbot_resolve_account_id(max_token)

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            template_type = _normalize_template_type(agent.template_type)
            if template_type == "content_factory":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="MAX userbot недоступен для шаблона Контент-завод",
                )

            existing_max_channel = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == "max_userbot",
                    AgentChannelConnection.connection_type == "userbot",
                )
            )
            if existing_max_channel:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключен MAX userbot-канал",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider="max_userbot",
                external_id=max_account_id,
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот MAX аккаунт уже подключен к другому агенту",
                )

            encrypted_bundle = encrypt_token(
                json.dumps(
                    {
                        "max_token": max_token,
                        "max_account_id": max_account_id,
                    },
                    ensure_ascii=False,
                )
            )

            now = datetime.utcnow()
            created_connection = await channel_connection_dao.add(
                {
                    "agent_id": agent.id,
                    "provider": "max_userbot",
                    "connection_type": "userbot",
                    "external_id": max_account_id,
                    "encrypted_credentials": encrypted_bundle,
                    "is_primary": bool(payload.make_primary),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            await session.flush()
            if payload.make_primary:
                await _set_primary_channel(
                    session=session,
                    agent_id=agent.id,
                    connection_id=created_connection.id,
                )
            await _sync_agent_primary_fields(agent=agent, agent_dao=agent_dao, session=session)
            channels = await _list_agent_channels(session, agent.id)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                },
                status_code=status.HTTP_201_CREATED,
            )


@router.delete("/channels")
async def delete_agent_channel(
    payload: DeleteAgentChannel = Depends(),
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            channel = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.id == payload.connection_id,
                    AgentChannelConnection.agent_id == agent.id,
                )
            )
            if not channel:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Канал подключения не найден")

            channels_before = await _list_agent_channels(session, agent.id)
            if len(channels_before) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Нельзя удалить единственный канал агента. Подключите новый канал сначала.",
                )

            if channel.provider == "telegram_bot" and channel.encrypted_credentials:
                bot_token = decrypt_token(channel.encrypted_credentials)
                try:
                    await _sync_telegram_bot_webhook(bot_token, int(channel.external_id), enabled=False)
                except HTTPException:
                    # Do not block channel deletion if webhook is already detached.
                    pass
            await _terminate_channel_session_if_supported(channel)

            deleting_primary = bool(channel.is_primary)
            await session.delete(channel)
            await session.flush()

            channels_after = await _list_agent_channels(session, agent.id)
            if deleting_primary and channels_after:
                channels_after[0].is_primary = True
                channels_after[0].updated_at = datetime.utcnow()

            await _sync_agent_primary_fields(agent=agent, agent_dao=agent_dao, session=session)
            channels = await _list_agent_channels(session, agent.id)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                },
                status_code=status.HTTP_200_OK,
            )


@router.patch("/by_botID")
async def update_by_bot_id(
    new_data: UpdateAgent,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(new_data)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            if not agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            updates = new_data.model_dump(exclude_none=True)
            updates.pop("bot_id", None)
            updates.pop("agent_id", None)
            if "yookassa_api_key" in updates:
                raw_yookassa_key = str(updates.pop("yookassa_api_key") or "").strip()
                if raw_yookassa_key:
                    if ":" not in raw_yookassa_key:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="yookassa_api_key must be in format shop_id:secret_key",
                        )
                    shop_id_part, secret_part = raw_yookassa_key.split(":", 1)
                    if not shop_id_part.strip() or not secret_part.strip():
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="yookassa_api_key must include both shop_id and secret_key",
                        )
                    updates["encrypted_booking_payment_api_key"] = encrypt_booking_payment_secret(raw_yookassa_key)
                else:
                    updates["encrypted_booking_payment_api_key"] = None
            if "external_webhook_url" in updates:
                updates["external_webhook_url"] = _normalize_external_webhook_url(updates["external_webhook_url"])
            if "template_type" in updates:
                updates["template_type"] = _normalize_template_type(updates["template_type"])
                if "template_config" not in updates:
                    if updates["template_type"] == "crm_admin":
                        updates["template_config"] = _normalize_template_config("crm_admin", None)
                    else:
                        updates["template_config"] = None
            if "template_config" in updates:
                normalized_type = _normalize_template_type(updates.get("template_type") or agent.template_type)
                updates["template_type"] = normalized_type
                updates["template_config"] = _normalize_template_config(
                    normalized_type,
                    updates.get("template_config"),
                )
                if normalized_type == "sales_manager":
                    try:
                        normalized_config = json.loads(updates["template_config"] or "{}")
                    except Exception:
                        normalized_config = {}
                    lead_generation_enabled = bool(normalized_config.get("lead_generation_enabled", True))
                    neuro_commenting_enabled = bool(normalized_config.get("neuro_commenting_enabled", False))
                    live_chat_simulation_enabled = bool(
                        normalized_config.get("live_chat_simulation_enabled", False)
                    )
                    if (
                        not lead_generation_enabled
                        and not neuro_commenting_enabled
                        and not live_chat_simulation_enabled
                    ):
                        updates["is_active"] = False
            await agent_dao.update(agent, updates)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/toggle_status")
async def toggle_status(
    agent_id: Agent_by_botID,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(agent_id)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            from ..services.agent_billing import enforce_expired_maintenance

            await enforce_expired_maintenance(agent_dao, agent)
            new_status = not agent.is_active
            billing_user = await _resolve_billing_user(session, agent, current_user)
            if new_status:
                from ..agent_template_pricing import (
                    PAYMENT_KIND_AGENT_MAINTENANCE,
                    build_agent_billing_state,
                    get_agent_template_pricing,
                    is_activation_paid,
                    is_maintenance_current,
                    user_has_free_agent_activation,
                )

                pricing = get_agent_template_pricing(agent.template_type)
                if (
                    pricing
                    and (
                        pricing.setup_rub_min <= 0
                        or user_has_free_agent_activation(billing_user)
                    )
                    and not is_activation_paid(agent, user=billing_user)
                ):
                    await agent_dao.update(
                        agent,
                        {"activation_paid_at": datetime.now(timezone.utc).replace(tzinfo=None)},
                    )
                    agent = await agent_dao.find_one_by_filter(id=agent.id)
                if pricing and pricing.monthly_maintenance_rub_min > 0 and not is_maintenance_current(agent):
                    billing = build_agent_billing_state(agent, user=billing_user)
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail={
                            "message": "Для активации агента требуется оплата подписки",
                            "billing": billing,
                            "payment_kind": PAYMENT_KIND_AGENT_MAINTENANCE,
                        },
                    )
                if not is_activation_paid(agent, user=billing_user):
                    billing = build_agent_billing_state(agent, user=billing_user)
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail={
                            "message": "Для активации агента требуется оплата",
                            "billing": billing,
                            "payment_kind": "agent_activation",
                        },
                    )
            await agent_dao.update(agent, {"is_active": new_status})

            telegram_channel = await _get_telegram_bot_channel_for_agent(session, agent.id)
            if telegram_channel and telegram_channel.encrypted_credentials:
                agent_token = decrypt_token(telegram_channel.encrypted_credentials)
                try:
                    await _sync_telegram_bot_webhook(
                        agent_token,
                        int(telegram_channel.external_id),
                        enabled=new_status,
                    )
                except HTTPException as exc:
                    if not new_status and exc.status_code == status.HTTP_502_BAD_GATEWAY:
                        # Webhook may already be removed; do not block deactivation.
                        pass
                    else:
                        raise

            channels = await _list_agent_channels(session, agent.id)
            payload = _serialize_agent(
                agent,
                user=billing_user,
                include_external_api_key=True,
                include_encrypted_token=internal,
            )
            payload["channels"] = [_serialize_channel_connection(item) for item in channels]
            return JSONResponse(
                content=payload,
                status_code=status.HTTP_200_OK,
            )


@router.patch("/autopay")
async def update_agent_autopay(
    payload: AgentAutopayUpdateRequest,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            from ..agent_template_pricing import build_agent_billing_state, get_agent_template_pricing

            pricing = get_agent_template_pricing(agent.template_type)
            if not pricing or pricing.monthly_maintenance_rub_min <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Автопродление доступно только для платных агентов",
                )
            if payload.enabled and not getattr(agent, "yookassa_payment_method_id", None):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Сначала оплатите подписку с включённым автопродлением, "
                        "чтобы сохранить способ оплаты"
                    ),
                )
            updates: dict[str, object] = {
                "autopay_enabled": payload.enabled,
                "autopay_last_error": None if payload.enabled else agent.autopay_last_error,
            }
            await agent_dao.update(agent, updates)
            agent = await agent_dao.find_one_by_filter(id=agent.id)
            billing_user = await _resolve_billing_user(session, agent, current_user)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "autopay_enabled": bool(agent.autopay_enabled),
                    "billing": build_agent_billing_state(agent, user=billing_user),
                },
                status_code=status.HTTP_200_OK,
            )


@router.delete("")
async def delete_by_bot_id(
    agent_id: Agent_by_botID = Depends(),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(agent_id)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            vector_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id
            is_deleted_vectors = await delete_agent_vectors(vector_namespace_id)
            if not is_deleted_vectors:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Qdrant deleting error",
                )
            channels = await _list_agent_channels(session, agent.id)
            for channel in channels:
                await _terminate_channel_session_if_supported(channel)
            await agent_dao.delete(agent)
    return Response(status_code=status.HTTP_200_OK)


@router.post("/ai/improve_prompt")
async def ai_improve_prompt(
    payload: AgentAIAction,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )

            try:
                improved_prompt = await improve_prompt_with_ai(agent.system_prompt or "")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Не удалось улучшить системный промпт через ИИ",
                )

            await agent_dao.update(agent, {"system_prompt": improved_prompt})
            return JSONResponse(
                content={"agent_id": agent.id, "bot_id": agent.bot_id, "system_prompt": improved_prompt},
                status_code=status.HTTP_200_OK,
            )


@router.post("/ai/generate_welcome")
async def ai_generate_welcome(
    payload: AgentAIAction,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )

            try:
                welcome_message = await generate_welcome_with_ai(agent.system_prompt or "")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Не удалось сгенерировать приветствие через ИИ",
                )

            await agent_dao.update(agent, {"welcome_message": welcome_message})
            return JSONResponse(
                content={"agent_id": agent.id, "bot_id": agent.bot_id, "welcome_message": welcome_message},
                status_code=status.HTTP_200_OK,
            )


@router.post("/external/regenerate_key")
async def regenerate_external_api_key(
    payload: Agent_by_botID,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            await _regenerate_external_api_key(agent, agent_dao)
            billing_user = await _resolve_billing_user(session, agent, current_user)
            return JSONResponse(
                content=_serialize_agent(
                    agent,
                    user=billing_user,
                    include_external_api_key=True,
                    include_encrypted_token=internal,
                ),
                status_code=status.HTTP_200_OK,
            )


@router.post("/analytics/messages/log")
async def log_analytics_message(
    request: Request,
    payload: AgentAnalyticsMessageLog,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    if internal:
        await verify_internal_signature(request)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            await _log_analytics_message(
                session=session,
                agent=agent,
                role=payload.role,
                message_text=payload.message_text,
                channel=payload.channel,
                user_external_id=payload.user_external_id,
                user_display_name=payload.user_display_name,
                telegram_peer_access_hash=payload.telegram_peer_access_hash,
                tool_name=payload.tool_name,
                tool_args_hash=payload.tool_args_hash,
                tool_status=payload.tool_status,
                latency_ms=payload.latency_ms,
                crm_provider=payload.crm_provider,
            )
    return Response(status_code=status.HTTP_201_CREATED)


@router.get("/analytics/summary")
async def read_analytics_summary(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    if agent_id is None and bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'agent_id' or 'bot_id' is required",
        )
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=agent_id,
                bot_id=bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id

            total_questions = (
                await session.scalar(
                    select(func.count(AgentAnalyticsMessage.id)).where(
                        AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                        AgentAnalyticsMessage.role == "user",
                    )
                )
            ) or 0

            unique_users = (
                await session.scalar(
                    select(func.count(func.distinct(AgentAnalyticsMessage.user_external_id))).where(
                        AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                        AgentAnalyticsMessage.role == "user",
                        AgentAnalyticsMessage.user_external_id.is_not(None),
                    )
                )
            ) or 0

            per_user_rows = (
                (
                    await session.execute(
                        select(
                            AgentAnalyticsMessage.user_external_id.label("uid"),
                            func.min(AgentAnalyticsMessage.created_at).label("first_at"),
                            func.max(AgentAnalyticsMessage.created_at).label("last_at"),
                            func.count(AgentAnalyticsMessage.id).label("questions"),
                        ).where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.role == "user",
                            AgentAnalyticsMessage.user_external_id.is_not(None),
                        ).group_by(AgentAnalyticsMessage.user_external_id)
                    )
                )
                .mappings()
                .all()
            )

            returning_users_over_time = 0
            for row in per_user_rows:
                first_at = row["first_at"]
                last_at = row["last_at"]
                if first_at and last_at and last_at > first_at:
                    returning_users_over_time += 1

            avg_questions_per_user = (float(total_questions) / unique_users) if unique_users > 0 else 0.0
            qualified_leads_share_percent = (
                (float(returning_users_over_time) / unique_users) * 100.0 if unique_users > 0 else 0.0
            )

            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "unique_users": unique_users,
                    "total_questions": total_questions,
                    "returned_over_time_users": returning_users_over_time,
                    "avg_questions_per_user": round(avg_questions_per_user, 2),
                    "qualified_leads_share_percent": round(qualified_leads_share_percent, 2),
                },
                status_code=status.HTTP_200_OK,
            )


@router.get("/analytics/timeseries")
async def read_analytics_timeseries(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    days: int = Query(default=30, ge=7, le=90),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    if agent_id is None and bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'agent_id' or 'bot_id' is required",
        )
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=agent_id,
                bot_id=bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id

            first_seen_rows = (
                (
                    await session.execute(
                        select(
                            AgentAnalyticsMessage.user_external_id.label("uid"),
                            func.min(AgentAnalyticsMessage.created_at).label("first_at"),
                        ).where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.role == "user",
                            AgentAnalyticsMessage.user_external_id.is_not(None),
                        ).group_by(AgentAnalyticsMessage.user_external_id)
                    )
                )
                .mappings()
                .all()
            )

            # Use cast(..., Date) instead of date_trunc('day', ...): with bound parameters,
            # PostgreSQL can reject GROUP BY when SELECT and GROUP BY date_trunc texts differ.
            day_bucket = cast(AgentAnalyticsMessage.created_at, Date).label("day")
            daily_rows = (
                (
                    await session.execute(
                        select(
                            day_bucket,
                            func.count(AgentAnalyticsMessage.id).label("questions_today"),
                            func.count(func.distinct(AgentAnalyticsMessage.user_external_id)).label("users_today"),
                        ).where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.role == "user",
                            AgentAnalyticsMessage.user_external_id.is_not(None),
                        ).group_by(day_bucket)
                    )
                )
                .mappings()
                .all()
            )

            today = datetime.utcnow().date()
            start_day = today - timedelta(days=days - 1)

            daily_activity = {}
            for row in daily_rows:
                day_value = row["day"]
                day_key = day_value.date() if hasattr(day_value, "date") else day_value
                daily_activity[day_key] = {
                    "questions_today": int(row["questions_today"] or 0),
                    "users_today": int(row["users_today"] or 0),
                }

            new_users_by_day = defaultdict(int)
            for row in first_seen_rows:
                first_at = row["first_at"]
                if not first_at:
                    continue
                first_day = first_at.date() if hasattr(first_at, "date") else first_at
                new_users_by_day[first_day] += 1

            timeline = []
            users_all_time = 0
            day_cursor = start_day
            while day_cursor <= today:
                users_all_time += int(new_users_by_day.get(day_cursor, 0))
                current_activity = daily_activity.get(day_cursor, {})
                timeline.append(
                    {
                        "date": day_cursor.isoformat(),
                        "users_all_time": users_all_time,
                        "users_today": int(current_activity.get("users_today", 0)),
                        "new_users": int(new_users_by_day.get(day_cursor, 0)),
                        "questions_today": int(current_activity.get("questions_today", 0)),
                    }
                )
                day_cursor += timedelta(days=1)

            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "days": days,
                    "timeline": timeline,
                },
                status_code=status.HTTP_200_OK,
            )


@router.get("/analytics/crm_actions")
async def read_analytics_crm_actions(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    if agent_id is None and bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'agent_id' or 'bot_id' is required",
        )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=agent_id,
                bot_id=bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id

            tool_calls_total = (
                await session.scalar(
                    select(func.count(AgentAnalyticsMessage.id)).where(
                        AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                        AgentAnalyticsMessage.tool_name.is_not(None),
                        AgentAnalyticsMessage.tool_name != "fallback_to_text",
                    )
                )
            ) or 0
            successful_tool_calls = (
                await session.scalar(
                    select(func.count(AgentAnalyticsMessage.id)).where(
                        AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                        AgentAnalyticsMessage.tool_name.is_not(None),
                        AgentAnalyticsMessage.tool_name != "fallback_to_text",
                        AgentAnalyticsMessage.tool_status == "success",
                    )
                )
            ) or 0
            fallback_to_text_count = (
                await session.scalar(
                    select(func.count(AgentAnalyticsMessage.id)).where(
                        AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                        AgentAnalyticsMessage.tool_name == "fallback_to_text",
                    )
                )
            ) or 0
            total_questions = (
                await session.scalar(
                    select(func.count(AgentAnalyticsMessage.id)).where(
                        AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                        AgentAnalyticsMessage.role == "user",
                    )
                )
            ) or 0

            crm_ops_errors = max(0, int(tool_calls_total) - int(successful_tool_calls))
            success_share_percent = (
                (float(successful_tool_calls) / float(tool_calls_total)) * 100.0
                if tool_calls_total > 0
                else 0.0
            )
            fallback_frequency_percent = (
                (float(fallback_to_text_count) / float(total_questions)) * 100.0
                if total_questions > 0
                else 0.0
            )
            error_rate_percent = (
                (float(crm_ops_errors) / float(tool_calls_total)) * 100.0
                if tool_calls_total > 0
                else 0.0
            )

            # Error budget is calculated against a baseline SLO success rate of 95%.
            target_error_budget_percent = 5.0
            error_budget_used_percent = (
                min(100.0, (error_rate_percent / target_error_budget_percent) * 100.0)
                if tool_calls_total > 0
                else 0.0
            )

            latency_rows = (
                (
                    await session.execute(
                        select(AgentAnalyticsMessage.latency_ms).where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.tool_name.is_not(None),
                            AgentAnalyticsMessage.tool_name != "fallback_to_text",
                            AgentAnalyticsMessage.latency_ms.is_not(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            latencies = sorted(int(value) for value in latency_rows if value is not None and int(value) >= 0)
            avg_latency_ms = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
            if latencies:
                p95_index = max(0, math.ceil(len(latencies) * 0.95) - 1)
                p95_latency_ms = int(latencies[p95_index])
            else:
                p95_latency_ms = 0

            by_tool_rows = (
                (
                    await session.execute(
                        select(
                            AgentAnalyticsMessage.tool_name,
                            func.count(AgentAnalyticsMessage.id).label("count"),
                        )
                        .where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.tool_name.is_not(None),
                            AgentAnalyticsMessage.tool_name != "fallback_to_text",
                        )
                        .group_by(AgentAnalyticsMessage.tool_name)
                        .order_by(func.count(AgentAnalyticsMessage.id).desc())
                    )
                )
                .mappings()
                .all()
            )
            by_status_rows = (
                (
                    await session.execute(
                        select(
                            AgentAnalyticsMessage.tool_status,
                            func.count(AgentAnalyticsMessage.id).label("count"),
                        )
                        .where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.tool_name.is_not(None),
                        )
                        .group_by(AgentAnalyticsMessage.tool_status)
                        .order_by(func.count(AgentAnalyticsMessage.id).desc())
                    )
                )
                .mappings()
                .all()
            )

            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "tool_calls_total": int(tool_calls_total),
                    "successful_tool_calls": int(successful_tool_calls),
                    "crm_ops_errors": int(crm_ops_errors),
                    "success_share_percent": round(success_share_percent, 2),
                    "avg_latency_ms": avg_latency_ms,
                    "p95_latency_ms": p95_latency_ms,
                    "fallback_to_text_count": int(fallback_to_text_count),
                    "fallback_frequency_percent": round(fallback_frequency_percent, 2),
                    "error_budget": {
                        "target_error_budget_percent": target_error_budget_percent,
                        "used_percent": round(error_budget_used_percent, 2),
                        "remaining_percent": round(max(0.0, 100.0 - error_budget_used_percent), 2),
                    },
                    "by_tool": [
                        {"tool_name": row["tool_name"], "count": int(row["count"] or 0)}
                        for row in by_tool_rows
                    ],
                    "by_status": [
                        {"tool_status": row["tool_status"] or "unknown", "count": int(row["count"] or 0)}
                        for row in by_status_rows
                    ],
                },
                status_code=status.HTTP_200_OK,
            )


@router.get("/analytics/telephony/calls")
async def read_analytics_telephony_calls(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    include_turns: bool = Query(default=True),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    if agent_id is None and bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'agent_id' or 'bot_id' is required",
        )
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=agent_id,
                bot_id=bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            calls = await list_agent_telephony_calls(
                session,
                agent_id=int(agent.id),
                limit=limit,
                include_turns=include_turns,
            )
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "calls": calls,
                },
                status_code=status.HTTP_200_OK,
            )


@router.get("/content/jobs")
async def list_content_jobs(
    payload: AgentLookup = Depends(),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            query = select(AgentContentJob).where(AgentContentJob.agent_id == agent.id)
            count_query = select(func.count(AgentContentJob.id)).where(AgentContentJob.agent_id == agent.id)
            normalized_status = str(status_filter or "").strip().lower()
            if normalized_status:
                query = query.where(AgentContentJob.status == normalized_status)
                count_query = count_query.where(AgentContentJob.status == normalized_status)

            total = int((await session.scalar(count_query)) or 0)
            rows = (
                await session.execute(
                    query.order_by(AgentContentJob.created_at.desc(), AgentContentJob.id.desc()).limit(limit).offset(offset)
                )
            ).scalars().all()
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "status_filter": normalized_status or None,
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "items": [_serialize_content_job(item) for item in rows],
                },
                status_code=status.HTTP_200_OK,
            )


@router.get("/content/jobs/metrics")
async def content_jobs_metrics(
    payload: AgentLookup = Depends(),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            total = int(
                (await session.scalar(select(func.count(AgentContentJob.id)).where(AgentContentJob.agent_id == agent.id)))
                or 0
            )
            published = int(
                (
                    await session.scalar(
                        select(func.count(AgentContentJob.id)).where(
                            AgentContentJob.agent_id == agent.id,
                            AgentContentJob.status == "published",
                        )
                    )
                )
                or 0
            )
            failed = int(
                (
                    await session.scalar(
                        select(func.count(AgentContentJob.id)).where(
                            AgentContentJob.agent_id == agent.id,
                            AgentContentJob.status == "failed",
                        )
                    )
                )
                or 0
            )
            retry_jobs = int(
                (
                    await session.scalar(
                        select(func.count(AgentContentJob.id)).where(
                            AgentContentJob.agent_id == agent.id,
                            AgentContentJob.retry_count > 0,
                        )
                    )
                )
                or 0
            )
            latency_rows = (
                await session.execute(
                    select(AgentContentJob.metadata_json).where(
                        AgentContentJob.agent_id == agent.id,
                        AgentContentJob.status.in_(["rendered", "publishing", "published", "failed"]),
                        AgentContentJob.metadata_json.is_not(None),
                    )
                )
            ).scalars().all()

            latencies_seconds: list[float] = []
            for raw_meta in latency_rows:
                meta = _parse_content_job_metadata(raw_meta)
                started_raw = str(meta.get("render_started_at") or "").strip()
                finished_raw = str(meta.get("render_finished_at") or "").strip()
                if not started_raw or not finished_raw:
                    continue
                try:
                    started_dt = datetime.fromisoformat(started_raw)
                    finished_dt = datetime.fromisoformat(finished_raw)
                except Exception:
                    continue
                delta = (finished_dt - started_dt).total_seconds()
                if delta >= 0:
                    latencies_seconds.append(delta)

            avg_render_latency_seconds = (
                round(sum(latencies_seconds) / len(latencies_seconds), 2) if latencies_seconds else 0.0
            )
            retry_rate = (float(retry_jobs) / float(total)) * 100.0 if total > 0 else 0.0
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "jobs_total": total,
                    "jobs_published": published,
                    "jobs_failed": failed,
                    "avg_render_latency_seconds": avg_render_latency_seconds,
                    "retry_rate_percent": round(retry_rate, 2),
                },
                status_code=status.HTTP_200_OK,
            )


@router.get("/content/jobs/{job_id}")
async def content_job_detail(
    job_id: int,
    payload: AgentLookup = Depends(),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            row = await session.scalar(
                select(AgentContentJob).where(
                    AgentContentJob.id == int(job_id),
                    AgentContentJob.agent_id == agent.id,
                )
            )
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content job not found")
            return JSONResponse(content=_serialize_content_job(row), status_code=status.HTTP_200_OK)


@router.get("/analytics/frozen/check")
async def analytics_frozen_check(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    user_external_id: str = Query(..., max_length=128),
    internal: bool = Depends(is_internal_request),
):
    if not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Internal API key required")
    if agent_id is None and bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'agent_id' or 'bot_id' is required",
        )
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            if agent_id is not None:
                agent = await agent_dao.find_one_by_filter(id=agent_id)
            else:
                agent, _ = await _find_agent_by_lookup_id(
                    session=session,
                    agent_dao=agent_dao,
                    lookup_id=bot_id,
                )
            if not agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            uid = user_external_id.strip()
            row_id = await session.scalar(
                select(AgentFrozenUser.id).where(
                    AgentFrozenUser.agent_id == agent.id,
                    AgentFrozenUser.user_external_id == uid,
                )
            )
            return JSONResponse(content={"frozen": bool(row_id)}, status_code=status.HTTP_200_OK)


@router.post("/analytics/frozen")
async def analytics_set_user_frozen(
    payload: AgentFreezeUserPayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            uid = payload.user_external_id.strip()
            if payload.frozen:
                exists = await session.scalar(
                    select(AgentFrozenUser.id).where(
                        AgentFrozenUser.agent_id == agent.id,
                        AgentFrozenUser.user_external_id == uid,
                    )
                )
                if not exists:
                    session.add(
                        AgentFrozenUser(
                            agent_id=agent.id,
                            user_external_id=uid,
                        )
                    )
            else:
                row = await session.scalar(
                    select(AgentFrozenUser).where(
                        AgentFrozenUser.agent_id == agent.id,
                        AgentFrozenUser.user_external_id == uid,
                    )
                )
                if row:
                    await session.delete(row)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/telegram/send_to_user")
async def telegram_send_to_user_as_owner(
    payload: AgentTelegramSendToUserPayload,
    current_user=Depends(get_current_user_required),
):
    try:
        chat_id = int(payload.user_external_id.strip())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный Telegram user id",
        )
    if chat_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный Telegram user id",
        )
    text = payload.message.strip()
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            telegram_channel = await _get_telegram_bot_channel_for_agent(session, agent.id)
            userbot_channel = await _get_telegram_userbot_channel_for_agent(session, agent.id)
            preferred_channel = (payload.preferred_channel or "").strip().lower()
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id
            send_errors: list[str] = []
            delivered = False
            delivered_channel: str | None = None
            if preferred_channel in {"", "telegram"}:
                if telegram_channel and telegram_channel.encrypted_credentials:
                    try:
                        bot_token = decrypt_token(telegram_channel.encrypted_credentials)
                        await _telegram_api_send_message(bot_token, chat_id, text)
                        delivered = True
                        delivered_channel = "telegram"
                    except HTTPException as exc:
                        send_errors.append(str(exc.detail))
                elif preferred_channel == "telegram":
                    send_errors.append("bot-канал не подключен")
            if (not delivered) and preferred_channel in {"", "telegram_userbot"}:
                if userbot_channel and userbot_channel.encrypted_credentials:
                    try:
                        peer_hash = await _latest_telegram_userbot_access_hash(
                            session,
                            analytics_namespace_id=analytics_namespace_id,
                            user_external_id=payload.user_external_id.strip(),
                        )
                        await _telegram_userbot_send_message(
                            userbot_channel.encrypted_credentials,
                            chat_id,
                            text,
                            access_hash=peer_hash,
                        )
                        delivered = True
                        delivered_channel = "telegram_userbot"
                    except HTTPException as exc:
                        send_errors.append(str(exc.detail))
                elif preferred_channel == "telegram_userbot":
                    send_errors.append("userbot-канал не подключен")
            if not delivered:
                joined_errors = "; ".join([err for err in send_errors if err]) or "каналы недоступны"
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Не удалось отправить сообщение через bot/userbot: {joined_errors}",
                )
            await _log_analytics_message(
                session=session,
                agent=agent,
                role="operator",
                message_text=text,
                channel=delivered_channel or "dashboard",
                user_external_id=str(chat_id),
                user_display_name=None,
            )
    return JSONResponse(content={"ok": True}, status_code=status.HTTP_200_OK)


@router.post("/external/send_to_user")
async def external_send_to_user_as_owner(
    payload: AgentExternalApiSendToUserPayload,
    current_user=Depends(get_current_user_required),
):
    user_external_id = payload.user_external_id.strip()
    if not user_external_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_external_id is required",
        )
    text = payload.message.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Сообщение пустое",
        )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            webhook_url = _normalize_external_webhook_url(agent.external_webhook_url)
            if not webhook_url:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="external_webhook_url is not configured for this agent",
                )
            webhook_result = await _send_external_webhook_message(
                webhook_url=webhook_url,
                agent=agent,
                user_external_id=user_external_id,
                message_text=text,
            )
            await _log_analytics_message(
                session=session,
                agent=agent,
                role="operator",
                message_text=text,
                channel="external_api",
                user_external_id=user_external_id,
                user_display_name=None,
            )
    return JSONResponse(content={"ok": True, "webhook_result": webhook_result}, status_code=status.HTTP_200_OK)


@router.get("/telegram/broadcast_recipients")
async def telegram_broadcast_recipients(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    if agent_id is None and bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'agent_id' or 'bot_id' is required",
        )
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=agent_id,
                bot_id=bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id
            recipients = await _list_telegram_broadcast_recipient_ids(session, analytics_namespace_id)
            if not recipients:
                return JSONResponse(
                    content={
                        "agent_id": agent.id,
                        "bot_id": agent.bot_id,
                        "telegram_users_total": 0,
                        "frozen_among_telegram": 0,
                        "eligible_when_skip_frozen": 0,
                    },
                    status_code=status.HTTP_200_OK,
                )
            recipient_ids = [r["user_external_id"] for r in recipients]
            frozen_rows = await session.scalars(
                select(AgentFrozenUser.user_external_id).where(
                    AgentFrozenUser.agent_id == agent.id,
                    AgentFrozenUser.user_external_id.in_(recipient_ids),
                )
            )
            frozen_set = set(frozen_rows.all())
            frozen_among = len([r for r in recipients if r["user_external_id"] in frozen_set])
            eligible = len([r for r in recipients if r["user_external_id"] not in frozen_set])
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "telegram_users_total": len(recipients),
                    "frozen_among_telegram": frozen_among,
                    "eligible_when_skip_frozen": eligible,
                },
                status_code=status.HTTP_200_OK,
            )


@router.post("/telegram/broadcast")
async def telegram_broadcast_as_owner(
    payload: AgentTelegramBroadcastPayload,
    current_user=Depends(get_current_user_required),
):
    text = payload.message.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Сообщение пустое",
        )
    max_n = payload.max_recipients

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id
            recipients = await _list_telegram_broadcast_recipient_ids(session, analytics_namespace_id)
            agent_pk = agent.id
            telegram_bot_id = analytics_namespace_id
            telegram_channel = await _get_telegram_bot_channel_for_agent(session, agent.id)
            userbot_channel = await _get_telegram_userbot_channel_for_agent(session, agent.id)
            bot_token = (
                decrypt_token(telegram_channel.encrypted_credentials)
                if telegram_channel and telegram_channel.encrypted_credentials
                else None
            )
            userbot_bundle = (
                userbot_channel.encrypted_credentials
                if userbot_channel and userbot_channel.encrypted_credentials
                else None
            )
            if not bot_token and not userbot_bundle:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="У агента нет активного Telegram bot/userbot канала для рассылки",
                )

    recipient_ids = [r["user_external_id"] for r in recipients]
    frozen_set: set[str] = set()
    if payload.skip_frozen and recipient_ids:
        async with async_session_maker() as session:
            async with session.begin():
                frozen_rows = await session.scalars(
                    select(AgentFrozenUser.user_external_id).where(
                        AgentFrozenUser.agent_id == agent_pk,
                        AgentFrozenUser.user_external_id.in_(recipient_ids),
                    )
                )
                frozen_set = set(frozen_rows.all())

    skipped_frozen = sum(
        1 for recipient in recipients
        if payload.skip_frozen and recipient["user_external_id"] in frozen_set
    )
    eligible_recipients = [
        recipient
        for recipient in recipients
        if not (payload.skip_frozen and recipient["user_external_id"] in frozen_set)
    ]
    to_send = eligible_recipients[:max_n]
    truncated_over_limit = max(0, len(eligible_recipients) - max_n)

    userbot_uids = [r["user_external_id"] for r in to_send if r["channel"] == "telegram_userbot"]
    userbot_access: dict[str, int] = {}
    if userbot_uids:
        async with async_session_maker() as session:
            async with session.begin():
                userbot_access = await _map_telegram_userbot_access_hashes(
                    session,
                    analytics_namespace_id=telegram_bot_id,
                    user_external_ids=userbot_uids,
                )

    sent = 0
    failed = 0
    errors: list[dict] = []
    throttle_seconds = 0.05

    for recipient in to_send:
        uid = recipient["user_external_id"]
        channel = recipient["channel"]
        chat_id = int(uid)
        try:
            if channel == "telegram":
                if not bot_token:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="bot-канал не подключен",
                    )
                await _telegram_api_send_message(bot_token, chat_id, text)
            elif channel == "telegram_userbot":
                if not userbot_bundle:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="userbot-канал не подключен",
                    )
                peer_hash = userbot_access.get(uid)
                await _telegram_userbot_send_message(
                    userbot_bundle,
                    chat_id,
                    text,
                    access_hash=peer_hash,
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Неподдерживаемый канал рассылки: {channel}",
                )
            sent += 1
            async with async_session_maker() as log_session:
                async with log_session.begin():
                    await _log_analytics_message_for_agent_ids(
                        session=log_session,
                        agent_id=agent_pk,
                        telegram_bot_id=telegram_bot_id,
                        role="operator",
                        message_text=text,
                        channel="dashboard",
                        user_external_id=uid,
                        user_display_name=None,
                    )
        except HTTPException as exc:
            failed += 1
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            if len(errors) < 25:
                errors.append({"user_external_id": uid, "channel": channel, "detail": detail})
        except Exception as exc:
            failed += 1
            if len(errors) < 25:
                errors.append({"user_external_id": uid, "channel": channel, "detail": str(exc)})
        await asyncio.sleep(throttle_seconds)

    return JSONResponse(
        content={
            "ok": True,
            "sent": sent,
            "failed": failed,
            "skipped_frozen": skipped_frozen,
            "truncated_over_limit": truncated_over_limit,
            "attempted": len(to_send),
            "errors": errors,
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/whatsapp_userbot/send_to_user")
async def whatsapp_userbot_send_to_user_as_owner(
    payload: AgentWhatsappUserbotSendToUserPayload,
    current_user=Depends(get_current_user_required),
):
    text = payload.message.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Сообщение пустое",
        )
    to_jid = _whatsapp_user_external_to_jid(payload.user_external_id)
    ext_id = payload.user_external_id.strip()
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            wa_channel = await _get_whatsapp_userbot_channel_for_agent(session, agent.id)
            if not wa_channel:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="У агента нет активного канала WhatsApp userbot",
                )
            connection_id = int(wa_channel.id)
            agent_pk = int(agent.id)
            analytics_namespace_id = int(agent.bot_id if agent.bot_id is not None else agent.id)
            encrypted_credentials = str(wa_channel.encrypted_credentials or "")

    # Убедимся что сессия активна в wa_bridge перед отправкой
    await _ensure_whatsapp_userbot_session(connection_id, encrypted_credentials)

    await _wa_userbot_bridge_post(
        "session/send",
        {
            "connection_id": connection_id,
            "to_jid": to_jid,
            "text": text,
        },
    )

    async with async_session_maker() as log_session:
        async with log_session.begin():
            await _log_analytics_message_for_agent_ids(
                session=log_session,
                agent_id=agent_pk,
                telegram_bot_id=analytics_namespace_id,
                role="operator",
                message_text=text,
                channel="whatsapp_userbot",
                user_external_id=ext_id,
                user_display_name=None,
            )
    return JSONResponse(content={"ok": True}, status_code=status.HTTP_200_OK)


@router.post(
    "/sales_manager/contacts/excel-upload",
    dependencies=[Depends(rate_limit(max_requests=15, window_seconds=60, scope="sales_manager_excel_upload"))],
)
async def sales_manager_contacts_excel_upload(
    background_tasks: BackgroundTasks,
    agent_id: int = Form(..., gt=0),
    file: UploadFile = File(...),
    current_user=Depends(get_current_user_required),
):
    """Загрузка Excel-базы для sales_manager: парсинг, сохранение, фоновый outreach."""
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл")

    from ..services.sales.agent_excel_import import import_agent_contacts_from_excel

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=agent_id,
                bot_id=None,
                session=session,
                current_user=current_user,
                internal=False,
            )
            if agent.template_type != "sales_manager":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Загрузка Excel доступна только для шаблона sales_manager",
                )
            try:
                stats = await import_agent_contacts_from_excel(
                    session,
                    agent_id=int(agent.id),
                    file_bytes=raw,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e

    batch_id = str(stats.get("import_batch_id") or "")
    if batch_id and (int(stats.get("imported") or 0) + int(stats.get("updated") or 0)) > 0:
        background_tasks.add_task(
            _run_sales_manager_excel_outreach,
            agent_id=int(agent.id),
            import_batch_id=batch_id,
        )

    msg_parts = [
        f"Добавлено контактов: {stats.get('imported', 0)}",
        f"обновлено: {stats.get('updated', 0)}",
    ]
    if stats.get("skipped_no_messenger"):
        msg_parts.append(f"без мессенджера/канала: {stats['skipped_no_messenger']}")
    if stats.get("skipped_duplicate"):
        msg_parts.append(f"пропущено (уже в работе): {stats['skipped_duplicate']}")
    msg_parts.append("Рассылка первых сообщений запущена в фоне.")

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            **stats,
            "message": ". ".join(msg_parts),
            "outreach_scheduled": bool(batch_id),
        },
    )


@router.get("/sales_manager/contacts/import-status")
async def sales_manager_contacts_import_status(
    agent_id: int = Query(..., gt=0),
    import_batch_id: str | None = Query(None),
    current_user=Depends(get_current_user_required),
):
    """Статистика импортированных контактов и outreach для sales_manager."""
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=agent_id,
                bot_id=None,
                session=session,
                current_user=current_user,
                internal=False,
            )
            if agent.template_type != "sales_manager":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Доступно только для sales_manager",
                )

            query = select(
                AgentSalesImportedContact.outreach_status,
                func.count(AgentSalesImportedContact.id),
            ).where(AgentSalesImportedContact.agent_id == agent.id)
            if import_batch_id:
                query = query.where(AgentSalesImportedContact.import_batch_id == import_batch_id.strip())
            query = query.group_by(AgentSalesImportedContact.outreach_status)
            rows = (await session.execute(query)).all()
            by_status = {str(status_key): int(cnt) for status_key, cnt in rows}

    return JSONResponse(
        content={
            "agent_id": agent_id,
            "import_batch_id": import_batch_id,
            "by_status": by_status,
            "total": sum(by_status.values()),
        }
    )


@router.post("/max_userbot/send_to_user")
async def max_userbot_send_to_user_as_owner(
    payload: AgentMaxUserbotSendToUserPayload,
    current_user=Depends(get_current_user_required),
):
    text = payload.message.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Сообщение пустое",
        )
    user_external_id = payload.user_external_id.strip()
    if not user_external_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_external_id is required",
        )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            max_channel = await _get_max_userbot_channel_for_agent(session, agent.id)
            if not max_channel:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="У агента нет активного канала MAX userbot",
                )
            encrypted_credentials = str(max_channel.encrypted_credentials or "")

    await _max_userbot_send_message(encrypted_credentials, text)

    async with async_session_maker() as session:
        async with session.begin():
            await _log_analytics_message_for_agent_ids(
                session=session,
                agent_id=agent.id,
                telegram_bot_id=agent.bot_id if agent.bot_id is not None else agent.id,
                role="operator",
                message_text=text,
                channel="dashboard",
                user_external_id=user_external_id,
                user_display_name=None,
            )
    return JSONResponse(content={"ok": True}, status_code=status.HTTP_200_OK)


@router.get("/whatsapp_userbot/broadcast_recipients")
async def whatsapp_userbot_broadcast_recipients(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    if agent_id is None and bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'agent_id' or 'bot_id' is required",
        )
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=agent_id,
                bot_id=bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id
            recipients = await _list_whatsapp_userbot_broadcast_recipients(session, analytics_namespace_id)
            if not recipients:
                return JSONResponse(
                    content={
                        "agent_id": agent.id,
                        "bot_id": agent.bot_id,
                        "whatsapp_userbot_users_total": 0,
                        "frozen_among_whatsapp_userbot": 0,
                        "eligible_when_skip_frozen": 0,
                    },
                    status_code=status.HTTP_200_OK,
                )
            recipient_ids = [r["user_external_id"] for r in recipients]
            frozen_rows = await session.scalars(
                select(AgentFrozenUser.user_external_id).where(
                    AgentFrozenUser.agent_id == agent.id,
                    AgentFrozenUser.user_external_id.in_(recipient_ids),
                )
            )
            frozen_set = set(frozen_rows.all())
            frozen_among = len([r for r in recipients if r["user_external_id"] in frozen_set])
            eligible = len([r for r in recipients if r["user_external_id"] not in frozen_set])
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "whatsapp_userbot_users_total": len(recipients),
                    "frozen_among_whatsapp_userbot": frozen_among,
                    "eligible_when_skip_frozen": eligible,
                },
                status_code=status.HTTP_200_OK,
            )


@router.post("/whatsapp_userbot/broadcast")
async def whatsapp_userbot_broadcast_as_owner(
    payload: AgentWhatsappUserbotBroadcastPayload,
    current_user=Depends(get_current_user_required),
):
    text = payload.message.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Сообщение пустое",
        )
    max_n = payload.max_recipients

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id
            recipients = await _list_whatsapp_userbot_broadcast_recipients(session, analytics_namespace_id)
            agent_pk = agent.id
            telegram_bot_id = analytics_namespace_id
            wa_channel = await _get_whatsapp_userbot_channel_for_agent(session, agent.id)
            if not wa_channel:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="У агента нет активного канала WhatsApp userbot для рассылки",
                )
            connection_id = int(wa_channel.id)
            encrypted_credentials = str(wa_channel.encrypted_credentials or "")

    # Убедимся что сессия активна в wa_bridge перед началом рассылки
    await _ensure_whatsapp_userbot_session(connection_id, encrypted_credentials)

    recipient_ids = [r["user_external_id"] for r in recipients]
    frozen_set: set[str] = set()
    if payload.skip_frozen and recipient_ids:
        async with async_session_maker() as session:
            async with session.begin():
                frozen_rows = await session.scalars(
                    select(AgentFrozenUser.user_external_id).where(
                        AgentFrozenUser.agent_id == agent_pk,
                        AgentFrozenUser.user_external_id.in_(recipient_ids),
                    )
                )
                frozen_set = set(frozen_rows.all())

    skipped_frozen = sum(
        1 for recipient in recipients
        if payload.skip_frozen and recipient["user_external_id"] in frozen_set
    )
    eligible_recipients = [
        recipient
        for recipient in recipients
        if not (payload.skip_frozen and recipient["user_external_id"] in frozen_set)
    ]
    to_send = eligible_recipients[:max_n]
    truncated_over_limit = max(0, len(eligible_recipients) - max_n)

    sent = 0
    failed = 0
    errors: list[dict] = []
    throttle_seconds = 0.35

    for recipient in to_send:
        uid = recipient["user_external_id"]
        channel = recipient["channel"]
        try:
            to_jid = _whatsapp_user_external_to_jid(uid)
            await _wa_userbot_bridge_post(
                "session/send",
                {
                    "connection_id": connection_id,
                    "to_jid": to_jid,
                    "text": text,
                },
            )
            sent += 1
            async with async_session_maker() as log_session:
                async with log_session.begin():
                    await _log_analytics_message_for_agent_ids(
                        session=log_session,
                        agent_id=agent_pk,
                        telegram_bot_id=telegram_bot_id,
                        role="operator",
                        message_text=text,
                        channel="dashboard",
                        user_external_id=uid,
                        user_display_name=None,
                    )
        except HTTPException as exc:
            failed += 1
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            if len(errors) < 25:
                errors.append({"user_external_id": uid, "channel": channel, "detail": detail})
        except Exception as exc:
            failed += 1
            if len(errors) < 25:
                errors.append({"user_external_id": uid, "channel": channel, "detail": str(exc)})
        await asyncio.sleep(throttle_seconds)

    return JSONResponse(
        content={
            "ok": True,
            "sent": sent,
            "failed": failed,
            "skipped_frozen": skipped_frozen,
            "truncated_over_limit": truncated_over_limit,
            "attempted": len(to_send),
            "errors": errors,
        },
        status_code=status.HTTP_200_OK,
    )


@router.get("/analytics/chats")
async def read_analytics_chats(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    limit_users: int = Query(default=100, ge=1, le=500),
    messages_per_user: int = Query(default=50, ge=1, le=200),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    if agent_id is None and bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'agent_id' or 'bot_id' is required",
        )
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=agent_id,
                bot_id=bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id

            supported_chat_channels = [
                "telegram",
                "telegram_userbot",
                "max_bot",
                "max_userbot",
                "whatsapp_userbot",
                "whatsapp_business_api",
                "phone",
                "external_api",
            ]

            user_rows = (
                (
                    await session.execute(
                        select(
                            AgentAnalyticsMessage.user_external_id.label("uid"),
                            AgentAnalyticsMessage.channel.label("channel"),
                            func.max(AgentAnalyticsMessage.user_display_name).label("display_name"),
                            func.count(AgentAnalyticsMessage.id).label("questions"),
                            func.max(AgentAnalyticsMessage.created_at).label("last_message_at"),
                        ).where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.role == "user",
                            AgentAnalyticsMessage.user_external_id.is_not(None),
                            AgentAnalyticsMessage.channel.in_(supported_chat_channels),
                        ).group_by(
                            AgentAnalyticsMessage.user_external_id,
                            AgentAnalyticsMessage.channel,
                        ).order_by(
                            func.max(AgentAnalyticsMessage.created_at).desc()
                        ).limit(limit_users)
                    )
                )
                .mappings()
                .all()
            )

            chat_keys = [
                (row["uid"], row["channel"])
                for row in user_rows
                if row["uid"] and row["channel"] in set(supported_chat_channels)
            ]
            if not chat_keys:
                return JSONResponse(
                    content={"agent_id": agent.id, "bot_id": agent.bot_id, "users": []},
                    status_code=status.HTTP_200_OK,
                )

            user_ids = list({uid for uid, _ in chat_keys})
            frozen_result = await session.scalars(
                select(AgentFrozenUser.user_external_id).where(
                    AgentFrozenUser.agent_id == agent.id,
                    AgentFrozenUser.user_external_id.in_(user_ids),
                )
            )
            frozen_ids = set(frozen_result.all())

            message_rows = (
                (
                    await session.execute(
                        select(
                            AgentAnalyticsMessage.user_external_id,
                            AgentAnalyticsMessage.user_display_name,
                            AgentAnalyticsMessage.role,
                            AgentAnalyticsMessage.channel,
                            AgentAnalyticsMessage.message_text,
                            AgentAnalyticsMessage.created_at,
                        ).where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.user_external_id.in_(user_ids),
                            AgentAnalyticsMessage.channel.in_(
                                [*supported_chat_channels, "dashboard"]
                            ),
                        ).order_by(AgentAnalyticsMessage.created_at.asc())
                    )
                )
                .mappings()
                .all()
            )

            grouped_messages = defaultdict(list)
            for row in message_rows:
                row_channel = row["channel"]
                if row_channel == "dashboard":
                    # Ответы из кабинета показываем в потоке того канала, куда писал пользователь.
                    grouped_messages[(row["user_external_id"], "telegram")].append(row)
                    grouped_messages[(row["user_external_id"], "telegram_userbot")].append(row)
                    grouped_messages[(row["user_external_id"], "max_bot")].append(row)
                    grouped_messages[(row["user_external_id"], "max_userbot")].append(row)
                    grouped_messages[(row["user_external_id"], "whatsapp_userbot")].append(row)
                    grouped_messages[(row["user_external_id"], "external_api")].append(row)
                else:
                    grouped_messages[(row["user_external_id"], row_channel)].append(row)

            users_payload = []
            for row in user_rows:
                uid = row["uid"]
                chat_channel = row["channel"]
                chat_key = f"{chat_channel}:{uid}"
                items = grouped_messages.get((uid, chat_channel), [])
                if messages_per_user > 0 and len(items) > messages_per_user:
                    items = items[-messages_per_user:]

                users_payload.append(
                    {
                        "chat_key": chat_key,
                        "chat_channel": chat_channel,
                        "user_external_id": uid,
                        "user_display_name": row["display_name"] or f"User {uid}",
                        "questions_count": int(row["questions"] or 0),
                        "last_message_at": _safe_iso(row["last_message_at"]),
                        "is_frozen": uid in frozen_ids,
                        "messages": [
                            {
                                "role": item["role"],
                                "channel": item["channel"],
                                "text": item["message_text"],
                                "created_at": _safe_iso(item["created_at"]),
                            }
                            for item in items
                        ],
                    }
                )

            return JSONResponse(
                content={"agent_id": agent.id, "bot_id": agent.bot_id, "users": users_payload},
                status_code=status.HTTP_200_OK,
            )


@router.post("/external/chat")
async def external_chat(
    payload: ExternalAgentChatRequest,
    agent=Depends(get_agent_by_external_api_key),
    _rate_limited=Depends(rate_limit(max_requests=60, window_seconds=60, scope="agents_external_chat")),
):
    if not agent.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent is disabled")
    template_type = str(agent.template_type or "qa").strip().lower()
    if template_type not in WIDGET_ALLOWED_TEMPLATE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="External chat is available only for qa and crm_admin templates",
        )

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message is empty")

    external_user_id = (payload.external_user_id or "").strip() or (payload.chat_id or "").strip() or None
    external_user_name = (payload.external_user_name or "").strip() or None
    if not external_user_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="external_user_id (or chat_id) is required for dashboard chat tracking",
        )

    knowledge_scope_id = agent.bot_id if agent.bot_id is not None else agent.id
    template_config = _decode_template_config(
        agent.template_config,
        template_type=agent.template_type,
    )
    portrait_enabled = bool((template_config or {}).get("enable_chat_portrait", True))
    if template_type == "content_factory":
        portrait_enabled = False

    # Keep parity with channel flows: persist user message before portrait refresh
    # so portrait can use the latest user turn.
    async with async_session_maker() as session:
        async with session.begin():
            await _log_analytics_message(
                session=session,
                agent=agent,
                role="user",
                channel="external_api",
                user_external_id=external_user_id,
                user_display_name=external_user_name,
                message_text=message,
            )
    chat_portrait = ""
    if portrait_enabled:
        chat_portrait = await get_template_runtime().update_chat_portrait(
            agent_id=agent.id,
            analytics_namespace_id=knowledge_scope_id,
            user_external_id=external_user_id,
            source_channel="external_api",
            user_message=message,
            base_prompt=agent.system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT,
            template_config=template_config,
        )

    try:
        execution = await get_template_runtime().execute(
            template_type=agent.template_type,
            prompt=agent.system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT,
            user_message=message,
            knowledge_scope_id=knowledge_scope_id,
            agent_id=agent.id,
            user_external_id=external_user_id,
            template_config=template_config,
            source_channel="external_api",
            chat_portrait=chat_portrait,
        )
        answer = execution.answer
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось получить ответ от LLM",
        )
    sources = execution.sources
    handoff_applied = False
    escalation_type_applied: str | None = None
    if execution.requires_owner_handoff and str(agent.template_type or "qa").strip().lower() == "qa":
        qa_escalation_type = (
            QAEscalationType.FREEZE_CHAT
            if execution.escalation_type == EscalationType.FREEZE_CHAT
            else QAEscalationType.NOTIFY_ONLY
        )
        await get_qa_handoff_service().escalate_to_operator(
            agent_id=agent.id,
            user_external_id=external_user_id,
            user_message=message,
            answer=answer,
            reason=execution.owner_handoff_reason,
            channel="external_api",
            user_display_name=external_user_name,
            escalation_type=qa_escalation_type,
        )
        handoff_applied = True
        escalation_type_applied = qa_escalation_type.value

    async with async_session_maker() as session:
        async with session.begin():
            await _log_analytics_message(
                session=session,
                agent=agent,
                role="agent",
                channel="external_api",
                user_external_id=external_user_id,
                user_display_name=external_user_name,
                message_text=answer,
            )
            for event in execution.tool_events:
                await _log_analytics_message(
                    session=session,
                    agent=agent,
                    role="operator",
                    channel="external_api",
                    user_external_id=external_user_id,
                    user_display_name=external_user_name,
                    message_text=_summarize_tool_event_for_log(event),
                    tool_name=event.get("tool_name"),
                    tool_args_hash=event.get("tool_args_hash"),
                    tool_status=event.get("tool_status"),
                    latency_ms=int(event.get("latency_ms") or 0),
                    crm_provider=event.get("crm_provider"),
                )
            if execution.fallback_to_text:
                await _log_analytics_message(
                    session=session,
                    agent=agent,
                    role="operator",
                    channel="external_api",
                    user_external_id=external_user_id,
                    user_display_name=external_user_name,
                    message_text=execution.fallback_reason or "fallback_to_text",
                    tool_name="fallback_to_text",
                    tool_status="fallback",
                    crm_provider=(
                        _decode_template_config(
                            agent.template_config,
                            template_type=agent.template_type,
                        )
                        or {}
                    ).get("crm_provider"),
                )
            if handoff_applied:
                tool_status = (
                    "chat_frozen" if escalation_type_applied == "freeze_chat" else "operator_notified"
                )
                await _log_analytics_message(
                    session=session,
                    agent=agent,
                    role="operator",
                    channel="external_api",
                    user_external_id=external_user_id,
                    user_display_name=external_user_name,
                    message_text=execution.owner_handoff_reason or "qa_owner_handoff",
                    tool_name="qa_owner_handoff",
                    tool_status=tool_status,
                )

    return JSONResponse(
        content={
            "bot_id": agent.bot_id,
            "bot_username": agent.bot_username,
            "external_user_id": external_user_id,
            "answer": answer,
            "sources": sources,
        },
        status_code=status.HTTP_200_OK,
    )


@router.get("/admin_template/domain-registry")
async def admin_template_domain_registry(
    _current_user=Depends(get_current_user_required),
):
    """Return the full domain registry for the crm_admin template.

    Frontend uses this to populate the domain selector and adapt UI labels.
    """
    items = [cfg.to_dict(key) for key, cfg in _DOMAIN_REGISTRY.items()]
    return JSONResponse(content={"items": items}, status_code=status.HTTP_200_OK)


@router.get("/admin_template/staff")
async def admin_template_staff_list(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    role: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    domain_type: str | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    if agent_id is None and bot_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="agent_id or bot_id is required")
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                agent_id=agent_id,
                bot_id=bot_id,
                domain_type=domain_type,
            )
            items = await get_admin_booking_service().list_staff(
                agent_id=agent.id,
                role=role.strip().lower() if role else None,
                active_only=active_only,
            )
    return JSONResponse(content={"items": items}, status_code=status.HTTP_200_OK)


@router.post("/admin_template/staff")
async def admin_template_staff_create(
    payload: AdminTemplateStaffCreatePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = await get_admin_booking_service().create_staff(
                agent_id=agent.id,
                role=payload.role,
                full_name=payload.full_name,
                specializations=payload.specializations,
                is_active=payload.is_active,
            )
    return JSONResponse(content=row, status_code=status.HTTP_201_CREATED)


@router.patch("/admin_template/staff")
async def admin_template_staff_update(
    payload: AdminTemplateStaffUpdatePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = await get_admin_booking_service().update_staff(
                agent_id=agent.id,
                staff_id=payload.staff_id,
                full_name=payload.full_name,
                specializations=payload.specializations,
                is_active=payload.is_active,
            )
    return JSONResponse(content=row, status_code=status.HTTP_200_OK)


@router.delete("/admin_template/staff")
async def admin_template_staff_delete(
    payload: AdminTemplateStaffDeletePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            await get_admin_booking_service().delete_staff(agent_id=agent.id, staff_id=payload.staff_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin_template/resources")
async def admin_template_resources_list(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    domain_type: str | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    if agent_id is None and bot_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="agent_id or bot_id is required")
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                agent_id=agent_id,
                bot_id=bot_id,
                domain_type=domain_type,
            )
            items = await get_admin_booking_service().list_resources(
                agent_id=agent.id,
                resource_type=resource_type.strip().lower() if resource_type else None,
                active_only=active_only,
            )
    return JSONResponse(content={"items": items}, status_code=status.HTTP_200_OK)


@router.post("/admin_template/resources")
async def admin_template_resources_create(
    payload: AdminTemplateResourceCreatePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = await get_admin_booking_service().create_resource(
                agent_id=agent.id,
                resource_type=payload.resource_type,
                title=payload.title,
                is_active=payload.is_active,
            )
    return JSONResponse(content=row, status_code=status.HTTP_201_CREATED)


@router.patch("/admin_template/resources")
async def admin_template_resources_update(
    payload: AdminTemplateResourceUpdatePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = await get_admin_booking_service().update_resource(
                agent_id=agent.id,
                resource_id=payload.resource_id,
                title=payload.title,
                is_active=payload.is_active,
            )
    return JSONResponse(content=row, status_code=status.HTTP_200_OK)


@router.delete("/admin_template/resources")
async def admin_template_resources_delete(
    payload: AdminTemplateResourceDeletePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            await get_admin_booking_service().delete_resource(agent_id=agent.id, resource_id=payload.resource_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin_template/services")
async def admin_template_services_list(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    target_role: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    domain_type: str | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    if agent_id is None and bot_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="agent_id or bot_id is required")
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                agent_id=agent_id,
                bot_id=bot_id,
                domain_type=domain_type,
            )
            items = await get_admin_booking_service().list_services(
                agent_id=agent.id,
                target_role=target_role.strip().lower() if target_role else None,
                active_only=active_only,
            )
    return JSONResponse(content={"items": items}, status_code=status.HTTP_200_OK)


@router.post("/admin_template/services")
async def admin_template_services_create(
    payload: AdminTemplateServiceCreatePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            try:
                row = await get_admin_booking_service().create_service(
                    agent_id=agent.id,
                    target_role=payload.target_role,
                    staff_id=payload.staff_id,
                    title=payload.title,
                    duration_minutes=payload.duration_minutes,
                    price_minor=payload.price_minor,
                    resource_type_filters=payload.resource_type_filters,
                    is_active=payload.is_active,
                )
            except IntegrityError as exc:
                err = str(exc.orig)
                if "uq_admin_services_agent_title" in err or "admin_services.agent_id" in err:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Услуга с таким названием уже существует для этого агента",
                    ) from exc
                raise
    return JSONResponse(content=row, status_code=status.HTTP_201_CREATED)


@router.patch("/admin_template/services")
async def admin_template_services_update(
    payload: AdminTemplateServiceUpdatePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = await get_admin_booking_service().update_service(
                agent_id=agent.id,
                service_id=payload.service_id,
                staff_id=payload.staff_id,
                title=payload.title,
                duration_minutes=payload.duration_minutes,
                price_minor=payload.price_minor,
                resource_type_filters=payload.resource_type_filters,
                is_active=payload.is_active,
            )
    return JSONResponse(content=row, status_code=status.HTTP_200_OK)


@router.delete("/admin_template/services")
async def admin_template_services_delete(
    payload: AdminTemplateServiceDeletePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            await get_admin_booking_service().delete_service(agent_id=agent.id, service_id=payload.service_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin_template/schedule")
async def admin_template_schedule_list(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    starts_at: str | None = Query(default=None),
    ends_at: str | None = Query(default=None),
    staff_id: int | None = Query(default=None),
    resource_id: int | None = Query(default=None),
    active_only: bool = Query(default=True),
    domain_type: str | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    if agent_id is None and bot_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="agent_id or bot_id is required")
    start_dt = _parse_iso_datetime(starts_at, field_name="starts_at") if starts_at else None
    end_dt = _parse_iso_datetime(ends_at, field_name="ends_at") if ends_at else None
    if start_dt and end_dt and end_dt <= start_dt:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ends_at must be greater than starts_at")

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                agent_id=agent_id,
                bot_id=bot_id,
                domain_type=domain_type,
            )
            conditions = [AdminScheduleSlot.agent_id == agent.id]
            if active_only:
                conditions.append(AdminScheduleSlot.is_active.is_(True))
            if staff_id is not None:
                conditions.append(AdminScheduleSlot.staff_id == staff_id)
            if resource_id is not None:
                conditions.append(AdminScheduleSlot.resource_id == resource_id)
            if start_dt is not None:
                conditions.append(AdminScheduleSlot.ends_at > start_dt)
            if end_dt is not None:
                conditions.append(AdminScheduleSlot.starts_at < end_dt)
            rows = (
                await session.execute(
                    select(AdminScheduleSlot)
                    .where(*conditions)
                    .order_by(AdminScheduleSlot.starts_at.asc(), AdminScheduleSlot.id.asc())
                )
            ).scalars().all()
    return JSONResponse(content={"items": [_serialize_admin_schedule_slot_row(row) for row in rows]}, status_code=status.HTTP_200_OK)


@router.get("/admin_template/schedule/available")
async def admin_template_schedule_available(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    starts_at: str = Query(...),
    ends_at: str = Query(...),
    staff_id: int | None = Query(default=None),
    resource_id: int | None = Query(default=None),
    service_id: int | None = Query(default=None),
    domain_type: str | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    if agent_id is None and bot_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="agent_id or bot_id is required")
    start_dt = _parse_iso_datetime(starts_at, field_name="starts_at")
    end_dt = _parse_iso_datetime(ends_at, field_name="ends_at")
    if end_dt <= start_dt:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ends_at must be greater than starts_at")

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                agent_id=agent_id,
                bot_id=bot_id,
                domain_type=domain_type,
            )
            items = await get_admin_booking_service().list_available_slots(
                agent_id=agent.id,
                starts_at=start_dt,
                ends_at=end_dt,
                staff_id=staff_id,
                resource_id=resource_id,
                service_id=service_id,
            )
    return JSONResponse(content={"items": items}, status_code=status.HTTP_200_OK)


@router.post("/admin_template/schedule")
async def admin_template_schedule_create(
    payload: AdminTemplateScheduleCreatePayload,
    current_user=Depends(get_current_user_required),
):
    start_dt = _parse_iso_datetime(payload.starts_at, field_name="starts_at")
    end_dt = _parse_iso_datetime(payload.ends_at, field_name="ends_at")
    if end_dt <= start_dt:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ends_at must be greater than starts_at")
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = await get_admin_booking_service().create_schedule_slot(
                agent_id=agent.id,
                starts_at=start_dt,
                ends_at=end_dt,
                staff_id=payload.staff_id,
                resource_id=payload.resource_id,
                slot_kind=payload.slot_kind,
                is_active=payload.is_active,
            )
    return JSONResponse(content=row, status_code=status.HTTP_201_CREATED)


@router.delete("/admin_template/schedule")
async def admin_template_schedule_delete(
    payload: AdminTemplateScheduleDeletePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = await session.scalar(
                select(AdminScheduleSlot).where(
                    AdminScheduleSlot.id == payload.schedule_slot_id,
                    AdminScheduleSlot.agent_id == agent.id,
                )
            )
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule slot not found")
            await session.delete(row)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin_template/appointments")
async def admin_template_appointments_list(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    starts_at: str | None = Query(default=None),
    ends_at: str | None = Query(default=None),
    staff_id: int | None = Query(default=None),
    resource_id: int | None = Query(default=None),
    service_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    domain_type: str | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    if agent_id is None and bot_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="agent_id or bot_id is required")
    start_dt = _parse_iso_datetime(starts_at, field_name="starts_at") if starts_at else None
    end_dt = _parse_iso_datetime(ends_at, field_name="ends_at") if ends_at else None
    if start_dt and end_dt and end_dt <= start_dt:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ends_at must be greater than starts_at")

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                agent_id=agent_id,
                bot_id=bot_id,
                domain_type=domain_type,
            )
            conditions = [AdminAppointment.agent_id == agent.id]
            if staff_id is not None:
                conditions.append(AdminAppointment.staff_id == staff_id)
            if resource_id is not None:
                conditions.append(AdminAppointment.resource_id == resource_id)
            if service_id is not None:
                conditions.append(AdminAppointment.service_id == service_id)
            if status_filter:
                conditions.append(AdminAppointment.status == status_filter.strip().lower())
            if start_dt is not None:
                conditions.append(AdminAppointment.ends_at > start_dt)
            if end_dt is not None:
                conditions.append(AdminAppointment.starts_at < end_dt)
            rows = (
                await session.execute(
                    select(AdminAppointment)
                    .where(*conditions)
                    .order_by(AdminAppointment.starts_at.asc(), AdminAppointment.id.asc())
                )
            ).scalars().all()
    return JSONResponse(content={"items": [_serialize_admin_appointment_row(row) for row in rows]}, status_code=status.HTTP_200_OK)


@router.post("/admin_template/appointments")
async def admin_template_appointments_create(
    payload: AdminTemplateAppointmentCreatePayload,
    current_user=Depends(get_current_user_required),
):
    start_dt = _parse_iso_datetime(payload.starts_at, field_name="starts_at")
    end_dt = _parse_iso_datetime(payload.ends_at, field_name="ends_at")
    if end_dt <= start_dt:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ends_at must be greater than starts_at")
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = await get_admin_booking_service().create_appointment(
                agent_id=agent.id,
                client_external_id=payload.client_external_id,
                starts_at=start_dt,
                ends_at=end_dt,
                staff_id=payload.staff_id,
                resource_id=payload.resource_id,
                service_id=payload.service_id,
                client_name=payload.client_name,
                source_channel=payload.source_channel,
                notes=payload.notes,
            )
    return JSONResponse(content=row, status_code=status.HTTP_201_CREATED)


@router.patch("/admin_template/appointments/reschedule")
async def admin_template_appointments_reschedule(
    payload: AdminTemplateAppointmentReschedulePayload,
    current_user=Depends(get_current_user_required),
):
    start_dt = _parse_iso_datetime(payload.starts_at, field_name="starts_at")
    end_dt = _parse_iso_datetime(payload.ends_at, field_name="ends_at")
    if end_dt <= start_dt:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ends_at must be greater than starts_at")
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = await get_admin_booking_service().reschedule_appointment(
                agent_id=agent.id,
                appointment_id=payload.appointment_id,
                starts_at=start_dt,
                ends_at=end_dt,
                staff_id=payload.staff_id,
                resource_id=payload.resource_id,
            )
    return JSONResponse(content=row, status_code=status.HTTP_200_OK)


@router.patch("/admin_template/appointments/cancel")
async def admin_template_appointments_cancel(
    payload: AdminTemplateAppointmentCancelPayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = await get_admin_booking_service().cancel_appointment(
                agent_id=agent.id,
                appointment_id=payload.appointment_id,
                reason=payload.reason,
            )
    return JSONResponse(content=row, status_code=status.HTTP_200_OK)


@router.get("/admin_template/refund_requests")
async def admin_template_refund_requests_list(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    domain_type: str | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    if agent_id is None and bot_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="agent_id or bot_id is required")
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                agent_id=agent_id,
                bot_id=bot_id,
                domain_type=domain_type,
            )
            items = await get_admin_booking_payment_service().list_refund_requests(
                agent_id=agent.id,
                status=status_filter,
            )
    return JSONResponse(content={"items": items}, status_code=status.HTTP_200_OK)


@router.post("/admin_template/refund_requests/approve")
async def admin_template_refund_requests_approve(
    payload: AdminTemplateRefundRequestActionPayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            try:
                item = await get_admin_booking_payment_service().approve_refund_request(
                    agent_id=agent.id,
                    refund_request_id=payload.refund_request_id,
                    reviewed_by_user_id=current_user.id,
                )
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
            except RuntimeError as exc:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return JSONResponse(content=item, status_code=status.HTTP_200_OK)


@router.post("/admin_template/refund_requests/reject")
async def admin_template_refund_requests_reject(
    payload: AdminTemplateRefundRequestActionPayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            try:
                item = await get_admin_booking_payment_service().reject_refund_request(
                    agent_id=agent.id,
                    refund_request_id=payload.refund_request_id,
                    reviewed_by_user_id=current_user.id,
                    reason=payload.reason,
                )
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return JSONResponse(content=item, status_code=status.HTTP_200_OK)


@router.patch("/admin_template/appointments/confirm")
async def admin_template_appointments_confirm(
    payload: AdminTemplateAppointmentConfirmPayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = await get_admin_booking_service().confirm_appointment(
                agent_id=agent.id,
                appointment_id=payload.appointment_id,
            )
    return JSONResponse(content=row, status_code=status.HTTP_200_OK)


@router.delete("/admin_template/appointments")
async def admin_template_appointments_delete(
    payload: AdminTemplateAppointmentDeletePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            await get_admin_booking_service().delete_appointment(
                agent_id=agent.id,
                appointment_id=payload.appointment_id,
                reason=payload.reason,
            )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin_template/waitlist")
async def admin_template_waitlist_list(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, cfg = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                agent_id=agent_id,
                bot_id=bot_id,
            )
            if not bool(cfg.get("waitlist_enabled", True)):
                return JSONResponse(content={"items": []}, status_code=status.HTTP_200_OK)
            conditions = [AdminWaitlistEntry.agent_id == agent.id]
            if status_filter:
                conditions.append(AdminWaitlistEntry.status == status_filter.strip().lower())
            rows = (
                await session.execute(
                    select(AdminWaitlistEntry)
                    .where(*conditions)
                    .order_by(AdminWaitlistEntry.created_at.desc())
                )
            ).scalars().all()
    return JSONResponse(content={"items": [_serialize_admin_waitlist_row(row) for row in rows]}, status_code=status.HTTP_200_OK)


@router.post("/admin_template/waitlist")
async def admin_template_waitlist_create(
    payload: AdminTemplateWaitlistCreatePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, cfg = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            if not bool(cfg.get("waitlist_enabled", True)):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Waitlist is disabled")
            row = AdminWaitlistEntry(
                agent_id=agent.id,
                client_external_id=payload.client_external_id.strip(),
                client_name=(payload.client_name or "").strip() or None,
                service_id=payload.service_id,
                desired_staff_id=payload.desired_staff_id,
                desired_resource_id=payload.desired_resource_id,
                earliest_starts_at=_parse_iso_datetime(payload.earliest_starts_at, field_name="earliest_starts_at")
                if payload.earliest_starts_at
                else None,
                latest_ends_at=_parse_iso_datetime(payload.latest_ends_at, field_name="latest_ends_at")
                if payload.latest_ends_at
                else None,
                notes=(payload.notes or "").strip() or None,
                status="waiting",
            )
            session.add(row)
            await session.flush()
            await session.refresh(row)
    return JSONResponse(content=_serialize_admin_waitlist_row(row), status_code=status.HTTP_201_CREATED)


@router.patch("/admin_template/waitlist")
async def admin_template_waitlist_update(
    payload: AdminTemplateWaitlistUpdatePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = await session.scalar(
                select(AdminWaitlistEntry).where(
                    AdminWaitlistEntry.id == payload.waitlist_id,
                    AdminWaitlistEntry.agent_id == agent.id,
                )
            )
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found")
            if payload.status is not None:
                row.status = payload.status.strip().lower()
            if payload.notes is not None:
                row.notes = payload.notes.strip() or None
            await session.flush()
            await session.refresh(row)
    return JSONResponse(content=_serialize_admin_waitlist_row(row), status_code=status.HTTP_200_OK)


@router.delete("/admin_template/waitlist")
async def admin_template_waitlist_delete(
    payload: AdminTemplateWaitlistDeletePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = await session.scalar(
                select(AdminWaitlistEntry).where(
                    AdminWaitlistEntry.id == payload.waitlist_id,
                    AdminWaitlistEntry.agent_id == agent.id,
                )
            )
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found")
            await session.delete(row)
    return JSONResponse(content={"ok": True}, status_code=status.HTTP_200_OK)


@router.get("/admin_template/client_profiles")
async def admin_template_client_profiles_list(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    client_external_id: str | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                agent_id=agent_id,
                bot_id=bot_id,
            )
            conditions = [AdminClientProfile.agent_id == agent.id]
            if client_external_id:
                conditions.append(AdminClientProfile.client_external_id == client_external_id.strip())
            rows = (
                await session.execute(
                    select(AdminClientProfile)
                    .where(*conditions)
                    .order_by(AdminClientProfile.updated_at.desc())
                )
            ).scalars().all()
    return JSONResponse(
        content={"items": [_serialize_admin_client_profile_row(row) for row in rows]},
        status_code=status.HTTP_200_OK,
    )


@router.patch("/admin_template/client_profiles")
async def admin_template_client_profiles_update(
    payload: AdminTemplateClientProfileUpdatePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            client_key = payload.client_external_id.strip()
            row = await session.scalar(
                select(AdminClientProfile).where(
                    AdminClientProfile.agent_id == agent.id,
                    AdminClientProfile.client_external_id == client_key,
                )
            )
            if row is None:
                row = AdminClientProfile(
                    agent_id=agent.id,
                    client_external_id=client_key,
                    client_name=(payload.client_name or "").strip() or None,
                    tags_json=_safe_json_dump(payload.tags or []),
                    preferences_json=_safe_json_dump(payload.preferences or {}),
                    history_json=None,
                )
                session.add(row)
                await session.flush()
            else:
                if payload.client_name is not None:
                    row.client_name = payload.client_name.strip() or None
                if payload.tags is not None:
                    normalized_tags = [str(item).strip() for item in payload.tags if str(item).strip()]
                    row.tags_json = _safe_json_dump(normalized_tags)
                if payload.preferences is not None:
                    row.preferences_json = _safe_json_dump(payload.preferences)
            if payload.history_note:
                existing_history = _parse_json_list(row.history_json)
                existing_history.append(
                    json.dumps(
                        {
                            "ts": datetime.utcnow().isoformat(),
                            "note": payload.history_note.strip(),
                        },
                        ensure_ascii=False,
                    )
                )
                row.history_json = _safe_json_dump(existing_history[-100:])
            await session.flush()
            await session.refresh(row)
    return JSONResponse(content=_serialize_admin_client_profile_row(row), status_code=status.HTTP_200_OK)


@router.get("/admin_template/quick_replies")
async def admin_template_quick_replies_list(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    active_only: bool = Query(default=True),
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                agent_id=agent_id,
                bot_id=bot_id,
            )
            conditions = [AdminQuickReplyTemplate.agent_id == agent.id]
            if active_only:
                conditions.append(AdminQuickReplyTemplate.is_active.is_(True))
            rows = (
                await session.execute(
                    select(AdminQuickReplyTemplate)
                    .where(*conditions)
                    .order_by(AdminQuickReplyTemplate.created_at.desc())
                )
            ).scalars().all()
    return JSONResponse(content={"items": [_serialize_admin_quick_reply_row(row) for row in rows]}, status_code=status.HTTP_200_OK)


@router.post("/admin_template/quick_replies")
async def admin_template_quick_replies_create(
    payload: AdminTemplateQuickReplyCreatePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = AdminQuickReplyTemplate(
                agent_id=agent.id,
                title=payload.title.strip(),
                body=payload.body.strip(),
                category=(payload.category or "").strip() or None,
                is_active=bool(payload.is_active),
            )
            session.add(row)
            await session.flush()
            await session.refresh(row)
    return JSONResponse(content=_serialize_admin_quick_reply_row(row), status_code=status.HTTP_201_CREATED)


@router.patch("/admin_template/quick_replies")
async def admin_template_quick_replies_update(
    payload: AdminTemplateQuickReplyUpdatePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = await session.scalar(
                select(AdminQuickReplyTemplate).where(
                    AdminQuickReplyTemplate.id == payload.quick_reply_id,
                    AdminQuickReplyTemplate.agent_id == agent.id,
                )
            )
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quick reply not found")
            if payload.title is not None:
                row.title = payload.title.strip()
            if payload.body is not None:
                row.body = payload.body.strip()
            if payload.category is not None:
                row.category = payload.category.strip() or None
            if payload.is_active is not None:
                row.is_active = bool(payload.is_active)
            await session.flush()
            await session.refresh(row)
    return JSONResponse(content=_serialize_admin_quick_reply_row(row), status_code=status.HTTP_200_OK)


@router.delete("/admin_template/quick_replies")
async def admin_template_quick_replies_delete(
    payload: AdminTemplateQuickReplyDeletePayload,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, _ = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            row = await session.scalar(
                select(AdminQuickReplyTemplate).where(
                    AdminQuickReplyTemplate.id == payload.quick_reply_id,
                    AdminQuickReplyTemplate.agent_id == agent.id,
                )
            )
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quick reply not found")
            await session.delete(row)
    return JSONResponse(content={"ok": True}, status_code=status.HTTP_200_OK)


@router.post("/admin_template/reminders/run")
async def admin_template_reminders_run(
    payload: AdminTemplateRemindersRunPayload,
    current_user=Depends(get_current_user_required),
):
    now_dt = _parse_iso_datetime(payload.now_iso, field_name="now_iso") if payload.now_iso else datetime.utcnow()
    channel = (payload.channel or "").strip().lower() or "system"
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, cfg = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                payload=payload,
            )
            if not bool(cfg.get("reminder_enabled", True)):
                return JSONResponse(content={"sent": 0, "items": []}, status_code=status.HTTP_200_OK)
            offsets_raw = cfg.get("reminder_offsets_hours") or [24, 2]
            offsets = []
            for item in offsets_raw if isinstance(offsets_raw, list) else [24, 2]:
                try:
                    hour = int(item)
                except Exception:
                    continue
                if 1 <= hour <= 72 and hour not in offsets:
                    offsets.append(hour)
            if not offsets:
                offsets = [24, 2]
            max_offset = max(offsets)
            appointments = (
                await session.execute(
                    select(AdminAppointment).where(
                        AdminAppointment.agent_id == agent.id,
                        AdminAppointment.status.in_(["pending_confirmation", "booked", "confirmed"]),
                        AdminAppointment.starts_at >= now_dt,
                        AdminAppointment.starts_at <= now_dt + timedelta(hours=max_offset, minutes=30),
                    )
                )
            ).scalars().all()
            sent_items = []
            for row in appointments:
                minutes_to_start = int((row.starts_at - now_dt).total_seconds() // 60)
                for offset in offsets:
                    offset_minutes = offset * 60
                    reminder_type = f"t{offset}h"
                    if not (offset_minutes - 30 <= minutes_to_start <= offset_minutes):
                        continue
                    existing = await session.scalar(
                        select(AdminAppointmentReminderLog.id).where(
                            AdminAppointmentReminderLog.appointment_id == row.id,
                            AdminAppointmentReminderLog.reminder_type == reminder_type,
                        )
                    )
                    if existing is not None:
                        continue
                    log_row = AdminAppointmentReminderLog(
                        agent_id=agent.id,
                        appointment_id=row.id,
                        reminder_type=reminder_type,
                        channel=channel,
                        status="sent",
                        sent_at=now_dt,
                        payload_json=_safe_json_dump(
                            {
                                "appointment_id": row.id,
                                "starts_at": _safe_iso(row.starts_at),
                                "client_external_id": row.client_external_id,
                            }
                        ),
                    )
                    session.add(log_row)
                    sent_items.append(
                        {
                            "appointment_id": row.id,
                            "reminder_type": reminder_type,
                            "client_external_id": row.client_external_id,
                            "starts_at": _safe_iso(row.starts_at),
                        }
                    )
    return JSONResponse(content={"sent": len(sent_items), "items": sent_items}, status_code=status.HTTP_200_OK)


@router.get("/admin_template/occupancy")
async def admin_template_occupancy(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    starts_at: str = Query(...),
    ends_at: str = Query(...),
    domain_type: str | None = Query(default=None),
    staff_id: int | None = Query(default=None),
    service_id: int | None = Query(default=None),
    resource_id: int | None = Query(default=None),
    granularity_minutes: int = Query(default=30, ge=5, le=120),
    current_user=Depends(get_current_user_required),
):
    if agent_id is None and bot_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="agent_id or bot_id is required")
    start_dt = _parse_iso_datetime(starts_at, field_name="starts_at")
    end_dt = _parse_iso_datetime(ends_at, field_name="ends_at")
    if end_dt <= start_dt:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ends_at must be greater than starts_at")
    if (end_dt - start_dt) > timedelta(days=31):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Time range is too large, maximum 31 days",
        )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent, cfg = await _find_admin_template_agent(
                session=session,
                agent_dao=agent_dao,
                current_user=current_user,
                agent_id=agent_id,
                bot_id=bot_id,
                domain_type=domain_type,
            )

            appointment_conditions = [
                AdminAppointment.agent_id == agent.id,
                AdminAppointment.status != "cancelled",
                AdminAppointment.starts_at < end_dt,
                AdminAppointment.ends_at > start_dt,
            ]
            if staff_id is not None:
                appointment_conditions.append(AdminAppointment.staff_id == staff_id)
            if service_id is not None:
                appointment_conditions.append(AdminAppointment.service_id == service_id)
            if resource_id is not None:
                appointment_conditions.append(AdminAppointment.resource_id == resource_id)

            appointments = (
                await session.execute(
                    select(AdminAppointment)
                    .where(*appointment_conditions)
                    .order_by(AdminAppointment.starts_at.asc())
                )
            ).scalars().all()

            resource_conditions = [AdminResource.agent_id == agent.id, AdminResource.is_active.is_(True)]
            if resource_id is not None:
                resource_conditions.append(AdminResource.id == resource_id)
            resources = (
                await session.execute(
                    select(AdminResource).where(*resource_conditions).order_by(AdminResource.id.asc())
                )
            ).scalars().all()
            staff_conditions = [AdminStaff.agent_id == agent.id, AdminStaff.is_active.is_(True)]
            if staff_id is not None:
                staff_conditions.append(AdminStaff.id == staff_id)
            staff_rows = (
                await session.execute(
                    select(AdminStaff).where(*staff_conditions).order_by(AdminStaff.id.asc())
                )
            ).scalars().all()
            service_conditions = [AdminService.agent_id == agent.id, AdminService.is_active.is_(True)]
            if service_id is not None:
                service_conditions.append(AdminService.id == service_id)
            service_rows = (
                await session.execute(
                    select(AdminService).where(*service_conditions).order_by(AdminService.id.asc())
                )
            ).scalars().all()
            schedule_conditions = [
                AdminScheduleSlot.agent_id == agent.id,
                AdminScheduleSlot.is_active.is_(True),
                AdminScheduleSlot.starts_at < end_dt,
                AdminScheduleSlot.ends_at > start_dt,
            ]
            if staff_id is not None:
                schedule_conditions.append(AdminScheduleSlot.staff_id == staff_id)
            if resource_id is not None:
                schedule_conditions.append(AdminScheduleSlot.resource_id == resource_id)
            schedule_rows = (
                await session.execute(
                    select(AdminScheduleSlot)
                    .where(*schedule_conditions)
                    .order_by(AdminScheduleSlot.starts_at.asc())
                )
            ).scalars().all()

    def _minutes_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> int:
        start = max(a_start, b_start)
        end = min(a_end, b_end)
        return max(0, int((end - start).total_seconds() // 60))

    staff_labels = {int(row.id): str(row.full_name or f"staff#{row.id}") for row in staff_rows}
    resource_labels = {int(row.id): str(row.title or f"resource#{row.id}") for row in resources}
    service_labels = {int(row.id): str(row.title or f"service#{row.id}") for row in service_rows}

    day_stats: dict[str, dict] = {}
    week_stats: dict[str, dict] = {}
    by_staff_stats: dict[int, dict] = {}
    by_resource_stats: dict[int, dict] = {}
    by_service_stats: dict[int, dict] = {}
    hour_stats: dict[int, dict] = {}
    unique_clients = set()
    total_occupied_minutes = 0

    for row in appointments:
        overlap_minutes = _minutes_overlap(start_dt, end_dt, row.starts_at, row.ends_at)
        if overlap_minutes <= 0:
            continue
        total_occupied_minutes += overlap_minutes
        unique_clients.add(row.client_external_id)

        overlap_start = max(start_dt, row.starts_at)
        day_key = overlap_start.date().isoformat()
        day_entry = day_stats.setdefault(day_key, {"appointments": 0, "occupied_minutes": 0, "unique_clients": set()})
        day_entry["appointments"] += 1
        day_entry["occupied_minutes"] += overlap_minutes
        day_entry["unique_clients"].add(row.client_external_id)

        iso_year, iso_week, _ = overlap_start.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        week_entry = week_stats.setdefault(
            week_key,
            {"appointments": 0, "occupied_minutes": 0, "unique_clients": set()},
        )
        week_entry["appointments"] += 1
        week_entry["occupied_minutes"] += overlap_minutes
        week_entry["unique_clients"].add(row.client_external_id)

        if row.staff_id is not None:
            item = by_staff_stats.setdefault(
                int(row.staff_id),
                {"appointments": 0, "occupied_minutes": 0, "appointment_ids": set()},
            )
            item["appointments"] += 1
            item["occupied_minutes"] += overlap_minutes
            item["appointment_ids"].add(int(row.id))
        if row.resource_id is not None:
            item = by_resource_stats.setdefault(
                int(row.resource_id),
                {"appointments": 0, "occupied_minutes": 0, "appointment_ids": set()},
            )
            item["appointments"] += 1
            item["occupied_minutes"] += overlap_minutes
            item["appointment_ids"].add(int(row.id))
        if row.service_id is not None:
            item = by_service_stats.setdefault(
                int(row.service_id),
                {"appointments": 0, "occupied_minutes": 0, "appointment_ids": set()},
            )
            item["appointments"] += 1
            item["occupied_minutes"] += overlap_minutes
            item["appointment_ids"].add(int(row.id))

        # distribute occupied time by hour for peak-hours KPI
        cursor_hour = overlap_start
        overlap_end = min(end_dt, row.ends_at)
        while cursor_hour < overlap_end:
            hour_end = min(
                overlap_end,
                cursor_hour.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1),
            )
            hour_key = int(cursor_hour.hour)
            minutes = max(0, int((hour_end - cursor_hour).total_seconds() // 60))
            if minutes > 0:
                hour_entry = hour_stats.setdefault(hour_key, {"occupied_minutes": 0, "appointment_ids": set()})
                hour_entry["occupied_minutes"] += minutes
                hour_entry["appointment_ids"].add(int(row.id))
            cursor_hour = hour_end

    buckets: list[tuple[datetime, datetime]] = []
    cursor = start_dt
    step = timedelta(minutes=granularity_minutes)
    while cursor < end_dt:
        bucket_end = min(end_dt, cursor + step)
        buckets.append((cursor, bucket_end))
        cursor = bucket_end

    appointments_by_resource: dict[int, list[AdminAppointment]] = {}
    for row in appointments:
        if row.resource_id is None:
            continue
        appointments_by_resource.setdefault(row.resource_id, []).append(row)

    occupancy_matrix: list[dict] = []
    for resource in resources:
        rows = appointments_by_resource.get(resource.id, [])
        cells: list[dict] = []
        for bucket_start, bucket_end in buckets:
            overlap_count = 0
            for item in rows:
                if item.starts_at < bucket_end and item.ends_at > bucket_start:
                    overlap_count += 1
            cells.append(
                {
                    "starts_at": _safe_iso(bucket_start),
                    "ends_at": _safe_iso(bucket_end),
                    "occupied": overlap_count > 0,
                    "appointments_count": overlap_count,
                }
            )
        occupancy_matrix.append(
            {
                "resource_id": resource.id,
                "resource_title": resource.title,
                "resource_type": resource.resource_type,
                "cells": cells,
            }
        )

    total_schedulable_minutes = 0
    schedulable_staff_minutes: dict[int, int] = {}
    schedulable_resource_minutes: dict[int, int] = {}
    schedule_gaps: list[dict] = []
    for slot in schedule_rows:
        slot_minutes = _minutes_overlap(start_dt, end_dt, slot.starts_at, slot.ends_at)
        if slot_minutes <= 0:
            continue
        total_schedulable_minutes += slot_minutes
        if slot.staff_id is not None:
            key = int(slot.staff_id)
            schedulable_staff_minutes[key] = int(schedulable_staff_minutes.get(key) or 0) + slot_minutes
        if slot.resource_id is not None:
            key = int(slot.resource_id)
            schedulable_resource_minutes[key] = int(schedulable_resource_minutes.get(key) or 0) + slot_minutes

        slot_start = max(start_dt, slot.starts_at)
        slot_end = min(end_dt, slot.ends_at)
        matching_appointments: list[tuple[datetime, datetime]] = []
        for row in appointments:
            if row.starts_at >= slot_end or row.ends_at <= slot_start:
                continue
            if slot.staff_id is not None and row.staff_id != slot.staff_id:
                continue
            if slot.resource_id is not None and row.resource_id != slot.resource_id:
                continue
            busy_start = max(slot_start, row.starts_at)
            busy_end = min(slot_end, row.ends_at)
            if busy_end > busy_start:
                matching_appointments.append((busy_start, busy_end))
        matching_appointments.sort(key=lambda item: item[0])
        merged_busy: list[tuple[datetime, datetime]] = []
        for busy_start, busy_end in matching_appointments:
            if not merged_busy:
                merged_busy.append((busy_start, busy_end))
                continue
            last_start, last_end = merged_busy[-1]
            if busy_start <= last_end:
                merged_busy[-1] = (last_start, max(last_end, busy_end))
            else:
                merged_busy.append((busy_start, busy_end))

        gap_cursor = slot_start
        for busy_start, busy_end in merged_busy:
            if busy_start > gap_cursor:
                gap_minutes = int((busy_start - gap_cursor).total_seconds() // 60)
                if gap_minutes > 0:
                    schedule_gaps.append(
                        {
                            "starts_at": _safe_iso(gap_cursor),
                            "ends_at": _safe_iso(busy_start),
                            "duration_minutes": gap_minutes,
                            "staff_id": slot.staff_id,
                            "staff_name": staff_labels.get(int(slot.staff_id or 0)),
                            "resource_id": slot.resource_id,
                            "resource_title": resource_labels.get(int(slot.resource_id or 0)),
                        }
                    )
            gap_cursor = max(gap_cursor, busy_end)
        if gap_cursor < slot_end:
            gap_minutes = int((slot_end - gap_cursor).total_seconds() // 60)
            if gap_minutes > 0:
                schedule_gaps.append(
                    {
                        "starts_at": _safe_iso(gap_cursor),
                        "ends_at": _safe_iso(slot_end),
                        "duration_minutes": gap_minutes,
                        "staff_id": slot.staff_id,
                        "staff_name": staff_labels.get(int(slot.staff_id or 0)),
                        "resource_id": slot.resource_id,
                        "resource_title": resource_labels.get(int(slot.resource_id or 0)),
                    }
                )

    day_items = [
        {
            "period": key,
            "appointments": value["appointments"],
            "occupied_minutes": value["occupied_minutes"],
            "unique_clients": len(value["unique_clients"]),
        }
        for key, value in sorted(day_stats.items(), key=lambda item: item[0])
    ]
    week_items = [
        {
            "period": key,
            "appointments": value["appointments"],
            "occupied_minutes": value["occupied_minutes"],
            "unique_clients": len(value["unique_clients"]),
        }
        for key, value in sorted(week_stats.items(), key=lambda item: item[0])
    ]
    by_staff_items = sorted(
        [
            {
                "staff_id": key,
                "staff_name": staff_labels.get(key) or f"staff#{key}",
                "appointments": value["appointments"],
                "occupied_minutes": value["occupied_minutes"],
                "utilization_percent": round(
                    (value["occupied_minutes"] / max(1, int(schedulable_staff_minutes.get(key) or 0))) * 100, 1
                )
                if int(schedulable_staff_minutes.get(key) or 0) > 0
                else 0.0,
                "appointment_ids": sorted(value["appointment_ids"]),
            }
            for key, value in by_staff_stats.items()
        ],
        key=lambda item: (-int(item["occupied_minutes"]), str(item["staff_name"])),
    )
    by_resource_items = sorted(
        [
            {
                "resource_id": key,
                "resource_title": resource_labels.get(key) or f"resource#{key}",
                "appointments": value["appointments"],
                "occupied_minutes": value["occupied_minutes"],
                "utilization_percent": round(
                    (value["occupied_minutes"] / max(1, int(schedulable_resource_minutes.get(key) or 0))) * 100, 1
                )
                if int(schedulable_resource_minutes.get(key) or 0) > 0
                else 0.0,
                "appointment_ids": sorted(value["appointment_ids"]),
            }
            for key, value in by_resource_stats.items()
        ],
        key=lambda item: (-int(item["occupied_minutes"]), str(item["resource_title"])),
    )
    by_service_items = sorted(
        [
            {
                "service_id": key,
                "service_title": service_labels.get(key) or f"service#{key}",
                "appointments": value["appointments"],
                "occupied_minutes": value["occupied_minutes"],
                "appointment_ids": sorted(value["appointment_ids"]),
            }
            for key, value in by_service_stats.items()
        ],
        key=lambda item: (-int(item["occupied_minutes"]), str(item["service_title"])),
    )
    peak_hours = sorted(
        [
            {
                "hour": hour,
                "label": f"{hour:02d}:00-{(hour + 1) % 24:02d}:00",
                "occupied_minutes": value["occupied_minutes"],
                "appointments": len(value["appointment_ids"]),
                "appointment_ids": sorted(value["appointment_ids"]),
            }
            for hour, value in hour_stats.items()
        ],
        key=lambda item: (-int(item["occupied_minutes"]), int(item["hour"])),
    )[:5]
    schedule_gaps_sorted = sorted(
        schedule_gaps,
        key=lambda item: (
            -int(item.get("duration_minutes") or 0),
            str(item.get("starts_at") or ""),
        ),
    )[:50]

    status_counts: dict[str, int] = {}
    for row in appointments:
        status_key = str(row.status or "").strip().lower() or "unknown"
        status_counts[status_key] = int(status_counts.get(status_key) or 0) + 1
    no_show_enabled = bool(cfg.get("appointment_confirmation_enabled")) or (
        str(cfg.get("confirmation_policy") or "confirm_risky").strip().lower() != "never_confirm"
    )
    no_show_denominator = int(status_counts.get("completed") or 0) + int(status_counts.get("no_show") or 0)
    if no_show_denominator == 0:
        no_show_rate_percent = 0.0
    else:
        no_show_rate_percent = round((int(status_counts.get("no_show") or 0) / no_show_denominator) * 100, 1)
    utilization_percent = (
        round((total_occupied_minutes / max(1, total_schedulable_minutes)) * 100, 1)
        if total_schedulable_minutes > 0
        else 0.0
    )

    return JSONResponse(
        content={
            "range": {"starts_at": _safe_iso(start_dt), "ends_at": _safe_iso(end_dt)},
            "filters": {
                "domain_type": domain_type,
                "staff_id": staff_id,
                "service_id": service_id,
                "resource_id": resource_id,
                "granularity_minutes": granularity_minutes,
            },
            "totals": {
                "appointments": len(appointments),
                "unique_clients": len(unique_clients),
                "occupied_minutes": total_occupied_minutes,
                "schedulable_minutes": total_schedulable_minutes,
            },
            "aggregates": {
                "by_day": day_items,
                "by_week": week_items,
                "by_staff": by_staff_items,
                "by_resource": by_resource_items,
                "by_service": by_service_items,
                "schedule_gaps": schedule_gaps_sorted,
            },
            "kpis": {
                "utilization_percent": utilization_percent,
                "peak_hours": peak_hours,
                "no_show": {
                    "enabled": no_show_enabled,
                    "rate_percent": no_show_rate_percent if no_show_enabled else None,
                    "no_show_count": int(status_counts.get("no_show") or 0) if no_show_enabled else None,
                    "basis_appointments": no_show_denominator if no_show_enabled else None,
                },
            },
            "drilldown": {
                "appointments": [_serialize_admin_appointment_row(row) for row in appointments],
            },
            "matrix": occupancy_matrix,
        },
        status_code=status.HTTP_200_OK,
    )


@router.get("/external/widget.css")
async def external_widget_css():
    return PlainTextResponse(
        content=WIDGET_CSS,
        media_type="text/css; charset=utf-8",
    )


@router.get("/external/widget.js")
async def external_widget_js():
    return PlainTextResponse(
        content=WIDGET_JS,
        media_type="application/javascript; charset=utf-8",
    )
