"""Pydantic schemas for /custom API."""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class CustomAdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class CustomAutomationLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class CustomLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    custom_admin: bool = False
    custom_automation_id: Optional[int] = None


class CustomAutomationDashboardAccountStats(BaseModel):
    total: int
    active: int
    banned: int
    revoked: int = 0
    spamblocked: int = 0
    frozen: int = 0
    by_class: dict[str, int] = {}


class CustomAutomationDashboardLeadStats(BaseModel):
    total: int
    by_status: dict[str, int]
    by_source: dict[str, int]


class CustomAutomationDashboardDmpStats(BaseModel):
    requested: int
    received: int
    purchased: int
    cost_rub: float
    cpl_rub: float | None


class CustomAutomationDashboardSashaStats(BaseModel):
    queued: int = 0
    uploaded: int = 0
    calls: int = 0
    completed: int = 0
    failed: int = 0
    committed_calls: int = 0
    committed_leads: int = 0
    avg_quality: float | None = None


class CustomAutomationDashboardActionStats(BaseModel):
    total: int
    last_24h: dict[str, int]
    last_7d: dict[str, int]


class CustomAutomationDashboardChatStats(BaseModel):
    total: int
    joined: int
    pending: int
    by_mode: dict[str, int]


class CustomAutomationDashboardResponse(BaseModel):
    automation_id: int
    name: str | None
    client_name: str | None
    accounts: CustomAutomationDashboardAccountStats
    leads: CustomAutomationDashboardLeadStats
    dmp: CustomAutomationDashboardDmpStats
    sasha: CustomAutomationDashboardSashaStats = Field(default_factory=CustomAutomationDashboardSashaStats)
    actions: CustomAutomationDashboardActionStats
    chats: CustomAutomationDashboardChatStats
    updated_at: str


class ActivityChatPreview(BaseModel):
    id: int | None = None
    title: str | None = None
    chat_type: str | None = None


class ActivityMessagePreview(BaseModel):
    direction: str
    text: str
    sent_at: datetime | None = None
    author: str | None = None


class ActivityItemResponse(BaseModel):
    id: str
    activity_type: str
    created_at: datetime
    chat: ActivityChatPreview | None = None
    lead_id: int | None = None
    post_id: int | None = None
    post_text: str | None = None
    comment: str | None = None
    user_message: str | None = None
    user_name: str | None = None
    dm_reply: str | None = None
    source_text: str | None = None
    reply: str | None = None
    setup: str | None = None
    setup_author: str | None = None
    reply_author: str | None = None
    lead_name: str | None = None
    lead_contact: str | None = None
    lead_company: str | None = None
    messages: list[ActivityMessagePreview] = []
    shilling_kind: str | None = None


class ActivityFeedResponse(BaseModel):
    items: list[ActivityItemResponse]
    total: int


class ErrorFeedItemResponse(BaseModel):
    id: int
    created_at: datetime
    action_type: str
    action_label: str
    result: str
    error_message: str | None = None
    target_id: str | None = None
    target_type: str | None = None
    account: str | None = None
    account_id: int | None = None
    chat_title: str | None = None
    chat_id: int | None = None
    context: dict = Field(default_factory=dict)


class ErrorFeedResponse(BaseModel):
    items: list[ErrorFeedItemResponse]
    total: int


class CustomAdminDashboardAutomationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    client_name: str | None
    is_amocrm_enabled: bool
    is_dmp_one_enabled: bool
    leads_total: int
    accounts_total: int
    accounts_banned: int
    messages_total: int
    created_at: datetime


class CustomAdminDashboardResponse(BaseModel):
    total_automations: int
    total_accounts: int
    total_banned_accounts: int
    total_leads: int
    total_messages: int
    automations: list[CustomAdminDashboardAutomationSummary]
    updated_at: str


class CustomAutomationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    client_name: Optional[str] = Field(None, max_length=200)
    industry: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = None
    solution_kind: Optional[str] = Field(None, max_length=32)


class CustomAutomationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    client_name: Optional[str] = Field(None, max_length=200)
    industry: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = None
    status: Optional[str] = Field(None, max_length=32)
    solution_kind: Optional[str] = Field(None, max_length=32)


class CustomAutomationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    client_name: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    status: str
    solution_kind: str = "generic"
    solution_slug: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CustomAutomationListResponse(BaseModel):
    items: list[CustomAutomationResponse]
    total: int


class ProxyDistributionItem(BaseModel):
    id: int
    scheme: str
    host: str
    port: int
    country_code: str | None = None
    region: str | None = None
    ip_version: int | None = None
    account_count: int


class CustomAutomationSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: int
    name: str
    rotation_strategy: str
    max_daily_messages_per_account: int
    is_chat_monitoring_enabled: bool
    lead_keywords: list[str] = Field(default_factory=list)
    is_neurocommenting_enabled: bool
    is_digital_footprint_enabled: bool
    is_dmp_one_enabled: bool
    is_amocrm_enabled: bool
    is_shilling_enabled: bool
    is_lead_qualification_enabled: bool = False
    solution_kind: str = "generic"
    solution_slug: str | None = None
    lead_manager_contact: str | None = None
    partner_utm_url: str | None = None
    partner_promo_code: str | None = None
    conversion_check_url: str | None = None
    status: str = "draft"
    warnings: list[str] = []
    dmp_webhook_url: str | None = None
    dmp_webhook_secret: str | None = None
    is_sasha_ai_enabled: bool = False
    sasha_upload_url: str | None = None
    sasha_upload_format: str = "api"
    sasha_auto_push: bool = True
    sasha_qualify_on_commit: bool = True
    sasha_notify_on_commit: bool = True
    sasha_webhook_url: str | None = None
    sasha_webhook_secret: str | None = None
    sasha_hmac_secret: str | None = None
    sasha_hmac_secret_set: bool = False
    sasha_connected: bool = False
    amocrm_redirect_uri: str | None = None
    telegram_bot_token_set: bool = False
    telegram_bot_username: str | None = None
    telegram_bot_webhook_url: str | None = None
    telegram_bot_subscribers: int = 0
    telegram_bot_password_set: bool = False
    google_sheets_spreadsheet_id: str | None = None
    google_sheets_worksheet: str | None = None
    google_sheets_credentials_set: bool = False
    google_sheets_service_account_email: str | None = None
    account_warmup_enabled: bool = False
    account_warmup_usernames: list[str] = Field(default_factory=list)
    account_warmup_messages: list[str] = Field(default_factory=list)
    proxy_list_text: str | None = None
    proxy_count: int = 0
    accounts_with_proxy: int = 0
    proxy_purity: int = 100
    proxy_unique_used: int = 0
    proxy_peak_load: int = 0
    proxy_distribution: list[ProxyDistributionItem] = Field(default_factory=list)
    work_hour_start: int = 8
    work_hour_end: int = 20
    work_weekdays: list[int] = Field(default_factory=list)


class CustomAutomationSettingsValidationResponse(BaseModel):
    warnings: list[str]
    can_enable: dict[str, bool]
    counts: dict[str, int]


class CustomAutomationSettingsUpdate(BaseModel):
    rotation_strategy: str | None = None
    max_daily_messages_per_account: int | None = None
    is_chat_monitoring_enabled: bool | None = None
    lead_keywords: list[str] | None = None
    is_neurocommenting_enabled: bool | None = None
    is_digital_footprint_enabled: bool | None = None
    is_dmp_one_enabled: bool | None = None
    is_amocrm_enabled: bool | None = None
    is_shilling_enabled: bool | None = None
    is_lead_qualification_enabled: bool | None = None
    is_sasha_ai_enabled: bool | None = None
    sasha_auto_push: bool | None = None
    sasha_qualify_on_commit: bool | None = None
    sasha_notify_on_commit: bool | None = None
    lead_manager_contact: str | None = None
    partner_utm_url: str | None = None
    partner_promo_code: str | None = None
    conversion_check_url: str | None = None
    status: str | None = None
    account_warmup_usernames: list[str] | None = None
    account_warmup_messages: list[str] | None = None
    account_warmup_enabled: bool | None = None
    proxy_list_text: str | None = None
    proxy_country: str | None = None
    work_hour_start: int | None = None
    work_hour_end: int | None = None
    work_weekdays: list[int] | None = None


class CustomAutomationCredentialCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class CustomAutomationCredentialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    custom_automation_id: int
    username: str
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class CustomAutomationCredentialListResponse(BaseModel):
    items: list[CustomAutomationCredentialResponse]
    total: int


class AccountUploadResponse(BaseModel):
    total: int
    created: int
    skipped: int
    errors: list[str]


class AccountBulkClassifyRequest(BaseModel):
    account_ids: list[int] = []


class AccountBulkClassifyResponse(BaseModel):
    queued: int


class AccountClassUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    bio: Optional[str] = Field(default=None, max_length=140)


class AccountQrStartRequest(BaseModel):
    proxy_id: int | None = None
    proxy_line: str | None = Field(default=None, max_length=512)


class AccountProxyOption(BaseModel):
    id: int
    label: str
    scheme: str
    host: str
    port: int
    country_code: str | None = None
    ip_version: int | None = None


class AccountProxyListResponse(BaseModel):
    items: list[AccountProxyOption] = Field(default_factory=list)


class AccountQrStatusRequest(BaseModel):
    auth_token: str = Field(..., min_length=20, max_length=16384)


class AccountQrVerify2faRequest(BaseModel):
    auth_token: str = Field(..., min_length=20, max_length=16384)
    password: str = Field(..., min_length=1, max_length=128)


class AccountSmsRequest(BaseModel):
    phone_number: str = Field(..., min_length=5, max_length=32)
    proxy_id: int | None = None
    proxy_line: str | None = Field(default=None, max_length=512)


class AccountSmsVerifyRequest(BaseModel):
    auth_token: str = Field(..., min_length=20, max_length=16384)
    code: str = Field(..., min_length=3, max_length=12)
    password: str | None = Field(default=None, max_length=128)


class AccountSmsStartResponse(BaseModel):
    auth_token: str


class AccountBulkUpdateProfilesRequest(BaseModel):
    account_ids: list[int] = []
    status: str | None = None
    bio_template: str = ""
    generate_unique: bool = False
    save_as_template: bool = False


class AccountBulkUpdateProfilesResponse(BaseModel):
    queued: int
    results: list[dict[str, Any]] | None = None


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    phone_number: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    avatar_file_path: Optional[str] = None
    warmup_status: str = "idle"
    warmup_started_at: Optional[datetime] = None
    warmup_dialog_count: int = 0
    status: str
    is_active: bool
    is_banned: bool
    is_spamblocked: bool = False
    is_frozen: bool = False
    is_channel_banned: bool = False
    restriction_kind: Optional[str] = None
    restriction_until: Optional[datetime] = None
    restriction_label: Optional[str] = None
    restriction_scope: Optional[str] = None
    rest_kind: Optional[str] = None
    rest_label: Optional[str] = None
    session_guard_enabled: bool = True
    session_guard_paused_until: Optional[datetime] = None
    risk_score: Optional[float] = None
    trust_score: Optional[float] = None
    session_file_path: Optional[str] = None
    daily_messages_sent: int = 0
    daily_messages_reset_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    max_daily_messages_per_account: int = 50
    added_at: datetime
    created_at: Optional[datetime] = None
    last_health_check_at: Optional[datetime] = None
    spamblock_checked_at: Optional[datetime] = None
    frozen_at: Optional[datetime] = None
    flood_quarantined_until: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    proxy_label: Optional[str] = None
    telegram_session_count: Optional[int] = None
    origin: str = "farm"
    intercept_stage: Optional[str] = None
    intercept_labels: list[str] = Field(default_factory=list)
    intercept_can_adopt: bool = False
    intercept_can_reauth: bool = False
    intercept_can_change_2fa: bool = False
    intercept_parent_kept: bool = False
    intercept_has_cloud_password: bool = False
    intercept_hold_until: Optional[datetime] = None
    intercept_adopt_until: Optional[datetime] = None
    intercept_reauthorized_at: Optional[datetime] = None
    intercept_reauth_error: Optional[str] = None


class AccountQrStartResponse(BaseModel):
    auth_token: str
    qr_url: str = ""
    qr_data_url: str = ""
    already_authorized: bool = False
    account: Optional[AccountResponse] = None


class AccountQrStatusResponse(BaseModel):
    status: str
    error: Optional[str] = None
    account: Optional[AccountResponse] = None


class AccountConnectResponse(BaseModel):
    account: AccountResponse


class AccountListResponse(BaseModel):
    items: list[AccountResponse]
    total: int


class AccountHealthCheckResult(BaseModel):
    account_id: int
    status: str
    classification: dict[str, Any] | None = None
    error: str | None = None


class AccountHealthCheckResponse(BaseModel):
    results: list[AccountHealthCheckResult]
    total: int
    ok: int
    fallback: int
    error: int


class AccountSpamblockCheckResponse(BaseModel):
    account: AccountResponse
    spamblocked: bool | None = None
    source: str | None = None
    detail: str
    restriction_kind: Optional[str] = None


class AccountTelegramCodeResponse(BaseModel):
    code: str | None = None
    sent_at: Optional[datetime] = None
    detail: str
    session_guard_paused_until: Optional[datetime] = None


class AccountSessionGuardPauseResponse(BaseModel):
    account: AccountResponse
    paused_until: Optional[datetime] = None
    detail: str


class AccountAuthorizationItem(BaseModel):
    hash: str
    current: bool = False
    device_model: Optional[str] = None
    platform: Optional[str] = None
    app_name: Optional[str] = None
    app_version: Optional[str] = None
    ip: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    place: Optional[str] = None
    title: str
    subtitle: Optional[str] = None
    created_at: Optional[datetime] = None
    active_at: Optional[datetime] = None
    can_terminate: bool = False


class AccountAuthorizationListResponse(BaseModel):
    items: list[AccountAuthorizationItem]
    count: int
    account: Optional[AccountResponse] = None


class CloudPasswordUpdateRequest(BaseModel):
    current_password: Optional[str] = None
    new_password: str
    hint: Optional[str] = ""
    email: Optional[str] = None


class CloudPasswordConfirmRequest(BaseModel):
    code: str


class CloudPasswordUpdateResponse(BaseModel):
    status: str
    detail: str = ""
    email_pattern: Optional[str] = None
    code_length: int = 6
    account: Optional[AccountResponse] = None


class InterceptReauthRequest(BaseModel):
    cloud_password: Optional[str] = None


class InterceptReauthResponse(BaseModel):
    status: str
    detail: str = ""
    account: Optional[AccountResponse] = None


class AccountPrepareStatusResponse(BaseModel):
    status: str
    alive: int = 0
    profiles_done: int = 0
    chats_joined: int = 0
    error: Optional[str] = None


class AccountSetupTemplatesResponse(BaseModel):
    templates: dict[str, Any] = {}


class AccountSetupTemplateUpdate(BaseModel):
    account_class: str = Field(default="*", min_length=1, max_length=32)
    bio_template: str = ""
    generate_unique: bool = False


class AccountBanStatsResponse(BaseModel):
    total: int
    active: int
    banned: int
    revoked: int = 0
    spamblocked: int = 0
    frozen: int = 0
    in_work: int = 0
    quarantine: int = 0
    invalid: int = 0
    channel_banned: int = 0
    banned_percent: float
    alert_threshold: float = 0.3
    alert: bool


class ChatTargetCreate(BaseModel):
    provider: str = "telegram"
    invite_link: str = Field(..., min_length=1, max_length=512)
    mode: str = "monitoring"
    folder_id: Optional[int] = None
    external_chat_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    chat_type: Optional[str] = None


class ChatTargetUpdate(BaseModel):
    mode: Optional[str] = None
    is_active: Optional[bool] = None
    neurocommenting_config: Optional[dict] = None
    discussion_config: Optional[dict] = None
    shilling_config: Optional[dict] = None


class NeurocommentingRunResponse(BaseModel):
    chats_processed: int
    comments_sent: int


class DiscussionRunResponse(BaseModel):
    chats_processed: int
    replies_sent: int


class ShillingRunResponse(BaseModel):
    chats_processed: int
    dialogues_sent: int


class DmpOneImportCreate(BaseModel):
    import_type: str
    source_url: Optional[str] = None
    requested_count: int = 100


class DmpOneImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    custom_automation_id: int
    import_type: str
    source_url: Optional[str] = None
    requested_count: Optional[int] = None
    received_count: Optional[int] = None
    purchased_count: Optional[int] = None
    cost_rub: Optional[float] = None
    cpl_rub: Optional[float] = None
    status: str
    raw_payload: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class DmpOneImportListResponse(BaseModel):
    items: list[DmpOneImportResponse]
    total: int


class DmpOneWebhookResponse(BaseModel):
    created_leads: int
    received_count: int
    purchased_count: int


class SashaAiConnectionUpdate(BaseModel):
    is_sasha_ai_enabled: bool | None = None
    sasha_upload_url: str | None = None
    sasha_upload_format: str | None = Field(None, max_length=16)
    sasha_hmac_secret: str | None = None
    sasha_auto_push: bool | None = None
    sasha_qualify_on_commit: bool | None = None
    sasha_notify_on_commit: bool | None = None


class SashaAiConnectionResponse(BaseModel):
    is_sasha_ai_enabled: bool = False
    sasha_upload_url: str | None = None
    sasha_upload_format: str = "api"
    sasha_auto_push: bool = True
    sasha_qualify_on_commit: bool = True
    sasha_notify_on_commit: bool = True
    sasha_webhook_url: str | None = None
    sasha_webhook_secret: str | None = None
    sasha_hmac_secret: str | None = None
    sasha_hmac_secret_set: bool = False
    sasha_connected: bool = False


class SashaAiCallResponse(BaseModel):
    id: int
    custom_automation_id: int
    custom_lead_id: int | None = None
    event_id: str
    event_type: str
    call_id: str | None = None
    session_id: str | None = None
    call_list_id: str | None = None
    call_list_name: str | None = None
    phone: str | None = None
    status: str | None = None
    hangup_reason: str | None = None
    duration_ms: int | None = None
    started_at: datetime | None = None
    connected_at: datetime | None = None
    ended_at: datetime | None = None
    is_commit: bool = False
    client_name: str | None = None
    client_facts: str | None = None
    agreements: str | None = None
    lead_quality: int | None = None
    warmth: str | None = None
    lead_destination: str | None = None
    agreements_status: str | None = None
    session_result_status: str | None = None
    session_result_reason: str | None = None
    record_url: str | None = None
    transcript: list = Field(default_factory=list)
    transcript_text: str = ""
    lead_transfer: dict = Field(default_factory=dict)
    outcome: str = ""
    created_at: datetime
    updated_at: datetime


class SashaAiCallListResponse(BaseModel):
    items: list[SashaAiCallResponse]
    total: int
    stats: dict = Field(default_factory=dict)


class SashaAiPushResponse(BaseModel):
    status: str
    lead_id: int | None = None
    pushed: int | None = None
    failed: int | None = None
    skipped: int | None = None
    error: str | None = None
    message: str | None = None


class SashaAiWebhookResponse(BaseModel):
    status: str
    call_id: int | None = None
    lead_id: int | None = None
    event_type: str | None = None
    is_commit: bool = False
    notified: bool = False


class TelegramBotSettingsUpdate(BaseModel):
    bot_token: Optional[str] = None
    password: Optional[str] = None
    disconnect: bool = False


class IntegrationRouteMapping(BaseModel):
    source: str = Field(..., min_length=1, max_length=120)
    target: str = Field(..., min_length=1, max_length=120)


class IntegrationRouteUpsert(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=80)
    enabled: bool = True
    direction: str = "outbound"
    event: str = "lead.transferred"
    url: Optional[str] = None
    secret_header: str = "X-Webhook-Secret"
    secret: Optional[str] = None
    mappings: list[IntegrationRouteMapping] = Field(default_factory=list)


class IntegrationRouteResponse(BaseModel):
    id: str
    name: str
    enabled: bool
    direction: str
    event: str
    method: str = "POST"
    url: Optional[str] = None
    secret_header: str
    secret: Optional[str] = None
    mappings: list[IntegrationRouteMapping] = Field(default_factory=list)
    inbound_url: Optional[str] = None


class IntegrationRouteListResponse(BaseModel):
    items: list[IntegrationRouteResponse] = Field(default_factory=list)


class GoogleSheetsSettingsUpdate(BaseModel):
    spreadsheet: Optional[str] = None
    worksheet: Optional[str] = None
    service_account_json: Optional[str] = None


class AmocrmCredentialsUpdate(BaseModel):
    subdomain: str
    client_id: str
    client_secret: Optional[str] = None


class AmocrmOAuthStartRequest(BaseModel):
    return_url: Optional[str] = None


class AmocrmOAuthStartResponse(BaseModel):
    auth_url: str
    redirect_uri: str


class AmocrmPipelineUpdate(BaseModel):
    pipeline_id: Optional[str] = None
    responsible_user_id: Optional[str] = None
    lead_status_id: Optional[str] = None


class AmocrmConnectionResponse(BaseModel):
    id: Optional[int] = None
    custom_automation_id: Optional[int] = None
    subdomain: Optional[str] = None
    client_id: Optional[str] = None
    has_credentials: bool = False
    client_secret_set: bool = False
    connected: bool = False
    pipeline_id: Optional[str] = None
    responsible_user_id: Optional[str] = None
    lead_status_id: Optional[str] = None
    is_active: bool = False
    last_sync_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    redirect_uri: str = ""


class AmocrmTransferResponse(BaseModel):
    lead_id: int
    status: str
    transferred_at: Optional[datetime] = None
    amocrm_lead_id: Optional[str] = None
    amocrm_contact_id: Optional[str] = None
    reason: Optional[str] = None


class CustomPromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    custom_automation_id: int
    prompt_type: str
    name: str
    content: str
    model: str
    temperature: float
    max_tokens: int
    response_format: Optional[str] = None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime
    shilling_setup: Optional[str] = None
    shilling_reply: Optional[str] = None


class CustomPromptListResponse(BaseModel):
    items: list[CustomPromptResponse]


class CustomPromptUpdate(BaseModel):
    content: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    is_active: Optional[bool] = None
    shilling_setup: Optional[str] = None
    shilling_reply: Optional[str] = None


class CustomPromptTestRequest(BaseModel):
    variables: dict[str, str] = {}


class CustomPromptTestResponse(BaseModel):
    rendered: str
    output: str
    error: Optional[str] = None
    missing_variables: list[str]


class SkillbaseBriefUpdate(BaseModel):
    business: str = ""
    processes: str = ""
    funnel: str = ""
    product: str = ""
    terms: str = ""
    notes: str = ""


class SkillbaseFileInfo(BaseModel):
    name: str
    chars: int


class SkillbaseBriefResponse(BaseModel):
    business: str
    processes: str
    funnel: str
    product: str
    terms: str
    notes: str
    files: list[SkillbaseFileInfo]
    knowledge_chars: int
    updated_at: Optional[str] = None
    generated_at: Optional[str] = None


class SkillbaseActivityResponse(BaseModel):
    key: str
    title: str
    where: str
    variables: list[str]
    storage: str
    module_text: str = ""


class SkillbaseResponse(BaseModel):
    brief: SkillbaseBriefResponse
    activities: list[SkillbaseActivityResponse]


class SkillbaseGenerateResponse(BaseModel):
    brief: SkillbaseBriefResponse
    updated: list[str]
    errors: list[str]


class SkillbaseComplaint(BaseModel):
    complaint: str = ""


class SkillbaseModuleSave(BaseModel):
    content: str = ""


class ChatTargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    custom_automation_id: int
    provider: str
    external_chat_id: Optional[str] = None
    invite_link: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    chat_type: Optional[str] = None
    mode: str
    source: str
    join_status: str
    join_attempts: int
    next_join_attempt_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None
    is_active: bool
    last_scanned_at: Optional[datetime] = None
    last_join_error: Optional[str] = None
    members_count: Optional[int] = None
    last_activity_at: Optional[datetime] = None
    comments_open: Optional[bool] = None
    comments_checked_at: Optional[datetime] = None
    comments_check_error: Optional[str] = None
    memberships_joined: int = 0
    memberships_total: int = 0
    folder_id: Optional[int] = None
    neurocommenting_config: Optional[dict] = None
    discussion_config: Optional[dict] = None
    shilling_config: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class ChatTargetListResponse(BaseModel):
    items: list[ChatTargetResponse]
    total: int


class ChatFolderResponse(BaseModel):
    id: int
    name: str
    chats_count: int
    created_at: datetime


class ChatFolderListResponse(BaseModel):
    items: list[ChatFolderResponse]
    total: int


class ChatImportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    custom_automation_id: int
    file_name: str
    status: str
    total_rows: int
    processed_rows: int
    error_rows: int
    duplicate_rows: int = 0
    skipped_rows: int = 0
    error_log: list = []
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _skipped_from_error_log(self):
        if self.skipped_rows:
            return self
        for item in self.error_log or []:
            if isinstance(item, dict) and item.get("skipped_rows") is not None:
                try:
                    self.skipped_rows = int(item["skipped_rows"])
                except (TypeError, ValueError):
                    continue
                break
        return self


class ChatImportJobListResponse(BaseModel):
    items: list[ChatImportJobResponse]
    total: int


class ChatInspectStatusResponse(BaseModel):
    status: str
    total: int = 0
    checked: int = 0
    comments_open: int = 0
    comments_closed: int = 0
    errors: int = 0
    error: Optional[str] = None


class ChatDiscoveryCreate(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    mode: Optional[str] = "monitoring"
    max_chats: int = Field(50, ge=1, le=200)
    require_approval: bool = True
    relevance_threshold: float = Field(0.6, ge=0.0, le=1.0)


class ChatDiscoveryCandidate(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    username: Optional[str] = None
    chat_type: Optional[str] = None
    participants_count: Optional[int] = None
    score: float = 0.0
    reason: Optional[str] = None
    relevant: bool = False


class ChatDiscoveryTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    custom_automation_id: int
    status: str
    query: str
    max_chats: int
    found_chats: list[dict]
    joined_chats: int
    rejected_chats: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class ChatDiscoveryTaskListResponse(BaseModel):
    items: list[ChatDiscoveryTaskResponse]
    total: int


class ChatDiscoveryApproveRequest(BaseModel):
    indices: list[int] = []
    mode: Optional[str] = None


class ChatDiscoveryActionResponse(BaseModel):
    created: int = 0
    rejected: int = 0


class UnifiedJobLog(BaseModel):
    ts: Optional[str] = None
    level: str = "info"
    message: str = ""


class UnifiedJobResponse(BaseModel):
    id: str
    source: str
    source_id: int
    category: str
    job_type: str
    badge: str = ""
    title: str
    subtitle: str = ""
    status: str
    params: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    logs: list[UnifiedJobLog] = Field(default_factory=list)
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: int = 0
    can_cancel: bool = False
    can_approve: bool = False
    can_pause: bool = False
    can_resume: bool = False
    can_edit: bool = False


class UnifiedJobPatchRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)
    title: Optional[str] = None


class UnifiedJobListResponse(BaseModel):
    items: list[UnifiedJobResponse]
    total: int


class UbtStatsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    period: str
    dashboard: dict[str, Any]
    accounts: dict[str, Any]
    history: dict[str, Any]


class ChatBlackboxRequest(BaseModel):
    chat_id: Optional[int] = None
    query: Optional[str] = None
    reason: str = "manual"


class ChatBlackboxBulkRequest(BaseModel):
    chat_ids: list[int] = Field(default_factory=list)
    reason: str = "generated_blacklist"


class TelegramAccountLogItem(BaseModel):
    id: int
    message: str
    rpc_name: str = ""
    result: str = "ok"
    error: Optional[str] = None
    created_at: Optional[datetime] = None


class TelegramAccountLogListResponse(BaseModel):
    items: list[TelegramAccountLogItem] = Field(default_factory=list)


class TaskAddlistItem(BaseModel):
    task_key: str
    task_title: str = ""
    account_id: int = 0
    slug: str = ""
    url: str = ""
    chat_ids: list[int] = Field(default_factory=list)
    chat_count: int = 0


class TaskAddlistListResponse(BaseModel):
    items: list[TaskAddlistItem] = Field(default_factory=list)


class TaskAddlistCreateRequest(BaseModel):
    account_id: int
    chat_ids: list[int] = Field(default_factory=list)
    task_key: str = "neurocommenting"
    title: str = ""


class TaskDistributeRequest(BaseModel):
    task_key: str
    assignments: dict[str, list[str]] = Field(default_factory=dict)


class TaskDistributeResponse(BaseModel):
    assignments: dict[str, list[int]] = Field(default_factory=dict)
    chat_ids: list[int] = Field(default_factory=list)
    reserve_chat_ids: list[int] = Field(default_factory=list)
    add_errors: list[str] = Field(default_factory=list)


class TaskPoolChatItem(BaseModel):
    id: int
    title: str = ""
    link: str = ""
    folder_id: Optional[int] = None
    folder_name: Optional[str] = None
    joined: bool = False


class TaskPoolAccountItem(BaseModel):
    id: int
    label: str = ""
    username: Optional[str] = None
    phone_number: Optional[str] = None
    assigned: list[TaskPoolChatItem] = Field(default_factory=list)
    assigned_count: int = 0
    joined_count: int = 0
    status: str = ""


class TaskPoolFolderMix(BaseModel):
    id: Optional[int] = None
    name: str = ""
    total: int = 0
    assigned: int = 0
    reserve: int = 0


class TaskPoolRequest(BaseModel):
    task_key: str
    account_ids: Optional[list[int]] = None
    folder_ids: Optional[list[int]] = None
    chat_ids: Optional[list[int]] = None
    mode: str = "fill"


class TaskPoolResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    task_key: str
    resource_kind: str = "any"
    cap: int = 50
    account_ids: list[int] = Field(default_factory=list)
    folder_ids: list[int] = Field(default_factory=list)
    chat_ids: list[int] = Field(default_factory=list)
    assignments: dict[str, list[int]] = Field(default_factory=dict)
    reserve_chat_ids: list[int] = Field(default_factory=list)
    accounts: list[TaskPoolAccountItem] = Field(default_factory=list)
    reserve: list[TaskPoolChatItem] = Field(default_factory=list)
    folder_mix: list[TaskPoolFolderMix] = Field(default_factory=list)
    available_accounts: list[dict[str, Any]] = Field(default_factory=list)
    available_folders: list[dict[str, Any]] = Field(default_factory=list)
    pending_joins: int = 0
    joins_complete: bool = False
    live: bool = False
    assigned_count: int = 0
    reserve_count: int = 0


class NeurocommentingSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    account_ids: list[int] = Field(default_factory=list)
    chat_ids: list[int] = Field(default_factory=list)
    folder_ids: list[int] = Field(default_factory=list)
    blacklisted_account_ids: list[int] = Field(default_factory=list)
    chat_assignments: dict[str, list[int]] = Field(default_factory=dict)
    reserve_chat_ids: list[int] = Field(default_factory=list)
    post_filter: str = "new"
    keywords: list[str] = Field(default_factory=list)
    probability: int = 100
    min_words: int = 0
    max_per_account: int = 15
    max_per_chat: int = 10
    delay_before_min: int = 180
    delay_before_max: int = 240
    comment_delay_min: int = 1200
    comment_delay_max: int = 2400
    join_delay_min: int = 1200
    join_delay_max: int = 2400
    respect_night_hours: bool = True
    prompt_id: Optional[int] = None
    require_proxy: bool = False
    hide_in_work: bool = False
    include_joined: bool = False
    presets: list[dict[str, Any]] = Field(default_factory=list)
    enabled: Optional[bool] = None
    warmup_enabled: Optional[bool] = None


class NeurocommentingModuleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool
    warmup_enabled: bool = False
    settings: dict[str, Any]
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    chats: list[dict[str, Any]] = Field(default_factory=list)
    folders: list[dict[str, Any]] = Field(default_factory=list)
    prompts: list[dict[str, Any]] = Field(default_factory=list)
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    blacklist: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    added_ids: list[int] = Field(default_factory=list)
    add_errors: list[str] = Field(default_factory=list)


class NeurocommentingChannelsRequest(BaseModel):
    links: str = ""


class NeurocommentingPresetRequest(BaseModel):
    name: str = ""


class NeurocommentingPromptCreate(BaseModel):
    name: str = "Мой промпт"
    content: str = ""


class NeurochattingSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    account_ids: list[int] = Field(default_factory=list)
    chat_ids: list[int] = Field(default_factory=list)
    folder_ids: list[int] = Field(default_factory=list)
    chat_assignments: dict[str, list[int]] = Field(default_factory=dict)
    reserve_chat_ids: list[int] = Field(default_factory=list)
    reply_mode: str = "interval"
    keywords: list[str] = Field(default_factory=list)
    reply_condition: str = ""
    probability: int = 30
    work_mode: str = "count"
    work_always: bool = False
    max_per_chat: int = 1
    max_per_account: int = 15
    max_replies_per_run: int = 1
    only_joined: bool = False
    respect_night_hours: bool = True
    delay_before_min: int = 42
    delay_before_max: int = 78
    comment_delay_min: int = 1200
    comment_delay_max: int = 2400
    join_delay_min: int = 1200
    join_delay_max: int = 2400
    prompt_id: Optional[int] = None
    require_proxy: bool = False
    hide_in_work: bool = False
    include_joined: bool = False
    context_depth: int = 5
    blacklisted_account_ids: list[int] = Field(default_factory=list)
    presets: list[dict[str, Any]] = Field(default_factory=list)
    enabled: Optional[bool] = None
    warmup_enabled: Optional[bool] = None


class NeurochattingModuleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool
    warmup_enabled: bool = False
    settings: dict[str, Any]
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    chats: list[dict[str, Any]] = Field(default_factory=list)
    folders: list[dict[str, Any]] = Field(default_factory=list)
    prompts: list[dict[str, Any]] = Field(default_factory=list)
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    blacklist: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    added_ids: list[int] = Field(default_factory=list)
    add_errors: list[str] = Field(default_factory=list)


class NeurochattingGroupsRequest(BaseModel):
    links: str = ""


class NeurochattingPresetRequest(BaseModel):
    name: str = ""


class NeurochattingPromptCreate(BaseModel):
    name: str = "Мой промпт"
    content: str = ""


class ChatMonitoringSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    account_ids: list[int] = Field(default_factory=list)
    chat_ids: list[int] = Field(default_factory=list)
    folder_ids: list[int] = Field(default_factory=list)
    chat_assignments: dict[str, list[int]] = Field(default_factory=dict)
    reserve_chat_ids: list[int] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    max_per_account: int = 15
    join_delay_min: int = 1200
    join_delay_max: int = 2400
    respect_night_hours: bool = True
    prompt_id: Optional[int] = None
    require_proxy: bool = False
    hide_in_work: bool = False
    include_joined: bool = False
    blacklisted_account_ids: list[int] = Field(default_factory=list)
    presets: list[dict[str, Any]] = Field(default_factory=list)
    enabled: Optional[bool] = None


class ChatMonitoringModuleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool
    settings: dict[str, Any]
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    chats: list[dict[str, Any]] = Field(default_factory=list)
    folders: list[dict[str, Any]] = Field(default_factory=list)
    prompts: list[dict[str, Any]] = Field(default_factory=list)
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    blacklist: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    added_ids: list[int] = Field(default_factory=list)
    add_errors: list[str] = Field(default_factory=list)


class ChatMonitoringGroupsRequest(BaseModel):
    links: str = ""


class ChatMonitoringPresetRequest(BaseModel):
    name: str = ""


class ChatMonitoringPromptCreate(BaseModel):
    name: str = "Мой промпт"
    content: str = ""
    prompt_type: str = "chat_monitoring_trigger"


class MasslookingSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    account_ids: list[int] = Field(default_factory=list)
    chat_ids: list[int] = Field(default_factory=list)
    folder_ids: list[int] = Field(default_factory=list)
    chat_assignments: dict[str, list[int]] = Field(default_factory=dict)
    reserve_chat_ids: list[int] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)
    user_folder_ids: list[int] = Field(default_factory=list)
    like_probability: int = 30
    view_feed: bool = True
    stories_limit: int = 0
    min_per_account: int = 50
    max_per_account: int = 50
    skip_seen: bool = True
    skip_hours: int = 24
    delay_min: int = 2
    delay_max: int = 6
    join_delay_min: int = 1200
    join_delay_max: int = 2400
    max_per_hour: int = 30
    respect_night_hours: bool = True
    limit_rate: bool = True
    require_proxy: bool = False
    hide_in_work: bool = False
    include_joined: bool = False
    blacklisted_account_ids: list[int] = Field(default_factory=list)
    presets: list[dict[str, Any]] = Field(default_factory=list)
    enabled: Optional[bool] = None
    warmup_enabled: Optional[bool] = None


class MasslookingModuleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool
    warmup_enabled: bool = False
    settings: dict[str, Any]
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    chats: list[dict[str, Any]] = Field(default_factory=list)
    folders: list[dict[str, Any]] = Field(default_factory=list)
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)


class MasslookingPresetRequest(BaseModel):
    name: str = ""


class MassprimingSettings(BaseModel):
    account_ids: list[int] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)
    user_folder_ids: list[int] = Field(default_factory=list)
    add_contact: bool = True
    ttl_mode: str = "toggle"
    ttl_period: int = 86400
    skip_seen: bool = True
    skip_hours: int = 72
    min_per_account: int = 20
    max_per_account: int = 20
    max_per_hour: int = 8
    delay_min: int = 8
    delay_max: int = 25
    respect_night_hours: bool = True
    limit_rate: bool = True
    skip_quarantine: bool = True
    require_proxy: bool = False
    hide_in_work: bool = False
    include_joined: bool = False
    blacklisted_account_ids: list[int] = Field(default_factory=list)
    presets: list[dict[str, Any]] = Field(default_factory=list)
    enabled: Optional[bool] = None
    warmup_enabled: Optional[bool] = None


class MassprimingModuleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool
    warmup_enabled: bool = False
    settings: dict[str, Any]
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)


class MassprimingPresetRequest(BaseModel):
    name: str = ""


class ParserSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    account_ids: list[int] = Field(default_factory=list)
    chat_ids: list[int] = Field(default_factory=list)
    folder_ids: list[int] = Field(default_factory=list)
    chat_assignments: dict[str, list[int]] = Field(default_factory=dict)
    reserve_chat_ids: list[int] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)
    source: str = "messages"
    do_join: bool = True
    since_hours: int = 24
    member_limit: int = 1000
    skip_bots: bool = True
    skip_deleted: bool = True
    skip_scam: bool = False
    only_username: bool = False
    only_photo: bool = False
    only_premium: bool = False
    only_admins: bool = False
    only_active_stories: bool = False
    delay_chat: int = 5
    delay_user: int = 1
    min_per_account: int = 100
    max_per_account: int = 100
    join_delay_min: int = 1200
    join_delay_max: int = 2400
    respect_night_hours: bool = True
    limit_rate: bool = True
    require_proxy: bool = False
    hide_in_work: bool = False
    include_joined: bool = False
    blacklisted_account_ids: list[int] = Field(default_factory=list)
    presets: list[dict[str, Any]] = Field(default_factory=list)
    enabled: Optional[bool] = None


class ParserModuleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool
    settings: dict[str, Any]
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    chats: list[dict[str, Any]] = Field(default_factory=list)
    folders: list[dict[str, Any]] = Field(default_factory=list)
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)
    results_total: int = 0
    summary: dict[str, Any] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)


class ParserPresetRequest(BaseModel):
    name: str = ""


class ParserTargetsRequest(BaseModel):
    links: str = ""


class ChatBroadcastsSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    account_ids: list[int] = Field(default_factory=list)
    chat_ids: list[int] = Field(default_factory=list)
    folder_ids: list[int] = Field(default_factory=list)
    chat_assignments: dict[str, list[int]] = Field(default_factory=dict)
    reserve_chat_ids: list[int] = Field(default_factory=list)
    only_joined: bool = True
    messages: list[dict[str, Any]] = Field(default_factory=list)
    first_mode: str = "template"
    skip_errors: bool = True
    skip_sent: bool = False
    scenario: str = "loop"
    limit_rate: bool = True
    respect_night_hours: bool = True
    imitate_typing: bool = True
    warmup_slow: bool = True
    work_mode: str = "count"
    max_messages: int = 100
    max_per_account: int = 15
    delay_group_min: int = 30
    delay_group_max: int = 90
    comment_delay_min: int = 1200
    comment_delay_max: int = 2400
    join_delay_min: int = 1200
    join_delay_max: int = 2400
    delay_msg_min: int = 3
    delay_msg_max: int = 8
    errors_until_stop: int = 10
    weekdays: list[int] = Field(default_factory=list)
    work_hour_start: Optional[int] = None
    work_hour_end: Optional[int] = None
    end_at: str = ""
    require_proxy: bool = False
    hide_in_work: bool = False
    include_joined: bool = False
    blacklisted_account_ids: list[int] = Field(default_factory=list)
    presets: list[dict[str, Any]] = Field(default_factory=list)
    enabled: Optional[bool] = None
    warmup_enabled: Optional[bool] = None


class ChatBroadcastsModuleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool
    warmup_enabled: bool = False
    settings: dict[str, Any]
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    chats: list[dict[str, Any]] = Field(default_factory=list)
    folders: list[dict[str, Any]] = Field(default_factory=list)
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    blacklist: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    added_ids: list[int] = Field(default_factory=list)
    add_errors: list[str] = Field(default_factory=list)


class ChatBroadcastsGroupsRequest(BaseModel):
    links: str = ""


class ChatBroadcastsPresetRequest(BaseModel):
    name: str = ""


class DmBroadcastsSettings(BaseModel):
    account_ids: list[int] = Field(default_factory=list)
    recipients: list[str] = Field(default_factory=list)
    user_folder_ids: list[int] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    first_mode: str = "template"
    skip_errors: bool = True
    skip_sent: bool = False
    limit_rate: bool = True
    respect_night_hours: bool = True
    work_mode: str = "count"
    max_messages: int = 100
    min_per_account: int = 15
    max_per_account: int = 15
    comment_delay_min: int = 1200
    comment_delay_max: int = 2400
    delay_peer_min: int = 30
    delay_peer_max: int = 90
    delay_msg_min: int = 3
    delay_msg_max: int = 8
    errors_until_stop: int = 10
    end_at: str = ""
    require_proxy: bool = False
    hide_in_work: bool = False
    include_joined: bool = False
    blacklisted_account_ids: list[int] = Field(default_factory=list)
    presets: list[dict[str, Any]] = Field(default_factory=list)
    enabled: Optional[bool] = None


class DmBroadcastsModuleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool
    settings: dict[str, Any]
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    added_ids: list[str] = Field(default_factory=list)
    add_errors: list[str] = Field(default_factory=list)


class DmBroadcastsRecipientsRequest(BaseModel):
    recipients: str = ""
    links: str = ""


class DmBroadcastsPresetRequest(BaseModel):
    name: str = ""


class NeuroshillingSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    account_ids: list[int] = Field(default_factory=list)
    chat_ids: list[int] = Field(default_factory=list)
    folder_ids: list[int] = Field(default_factory=list)
    chat_assignments: dict[str, list[int]] = Field(default_factory=dict)
    reserve_chat_ids: list[int] = Field(default_factory=list)
    channel_ids: list[int] = Field(default_factory=list)
    chat_shilling: bool = True
    post_shilling: bool = True
    unique_messages: bool = True
    skip_fresh: bool = True
    require_proxy: bool = False
    hide_in_work: bool = False
    include_joined: bool = False
    delay_min: int = 8
    delay_max: int = 25
    max_per_account: int = 15
    comment_delay_min: int = 1200
    comment_delay_max: int = 2400
    join_delay_min: int = 1200
    join_delay_max: int = 2400
    prompt_id: Optional[int] = None
    setup: Optional[str] = None
    reply: Optional[str] = None
    blacklisted_account_ids: list[int] = Field(default_factory=list)
    presets: list[dict[str, Any]] = Field(default_factory=list)
    enabled: Optional[bool] = None
    warmup_enabled: Optional[bool] = None


class NeuroshillingModuleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool
    warmup_enabled: bool = False
    settings: dict[str, Any]
    setup: str = ""
    reply: str = ""
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    chats: list[dict[str, Any]] = Field(default_factory=list)
    folders: list[dict[str, Any]] = Field(default_factory=list)
    prompts: list[dict[str, Any]] = Field(default_factory=list)
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    blacklist: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    added_ids: list[int] = Field(default_factory=list)
    add_errors: list[str] = Field(default_factory=list)
    check: Optional[dict[str, Any]] = None


class NeuroshillingTargetsRequest(BaseModel):
    links: str = ""
    kind: str = "auto"


class NeuroshillingPresetRequest(BaseModel):
    name: str = ""


class NeuroshillingGenerateRequest(BaseModel):
    topic: str = ""


class WarmupSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    account_ids: list[int] = Field(default_factory=list)
    chat_ids: list[int] = Field(default_factory=list)
    folder_ids: list[int] = Field(default_factory=list)
    chat_assignments: dict[str, list[int]] = Field(default_factory=dict)
    reserve_chat_ids: list[int] = Field(default_factory=list)
    mode: str = "auto"
    intensity: str = "auto"
    do_warmup_dms: bool = True
    do_peer_dialogs: bool = True
    do_reactions: bool = True
    do_read_channels: bool = True
    do_stories: bool = True
    do_comment_contacts: bool = True
    do_joins: bool = True
    join_delay_min: int = 1200
    join_delay_max: int = 2400
    session_minutes: int = 0
    require_proxy: bool = False
    hide_in_work: bool = False
    include_joined: bool = False
    blacklisted_account_ids: list[int] = Field(default_factory=list)
    presets: list[dict[str, Any]] = Field(default_factory=list)
    enabled: Optional[bool] = None
    usernames: Optional[list[str]] = None
    messages: Optional[list[str]] = None


class WarmupModuleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool
    is_admin: bool = False
    settings: dict[str, Any]
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    chats: list[dict[str, Any]] = Field(default_factory=list)
    folders: list[dict[str, Any]] = Field(default_factory=list)
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    username_count: int = 0
    usernames: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    stages: dict[str, int] = Field(default_factory=dict)
    added_ids: list[int] = Field(default_factory=list)
    add_errors: list[str] = Field(default_factory=list)


class WarmupTargetsRequest(BaseModel):
    links: str = ""


class WarmupPresetRequest(BaseModel):
    name: str = ""


class NeuroblogModuleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = False
    settings: dict[str, Any] = Field(default_factory=dict)
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    channels: list[dict[str, Any]] = Field(default_factory=list)
    posts: list[dict[str, Any]] = Field(default_factory=list)
    logs: list[dict[str, Any]] = Field(default_factory=list)
    next_slots: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    themes: list[dict[str, str]] = Field(default_factory=list)
    text_providers: list[dict[str, Any]] = Field(default_factory=list)
    image_providers: list[dict[str, Any]] = Field(default_factory=list)
    text_models: list[str] = Field(default_factory=list)
    image_models: list[dict[str, str]] = Field(default_factory=list)


class NeuroblogSaveRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    custom_automation_id: int
    chat_target_id: int
    external_message_id: str
    external_chat_id: str
    sender_id: Optional[str] = None
    sender_username: Optional[str] = None
    sender_name: Optional[str] = None
    text: str
    sent_at: datetime
    dedup_key: Optional[str] = None
    is_processed: bool
    is_duplicate: bool
    matched_intent: Optional[str] = None
    trigger_confidence: Optional[float] = None
    created_at: datetime


class ChatMessageListResponse(BaseModel):
    items: list[ChatMessageResponse]
    total: int


class CustomLeadMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    custom_lead_id: int
    social_account_id: Optional[int] = None
    direction: str
    text: str
    external_message_id: Optional[str] = None
    sent_at: datetime
    created_at: datetime


class CustomLeadMessageListResponse(BaseModel):
    items: list[CustomLeadMessageResponse]
    total: int


class CustomLeadStatusUpdate(BaseModel):
    status: str


class CustomLeadTransferResponse(BaseModel):
    lead_id: int
    status: str
    transferred_at: datetime


class CustomLeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    custom_automation_id: int
    source: str
    contact_type: str
    contact_value: str
    full_name: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    status: str
    assigned_account_id: Optional[int] = None
    chat_message_id: Optional[int] = None
    dmp_raw_data: Optional[dict[str, Any]] = None
    last_message_at: Optional[datetime] = None
    transferred_at: Optional[datetime] = None
    status_history: Optional[list] = None
    sasha_status: Optional[str] = None
    sasha_uploaded_at: Optional[datetime] = None
    sasha_last_event_at: Optional[datetime] = None
    sasha_lead_quality: Optional[int] = None
    sasha_is_commit: bool = False
    sasha_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CustomLeadListResponse(BaseModel):
    items: list[CustomLeadResponse]
    total: int


class AccountWarmupStartResponse(BaseModel):
    account_warmup_enabled: bool
    account_warmup_usernames: list[str] = Field(default_factory=list)


class TestLabChatPayload(BaseModel):
    id: int
    title: Optional[str] = None
    username: Optional[str] = None
    chat_type: Optional[str] = None
    join_status: Optional[str] = None
    last_join_error: Optional[str] = None
    joined_accounts: Optional[int] = None
    total_accounts: Optional[int] = None


class TestLabWatchPayload(BaseModel):
    ok: bool = False
    status: str = "idle"
    detail: str = ""
    activity: Optional[str] = None
    seconds_left: int = 0
    post_id: Optional[int] = None


class TestLabResponse(BaseModel):
    channel_username: str = ""
    chat_username: str = ""
    channel: Optional[TestLabChatPayload] = None
    chat: Optional[TestLabChatPayload] = None
    watch: Optional[TestLabWatchPayload] = None


class TestLabUpdate(BaseModel):
    channel_username: Optional[str] = None
    chat_username: Optional[str] = None


class TestLabJoinRequest(BaseModel):
    channel_username: Optional[str] = None
    chat_username: Optional[str] = None


class TestLabChannelActivityRequest(BaseModel):
    activity: str = Field(..., min_length=3, max_length=32)


class TestLabActionResponse(BaseModel):
    ok: bool
    status: str
    detail: str
    activity: Optional[str] = None
    seconds_left: Optional[int] = None
    post_id: Optional[int] = None


class TestLabDmpRequest(BaseModel):
    phone: str = Field(..., min_length=5, max_length=32)


class ContentFactorySettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    sandbox_mode: Optional[bool] = None
    product_name: Optional[str] = Field(None, max_length=200)
    product_description: Optional[str] = None
    product_url: Optional[str] = Field(None, max_length=512)
    cta_text: Optional[str] = Field(None, max_length=200)
    audience: Optional[str] = None
    niche: Optional[str] = Field(None, max_length=128)
    content_formats: Optional[list[str]] = None
    visual_styles: Optional[list[str]] = None
    language: Optional[str] = Field(None, max_length=16)
    tone: Optional[str] = Field(None, max_length=64)
    brand_voice: Optional[str] = None
    forbidden_topics: Optional[str] = None
    videos_per_day: Optional[float] = Field(None, ge=0.2, le=8)
    duration_min: Optional[int] = Field(None, ge=8, le=90)
    duration_max: Optional[int] = Field(None, ge=8, le=120)
    aspect_ratio: Optional[str] = Field(None, max_length=16)
    posting_window_start: Optional[str] = Field(None, max_length=8)
    posting_window_end: Optional[str] = Field(None, max_length=8)
    timezone: Optional[str] = Field(None, max_length=64)
    idea_model: Optional[str] = Field(None, max_length=128)
    script_model: Optional[str] = Field(None, max_length=128)
    video_model: Optional[str] = Field(None, max_length=128)
    tts_model: Optional[str] = Field(None, max_length=128)
    tts_voice: Optional[str] = Field(None, max_length=64)
    carousel_share: Optional[int] = Field(None, ge=0, le=100)
    image_provider: Optional[str] = Field(None, max_length=32)
    image_model: Optional[str] = Field(None, max_length=128)
    xai_api_key: Optional[str] = None
    clear_xai_api_key: Optional[bool] = None
    music_mode: Optional[str] = Field(None, max_length=16)
    music_volume: Optional[int] = Field(None, ge=0, le=100)
    grok_bot_name: Optional[str] = Field(None, max_length=80)
    grok_bot_brief: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    kling_api_key: Optional[str] = None
    runway_api_key: Optional[str] = None
    luma_api_key: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    clear_openai_api_key: Optional[bool] = None
    clear_anthropic_api_key: Optional[bool] = None
    clear_kling_api_key: Optional[bool] = None
    clear_runway_api_key: Optional[bool] = None
    clear_luma_api_key: Optional[bool] = None
    clear_elevenlabs_api_key: Optional[bool] = None
    warmup_days: Optional[int] = Field(None, ge=1, le=30)
    warmup_actions_per_day: Optional[int] = Field(None, ge=2, le=20)
    max_posts_per_account_per_day: Optional[int] = Field(None, ge=1, le=8)
    stagger_min_minutes: Optional[int] = Field(None, ge=5, le=240)
    uniqualize_enabled: Optional[bool] = None
    unique_per_platform: Optional[bool] = None
    hook_required: Optional[bool] = None
    avoid_exact_hour: Optional[bool] = None
    shadowban_pause_zero_views: Optional[bool] = None
    shadowban_zero_views_threshold: Optional[int] = Field(None, ge=2, le=10)


class ContentFactoryAccountConnectRequest(BaseModel):
    platform: str = Field(..., min_length=3, max_length=32)
    display_name: str = Field("", max_length=200)
    handle: str = Field("", max_length=128)
    external_id: str = Field("", max_length=191)
    credentials: dict[str, str] = Field(default_factory=dict)


class ContentFactoryAccountUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, max_length=200)
    handle: Optional[str] = Field(None, max_length=128)
    external_id: Optional[str] = Field(None, max_length=191)
    is_enabled: Optional[bool] = None
    credentials: Optional[dict[str, str]] = None
    pause: Optional[bool] = None
    resume: Optional[bool] = None


class ContentFactoryGrokBotRequest(BaseModel):
    grok_bot_name: Optional[str] = Field(None, max_length=80)
    grok_bot_brief: Optional[str] = None
    xai_api_key: Optional[str] = None


class ContentFactoryYoutubeOauthStartRequest(BaseModel):
    return_url: Optional[str] = Field(None, max_length=512)

