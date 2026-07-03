"""Project AI Manager — an LLM-powered assistant with access to project data."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func, and_

from app.alembic.database import async_session_maker
from app.alembic.models import (
    Agent,
    Website,
    Project,
    ProjectIntegration,
    ProjectExternalEvent,
    AgentSalesContact,
    AdminAppointment,
    AgentAnalyticsMessage,
    ProjectDocument,
)
from app.services.ai_authoring import ai_client


class ProjectAiManagerService:
    """Answer user questions about a project using live data and LLM."""

    def __init__(self, model: str = "deepseek-chat"):
        self.model = model

    async def answer(
        self,
        project_id: int,
        user_id: int,
        message: str,
        history: list[dict],
    ) -> str:
        context = await self._gather_context(project_id)
        system_prompt = self._build_system_prompt(context)
        messages = [{"role": "system", "content": system_prompt}]
        for turn in history[-10:]:
            role = turn.get("role")
            content = turn.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": str(content)})
        messages.append({"role": "user", "content": message})

        try:
            response = await ai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.4,
                max_tokens=1500,
            )
            content = response.choices[0].message.content or ""
            return self._polish(content)
        except Exception as e:
            return f"Не удалось получить ответ от ИИ-менеджера: {e}"

    async def _gather_context(self, project_id: int) -> dict[str, Any]:
        async with async_session_maker() as session:
            project_result = await session.execute(
                select(Project).where(Project.id == project_id)
            )
            project = project_result.scalar_one_or_none()

            agents_result = await session.execute(
                select(Agent).where(Agent.project_id == project_id)
            )
            agents = agents_result.scalars().all()

            websites_result = await session.execute(
                select(Website).where(Website.project_id == project_id)
            )
            websites = websites_result.scalars().all()

            integrations_result = await session.execute(
                select(ProjectIntegration).where(
                    and_(
                        ProjectIntegration.project_id == project_id,
                        ProjectIntegration.is_active == True,
                    )
                )
            )
            integrations = integrations_result.scalars().all()

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            since_7d = now - timedelta(days=7)
            since_1d = now - timedelta(days=1)
            agent_ids = [a.id for a in agents]

            dialogs_7d = 0
            dialogs_1d = 0
            leads_7d = 0
            leads_1d = 0
            bookings_7d = 0
            bookings_1d = 0
            if agent_ids:
                dialogs_7d = (
                    await session.execute(
                        select(func.count(AgentAnalyticsMessage.id)).where(
                            and_(
                                AgentAnalyticsMessage.agent_id.in_(agent_ids),
                                AgentAnalyticsMessage.created_at >= since_7d,
                            )
                        )
                    )
                ).scalar() or 0
                dialogs_1d = (
                    await session.execute(
                        select(func.count(AgentAnalyticsMessage.id)).where(
                            and_(
                                AgentAnalyticsMessage.agent_id.in_(agent_ids),
                                AgentAnalyticsMessage.created_at >= since_1d,
                            )
                        )
                    )
                ).scalar() or 0
                leads_7d = (
                    await session.execute(
                        select(func.count(AgentSalesContact.id)).where(
                            and_(
                                AgentSalesContact.agent_id.in_(agent_ids),
                                AgentSalesContact.created_at >= since_7d,
                            )
                        )
                    )
                ).scalar() or 0
                leads_1d = (
                    await session.execute(
                        select(func.count(AgentSalesContact.id)).where(
                            and_(
                                AgentSalesContact.agent_id.in_(agent_ids),
                                AgentSalesContact.created_at >= since_1d,
                            )
                        )
                    )
                ).scalar() or 0
                bookings_7d = (
                    await session.execute(
                        select(func.count(AdminAppointment.id)).where(
                            and_(
                                AdminAppointment.agent_id.in_(agent_ids),
                                AdminAppointment.created_at >= since_7d,
                            )
                        )
                    )
                ).scalar() or 0
                bookings_1d = (
                    await session.execute(
                        select(func.count(AdminAppointment.id)).where(
                            and_(
                                AdminAppointment.agent_id.in_(agent_ids),
                                AdminAppointment.created_at >= since_1d,
                            )
                        )
                    )
                ).scalar() or 0

            recent_events_result = await session.execute(
                select(ProjectExternalEvent)
                .where(ProjectExternalEvent.project_id == project_id)
                .order_by(ProjectExternalEvent.created_at.desc())
                .limit(10)
            )
            recent_events = recent_events_result.scalars().all()

            docs_result = await session.execute(
                select(ProjectDocument)
                .where(ProjectDocument.project_id == project_id)
                .order_by(ProjectDocument.created_at.desc())
                .limit(10)
            )
            docs = docs_result.scalars().all()

            return {
                "project": project,
                "agents": agents,
                "websites": websites,
                "integrations": integrations,
                "dialogs_7d": dialogs_7d,
                "dialogs_1d": dialogs_1d,
                "leads_7d": leads_7d,
                "leads_1d": leads_1d,
                "bookings_7d": bookings_7d,
                "bookings_1d": bookings_1d,
                "recent_events": recent_events,
                "documents": docs,
            }

    def _build_system_prompt(self, context: dict[str, Any]) -> str:
        project = context["project"]
        agents = context["agents"]
        websites = context["websites"]
        integrations = context["integrations"]
        recent_events = context["recent_events"]
        documents = context["documents"]

        lines = [
            "Ты — ИИ-менеджер проекта в сервисе RSD. У тебя есть доступ ко всем данным проекта.",
            "Отвечай кратко, по делу, на русском языке. Опирайся только на предоставленные данные.",
            "Если чего-то не знаешь — скажи об этом прямо и предложи уточнить вопрос.",
            "",
            "=== ДАННЫЕ ПРОЕКТА ===",
            f"Название: {project.name if project else 'Неизвестно'}",
            f"Отрасль: {project.industry or 'Не указана'}" if project else "",
            f"Описание: {project.description or 'Не указано'}" if project else "",
            "",
            "=== АГЕНТЫ ===",
        ]
        for a in agents:
            lines.append(
                f"- Агент #{a.id} ({a.template_type}): активен={a.is_active}, "
                f"username={a.bot_username or 'нет'}"
            )
        if not agents:
            lines.append("Агентов пока нет.")

        lines.extend(["", "=== САЙТЫ ==="])
        for w in websites:
            lines.append(
                f"- Сайт #{w.id} '{w.title or w.slug}': статус={w.status}, "
                f"публикация={w.status == 'published'}"
            )
        if not websites:
            lines.append("Сайтов пока нет.")

        lines.extend(["", "=== ИНТЕГРАЦИИ ==="])
        for i in integrations:
            lines.append(f"- {i.name} (тип {i.type})")
        if not integrations:
            lines.append("Интеграций пока нет.")

        lines.extend(["", "=== АКТИВНОСТЬ ЗА 7 ДНЕЙ ==="])
        lines.append(f"Диалогов: {context['dialogs_7d']}")
        lines.append(f"Новых лидов: {context['leads_7d']}")
        lines.append(f"Бронирований/записей: {context['bookings_7d']}")
        lines.append(f"За последние 24 часа: диалогов={context['dialogs_1d']}, лидов={context['leads_1d']}, бронирований={context['bookings_1d']}")

        lines.extend(["", "=== ПОСЛЕДНИЕ ВНЕШНИЕ СОБЫТИЯ ==="])
        for e in recent_events:
            lines.append(f"- {e.event_type} из {e.source} at {e.created_at.isoformat() if e.created_at else ''}")
        if not recent_events:
            lines.append("Событий нет.")

        lines.extend(["", "=== ДОКУМЕНТЫ БАЗЫ ЗНАНИЙ ==="])
        for d in documents:
            lines.append(f"- {d.file_name} ({d.status})")
        if not documents:
            lines.append("Документов нет.")

        return "\n".join(lines)

    def _polish(self, text: str) -> str:
        text = (text or "").strip()
        # Remove any accidental markdown code blocks
        if text.startswith("```"):
            text = text.strip("`")
        return text
