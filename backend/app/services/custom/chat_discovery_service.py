"""AI-driven discovery of relevant Telegram chats/channels for an automation.

Searches Telegram globally using a pool account, scores each candidate with an LLM
prompt, and creates ChatTarget records for relevant results. Supports manual
moderation before joining when configured.
"""
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import InputMessagesFilterEmpty, InputPeerEmpty

from .prompt_service import DEFAULT_PROMPTS, render_prompt
from .chat_target_dedup import find_existing_chat_target
from .rotation_service import select_account_for_action
from .telegram_account_client import TelegramAccountClient
from ...alembic.models import (
    ChatDiscoveryTask,
    ChatJoinStatus,
    ChatMode,
    ChatSource,
    ChatTarget,
    CustomAutomation,
    CustomPrompt,
    PromptType,
)
from ...config import settings
from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)

DEFAULT_RELEVANCE_PROMPT = """Ты оцениваешь релевантность Telegram-чата или канала для кампании.

Кампания: {query}

Название: {title}
Описание: {description}
Тип: {chat_type}
Участников: {participants_count}

Оцени релевантность от 0 до 1, где 1 — идеально подходит, 0 — не подходит.
Верни ТОЛЬКО JSON:
{
  "score": 0.0-1.0,
  "reason": "краткое объяснение",
  "relevant": true/false
}
"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


async def _ensure_relevance_prompt(session: AsyncSession, automation_id: int) -> CustomPrompt:
    prompt = await session.scalar(
        select(CustomPrompt).where(
            CustomPrompt.custom_automation_id == automation_id,
            CustomPrompt.prompt_type == PromptType.CHAT_RELEVANCE.value,
            CustomPrompt.is_active.is_(True),
        ).order_by(CustomPrompt.created_at.desc())
    )
    if prompt:
        return prompt
    defaults = DEFAULT_PROMPTS.get(PromptType.CHAT_RELEVANCE.value)
    prompt = CustomPrompt(
        custom_automation_id=automation_id,
        prompt_type=PromptType.CHAT_RELEVANCE.value,
        name=defaults["name"] if defaults else "Chat Relevance",
        content=defaults["content"] if defaults else DEFAULT_RELEVANCE_PROMPT,
        model=defaults["model"] if defaults else "deepseek-chat",
        temperature=defaults.get("temperature", 0.3) if defaults else 0.3,
        max_tokens=defaults.get("max_tokens", 300) if defaults else 300,
        response_format="json",
        is_active=True,
        version=1,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    session.add(prompt)
    await session.commit()
    await session.refresh(prompt)
    return prompt


async def _load_relevance_prompt(session: AsyncSession, automation_id: int) -> str:
    prompt = await _ensure_relevance_prompt(session, automation_id)
    return str(prompt.content).strip() if prompt and prompt.content else DEFAULT_RELEVANCE_PROMPT


async def _score_candidate(
    session: AsyncSession,
    automation_id: int,
    query: str,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    prompt_template = await _load_relevance_prompt(session, automation_id)
    prompt = render_prompt(
        prompt_template,
        {
            "query": query,
            "title": candidate.get("title") or "",
            "description": candidate.get("description") or "",
            "chat_type": candidate.get("chat_type") or "",
            "participants_count": candidate.get("participants_count") or 0,
        },
    )
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        data = _extract_json(response.choices[0].message.content or "")
        score = float(data.get("score") or 0.0)
        reason = str(data.get("reason") or "")
        relevant = bool(data.get("relevant", False)) or score >= 0.6
        return {"score": score, "reason": reason, "relevant": relevant}
    except Exception as exc:
        logger.warning("Relevance scoring failed for candidate %s: %s", candidate.get("id"), exc)
        return {"score": 0.0, "reason": "llm_error", "relevant": False}


def _candidate_from_entity(entity) -> dict[str, Any] | None:
    chat_id = getattr(entity, "id", None)
    if not chat_id:
        return None
    username = getattr(entity, "username", None) or ""
    title = getattr(entity, "title", None) or ""
    if not title:
        return None
    description = getattr(entity, "about", "") or ""
    participants_count = getattr(entity, "participants_count", None) or 0
    chat_type = "channel" if getattr(entity, "broadcast", False) else "chat"
    return {
        "id": str(chat_id),
        "title": title,
        "description": description,
        "username": username,
        "chat_type": chat_type,
        "participants_count": participants_count,
    }


async def _enrich_entity(client: TelegramAccountClient, entity) -> dict[str, Any] | None:
    candidate = _candidate_from_entity(entity)
    if not candidate:
        return None
    try:
        full = await client(GetFullChannelRequest(entity))
        about = getattr(getattr(full, "full_chat", None), "about", None)
        participants = getattr(getattr(full, "full_chat", None), "participants_count", None)
        if about:
            candidate["description"] = about
        if participants:
            candidate["participants_count"] = participants
    except Exception:
        pass
    return candidate


async def _search_telegram(
    session: AsyncSession,
    automation_id: int,
    query: str,
    max_results: int,
) -> list[dict[str, Any]]:
    account = await select_account_for_action(session, automation_id, "commenting")
    if not account or not account.session_file_path:
        logger.warning("No eligible account for discovery in automation %s", automation_id)
        return []
    session_path = Path(settings.MEDIA_ROOT).resolve() / account.session_file_path
    if not session_path.exists():
        logger.warning("Session file missing for discovery account %s", account.id)
        return []

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []

    def _add(candidate: dict[str, Any] | None) -> None:
        if not candidate or candidate["id"] in seen:
            return
        seen.add(candidate["id"])
        unique.append(candidate)

    try:
        async with TelegramAccountClient.for_account(account) as client:
            try:
                search = await client(
                    SearchRequest(q=query, limit=min(100, max(20, max_results * 3)))
                )
                for chat in getattr(search, "chats", []) or []:
                    _add(await _enrich_entity(client, chat))
            except Exception as exc:
                logger.warning("contacts.SearchRequest failed for automation %s: %s", automation_id, exc)

            if len(unique) < max_results:
                try:
                    result = await client(
                        SearchGlobalRequest(
                            q=query,
                            filter=InputMessagesFilterEmpty(),
                            min_date=None,
                            max_date=None,
                            offset_rate=0,
                            offset_peer=InputPeerEmpty(),
                            offset_id=0,
                            limit=max(50, max_results * 3),
                        )
                    )
                    for chat in getattr(result, "chats", []) or []:
                        _add(await _enrich_entity(client, chat))
                except Exception as exc:
                    logger.warning("SearchGlobal failed for automation %s: %s", automation_id, exc)
    except Exception as exc:
        logger.warning("Telegram search failed for automation %s: %s", automation_id, exc)
        return unique[: max_results * 3]

    return unique[: max_results * 3]


async def create_discovery_task(
    session: AsyncSession,
    automation_id: int,
    *,
    query: str,
    mode: str = ChatMode.MONITORING.value,
    max_chats: int = 50,
    require_approval: bool = True,
    relevance_threshold: float = 0.6,
) -> ChatDiscoveryTask:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")

    await _ensure_relevance_prompt(session, automation_id)

    task = ChatDiscoveryTask(
        custom_automation_id=automation_id,
        query=query.strip(),
        status="pending",
        mode=mode,
        max_chats=max_chats,
        require_approval=require_approval,
        relevance_threshold=relevance_threshold,
        found_chats=[],
        joined_chats=0,
        rejected_chats=0,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def run_discovery_task(
    session: AsyncSession,
    task_id: int,
) -> ChatDiscoveryTask:
    task = await session.get(ChatDiscoveryTask, task_id)
    if not task:
        raise ValueError("Discovery task not found")
    if task.status not in {"pending", "processing"}:
        return task

    task.status = "processing"
    task.updated_at = _utc_now()
    await session.commit()

    mode = task.mode or ChatMode.MONITORING.value
    require_approval = task.require_approval
    relevance_threshold = float(task.relevance_threshold or 0.6)
    max_chats = task.max_chats

    try:
        candidates = await _search_telegram(session, task.custom_automation_id, task.query, max_chats)
        scored: list[dict[str, Any]] = []
        for candidate in candidates:
            score_data = await _score_candidate(session, task.custom_automation_id, task.query, candidate)
            candidate["score"] = score_data["score"]
            candidate["reason"] = score_data["reason"]
            candidate["relevant"] = score_data["relevant"]
            scored.append(candidate)

        scored.sort(key=lambda c: c.get("score", 0.0), reverse=True)
        relevant = [c for c in scored if c.get("relevant") and c.get("score", 0.0) >= relevance_threshold][:max_chats]

        created_count = 0
        if not require_approval:
            for candidate in relevant:
                created = await _create_chat_target_from_candidate(session, task, candidate, mode, approved=True)
                if created:
                    created_count += 1
            task.joined_chats = created_count
            task.status = "completed"
            task.completed_at = _utc_now()
        else:
            task.status = "awaiting_approval"

        task.found_chats = relevant
        task.updated_at = _utc_now()
        await session.commit()
        await session.refresh(task)
        return task
    except Exception as cop:
        logger.exception("Discovery task %s failed: %s", task_id, cop)
        task.status = "error"
        task.updated_at = _utc_now()
        await session.commit()
        await session.refresh(task)
        return task


async def _existing_chat_target(
    session: AsyncSession,
    automation_id: int,
    candidate: dict[str, Any],
) -> ChatTarget | None:
    invite_link = f"https://t.me/{candidate['username']}" if candidate.get("username") else None
    external_id = str(candidate["id"]) if candidate.get("id") else None
    return await find_existing_chat_target(
        session,
        automation_id,
        invite_link=invite_link,
        external_chat_id=external_id,
        title=candidate.get("title"),
    )


async def _create_chat_target_from_candidate(
    session: AsyncSession,
    task: ChatDiscoveryTask,
    candidate: dict[str, Any],
    mode: str,
    approved: bool,
) -> ChatTarget | None:
    existing = await _existing_chat_target(session, task.custom_automation_id, candidate)
    if existing:
        candidate["chat_target_id"] = existing.id
        candidate["approved"] = approved
        candidate["already_exists"] = True
        return None

    invite_link = f"https://t.me/{candidate['username']}" if candidate.get("username") else None
    chat_target = ChatTarget(
        custom_automation_id=task.custom_automation_id,
        provider="telegram",
        external_chat_id=candidate.get("id"),
        invite_link=invite_link,
        title=candidate.get("title"),
        description=candidate.get("description"),
        chat_type=candidate.get("chat_type"),
        mode=mode,
        source=ChatSource.AI_DISCOVERY.value,
        discovery_task_id=task.id,
        join_status=ChatJoinStatus.PENDING.value,
        is_active=True,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    session.add(chat_target)
    await session.flush()
    from .chat_membership_service import ensure_memberships_for_chat

    await ensure_memberships_for_chat(session, task.custom_automation_id, chat_target)
    candidate["chat_target_id"] = chat_target.id
    candidate["approved"] = approved
    return chat_target


async def approve_discovered_chats(
    session: AsyncSession,
    automation_id: int,
    task_id: int,
    indices: list[int],
    mode: str | None = None,
) -> dict[str, Any]:
    task = await session.get(ChatDiscoveryTask, task_id)
    if not task or task.custom_automation_id != automation_id:
        raise ValueError("Discovery task not found")
    if task.status not in {"awaiting_approval", "completed"}:
        raise ValueError("Task is not awaiting approval")

    default_mode = task.mode or ChatMode.MONITORING.value
    selected = set(indices)

    created = 0
    rejected = 0
    found = list(task.found_chats or [])
    for idx, candidate in enumerate(found):
        if idx in selected and not candidate.get("chat_target_id"):
            created_target = await _create_chat_target_from_candidate(
                session,
                task,
                candidate,
                mode or default_mode,
                approved=True,
            )
            if created_target:
                created += 1
        elif idx not in selected and not candidate.get("chat_target_id") and not candidate.get("approved"):
            continue

    task.joined_chats += created
    task.rejected_chats += rejected
    remaining = [
        c for c in found
        if not c.get("chat_target_id") and c.get("approved") is not False
    ]
    task.status = "completed" if not remaining else "awaiting_approval"
    task.completed_at = _utc_now() if task.status == "completed" else None
    task.updated_at = _utc_now()
    task.found_chats = found
    await session.commit()
    await session.refresh(task)
    return {"created": created, "rejected": rejected}


async def reject_discovered_chats(
    session: AsyncSession,
    automation_id: int,
    task_id: int,
    indices: list[int],
) -> dict[str, Any]:
    task = await session.get(ChatDiscoveryTask, task_id)
    if not task or task.custom_automation_id != automation_id:
        raise ValueError("Discovery task not found")
    if task.status not in {"awaiting_approval", "completed"}:
        raise ValueError("Task is not awaiting approval")

    found = list(task.found_chats or [])
    rejected = 0
    for idx in indices:
        if 0 <= idx < len(found):
            found[idx]["approved"] = False
            rejected += 1
    task.rejected_chats += rejected
    task.status = "completed" if task.joined_chats else "awaiting_approval"
    task.completed_at = _utc_now() if task.status == "completed" else None
    task.updated_at = _utc_now()
    task.found_chats = found
    await session.commit()
    await session.refresh(task)
    return {"rejected": rejected}


async def discovery_task_by_id(
    session: AsyncSession,
    task_id: int,
) -> ChatDiscoveryTask | None:
    return await session.get(ChatDiscoveryTask, task_id)


async def list_discovery_tasks(
    session: AsyncSession,
    automation_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[ChatDiscoveryTask]:
    result = await session.execute(
        select(ChatDiscoveryTask)
        .where(ChatDiscoveryTask.custom_automation_id == automation_id)
        .order_by(ChatDiscoveryTask.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def run_pending_discovery_for_automation(automation_id: int) -> dict[str, Any]:
    """Scheduler entrypoint: process pending or stuck discovery tasks."""
    from ...alembic.database import async_session_maker

    processed = 0
    stuck_before = _utc_now() - timedelta(minutes=15)
    async with async_session_maker() as session:
        result = await session.execute(
            select(ChatDiscoveryTask).where(
                ChatDiscoveryTask.custom_automation_id == automation_id,
                ChatDiscoveryTask.status.in_(["pending", "processing"]),
            )
        )
        tasks = list(result.scalars().all())
        for task in tasks:
            if task.status == "processing" and task.updated_at and task.updated_at > stuck_before:
                continue
            if task.status == "processing":
                task.status = "pending"
                await session.commit()
            try:
                await run_discovery_task(session, task.id)
                processed += 1
            except Exception as exc:
                logger.exception("Pending discovery task %s failed: %s", task.id, exc)
    return {"processed": processed}
