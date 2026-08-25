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


class CustomAutomationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    client_name: Optional[str] = Field(None, max_length=200)
    industry: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = None
    status: Optional[str] = Field(None, max_length=32)


class CustomAutomationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    client_name: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class CustomAutomationListResponse(BaseModel):
    items: list[CustomAutomationResponse]
    total: int


class CustomAutomationSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: int
    name: str
    rotation_strategy: str
    max_daily_messages_per_account: int
    is_chat_monitoring_enabled: bool
    is_neurocommenting_enabled: bool
    is_digital_footprint_enabled: bool
    is_dmp_one_enabled: bool
    is_amocrm_enabled: bool
    is_shilling_enabled: bool
    lead_manager_contact: str | None = None
    status: str = "draft"
    warnings: list[str] = []
    dmp_webhook_url: str | None = None
    dmp_webhook_secret: str | None = None
    amocrm_redirect_uri: str | None = None


class CustomAutomationSettingsValidationResponse(BaseModel):
    warnings: list[str]
    can_enable: dict[str, bool]
    counts: dict[str, int]


class CustomAutomationSettingsUpdate(BaseModel):
    rotation_strategy: str | None = None
    max_daily_messages_per_account: int | None = None
    is_chat_monitoring_enabled: bool | None = None
    is_neurocommenting_enabled: bool | None = None
    is_digital_footprint_enabled: bool | None = None
    is_dmp_one_enabled: bool | None = None
    is_amocrm_enabled: bool | None = None
    is_shilling_enabled: bool | None = None
    lead_manager_contact: str | None = None
    status: str | None = None


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
    assigned_class: str = Field(..., min_length=1, max_length=32)


class AccountBulkUpdateProfilesRequest(BaseModel):
    account_ids: list[int] = []
    account_class: str | None = None
    status: str | None = None
    bio_template: str = ""
    generate_unique: bool = False


class AccountBulkUpdateProfilesResponse(BaseModel):
    queued: int


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    phone_number: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    account_class: str
    assigned_class: str
    status: str
    is_active: bool
    is_banned: bool
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


class AccountBanStatsResponse(BaseModel):
    total: int
    active: int
    banned: int
    banned_percent: float
    alert_threshold: float = 0.3
    alert: bool


class ChatTargetCreate(BaseModel):
    provider: str = "telegram"
    external_chat_id: Optional[str] = None
    invite_link: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    chat_type: Optional[str] = None
    mode: str = "monitoring"


class ChatTargetUpdate(BaseModel):
    mode: Optional[str] = None
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


class CustomPromptListResponse(BaseModel):
    items: list[CustomPromptResponse]


class CustomPromptUpdate(BaseModel):
    content: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    is_active: Optional[bool] = None


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
    error_log: list = []
    created_at: datetime
    updated_at: datetime


class ChatImportJobListResponse(BaseModel):
    items: list[ChatImportJobResponse]
    total: int


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
