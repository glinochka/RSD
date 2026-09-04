"""Pydantic schemas for /custom API."""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict


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
    by_class: dict[str, int]


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
    amocrm_redirect_uri: str | None = None
    telegram_bot_token_set: bool = False
    telegram_bot_username: str | None = None
    telegram_bot_webhook_url: str | None = None
    telegram_bot_subscribers: int = 0
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
    proxy_distribution: list[ProxyDistributionItem] = Field(default_factory=list)


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
    lead_manager_contact: str | None = None
    partner_utm_url: str | None = None
    partner_promo_code: str | None = None
    conversion_check_url: str | None = None
    status: str | None = None
    account_warmup_usernames: list[str] | None = None
    account_warmup_messages: list[str] | None = None
    account_warmup_enabled: bool | None = None
    proxy_list_text: str | None = None


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
    assigned_class: Optional[str] = Field(default=None, min_length=1, max_length=32)
    roles: Optional[list[str]] = None
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    bio: Optional[str] = Field(default=None, max_length=140)


class AccountQrStartRequest(BaseModel):
    assign_class: str = Field(default="one_day", min_length=1, max_length=32)


class AccountQrStatusRequest(BaseModel):
    auth_token: str = Field(..., min_length=20, max_length=16384)


class AccountQrVerify2faRequest(BaseModel):
    auth_token: str = Field(..., min_length=20, max_length=16384)
    password: str = Field(..., min_length=1, max_length=128)


class AccountSmsRequest(BaseModel):
    phone_number: str = Field(..., min_length=5, max_length=32)
    assign_class: str = Field(default="one_day", min_length=1, max_length=32)


class AccountSmsVerifyRequest(BaseModel):
    auth_token: str = Field(..., min_length=20, max_length=16384)
    code: str = Field(..., min_length=3, max_length=12)
    password: str | None = Field(default=None, max_length=128)


class AccountSmsStartResponse(BaseModel):
    auth_token: str


class AccountBulkUpdateProfilesRequest(BaseModel):
    account_ids: list[int] = []
    account_class: str | None = None
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
    account_class: str
    assigned_class: str
    roles: list[str] = Field(default_factory=list)
    warmup_status: str = "idle"
    warmup_started_at: Optional[datetime] = None
    warmup_dialog_count: int = 0
    status: str
    is_active: bool
    is_banned: bool
    is_spamblocked: bool = False
    auto_classified: bool = False
    risk_score: Optional[float] = None
    trust_score: Optional[float] = None
    session_file_path: Optional[str] = None
    daily_messages_sent: int = 0
    daily_messages_reset_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    max_daily_messages_per_account: int = 50
    added_at: datetime
    last_health_check_at: Optional[datetime] = None
    spamblock_checked_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    proxy_label: Optional[str] = None


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


class AccountPrepareStatusResponse(BaseModel):
    status: str
    alive: int = 0
    profiles_done: int = 0
    chats_joined: int = 0
    error: Optional[str] = None


class AccountSetupTemplatesResponse(BaseModel):
    templates: dict[str, Any] = {}


class AccountSetupTemplateUpdate(BaseModel):
    account_class: str = Field(..., min_length=1, max_length=32)
    bio_template: str = ""
    generate_unique: bool = False


class AccountBanStatsResponse(BaseModel):
    total: int
    active: int
    banned: int
    revoked: int = 0
    spamblocked: int = 0
    banned_percent: float
    alert_threshold: float = 0.3
    alert: bool


class ChatTargetCreate(BaseModel):
    provider: str = "telegram"
    invite_link: str = Field(..., min_length=1, max_length=512)
    mode: str = "monitoring"
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


class TelegramBotSettingsUpdate(BaseModel):
    bot_token: Optional[str] = None
    disconnect: bool = False


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
    neurocommenting_config: Optional[dict] = None
    discussion_config: Optional[dict] = None
    shilling_config: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class ChatTargetListResponse(BaseModel):
    items: list[ChatTargetResponse]
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
    error_log: list = []
    created_at: datetime
    updated_at: datetime


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
    last_message_at: Optional[datetime] = None
    transferred_at: Optional[datetime] = None
    status_history: Optional[list] = None
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
