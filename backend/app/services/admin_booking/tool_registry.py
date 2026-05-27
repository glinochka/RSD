"""Domain booking tool registry with validation and idempotency controls."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import time
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator
from yookassa import Configuration, Payment

from ...config import settings
from .service import get_admin_booking_service

_IDEMPOTENCY_TTL_SECONDS = 120
_IDEMPOTENCY_CACHE: dict[str, tuple[datetime, dict[str, Any]]] = {}
_MAX_RAW_ARGUMENTS_BYTES = 16_000
# Only write/mutating operations are idempotency-protected; reads always get fresh data.
_IDEMPOTENCY_PROTECTED_TOOLS = {"create_appointment", "reschedule_appointment", "cancel_appointment"}
_PAID_BOOKING_CACHE: dict[str, dict[str, Any]] = {}


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


def _filter_slots_by_min_duration(
    slots: list[dict[str, Any]],
    duration_minutes: int | None,
) -> list[dict[str, Any]]:
    if not duration_minutes or int(duration_minutes) <= 0:
        return slots
    min_sec = float(int(duration_minutes) * 60)
    out: list[dict[str, Any]] = []
    for slot in slots:
        try:
            start = _parse_iso_datetime(str(slot.get("starts_at") or ""))
            end = _parse_iso_datetime(str(slot.get("ends_at") or ""))
        except Exception:
            continue
        if (end - start).total_seconds() + 0.001 >= min_sec:
            out.append(slot)
    return out


async def _enrich_services_with_staff_names(
    booking_service: Any,
    agent_id: int,
    services: list[dict[str, Any]],
) -> None:
    if not services:
        return
    need_ids = set()
    for item in services:
        raw = item.get("staff_id")
        if raw is not None:
            try:
                need_ids.add(int(raw))
            except (TypeError, ValueError):
                continue
    if not need_ids:
        return
    staff_rows = await booking_service.list_staff(agent_id=agent_id, active_only=False)
    names_by_id: dict[int, str] = {}
    for row in staff_rows:
        try:
            sid = int(row["id"])
        except (TypeError, ValueError, KeyError):
            continue
        name = str(row.get("full_name") or "").strip()
        if name:
            names_by_id[sid] = name
    for item in services:
        raw = item.get("staff_id")
        if raw is None:
            continue
        try:
            sid = int(raw)
        except (TypeError, ValueError):
            continue
        if sid in names_by_id:
            item["staff_full_name"] = names_by_id[sid]


class _ListStaffArgs(BaseModel):
    role: str | None = Field(default=None, max_length=32)
    active_only: bool = Field(default=True)


class _ListServicesArgs(BaseModel):
    target_role: str | None = Field(default=None, max_length=32)
    active_only: bool = Field(default=True)


class _CheckAvailabilityArgs(BaseModel):
    starts_at: str = Field(..., min_length=16, max_length=40)
    ends_at: str = Field(..., min_length=16, max_length=40)
    staff_id: int | None = Field(default=None, gt=0)
    resource_id: int | None = Field(default=None, gt=0)
    service_id: int | None = Field(default=None, gt=0)
    duration_minutes: int | None = Field(
        default=None,
        description="Optional. When set, only return slots at least this long (matches the requested service).",
    )

    @model_validator(mode="after")
    def _validate_window(self):
        starts = _parse_iso_datetime(self.starts_at)
        ends = _parse_iso_datetime(self.ends_at)
        if ends <= starts:
            raise ValueError("ends_at must be greater than starts_at")
        if self.duration_minutes is not None and int(self.duration_minutes) <= 0:
            raise ValueError("duration_minutes must be positive when provided")
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


class _ConfirmPaidAppointmentArgs(BaseModel):
    payment_id: str = Field(..., min_length=4, max_length=128)


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
    "confirm_paid_appointment": _ConfirmPaidAppointmentArgs,
    "reschedule_appointment": _RescheduleAppointmentArgs,
    "cancel_appointment": _CancelAppointmentArgs,
    "list_appointments": _ListAppointmentsArgs,
    "list_staff": _ListStaffArgs,
    "list_services": _ListServicesArgs,
    "find_next_available": _FindNextAvailableArgs,
}

_TOOL_DESCRIPTIONS = {
    "check_availability": (
        "Check free time inside staff schedule for a date range. "
        "Always use a full calendar day (starts_at=DATE 00:00:00, ends_at=DATE 23:59:59) when checking one day. "
        "staff_id must be taken from the latest list_staff response (integer id field) — never guess or reuse resource/service ids. "
        "When the user names a service, pass service_id from list_services and set duration_minutes to that service's duration_minutes "
        "so short gaps are not mistaken for a full appointment. "
        "Returns schedule-backed free intervals (not 'invented' windows)."
    ),
    "create_appointment": "Create a booking appointment immediately without asking the user for confirmation.",
    "confirm_paid_appointment": (
        "Confirm paid booking by payment_id. Use it after the client says they completed payment."
    ),
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
    "list_services": (
        "List bookable services. Each item may include staff_id and staff_full_name when the service is tied to one specialist; "
        "use this so you know which doctor performs which procedure before offering a time. "
        "For client-facing prices use price_rub (rubles), not price_minor."
    ),
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
        paid_booking_enabled: bool = False,
        yookassa_api_key: str | None = None,
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
        self._paid_booking_enabled = bool(paid_booking_enabled)
        self._yookassa_api_key = (yookassa_api_key or "").strip() or None

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

    def _parse_yookassa_credentials(self) -> tuple[str, str]:
        raw = (self._yookassa_api_key or "").strip()
        if not raw or ":" not in raw:
            raise RuntimeError("Платная бронь включена, но ЮKassa API ключ не настроен")
        shop_id, secret_key = raw.split(":", 1)
        shop_id = shop_id.strip()
        secret_key = secret_key.strip()
        if not shop_id or not secret_key:
            raise RuntimeError("ЮKassa API ключ должен быть в формате shop_id:secret_key")
        return shop_id, secret_key

    async def _lookup_appointment_id(
        self,
        *,
        service: Any,
        appointment_date: str,
        staff_id: int | None,
    ) -> int:
        """Find an active appointment for the current user by date, return its ID.

        Strategy: always search by client + time window ignoring staff_id first
        (LLM may pass a stale/wrong staff_id from portrait).  If multiple active
        appointments are found in the window, narrow by staff_id.
        """
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

        # Search without staff_id to avoid failures when LLM passes a wrong ID
        all_appointments = await service.list_appointments(
            agent_id=self._agent_id,
            starts_at=window_start,
            ends_at=window_end,
            staff_id=None,
            client_external_id=self._user_external_id,
            status=None,
        )
        active = [
            a for a in all_appointments
            if a.get("status") not in ("cancelled", "completed", "no_show")
        ]
        if not active:
            raise RuntimeError(
                f"No active appointments found for {date_str}. "
                "Please specify the date and time more precisely."
            )
        if len(active) == 1:
            return int(active[0]["id"])
        # Multiple hits — try to narrow by staff_id hint
        if staff_id is not None:
            narrowed = [a for a in active if a.get("staff_id") == staff_id]
            if len(narrowed) == 1:
                return int(narrowed[0]["id"])
        raise RuntimeError(
            f"Multiple appointments found for {date_str}. "
            "Please specify the exact time or staff member."
        )

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
        use_idempotency = tool_name in _IDEMPOTENCY_PROTECTED_TOOLS
        _cleanup_idempotency_cache()
        idempotency_key = self._idempotency_key(tool_name, canonical_args)
        if use_idempotency:
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
            await _enrich_services_with_staff_names(service, self._agent_id, result)
        elif tool_name == "check_availability":
            raw_staff = data.get("staff_id")
            raw_service = data.get("service_id")
            duration_minutes = data.get("duration_minutes")
            staff_rows_list = await service.list_staff(agent_id=self._agent_id, active_only=False)
            valid_staff_ids = set()
            staff_name_by_id: dict[int, str] = {}
            for row in staff_rows_list:
                try:
                    sid = int(row["id"])
                except (TypeError, ValueError, KeyError):
                    continue
                valid_staff_ids.add(sid)
                n = str(row.get("full_name") or "").strip()
                if n:
                    staff_name_by_id[sid] = n

            if raw_staff is not None and int(raw_staff) not in valid_staff_ids:
                result = {
                    "validation_error": (
                        "Указанный staff_id отсутствует в списке сотрудников этого агента. "
                        "Вызови list_staff и используй поле id из актуального ответа. "
                        "Не смешивай id сотрудника с id услуги, ресурса или произвольными числами из памяти."
                    ),
                    "available_slots": [],
                }
            elif raw_staff is not None and raw_service is not None:
                svc_list = await service.list_services(agent_id=self._agent_id, active_only=False)
                await _enrich_services_with_staff_names(service, self._agent_id, svc_list)
                srv = next((x for x in svc_list if int(x["id"]) == int(raw_service)), None)
                bound: int | None = None
                if srv is not None and srv.get("staff_id") is not None:
                    bound = int(srv["staff_id"])
                if bound is not None and bound != int(raw_staff):
                    title = str((srv or {}).get("title") or "услуга")
                    other_name = staff_name_by_id.get(bound, "")
                    result = {
                        "validation_error": (
                            f"Услуга «{title}» в каталоге привязана к другому специалисту"
                            + (f" ({other_name})" if other_name else "")
                            + ". Указанному мастеру эту услугу искать нельзя. "
                            "Предложи записаться к нужному врачу из list_services (поля staff_id / staff_full_name) "
                            "или выбрать у этого мастера другую услугу из его списка."
                        ),
                        "available_slots": [],
                    }
                else:
                    slots = await service.list_available_slots(
                        agent_id=self._agent_id,
                        starts_at=_parse_iso_datetime(str(data.get("starts_at") or "")),
                        ends_at=_parse_iso_datetime(str(data.get("ends_at") or "")),
                        staff_id=data.get("staff_id"),
                        resource_id=data.get("resource_id"),
                        service_id=data.get("service_id"),
                    )
                    result = _filter_slots_by_min_duration(slots, duration_minutes)
            else:
                slots = await service.list_available_slots(
                    agent_id=self._agent_id,
                    starts_at=_parse_iso_datetime(str(data.get("starts_at") or "")),
                    ends_at=_parse_iso_datetime(str(data.get("ends_at") or "")),
                    staff_id=data.get("staff_id"),
                    resource_id=data.get("resource_id"),
                    service_id=data.get("service_id"),
                )
                result = _filter_slots_by_min_duration(slots, duration_minutes)
        elif tool_name == "create_appointment":
            if self._paid_booking_enabled:
                service_id = data.get("service_id")
                if service_id is None:
                    raise RuntimeError("Для платной брони нужно выбрать услугу с service_id")
                services = await service.list_services(agent_id=self._agent_id, active_only=False)
                service_row = next(
                    (
                        item for item in services
                        if str(item.get("id")) == str(service_id)
                    ),
                    None,
                )
                if not service_row:
                    raise RuntimeError("Услуга не найдена, обновите список услуг и выберите заново")
                amount_minor = int(service_row.get("price_minor") or 0)
                if amount_minor <= 0:
                    raise RuntimeError("Для выбранной услуги не задана стоимость. Платная бронь недоступна")

                shop_id, secret_key = self._parse_yookassa_credentials()
                Configuration.account_id = shop_id
                Configuration.secret_key = secret_key
                payment_payload = {
                    "amount": {"value": f"{amount_minor / 100:.2f}", "currency": "RUB"},
                    "capture": True,
                    "confirmation": {
                        "type": "redirect",
                        "return_url": (settings.YOOKASSA_RETURN_URL or "https://yookassa.ru").strip(),
                    },
                    "description": f"Оплата брони: {str(service_row.get('title') or 'услуга').strip()}",
                    "metadata": {
                        "kind": "admin_booking",
                        "agent_id": str(self._agent_id),
                        "user_external_id": self._user_external_id,
                        "starts_at": str(data.get("starts_at") or ""),
                        "ends_at": str(data.get("ends_at") or ""),
                        "staff_id": str(data.get("staff_id") or ""),
                        "resource_id": str(data.get("resource_id") or ""),
                        "service_id": str(service_id),
                        "client_name": str(data.get("client_name") or ""),
                        "notes": str(data.get("notes") or ""),
                        "source_channel": self._source_channel,
                    },
                }
                payment = Payment.create(payment_payload, hashlib.sha256(f"{self._agent_id}:{canonical_args}".encode("utf-8")).hexdigest())
                confirmation = getattr(payment, "confirmation", None)
                confirmation_url = None
                if isinstance(confirmation, dict):
                    confirmation_url = confirmation.get("confirmation_url")
                else:
                    confirmation_url = getattr(confirmation, "confirmation_url", None)
                payment_id = str(getattr(payment, "id", "") or "")
                if not payment_id or not confirmation_url:
                    raise RuntimeError("Не удалось сформировать ссылку на оплату")
                _PAID_BOOKING_CACHE[payment_id] = {
                    "agent_id": self._agent_id,
                    "user_external_id": self._user_external_id,
                    "payload": data,
                }
                result = {
                    "requires_payment": True,
                    "payment_id": payment_id,
                    "payment_url": confirmation_url,
                    "amount_minor": amount_minor,
                    "amount_rub": round(amount_minor / 100, 2),
                    "service_title": str(service_row.get("title") or "").strip(),
                    "status": "awaiting_payment",
                    "message": "Ссылка на оплату сформирована. После оплаты подтвердите бронь через confirm_paid_appointment.",
                }
            else:
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
        elif tool_name == "confirm_paid_appointment":
            if not self._paid_booking_enabled:
                raise RuntimeError("Платная бронь выключена для текущего агента")
            payment_id = str(data.get("payment_id") or "").strip()
            if not payment_id:
                raise RuntimeError("payment_id обязателен")
            cached = _PAID_BOOKING_CACHE.get(payment_id)
            if not cached:
                raise RuntimeError("Платеж не найден в текущей сессии. Запросите новую ссылку на оплату.")
            shop_id, secret_key = self._parse_yookassa_credentials()
            Configuration.account_id = shop_id
            Configuration.secret_key = secret_key
            payment = Payment.find_one(payment_id)
            payment_status = str(getattr(payment, "status", "") or "").strip().lower()
            if payment_status != "succeeded":
                result = {
                    "status": "awaiting_payment",
                    "payment_id": payment_id,
                    "payment_status": payment_status or "pending",
                    "message": "Оплата еще не подтверждена. Проверьте статус позже.",
                }
            else:
                cached_payload = cached.get("payload") or {}
                result = await service.create_appointment(
                    agent_id=self._agent_id,
                    client_external_id=self._user_external_id,
                    starts_at=_parse_iso_datetime(str(cached_payload.get("starts_at") or "")),
                    ends_at=_parse_iso_datetime(str(cached_payload.get("ends_at") or "")),
                    staff_id=cached_payload.get("staff_id"),
                    resource_id=cached_payload.get("resource_id"),
                    service_id=cached_payload.get("service_id"),
                    client_name=cached_payload.get("client_name"),
                    source_channel=cached_payload.get("source_channel") or self._source_channel,
                    notes=cached_payload.get("notes"),
                )
                result = {
                    "status": "paid_and_booked",
                    "payment_id": payment_id,
                    "appointment": result,
                    "message": "Оплата подтверждена, бронь успешно оформлена.",
                }
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
            fsid = data.get("staff_id")
            if fsid is not None:
                staff_chk = await service.list_staff(agent_id=self._agent_id, active_only=False)
                ok_ids = set()
                for row in staff_chk:
                    try:
                        ok_ids.add(int(row["id"]))
                    except (TypeError, ValueError, KeyError):
                        continue
                if int(fsid) not in ok_ids:
                    result = {
                        "validation_error": (
                            "Указанный staff_id не найден. Вызови list_staff и используй актуальное поле id."
                        ),
                        "available": False,
                    }
                else:
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

        if use_idempotency:
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
