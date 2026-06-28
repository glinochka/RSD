"""Agent routes: booking."""
from fastapi import APIRouter

from .shared import *  # noqa: F403

router = APIRouter()

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



@router.get("/admin_template/applications")
async def admin_template_applications_list(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    client_external_id: str | None = Query(default=None),
    source_channel: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user_required),
):
    if agent_id is None and bot_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="agent_id or bot_id is required")
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
            workflow_mode = str(cfg.get("workflow_mode") or "booking").strip().lower()
            channel = str(source_channel or "").strip().lower() or None
            if workflow_mode != "applications" and channel != "website":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Applications API is available only for agents with workflow_mode=applications",
                )
            items = await get_admin_application_service().list_applications(
                session,
                agent_id=agent.id,
                status=status_filter,
                client_external_id=client_external_id,
                source_channel=channel,
                limit=limit,
                offset=offset,
            )
            if channel == "website":
                fields_schema = WEBSITE_UNIFIED_LEAD_FIELDS
            else:
                fields_schema = get_admin_application_service().get_fields_schema(cfg)
    return JSONResponse(
        content={
            "items": items,
            "fields_schema": fields_schema,
        },
        status_code=status.HTTP_200_OK,
    )



@router.get("/admin_template/applications/stats")
async def admin_template_applications_stats(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    source_channel: str | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    if agent_id is None and bot_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="agent_id or bot_id is required")
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
            workflow_mode = str(cfg.get("workflow_mode") or "booking").strip().lower()
            channel = str(source_channel or "").strip().lower() or None
            if workflow_mode != "applications" and channel != "website":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Applications API is available only for agents with workflow_mode=applications",
                )
            counts = await get_admin_application_service().count_by_status(
                session,
                agent_id=agent.id,
                source_channel=channel,
            )
    return JSONResponse(content={"counts": counts}, status_code=status.HTTP_200_OK)



@router.patch("/admin_template/applications")
async def admin_template_applications_update(
    payload: AdminTemplateApplicationUpdatePayload,
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
            workflow_mode = str(cfg.get("workflow_mode") or "booking").strip().lower()
            if workflow_mode != "applications":
                existing = await get_admin_application_service().get_application(
                    session,
                    agent_id=agent.id,
                    application_id=payload.application_id,
                )
                if not existing or str(existing.get("source_channel") or "").lower() != "website":
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Applications API is available only for agents with workflow_mode=applications",
                    )
            try:
                row = await get_admin_application_service().update_application(
                    session,
                    agent_id=agent.id,
                    application_id=payload.application_id,
                    status=payload.status,
                    notes=payload.notes,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
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
    if item.get("status") == "refunded":
        from ..services.admin_booking.client_notify import notify_refund_request_approved

        try:
            await notify_refund_request_approved(
                agent_id=agent.id,
                client_external_id=str(item.get("client_external_id") or ""),
                source_channel=item.get("source_channel"),
                amount_rub=item.get("amount_rub"),
            )
        except Exception:
            logger.exception(
                "Failed to notify client about approved refund request_id=%s",
                payload.refund_request_id,
            )
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
    if item.get("status") == "rejected":
        from ..services.admin_booking.client_notify import notify_refund_request_rejected

        try:
            await notify_refund_request_rejected(
                agent_id=agent.id,
                client_external_id=str(item.get("client_external_id") or ""),
                source_channel=item.get("source_channel"),
                reason=item.get("error_message") or payload.reason,
            )
        except Exception:
            logger.exception(
                "Failed to notify client about rejected refund request_id=%s",
                payload.refund_request_id,
            )
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


