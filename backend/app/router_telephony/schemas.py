from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TelephonyWebhookAuthRequest(BaseModel):
    connection_id: int = Field(..., gt=0)


class TelephonyWebhookAuthResponse(BaseModel):
    connection_id: int
    webhook_secret: str
    phone_number_e164: str
    is_active: bool


class TelephonyResolveRequest(BaseModel):
    connection_id: int = Field(..., gt=0)
    caller_e164: str = Field(..., min_length=8, max_length=32)
    call_id: str | None = Field(default=None, max_length=191)


class TelephonyResolveResponse(BaseModel):
    agent_id: int
    connection_id: int
    call_id: str | None = None
    system_prompt: str
    welcome_message: str | None
    template_type: str
    template_config: dict[str, Any] | None
    voice_id: str
    language: str
    record_calls: bool
    disclaimer_played: bool
    operator_transfer_e164: str
    phone_number_e164: str


class TelephonyCallEventRequest(BaseModel):
    connection_id: int = Field(..., gt=0)
    external_call_id: str = Field(..., min_length=1, max_length=191)
    caller_e164: str = Field(..., min_length=8, max_length=32)
    event: Literal[
        "call.inbound",
        "call.answered",
        "call.recording_ready",
        "call.hangup",
        "dtmf",
    ]
    status: Literal["ringing", "active", "completed", "failed", "transferred"] | None = None
    recording_url: str | None = None
    duration_sec: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] | None = None


class TelephonyCallEventResponse(BaseModel):
    call_db_id: int
    status: str
    created: bool


class TelephonyPartialRequest(BaseModel):
    connection_id: int = Field(..., gt=0)
    call_db_id: int = Field(..., gt=0)
    caller_e164: str = Field(..., min_length=8, max_length=32)
    transcript: str = Field(default="", max_length=8192)
    is_final: bool = False
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    turn_index: int | None = Field(default=None, ge=0)


class TelephonyPartialResponse(BaseModel):
    accepted: bool = True
    transcript: str = ""
    partial_count: int = 0
    is_final: bool = False
    suggest_backchannel: bool = False


class TelephonyTurnRequest(BaseModel):
    connection_id: int = Field(..., gt=0)
    call_db_id: int = Field(..., gt=0)
    caller_e164: str = Field(..., min_length=8, max_length=32)
    user_transcript: str | None = None
    audio_base64: str | None = None
    recording_url: str | None = Field(default=None, max_length=4096)
    turn_index: int | None = Field(default=None, ge=0)
    streaming: bool | None = None
    barged_in: bool = False
    interrupted_agent_text: str | None = Field(default=None, max_length=2048)
    dtmf_digit: str | None = Field(default=None, max_length=1)


class TelephonyCancelRequest(BaseModel):
    connection_id: int = Field(..., gt=0)
    call_db_id: int = Field(..., gt=0)


class TelephonyCancelResponse(BaseModel):
    cancelled: bool = False


class TelephonyTurnResponse(BaseModel):
    reply_text: str = ""
    reply_chunks: list[str] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    stage: str = "ok"
    latency_ms: int | None = None
    play_filler: bool = False
    partial_stt_count: int | None = None
    dialog_state: str | None = None
    use_ssml: bool = False


class TelephonyMetricsResponse(BaseModel):
    calls_started: int
    calls_completed: int
    turn_latency_p95_ms: float | None
    transfer_rate: float
    stt_empty_rate: float
    turn_samples: int
    alerts: list[dict[str, Any]] = Field(default_factory=list)


class TelephonyRetentionPurgeResponse(BaseModel):
    deleted: int
    retention_days: int
    cutoff: str
