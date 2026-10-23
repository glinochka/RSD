"""Project skillbase: brief, knowledge files, generated activity skills."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from ...alembic.models import CustomAutomation, CustomPrompt
from ...config import settings
from .prompt_service import create_default_prompts, update_prompt
from .shilling_service import encode_shilling_lines
from .skillbase_prompts import ACTIVITIES, SKILLBASE_AUTHOR, SKILLBASE_EDITOR, activity_by_key

logger = logging.getLogger(__name__)

_SKILL_KEY = "skillbase"
_KNOWLEDGE_CAP = 80_000
_MODEL_KNOWLEDGE_CAP = 12_000
_FILE_CAP = 20_000
_FILE_BYTES = 1_500_000
_TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".csv", ".json", ".html", ".htm", ".log"}
_TAG_RE = re.compile(r"<[^>]+>")
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)

_author_client = AsyncOpenAI(
    api_key=settings.DEEPSEEK_API_KEY or "missing",
    base_url="https://api.deepseek.com",
    timeout=90.0,
    max_retries=0,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clip(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def empty_brief() -> dict[str, Any]:
    return {
        "business": "",
        "processes": "",
        "funnel": "",
        "product": "",
        "terms": "",
        "notes": "",
        "files": [],
        "knowledge": "",
        "updated_at": None,
        "generated_at": None,
    }


def normalize_brief(raw: Any) -> dict[str, Any]:
    data = empty_brief()
    incoming = raw if isinstance(raw, dict) else {}
    for key, limit in (
        ("business", 2000),
        ("processes", 2000),
        ("funnel", 2000),
        ("product", 2000),
        ("terms", 2000),
        ("notes", 2000),
    ):
        data[key] = _clip(incoming.get(key), limit)
    files = []
    for item in incoming.get("files") or []:
        if not isinstance(item, dict):
            continue
        name = _clip(item.get("name"), 180)
        text = str(item.get("text") or "")
        if not name or not text.strip():
            continue
        files.append({"name": name, "text": text[:_FILE_CAP]})
        if len(files) >= 12:
            break
    data["files"] = files
    data["knowledge"] = _join_knowledge(files)[:_KNOWLEDGE_CAP]
    data["updated_at"] = incoming.get("updated_at")
    data["generated_at"] = incoming.get("generated_at")
    return data


def public_brief(raw: Any) -> dict[str, Any]:
    data = normalize_brief(raw)
    files = [{"name": item["name"], "chars": len(item["text"])} for item in data["files"]]
    return {
        "business": data["business"],
        "processes": data["processes"],
        "funnel": data["funnel"],
        "product": data["product"],
        "terms": data["terms"],
        "notes": data["notes"],
        "files": files,
        "knowledge_chars": len(data["knowledge"]),
        "updated_at": data["updated_at"],
        "generated_at": data["generated_at"],
    }


def _join_knowledge(files: list[dict[str, str]]) -> str:
    parts = []
    for item in files:
        parts.append(f"## {item['name']}\n{item['text'].strip()}")
    return "\n\n".join(parts).strip()


def brief_ready(raw: Any) -> bool:
    data = normalize_brief(raw)
    return len(data["business"]) >= 20 or len(data["product"]) >= 20


def _stored_brief(automation: CustomAutomation) -> dict[str, Any]:
    blob = automation.module_settings if isinstance(automation.module_settings, dict) else {}
    return normalize_brief(blob.get(_SKILL_KEY))


def _save_brief(automation: CustomAutomation, brief: dict[str, Any]) -> None:
    blob = dict(automation.module_settings or {})
    blob[_SKILL_KEY] = brief
    automation.module_settings = blob
    flag_modified(automation, "module_settings")


def read_text_file(filename: str, raw: bytes) -> str:
    name = (filename or "file.txt").strip()
    suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if suffix not in _TEXT_SUFFIXES:
        raise ValueError("Нужен текстовый файл: txt, md, csv, json, html")
    if len(raw) > _FILE_BYTES:
        raise ValueError("Файл больше 1.5 МБ")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251", errors="replace")
    if suffix in {".html", ".htm"}:
        text = _TAG_RE.sub(" ", text)
    text = re.sub(r"\s+\n", "\n", text).strip()
    if len(text) < 20:
        raise ValueError("В файле слишком мало текста")
    return text[:_FILE_CAP]


def missing_anchors(content: str, anchors: list[str]) -> list[str]:
    body = content or ""
    return [item for item in anchors if item not in body]


def parse_skill_bundle(raw: str) -> dict[str, dict[str, str]]:
    text = (raw or "").strip()
    text = _FENCE_RE.sub("", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    data = json.loads(text)
    rows = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Модель не вернула список навыков")
    found: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "").strip()
        if not key:
            continue
        found[key] = {
            "content": str(row.get("content") or "").strip(),
            "setup": str(row.get("setup") or "").strip(),
            "reply": str(row.get("reply") or "").strip(),
        }
    return found


def parse_skill_edit(raw: str) -> dict[str, str]:
    text = (raw or "").strip()
    text = _FENCE_RE.sub("", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Модель вернула не объект")
    return {
        "content": str(data.get("content") or "").strip(),
        "setup": str(data.get("setup") or "").strip(),
        "reply": str(data.get("reply") or "").strip(),
    }


def _brief_block(brief: dict[str, Any]) -> str:
    knowledge = (brief.get("knowledge") or "")[:_MODEL_KNOWLEDGE_CAP]
    lines = [
        f"Бизнес:\n{brief.get('business') or '—'}",
        f"Процессы:\n{brief.get('processes') or '—'}",
        f"Воронка:\n{brief.get('funnel') or '—'}",
        f"Конечный продукт и оффер:\n{brief.get('product') or '—'}",
        f"Условия, ограничения, табу:\n{brief.get('terms') or '—'}",
        f"Заметки:\n{brief.get('notes') or '—'}",
        f"База знаний:\n{knowledge or '—'}",
    ]
    return "\n\n".join(lines)


def _activity_block(item: dict[str, Any]) -> str:
    variables = ", ".join("{" + name + "}" for name in item["variables"]) or "нет"
    return (
        f"- key: {item['key']}\n"
        f"  активность: {item['title']}. {item['where']}\n"
        f"  плейсхолдеры: {variables}\n"
        f"  контракт: {item['contract']}"
    )


def author_user_prompt(brief: dict[str, Any]) -> str:
    activities = "\n".join(_activity_block(item) for item in ACTIVITIES)
    return (
        "Собери скилл на каждую активность ниже. Факты только из этого проекта.\n\n"
        f"{_brief_block(brief)}\n\n"
        f"Активности:\n{activities}"
    )


def editor_user_prompt(
    brief: dict[str, Any],
    item: dict[str, Any],
    current: str,
    complaint: str,
) -> str:
    return (
        f"Активность: {item['title']}. {item['where']}\n"
        f"Контракт: {item['contract']}\n"
        f"Плейсхолдеры, которые нельзя потерять: {', '.join('{' + name + '}' for name in item['variables']) or 'нет'}\n\n"
        f"Текущий скилл:\n{current}\n\n"
        f"Проект:\n{_brief_block(brief)}\n\n"
        f"Что не так в этой активности:\n{complaint.strip()}"
    )


def skill_body(item: dict[str, Any], row: dict[str, str]) -> str:
    if item["shape"] == "pair":
        setup = row.get("setup") or ""
        reply = row.get("reply") or ""
        if len(setup) < 12 or len(reply) < 12:
            raise ValueError("пустая пара реплик")
        return encode_shilling_lines(setup[:500], reply[:500])
    content = row.get("content") or ""
    if item["key"] == "neuroblog":
        content = content[:4000]
    if len(content) < 40:
        raise ValueError("слишком короткий текст")
    missed = missing_anchors(content, item["anchors"])
    if missed:
        raise ValueError("потеряны " + ", ".join(missed))
    return content


async def _complete(system_prompt: str, user_prompt: str, *, max_tokens: int) -> str:
    if not settings.DEEPSEEK_API_KEY:
        raise ValueError("Не задан ключ модели для сборки скиллбейза")
    response = await _author_client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


async def get_skillbase(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if automation is None:
        raise ValueError("Automation not found")
    brief = _stored_brief(automation)
    blob = automation.module_settings if isinstance(automation.module_settings, dict) else {}
    neuro = blob.get("neuroblog") if isinstance(blob.get("neuroblog"), dict) else {}
    return {
        "brief": public_brief(brief),
        "activities": [
            {**activity_public_safe(item), "module_text": str(neuro.get("prompt") or "") if item["key"] == "neuroblog" else ""}
            for item in ACTIVITIES
        ],
    }


def activity_public_safe(item: dict[str, Any]) -> dict[str, Any]:
    from .skillbase_prompts import activity_public

    return activity_public(item)


async def save_skillbase_brief(session: AsyncSession, automation_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if automation is None:
        raise ValueError("Automation not found")
    current = _stored_brief(automation)
    merged = normalize_brief({**current, **payload, "files": current["files"]})
    merged["updated_at"] = _utc_now().isoformat()
    merged["generated_at"] = current.get("generated_at")
    _save_brief(automation, merged)
    await session.commit()
    return public_brief(merged)


async def add_knowledge_file(
    session: AsyncSession,
    automation_id: int,
    filename: str,
    raw: bytes,
) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if automation is None:
        raise ValueError("Automation not found")
    text = read_text_file(filename, raw)
    brief = _stored_brief(automation)
    name = _clip(filename, 180) or "file.txt"
    files = [item for item in brief["files"] if item["name"] != name]
    files.append({"name": name, "text": text})
    brief["files"] = files[-12:]
    brief = normalize_brief(brief)
    brief["updated_at"] = _utc_now().isoformat()
    _save_brief(automation, brief)
    await session.commit()
    return public_brief(brief)


async def remove_knowledge_file(session: AsyncSession, automation_id: int, filename: str) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if automation is None:
        raise ValueError("Automation not found")
    brief = _stored_brief(automation)
    name = (filename or "").strip()
    brief["files"] = [item for item in brief["files"] if item["name"] != name]
    brief = normalize_brief(brief)
    brief["updated_at"] = _utc_now().isoformat()
    _save_brief(automation, brief)
    await session.commit()
    return public_brief(brief)


async def _active_prompt(session: AsyncSession, automation_id: int, prompt_type: str) -> CustomPrompt | None:
    return await session.scalar(
        select(CustomPrompt)
        .where(
            CustomPrompt.custom_automation_id == automation_id,
            CustomPrompt.prompt_type == prompt_type,
            CustomPrompt.is_active.is_(True),
        )
        .order_by(CustomPrompt.version.desc())
        .limit(1)
    )


async def _write_prompt(session: AsyncSession, automation_id: int, prompt_type: str, content: str) -> None:
    current = await _active_prompt(session, automation_id, prompt_type)
    if current is None:
        raise ValueError("нет активного навыка")
    if (current.content or "").strip() == content.strip():
        return
    await update_prompt(session, automation_id, current.id, content=content, commit=False)


def _write_neuroblog(automation: CustomAutomation, content: str) -> None:
    blob = dict(automation.module_settings or {})
    neuro = dict(blob.get("neuroblog") or {})
    neuro["prompt"] = content[:4000]
    blob["neuroblog"] = neuro
    brief = normalize_brief(blob.get(_SKILL_KEY))
    blob[_SKILL_KEY] = brief
    automation.module_settings = blob
    flag_modified(automation, "module_settings")


async def generate_skillbase(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if automation is None:
        raise ValueError("Automation not found")
    brief = _stored_brief(automation)
    if not brief_ready(brief):
        raise ValueError("Опишите бизнес или продукт — хотя бы пару предложений")
    await create_default_prompts(session, automation_id)
    automation = await session.get(CustomAutomation, automation_id)
    raw = await _complete(SKILLBASE_AUTHOR, author_user_prompt(brief), max_tokens=7000)
    try:
        bundle = parse_skill_bundle(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Skillbase bundle parse failed: %s", exc)
        raise ValueError("Модель вернула скиллбейз, который не удалось разобрать") from exc
    updated: list[str] = []
    errors: list[str] = []
    for item in ACTIVITIES:
        row = bundle.get(item["key"])
        if not row:
            errors.append(f"{item['title']}: модель пропустила навык")
            continue
        try:
            body = skill_body(item, row)
        except ValueError as exc:
            errors.append(f"{item['title']}: {exc}")
            continue
        try:
            if item.get("storage") == "neuroblog":
                _write_neuroblog(automation, body)
            else:
                await _write_prompt(session, automation_id, item["key"], body)
        except ValueError as exc:
            errors.append(f"{item['title']}: {exc}")
            continue
        updated.append(item["key"])
    fresh = _stored_brief(await session.get(CustomAutomation, automation_id))
    fresh["generated_at"] = _utc_now().isoformat()
    fresh["updated_at"] = fresh["generated_at"]
    holder = await session.get(CustomAutomation, automation_id)
    _save_brief(holder, fresh)
    await session.commit()
    return {"brief": public_brief(fresh), "updated": updated, "errors": errors}


async def revise_prompt(
    session: AsyncSession,
    automation_id: int,
    prompt_id: int,
    complaint: str,
) -> CustomPrompt:
    text = (complaint or "").strip()
    if len(text) < 8:
        raise ValueError("Опишите, что не так в этой активности")
    prompt = await session.get(CustomPrompt, prompt_id)
    if prompt is None or prompt.custom_automation_id != automation_id:
        raise ValueError("Prompt not found")
    item = activity_by_key(prompt.prompt_type)
    if item is None:
        raise ValueError("Для этого навыка правка моделью не настроена")
    automation = await session.get(CustomAutomation, automation_id)
    brief = _stored_brief(automation)
    raw = await _complete(
        SKILLBASE_EDITOR,
        editor_user_prompt(brief, item, prompt.content, text),
        max_tokens=1800,
    )
    try:
        edited = parse_skill_edit(raw)
        body = skill_body(item, edited)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Модель не смогла поправить навык, текст не менялся") from exc
    if body.strip() == (prompt.content or "").strip():
        return prompt
    return await update_prompt(session, automation_id, prompt.id, content=body)


async def revise_neuroblog(session: AsyncSession, automation_id: int, complaint: str) -> str:
    text = (complaint or "").strip()
    if len(text) < 8:
        raise ValueError("Опишите, что не так в этой активности")
    automation = await session.get(CustomAutomation, automation_id)
    if automation is None:
        raise ValueError("Automation not found")
    item = activity_by_key("neuroblog")
    blob = automation.module_settings if isinstance(automation.module_settings, dict) else {}
    current = str((blob.get("neuroblog") or {}).get("prompt") or "")
    brief = _stored_brief(automation)
    raw = await _complete(
        SKILLBASE_EDITOR,
        editor_user_prompt(brief, item, current or "Памятки ещё нет.", text),
        max_tokens=1200,
    )
    try:
        edited = parse_skill_edit(raw)
        body = skill_body(item, edited)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Модель не смогла поправить навык, текст не менялся") from exc
    _write_neuroblog(automation, body)
    await session.commit()
    return body


async def save_neuroblog_skill(session: AsyncSession, automation_id: int, content: str) -> str:
    automation = await session.get(CustomAutomation, automation_id)
    if automation is None:
        raise ValueError("Automation not found")
    body = (content or "").strip()[:4000]
    if len(body) < 8:
        raise ValueError("Текст навыка пуст")
    _write_neuroblog(automation, body)
    await session.commit()
    return body
