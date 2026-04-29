"""Domain booking tool registry with validation and idempotency controls."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import time
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator

from .service import get_admin_booking_service

_IDEMPOTENCY_TTL_SECONDS = 120
_IDEMPOTENCY_CACHE: dict[str, tuple[datetime, dict[str, Any]]] = {}
_MAX_RAW_ARGUMENTS_BYTES = 16_000

_READ_ONLY_TOOLS = {"check_availability", "list_staff", "list_services", "list_appointments"}
_HIGH_RISK_TOOLS = {
    "create_appointment",
    "reschedule_appointment",
    "cancel_appointment",
    "confirm_appointment",
}


class AdminBookingNeedsConfirmationError(RuntimeError):
    pass


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _cleanup_idempotency_cache() -> None:
    now = _now_utc()
    expired = [key for key, (expires_at, _) in _IDEMPOTENCY_CACHE.items() if expires_at <= now]
    for key in expired:
        _IDEMPOTENCY_CACHE.pop(key, None)


def _has_confirmation_marker(user_message: str) -> bool:
    text = (user_message or "").strip().lower()
    if not text:
        return False
    markers = {"подтверждаю", "подтвердить", "confirm", "подтверждено", "ok, выполняй", "выполняй"}
    return any(marker in text for marker in markers)


def _parse_iso_datetime(raw: str) -> datetime:
    normalized = str(raw or "").strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


class _ListStaffArgs(BaseModel):
    role: str | None = Field(default=None, pattern="^(master|doctor)$")
    active_only: bool = Field(default=True)


class _ListServicesArgs(BaseModel):
    target_role: str | None = Field(default=None, pattern="^(master|doctor)$")
    active_only: bool = Field(default=True)


class _CheckAvailabilityArgs(BaseModel):
    starts_at: str = Field(..., min_length=16, max_length=40)
    ends_at: str = Field(..., min_length=16, max_length=40)
    staff_id: int | None = Field(default=None, gt=0)
    resource_id: int | None = Field(default=None, gt=0)
    service_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _validate_window(self):
        starts = _parse_iso_datetime(self.starts_at)
        ends = _parse_iso_datetime(self.ends_at)
        if ends <= starts:
            raise ValueError("ends_at must be greater than starts_at")
        return self


class _CreateAppointmentArgs(BaseModel):
    starts_at: str = Field(..., min_length=16, max_length=40)
    ends_at: str = Field(..., min_length=16, max_length=40)
    staff_id: int | None = Field(default=None, gt=0)
    resource_id: int | None = Field(default=None, gt=0)
    service_id: int | None = Field(default=None, gt=0)
    client_name: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _validate_targets_and_window(self):
        if self.staff_id is None and self.resource_id is None:
            raise ValueError("staff_id or resource_id is required")
        starts = _parse_iso_datetime(self.starts_at)
        ends = _parse_iso_datetime(self.ends_at)
        if ends <= starts:
            raise ValueError("ends_at must be greater than starts_at")
        return self


class _RescheduleAppointmentArgs(BaseModel):
    appointment_id: int = Field(..., gt=0)
    starts_at: str = Field(..., min_length=16, max_length=40)
    ends_at: str = Field(..., min_length=16, max_length=40)
    staff_id: int | None = Field(default=None, gt=0)
    resource_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _validate_window(self):
        starts = _parse_iso_datetime(self.starts_at)
        ends = _parse_iso_datetime(self.ends_at)
        if ends <= starts:
            raise ValueError("ends_at must be greater than starts_at")
        return self


class _CancelAppointmentArgs(BaseModel):
    appointment_id: int = Field(..., gt=0)
    reason: str | None = Field(default=None, max_length=1000)


class _ConfirmAppointmentArgs(BaseModel):
    appointment_id: int = Field(..., gt=0)


class _ListAppointmentsArgs(BaseModel):
    starts_at: str | None = Field(default=None, min_length=16, max_length=40)
    ends_at: str | None = Field(default=None, min_length=16, max_length=40)
    staff_id: int | None = Field(default=None, gt=0)
    resource_id: int | None = Field(default=None, gt=0)
    service_id: int | None = Field(default=None, gt=0)
    client_external_id: str | None = Field(default=None, min_length=1, max_length=128)
    status: str | None = Field(
        default=None,
        pattern="^(pending_confirmation|booked|confirmed|in_progress|completed|cancelled|no_show)$",
    )

    @model_validator(mode="after")
    def _validate_window(self):
        if self.starts_at and self.ends_at:
            starts = _parse_iso_datetime(self.starts_at)
            ends = _parse_iso_datetime(self.ends_at)
            if ends <= starts:
                raise ValueError("ends_at must be greater than starts_at")
        return self


_TOOL_MODELS: dict[str, type[BaseModel]] = {
    "check_availability": _CheckAvailabilityArgs,
    "create_appointment": _CreateAppointmentArgs,
    "reschedule_appointment": _RescheduleAppointmentArgs,
    "cancel_appointment": _CancelAppointmentArgs,
    "confirm_appointment": _ConfirmAppointmentArgs,
    "list_appointments": _ListAppointmentsArgs,
    "list_staff": _ListStaffArgs,
    "list_services": _ListServicesArgs,
}

_TOOL_DESCRIPTIONS = {
    "check_availability": "Check available booking slots for requested period. Use a wide window (e.g. full day 00:00-23:59) to discover all schedule slots, then narrow down. Returns only slots with actual staff schedule entries.",
    "create_appointment": "Create booking appointment for selected slot/staff/resource.",
    "reschedule_appointment": "Reschedule existing appointment to a new time.",
    "cancel_appointment": "Cancel existing appointment by id.",
    "confirm_appointment": "Confirm existing appointment by id.",
    "list_appointments": "List appointments by period/client/staff/status filters.",
    "list_staff": "List staff members available for booking.",
    "list_services": "List available services for booking.",
}


class AdminBookingToolRegistry:
    def __init__(
        self,
        *,
        agent_id: int,
        user_external_id: str | None,
        source_channel: str,
        confirmation_policy: str,
        user_message: str,
        allowed_tools: list[str] | None = None,
    ) -> None:
        requested = [str(tool or "").strip() for tool in (allowed_tools or [])]
        unique = []
        for tool in requested:
            if tool and tool in _TOOL_MODELS and tool not in unique:
                unique.append(tool)
        self._allowed_tools = unique or list(_TOOL_MODELS.keys())
        self._agent_id = agent_id
        self._user_external_id = (user_external_id or "").strip() or "anonymous"
        self._source_channel = (source_channel or "telegram").strip().lower() or "telegram"
        self._confirmation_policy = (confirmation_policy or "confirm_risky").strip().lower()
        self._user_message = user_message or ""

    def tools_for_llm(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for name in self._allowed_tools:
            model = _TOOL_MODELS[name]
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": _TOOL_DESCRIPTIONS[name],
                        "parameters": model.model_json_schema(),
                    },
                }
            )
        return tools

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self._allowed_tools

    def _requires_confirmation(self, tool_name: str) -> bool:
        policy = self._confirmation_policy
        if policy == "never_confirm":
            return False
        if policy == "always_confirm":
            return tool_name not in _READ_ONLY_TOOLS
        return tool_name in _HIGH_RISK_TOOLS

    @staticmethod
    def _canonical_args(model: BaseModel) -> str:
        return json.dumps(model.model_dump(), ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _tool_args_hash(canonical_args: str) -> str:
        return hashlib.sha256(canonical_args.encode("utf-8")).hexdigest()

    def _idempotency_key(self, tool_name: str, canonical_args: str) -> str:
        raw = f"{self._agent_id}:{self._user_external_id}:{tool_name}:{canonical_args}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def execute_tool(self, tool_name: str, raw_arguments: str) -> dict[str, Any]:
        if len((raw_arguments or "").encode("utf-8")) > _MAX_RAW_ARGUMENTS_BYTES:
            raise RuntimeError("Tool arguments payload is too large")
        if tool_name not in self._allowed_tools:
            raise RuntimeError(f"Tool '{tool_name}' is not allowed")
        model_type = _TOOL_MODELS.get(tool_name)
        if not model_type:
            raise RuntimeError(f"Tool '{tool_name}' is not implemented")
        try:
            payload = json.loads(raw_arguments or "{}")
        except Exception as exc:
            raise RuntimeError(f"Invalid JSON arguments for tool '{tool_name}': {exc}")
        try:
            args = model_type.model_validate(payload)
        except ValidationError as exc:
            raise RuntimeError(f"Validation failed for tool '{tool_name}': {exc}")

        canonical_args = self._canonical_args(args)
        tool_args_hash = self._tool_args_hash(canonical_args)
        _cleanup_idempotency_cache()
        idempotency_key = self._idempotency_key(tool_name, canonical_args)
        cached = _IDEMPOTENCY_CACHE.get(idempotency_key)
        if cached:
            _, value = cached
            return {
                "ok": True,
                "tool_name": tool_name,
                "tool_args_hash": tool_args_hash,
                "tool_status": "success",
                "crm_provider": "booking",
                "latency_ms": 0,
                "idempotent_replay": True,
                "idempotency_key": idempotency_key,
                "result": value,
            }

        data = args.model_dump()
        started = time.perf_counter()
        service = get_admin_booking_service()

        if tool_name == "list_staff":
            result = await service.list_staff(
                agent_id=self._agent_id,
                role=data.get("role"),
                active_only=bool(data.get("active_only", True)),
            )
        elif tool_name == "list_services":
            result = await service.list_services(
                agent_id=self._agent_id,
                target_role=data.get("target_role"),
                active_only=bool(data.get("active_only", True)),
            )
        elif tool_name == "check_availability":
            result = await service.list_available_slots(
                agent_id=self._agent_id,
                starts_at=_parse_iso_datetime(str(data.get("starts_at") or "")),
                ends_at=_parse_iso_datetime(str(data.get("ends_at") or "")),
                staff_id=data.get("staff_id"),
                resource_id=data.get("resource_id"),
                service_id=data.get("service_id"),
            )
        elif tool_name == "create_appointment":
            result = await service.create_appointment(
                agent_id=self._agent_id,
                client_external_id=self._user_external_id,
                starts_at=_parse_iso_datetime(str(data.get("starts_at") or "")),
                ends_at=_parse_iso_datetime(str(data.get("ends_at") or "")),
                staff_id=data.get("staff_id"),
                resource_id=data.get("resource_id"),
                service_id=data.get("service_id"),
                client_name=data.get("client_name"),
                source_channel=self._source_channel,
                notes=data.get("notes"),
            )
        elif tool_name == "reschedule_appointment":
            result = await service.reschedule_appointment(
                agent_id=self._agent_id,
                appointment_id=int(data["appointment_id"]),
                starts_at=_parse_iso_datetime(str(data.get("starts_at") or "")),
                ends_at=_parse_iso_datetime(str(data.get("ends_at") or "")),
                staff_id=data.get("staff_id"),
                resource_id=data.get("resource_id"),
            )
        elif tool_name == "cancel_appointment":
            result = await service.cancel_appointment(
                agent_id=self._agent_id,
                appointment_id=int(data["appointment_id"]),
                reason=data.get("reason"),
            )
        elif tool_name == "confirm_appointment":
            result = await service.confirm_appointment(
                agent_id=self._agent_id,
                appointment_id=int(data["appointment_id"]),
            )
        elif tool_name == "list_appointments":
            result = await service.list_appointments(
                agent_id=self._agent_id,
                starts_at=(
                    _parse_iso_datetime(str(data.get("starts_at") or ""))
                    if data.get("starts_at")
                    else None
                ),
                ends_at=(
                    _parse_iso_datetime(str(data.get("ends_at") or ""))
                    if data.get("ends_at")
                    else None
                ),
                staff_id=data.get("staff_id"),
                resource_id=data.get("resource_id"),
                service_id=data.get("service_id"),
                client_external_id=data.get("client_external_id"),
                status=data.get("status"),
            )
        else:
            raise RuntimeError(f"Tool '{tool_name}' is not supported")

        _IDEMPOTENCY_CACHE[idempotency_key] = (
            _now_utc() + timedelta(seconds=_IDEMPOTENCY_TTL_SECONDS),
            {"tool": tool_name, "result": result},
        )
        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        return {
            "ok": True,
            "tool_name": tool_name,
            "tool_args_hash": tool_args_hash,
            "tool_status": "success",
            "crm_provider": "booking",
            "latency_ms": latency_ms,
            "idempotency_key": idempotency_key,
            "result": result,
        }
