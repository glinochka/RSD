"""LLM script generation service for content_factory jobs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
import re
from typing import Any

from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentContentJob
from ..prompts.system_prompts import build_kling_scriptwriter_prompt
from .ai_authoring import ai_client
from .content_job_service import get_content_job_service

_MULTIPART_MARKERS = (
    "scene 2",
    "scene two",
    "сцена 2",
    "часть 2",
    "part 2",
    "clip 2",
    "эпизод 2",
)


@dataclass(frozen=True)
class ScriptGenerationResult:
    script_text: str
    script_model: str
    estimated_duration_seconds: int
    max_duration_seconds: int
    trimmed_to_fit_duration: bool


class ScriptService:
    """Generate and sanitize short content scripts for Kling MVP constraints."""

    async def generate_for_job(self, *, job_id: int) -> ScriptGenerationResult:
        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(select(AgentContentJob).where(AgentContentJob.id == job_id))
                if row is None:
                    raise ValueError(f"Content job not found: id={job_id}")
                agent = await session.scalar(select(Agent).where(Agent.id == row.agent_id))
                if agent is None:
                    raise ValueError(f"Agent not found for content job: job_id={job_id}")
                cfg = self._parse_config(agent.template_config)

        max_duration_seconds = self._resolve_duration_limit(cfg)
        script_model = str(cfg.get("script_model") or cfg.get("generation_model") or "deepseek-chat").strip()
        if not script_model:
            script_model = "deepseek-chat"

        system_prompt = self._build_prompt(
            template_config=cfg,
            system_prompt=agent.system_prompt or "",
            max_duration_seconds=max_duration_seconds,
        )
        completion = await ai_client.chat.completions.create(
            model=script_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "Сгенерируй сценарий короткого ролика. Верни только чистый текст сценария.",
                },
            ],
            temperature=0.4,
        )
        raw_script = (completion.choices[0].message.content or "").strip()
        sanitized = self._sanitize_script(raw_script)
        script_text, trimmed = self._trim_to_duration(sanitized, max_duration_seconds=max_duration_seconds)
        if not script_text:
            raise RuntimeError("Script generation returned empty output after sanitization")
        estimated_duration_seconds = self._estimate_duration_seconds(script_text)

        metadata = {
            "script_generation": {
                "generated_at": datetime.utcnow().isoformat(),
                "estimated_duration_seconds": estimated_duration_seconds,
                "max_duration_seconds": max_duration_seconds,
                "trimmed_to_fit_duration": trimmed,
                "single_clip_enforced": True,
            }
        }
        await get_content_job_service().mark_status(
            job_id=job_id,
            status="script_ready",
            script_text=script_text,
            script_model=script_model,
            metadata_update=metadata,
        )

        return ScriptGenerationResult(
            script_text=script_text,
            script_model=script_model,
            estimated_duration_seconds=estimated_duration_seconds,
            max_duration_seconds=max_duration_seconds,
            trimmed_to_fit_duration=trimmed,
        )

    async def generate_script(
        self,
        *,
        agent_id: int,
        content_date: str,
        template_config: dict[str, Any] | None = None,
        system_prompt: str = "",
    ) -> dict[str, Any]:
        """Generate script payload without writing to DB (for future orchestration usage)."""
        cfg = template_config or {}
        max_duration_seconds = self._resolve_duration_limit(cfg)
        script_model = str(cfg.get("script_model") or "deepseek-chat").strip() or "deepseek-chat"
        prompt = self._build_prompt(
            template_config=cfg,
            system_prompt=system_prompt,
            max_duration_seconds=max_duration_seconds,
        )
        completion = await ai_client.chat.completions.create(
            model=script_model,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        f"Контент-дата: {content_date}. "
                        "Сгенерируй один сценарий ролика для этого дня. Верни только текст."
                    ),
                },
            ],
            temperature=0.4,
        )
        raw_script = (completion.choices[0].message.content or "").strip()
        sanitized = self._sanitize_script(raw_script)
        script_text, trimmed = self._trim_to_duration(sanitized, max_duration_seconds=max_duration_seconds)
        return {
            "agent_id": agent_id,
            "content_date": content_date,
            "script_text": script_text,
            "script_model": script_model,
            "estimated_duration_seconds": self._estimate_duration_seconds(script_text),
            "max_duration_seconds": max_duration_seconds,
            "trimmed_to_fit_duration": trimmed,
        }

    @staticmethod
    def _parse_config(raw_template_config: str | None) -> dict[str, Any]:
        if not raw_template_config:
            return {}
        try:
            loaded = json.loads(raw_template_config)
        except Exception:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    @staticmethod
    def _resolve_duration_limit(template_config: dict[str, Any]) -> int:
        value = template_config.get("video_duration_seconds", 8)
        try:
            duration = int(value)
        except (TypeError, ValueError):
            duration = 8
        return max(1, min(duration, 8))

    def _build_prompt(
        self,
        *,
        template_config: dict[str, Any],
        system_prompt: str,
        max_duration_seconds: int,
    ) -> str:
        return build_kling_scriptwriter_prompt(
            base_prompt=system_prompt or "",
            company_name=str(template_config.get("company_name") or "").strip() or "Компания",
            company_activity=str(template_config.get("company_activity") or "").strip() or "бизнес-деятельность",
            brand_tone=str(template_config.get("brand_tone") or "").strip() or "понятный и дружелюбный",
            content_language=str(template_config.get("content_language") or "ru").strip().lower() or "ru",
            max_duration_seconds=max_duration_seconds,
        )

    def _sanitize_script(self, text: str) -> str:
        cleaned = (text or "").replace("#", "").replace("*", "").strip()
        if not cleaned:
            return ""

        lines = []
        for raw_line in cleaned.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                if lines:
                    break  # first paragraph only -> single clip
                continue
            lower = line.lower()
            if any(marker in lower for marker in _MULTIPART_MARKERS):
                break
            if lower.startswith(("сцена ", "scene ", "часть ", "part ", "клип ", "clip ")):
                if lines:
                    break
                line = re.sub(r"^(сцена|scene|часть|part|клип|clip)\s*\d*[:.\-\s]*", "", line, flags=re.IGNORECASE).strip()
            line = re.sub(r"^\d+[).:\-\s]+", "", line)  # remove numbered list starts
            line = re.sub(r"^[•\-\u2022]\s*", "", line)  # remove bullet starts
            if line:
                lines.append(line)

        result = " ".join(lines).strip()
        result = re.sub(r"\s+", " ", result)
        return result

    def _trim_to_duration(self, text: str, *, max_duration_seconds: int) -> tuple[str, bool]:
        if not text:
            return "", False
        words = text.split()
        max_words = max(4, int(max_duration_seconds * 2.4))
        if len(words) <= max_words:
            return text, False
        trimmed = " ".join(words[:max_words]).strip()
        return trimmed.rstrip(" ,;:-.") + ".", True

    @staticmethod
    def _estimate_duration_seconds(text: str) -> int:
        words_count = len((text or "").split())
        if words_count == 0:
            return 1
        return max(1, math.ceil(words_count / 2.4))


_script_service: ScriptService | None = None


def get_script_service() -> ScriptService:
    global _script_service
    if _script_service is None:
        _script_service = ScriptService()
    return _script_service
