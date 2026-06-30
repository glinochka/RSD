"""Service for AI project plan generation."""
import json
import re
from typing import Dict, Any, Optional, List
from logging import getLogger

from openai import AsyncOpenAI

from app.config import settings
from app.prompts.project_plan import get_project_plan_system_prompt, get_project_plan_user_prompt
from app.router_projects.schemas import ProjectBriefRequest, ProjectPlanResponse, AgentPlanItem, WebsitePlanItem

logger = getLogger(__name__)

# Allowed template types
ALLOWED_TEMPLATE_TYPES = ["qa", "crm_admin", "sales_manager"]
MAX_AGENTS = 4


class ProjectPlanGenerationError(Exception):
    """Error generating project plan."""
    pass


class ProjectPlanService:
    """Service for generating AI project plans."""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )
        self.model = settings.WEBSITE_GENERATION_MODEL or "deepseek-chat"

    async def generate_plan(
        self,
        brief: ProjectBriefRequest,
        max_retries: int = 2,
    ) -> ProjectPlanResponse:
        """Generate AI plan from brief with retry logic."""
        
        # Check feature flags
        content_factory_enabled = getattr(settings, 'CONTENT_FACTORY_ENABLED', False)
        ai_mop_enabled = getattr(settings, 'AI_MOP_ENABLED', False)
        
        system_prompt = get_project_plan_system_prompt()
        user_prompt = get_project_plan_user_prompt(
            name=brief.name,
            industry=brief.industry,
            automation_goals=brief.automation_goals,
            channels=brief.channels,
            description=brief.description,
            communication_tone=brief.communication_tone or "friendly",
            city=brief.city or "",
            content_factory_enabled=content_factory_enabled,
            ai_mop_enabled=ai_mop_enabled,
        )

        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=4000,
                    response_format={"type": "json_object"} if "deepseek" in self.model else None,
                )
                
                content = response.choices[0].message.content
                if not content:
                    raise ProjectPlanGenerationError("Empty response from LLM")
                
                # Parse JSON
                plan_data = self._parse_json_response(content)
                
                # Validate and sanitize plan
                sanitized_plan = self._sanitize_plan(plan_data, brief)
                
                return ProjectPlanResponse(**sanitized_plan)
                
            except json.JSONDecodeError as e:
                last_error = f"JSON parse error: {str(e)}"
                logger.warning(f"Plan generation attempt {attempt + 1} failed: {last_error}")
                if attempt < max_retries:
                    # Add correction hint to prompt for retry
                    user_prompt += f"\n\nPREVIOUS ATTEMPT FAILED with error: {last_error}\nPlease ensure your response is valid JSON without markdown formatting."
                continue
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Plan generation attempt {attempt + 1} failed: {last_error}")
                if attempt < max_retries:
                    continue
                raise ProjectPlanGenerationError(f"Failed to generate plan after {max_retries + 1} attempts: {last_error}")
        
        raise ProjectPlanGenerationError(f"Failed to generate plan: {last_error}")

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling common issues."""
        # Strip markdown code blocks
        content = re.sub(r'^```json\s*', '', content.strip())
        content = re.sub(r'^```\s*', '', content)
        content = re.sub(r'```\s*$', '', content)
        
        # Try to extract JSON if wrapped in other text
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            content = json_match.group(0)
        
        return json.loads(content)

    def _sanitize_plan(
        self,
        plan_data: Dict[str, Any],
        brief: ProjectBriefRequest,
    ) -> Dict[str, Any]:
        """Sanitize and validate the generated plan."""
        
        # Ensure project info
        if "project" not in plan_data:
            plan_data["project"] = {}
        
        plan_data["project"]["name"] = brief.name
        plan_data["project"]["industry"] = brief.industry
        plan_data["project"]["description"] = brief.description[:200]
        
        # Sanitize agents
        agents = plan_data.get("agents", [])
        sanitized_agents: List[Dict[str, Any]] = []
        
        for agent in agents[:MAX_AGENTS]:  # Limit to max agents
            template_type = agent.get("template_type", "qa")
            
            # Filter to allowed template types
            if template_type not in ALLOWED_TEMPLATE_TYPES:
                template_type = "qa"
            
            # Trust LLM choice; only downgrade if goals explicitly exclude the type
            goals = brief.automation_goals or []
            if goals and template_type == "crm_admin" and "booking" not in goals:
                if not any(kw in brief.description.lower() for kw in ["запись", "бронирование", "crm"]):
                    template_type = "qa"

            if goals and template_type == "sales_manager" and "sales" not in goals:
                if not any(kw in brief.description.lower() for kw in ["продаж", "лид", "клиент"]):
                    template_type = "qa"
            
            # Validate system prompt
            system_prompt = agent.get("system_prompt", "")
            if len(system_prompt) < 100:
                system_prompt = self._generate_fallback_prompt(agent.get("suggested_name", "Ассистент"), brief)
            if len(system_prompt) > 2000:
                system_prompt = system_prompt[:1997] + "..."
            
            # Check for forbidden placeholders
            system_prompt = re.sub(r'\{\{[^}]+\}\}', '', system_prompt)
            
            sanitized_agent = {
                "suggested_name": agent.get("suggested_name", "AI Ассистент")[:100],
                "template_type": template_type,
                "system_prompt": system_prompt,
                "welcome_message": agent.get("welcome_message", "Здравствуйте! Чем могу помочь?")[:500],
                "template_config": agent.get("template_config", {}),
            }
            
            # Add minimal crm_admin config if needed
            if template_type == "crm_admin" and not sanitized_agent["template_config"]:
                sanitized_agent["template_config"] = {
                    "services": [
                        {"title": "Консультация", "duration_minutes": 30, "price_minor": 0}
                    ]
                }
            
            sanitized_agents.append(sanitized_agent)
        
        plan_data["agents"] = sanitized_agents
        
        # Sanitize website — trust LLM when no explicit goals, otherwise respect goals
        goals = brief.automation_goals or []
        if goals:
            include_website = "website" in goals
        else:
            include_website = True
        website_data = plan_data.get("website", {})
        
        if not isinstance(website_data, dict):
            website_data = {}
        
        # Generate slug from name
        base_slug = self._slugify(brief.name)
        
        plan_data["website"] = {
            "enabled": include_website and website_data.get("enabled", False),
            "title": website_data.get("title", brief.name)[:100],
            "suggested_slug": website_data.get("suggested_slug", base_slug)[:50],
            "generation_prompt": website_data.get("generation_prompt", self._generate_website_prompt(brief))[:1000],
        }
        
        # Sanitize knowledge recommendations
        knowledge_recs = plan_data.get("knowledge_recommendations", [])
        if not isinstance(knowledge_recs, list):
            knowledge_recs = []
        
        if len(knowledge_recs) < 3:
            # Add default recommendations based on industry
            default_recs = self._generate_default_knowledge_recs(brief)
            knowledge_recs = knowledge_recs + default_recs
        
        plan_data["knowledge_recommendations"] = [str(r)[:100] for r in knowledge_recs[:5]]
        
        # Sanitize CRM hints
        crm_hints = plan_data.get("crm_hints", {})
        if not isinstance(crm_hints, dict):
            crm_hints = {}
        
        has_crm_admin = any(a.get("template_type") == "crm_admin" for a in sanitized_agents)
        
        plan_data["crm_hints"] = {
            "booking_backend": crm_hints.get("booking_backend", "crm"),
            "suggested_services": crm_hints.get("suggested_services", []) if has_crm_admin else [],
        }
        
        return plan_data

    def _slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug."""
        # Simple transliteration for Russian
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
            'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i',
            'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
            'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
            'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch',
            'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '',
            'э': 'e', 'ю': 'yu', 'я': 'ya',
        }
        
        text = text.lower()
        result = []
        for char in text:
            if char in translit_map:
                result.append(translit_map[char])
            elif char.isalnum():
                result.append(char)
            else:
                result.append('-')
        
        slug = ''.join(result)
        slug = re.sub(r'-+', '-', slug).strip('-')
        return slug[:50]

    def _generate_fallback_prompt(self, name: str, brief: ProjectBriefRequest) -> str:
        """Generate fallback system prompt."""
        return f"""Вы — AI-ассистент бизнеса "{brief.name}".

Ваша задача — помогать клиентам, отвечать на вопросы и поддерживать коммуникацию.

О бизнесе: {brief.description[:200]}

Общайтесь вежливо и профессионально. Если не знаете ответ — предложите связаться с менеджером."""

    def _generate_website_prompt(self, brief: ProjectBriefRequest) -> str:
        """Generate website generation prompt."""
        return f"""Создайте современный сайт для бизнеса "{brief.name}".

Бизнес: {brief.industry}
Описание: {brief.description[:300]}

Разделы сайта:
- Главный экран (hero) с призывом к действию
- Описание услуг
- Преимущества
- Контакты и адрес
- Форма обратной связи

Стиль: современный, чистый, профессиональный."""

    def _generate_default_knowledge_recs(self, brief: ProjectBriefRequest) -> List[str]:
        """Generate default knowledge recommendations."""
        recs = ["Описание услуг и цен"]
        desc = brief.description.lower()
        goals = brief.automation_goals or []

        if "booking" in goals or any(kw in desc for kw in ["запись", "бронирован"]):
            recs.append("Регламент записи и отмены")

        if "support" in goals or any(kw in desc for kw in ["поддержк", "вопрос", "faq"]):
            recs.append("Часто задаваемые вопросы (FAQ)")

        if "sales" in goals or any(kw in desc for kw in ["продаж", "прайс", "цен"]):
            recs.append("Описание продуктов и прайс-лист")

        recs.append("Контактная информация и адреса")

        return recs


# Singleton instance
_project_plan_service: Optional[ProjectPlanService] = None


def get_project_plan_service() -> ProjectPlanService:
    """Get or create ProjectPlanService singleton."""
    global _project_plan_service
    if _project_plan_service is None:
        _project_plan_service = ProjectPlanService()
    return _project_plan_service
