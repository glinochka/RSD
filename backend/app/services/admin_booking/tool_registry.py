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


class AdminBookingNeedsConfirmationError(RuntimeError):
    pass


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _cleanup_idempotency_cache() -> None:
    now = _now_utc()
    expired = [key for key, (expires_at, _) in _IDEMPOTENCY_CACHE.items() if expires_at <= now]
    for key in expired:
        _IDEMPOTENCY_CACHE.pop(key, None)


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
    """Reschedule an appointment to a new time.

    Provide ``appointment_id`` when known. Otherwise provide ``appointment_date``
    (ISO date "YYYY-MM-DD" or datetime "YYYY-MM-DDTHH:MM") so the system can
    look up the booking by the current user + date.
    ``lookup_staff_id`` narrows the lookup when the user has appointments with
    multiple staff on the same day.
    ``new_starts_at`` / ``new_ends_at`` are the desired new slot (ISO datetime).
    """

    appointment_id: int | None = Field(default=None, gt=0)
    appointment_date: str | None = Field(default=None, min_length=8, max_length=40)
    lookup_staff_id: int | None = Field(default=None, gt=0)
    new_starts_at: str = Field(..., min_length=16, max_length=40)
    new_ends_at: str = Field(..., min_length=16, max_length=40)
    new_staff_id: int | None = Field(default=None, gt=0)
    new_resource_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _validate(self):
        if self.appointment_id is None and not (self.appointment_date or "").strip():
            raise ValueError("Either appointment_id or appointment_date is required")
        starts = _parse_iso_datetime(self.new_starts_at)
        ends = _parse_iso_datetime(self.new_ends_at)
        if ends <= starts:
            raise ValueError("new_ends_at must be greater than new_starts_at")
        return self


class _CancelAppointmentArgs(BaseModel):
    """Cancel an appointment.

    Provide ``appointment_id`` when known. Otherwise provide ``appointment_date``
    (ISO date "YYYY-MM-DD" or datetime "YYYY-MM-DDTHH:MM") so the system can
    look up the booking by the current user + date.
    ``staff_id`` narrows the lookup when needed.
    """

    appointment_id: int | None = Field(default=None, gt=0)
    appointment_date: str | None = Field(default=None, min_length=8, max_length=40)
    staff_id: int | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _validate(self):
        if self.appointment_id is None and not (self.appointment_date or "").strip():
            raise ValueError("Either appointment_id or appointment_date is required")
        return self


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


class _FindNextAvailableArgs(BaseModel):
    duration_minutes: int = Field(default=30, gt=0, le=480)
    staff_id: int | None = Field(default=None, gt=0)
    resource_id: int | None = Field(default=None, gt=0)
    service_id: int | None = Field(default=None, gt=0)
    earliest_starts_at: str | None = Field(default=None, min_length=16, max_length=40)
    search_days_ahead: int = Field(default=7, gt=0, le=30)


def _fmt_dt(raw: str | None) -> str:
    if not raw:
        return "?"
    try:
        return str(raw)[:16].replace("T", " ")
    except Exception:
        return str(raw)


def _build_args_summary(tool_name: str, data: dict) -> str:
    if tool_name == "check_availability":
        parts = [f"{_fmt_dt(data.get('starts_at'))}→{_fmt_dt(data.get('ends_at'))}"]
        if data.get("staff_id"):
            parts.append(f"staff={data['staff_id']}")
        if data.get("resource_id"):
            parts.append(f"res={data['resource_id']}")
        return " ".join(parts)
    if tool_name == "create_appointment":
        parts = [f"{_fmt_dt(data.get('starts_at'))}→{_fmt_dt(data.get('ends_at'))}"]
        if data.get("staff_id"):
            parts.append(f"staff={data['staff_id']}")
        if data.get("client_name"):
            parts.append(f"client={data['client_name']}")
        return " ".join(parts)
    if tool_name == "find_next_available":
        parts = []
        if data.get("earliest_starts_at"):
            parts.append(f"from={_fmt_dt(data.get('earliest_starts_at'))}")
        if data.get("duration_minutes"):
            parts.append(f"{data['duration_minutes']}min")
        if data.get("staff_id"):
            parts.append(f"staff={data['staff_id']}")
        return " ".join(parts)
    if tool_name in ("cancel_appointment", "reschedule_appointment"):
        parts = []
        if data.get("appointment_date"):
            parts.append(f"date={_fmt_dt(data.get('appointment_date'))}")
        if data.get("new_starts_at"):
            parts.append(f"new={_fmt_dt(data.get('new_starts_at'))}")
        return " ".join(parts)
    return ""


_TOOL_MODELS: dict[str, type[BaseModel]] = {
    "check_availability": _CheckAvailabilityArgs,
    "create_appointment": _CreateAppointmentArgs,
    "reschedule_appointment": _RescheduleAppointmentArgs,
    "cancel_appointment": _CancelAppointmentArgs,
    "list_appointments": _ListAppointmentsArgs,
    "list_staff": _ListStaffArgs,
    "list_services": _ListServicesArgs,
    "find_next_available": _FindNextAvailableArgs,
}

_TOOL_DESCRIPTIONS = {
    "check_availability": (
        "Check available booking slots for a specific date or period. "
        "Always use a full-day window (starts_at=DATE 00:00, ends_at=DATE 23:59) when checking a specific date. "
        "Returns only slots with actual staff schedule entries."
    ),
    "create_appointment": "Create a booking appointment immediately without asking the user for confirmation.",
    "reschedule_appointment": (
        "Reschedule an existing appointment to a new time. "
        "If appointment_id is unknown, provide appointment_date (ISO date or datetime) to look up the booking "
        "by the current user. Use lookup_staff_id to narrow the search if needed."
    ),
    "cancel_appointment": (
        "Cancel an existing appointment. "
        "If appointment_id is unknown, provide appointment_date (ISO date or datetime) to look up the booking "
        "by the current user. Never ask the user for an appointment ID."
    ),
    "list_appointments": "List appointments by period/client/staff/status filters. Use client_external_id filter to find appointments for the current user.",
    "list_staff": "List staff members available for booking.",
    "list_services": "List available services for booking.",
    "find_next_available": (
        "Find the next available time slot starting from a given date. "
        "Use ONLY when the user asks for 'nearest available time' or does not specify a date. "
        "For a specific requested date, use check_availability instead."
    ),
}


class AdminBookingToolRegistry:
    def __init__(
        self,
        *,
        agent_id: int,
        user_external_id: str | None,
        source_channel: str,
        confirmation_policy: str = "never_confirm",
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

    @staticmethod
    def _canonical_args(model: BaseModel) -> str:
        return json.dumps(model.model_dump(), ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _tool_args_hash(canonical_args: str) -> str:
        return hashlib.sha256(canonical_args.encode("utf-8")).hexdigest()

    def _idempotency_key(self, tool_name: str, canonical_args: str) -> str:
        raw = f"{self._agent_id}:{self._user_external_id}:{tool_name}:{canonical_args}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def _lookup_appointment_id(
        self,
        *,
        service: Any,
        appointment_date: str,
        staff_id: int | None,
    ) -> int:
        """Find an active appointment for the current user by date, return its ID."""
        date_str = appointment_date.strip()
        if not date_str:
            raise RuntimeError("appointment_date is required to look up the appointment")
        has_time = "T" in date_str or (":" in date_str and len(date_str) > 10)
        if has_time:
            pivot = _parse_iso_datetime(date_str)
            window_start = pivot.replace(second=0) - timedelta(minutes=1)
            window_end = pivot.replace(second=0) + timedelta(minutes=59)
        else:
            pivot = datetime.fromisoformat(date_str)
            window_start = pivot.replace(hour=0, minute=0, second=0)
            window_end = pivot.replace(hour=23, minute=59, second=59)

        appointments = await service.list_appointments(
            agent_id=self._agent_id,
            starts_at=window_start,
            ends_at=window_end,
            staff_id=staff_id,
            client_external_id=self._user_external_id,
            status=None,
        )
        active = [
            a for a in appointments
            if a.get("status") not in ("cancelled", "completed", "no_show")
        ]
        if not active:
            raise RuntimeError(
                f"No active appointments found for {date_str}. "
                "Please specify the date and time more precisely."
            )
        if len(active) > 1:
            raise RuntimeError(
                f"Multiple appointments found for {date_str}. "
                "Please specify the exact time or staff member."
            )
        return int(active[0]["id"])

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
            appt_id = data.get("appointment_id")
            if not appt_id:
                appt_id = await self._lookup_appointment_id(
                    service=service,
                    appointment_date=str(data.get("appointment_date") or ""),
                    staff_id=data.get("lookup_staff_id"),
                )
            result = await service.reschedule_appointment(
                agent_id=self._agent_id,
                appointment_id=int(appt_id),
                starts_at=_parse_iso_datetime(str(data.get("new_starts_at") or "")),
                ends_at=_parse_iso_datetime(str(data.get("new_ends_at") or "")),
                staff_id=data.get("new_staff_id"),
                resource_id=data.get("new_resource_id"),
            )
        elif tool_name == "cancel_appointment":
            appt_id = data.get("appointment_id")
            if not appt_id:
                appt_id = await self._lookup_appointment_id(
                    service=service,
                    appointment_date=str(data.get("appointment_date") or ""),
                    staff_id=data.get("staff_id"),
                )
            result = await service.cancel_appointment(
                agent_id=self._agent_id,
                appointment_id=int(appt_id),
                reason=data.get("reason"),
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
        elif tool_name == "find_next_available":
            result = await service.find_next_available_slot(
                agent_id=self._agent_id,
                duration_minutes=int(data.get("duration_minutes") or 30),
                staff_id=data.get("staff_id"),
                resource_id=data.get("resource_id"),
                service_id=data.get("service_id"),
                earliest_starts_at=(
                    _parse_iso_datetime(str(data.get("earliest_starts_at") or ""))
                    if data.get("earliest_starts_at")
                    else None
                ),
                search_days_ahead=int(data.get("search_days_ahead") or 7),
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
            "tool_args_summary": _build_args_summary(tool_name, data),
            "result": result,
        }
