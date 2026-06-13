"""Content factory runtime contracts and orchestration boundary.

Stage 0 introduces a pipeline-first architecture boundary for `content_factory`.
The actual render/publish implementation is intentionally deferred to next stages.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ContentFactoryMessageDecision:
    """Decision for handling inbound channel messages in content-factory mode."""

    answer: str
    fallback_to_text_runtime: bool = False
    fallback_reason: str | None = None


class ScriptService(Protocol):
    """Boundary for script generation used by scheduled pipeline jobs."""

    async def generate_script(self, *, agent_id: int, content_date: str) -> dict:
        """Generate a short script payload for one content job."""


class KlingClient(Protocol):
    """Boundary for rendering API integration."""

    async def submit_render(self, *, script_text: str, duration_seconds: int) -> str:
        """Submit render task and return external task id."""

    async def poll_render(self, *, task_id: str) -> dict:
        """Poll render status and final video URL payload."""


class PublisherRouter(Protocol):
    """Boundary for channel publishing adapters (youtube first, others later)."""

    async def publish(self, *, provider: str, video_url: str, metadata: dict) -> dict:
        """Publish rendered content into target channel/provider."""


class ContentFactoryOrchestrator:
    """Pipeline-first orchestrator for content_factory.

    Inbound chat is not the primary operating mode for this template. The normal
    production flow is scheduler -> job worker -> script/render/publish.
    """

    _TECHNICAL_FALLBACK_KEYWORDS = (
        "ошиб",
        "error",
        "exception",
        "traceback",
        "лог",
        "debug",
        "health",
        "статус",
        "status",
        "настро",
        "config",
        "template_config",
        "подключ",
        "oauth",
        "token",
        "api",
        "pipeline",
        "worker",
        "kling",
        "youtube",
    )

    def route_incoming_message(self, *, user_message: str) -> ContentFactoryMessageDecision:
        text = (user_message or "").strip().lower()
        if self._should_fallback_to_text_runtime(text):
            return ContentFactoryMessageDecision(
                answer="",
                fallback_to_text_runtime=True,
                fallback_reason="content_factory_technical_fallback",
            )

        return ContentFactoryMessageDecision(
            answer=(
                "Этот агент работает как ИИ контент-завод в pipeline-режиме: "
                "сценарии и публикации запускаются по расписанию через фоновые задачи. "
                "Входящие сообщения в чате не являются его основным режимом."
            ),
            fallback_to_text_runtime=False,
        )

    def _should_fallback_to_text_runtime(self, message_text: str) -> bool:
        if not message_text:
            return False
        if message_text.startswith("/"):
            return True
        return any(keyword in message_text for keyword in self._TECHNICAL_FALLBACK_KEYWORDS)


_content_factory_orchestrator: ContentFactoryOrchestrator | None = None


def get_content_factory_orchestrator() -> ContentFactoryOrchestrator:
    global _content_factory_orchestrator
    if _content_factory_orchestrator is None:
        _content_factory_orchestrator = ContentFactoryOrchestrator()
    return _content_factory_orchestrator
