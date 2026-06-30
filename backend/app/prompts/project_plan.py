"""Prompts for AI project plan generation."""

from typing import List


def get_project_plan_system_prompt() -> str:
    """System prompt for project plan generation."""
    return """You are an expert business automation consultant specializing in AI solutions for small and medium businesses.

Your task is to analyze the business brief provided by the user and generate a comprehensive AI automation plan in JSON format.

RULES:
1. Analyze the business description and determine which AI agents are needed (1-4 maximum)
2. Only use these template types: qa, crm_admin, sales_manager
3. Do NOT suggest content_factory or ai_manager unless explicitly requested in settings
4. System prompts must be in Russian, 500-2000 characters, without {{}} placeholders
5. Welcome messages should be friendly and professional
6. For crm_admin, include minimal template_config with services if booking is mentioned
7. Suggest a website if the business would benefit from one (infer from description)
8. Infer communication tone and location from the description when not specified
9. Knowledge recommendations should be practical documents the business likely has

CRITICAL: Respond ONLY with valid JSON matching the schema. No markdown, no explanations."""


def _infer_agents_from_description(description: str) -> List[str]:
    """Infer suggested agent types from business description."""
    desc = description.lower()
    suggested = []

    support_keywords = ["поддержк", "консультац", "вопрос", "помощ", "faq", "справк"]
    booking_keywords = ["запись", "бронирован", "расписан", "приём", "прием", "crm", "календар"]
    sales_keywords = ["продаж", "лид", "заказ", "покуп", "клиент", "конверс"]

    if any(kw in desc for kw in support_keywords):
        suggested.append("qa")
    if any(kw in desc for kw in booking_keywords):
        suggested.append("crm_admin")
    if any(kw in desc for kw in sales_keywords):
        suggested.append("sales_manager")

    if not suggested:
        suggested = ["qa"]

    return suggested


def _infer_website_from_description(description: str) -> bool:
    """Infer whether a website is needed from business description."""
    desc = description.lower()
    website_keywords = ["сайт", "лендинг", "онлайн", "визитк", "страниц"]
    return any(kw in desc for kw in website_keywords)


def get_project_plan_user_prompt(
    name: str,
    industry: str,
    automation_goals: List[str],
    channels: List[str],
    description: str,
    communication_tone: str = "friendly",
    city: str = "",
    content_factory_enabled: bool = False,
    ai_mop_enabled: bool = False,
) -> str:
    """User prompt for project plan generation."""

    # Build available template types
    available_templates = ["qa", "crm_admin", "sales_manager"]
    if content_factory_enabled:
        available_templates.append("content_factory")
    if ai_mop_enabled:
        available_templates.append("ai_manager")

    # Determine agents: use explicit goals if provided, otherwise infer from description
    if automation_goals:
        suggested_agents = []
        if "support" in automation_goals:
            suggested_agents.append("qa")
        if "booking" in automation_goals:
            suggested_agents.append("crm_admin")
        if "sales" in automation_goals:
            suggested_agents.append("sales_manager")
        if not suggested_agents:
            suggested_agents = _infer_agents_from_description(description)
    else:
        suggested_agents = _infer_agents_from_description(description)

    if automation_goals:
        include_website = "website" in automation_goals or _infer_website_from_description(description)
    else:
        include_website = _infer_website_from_description(description)

    goals_line = (
        f"- Automation Goals: {', '.join(automation_goals)}"
        if automation_goals
        else "- Automation Goals: Determine from description"
    )

    prompt = f"""Generate an AI automation plan for the following business:

BUSINESS INFORMATION:
- Name: {name}
- Industry: {industry}
- Description: {description}
{goals_line}

REQUIREMENTS:
1. Analyze the description and create {len(suggested_agents)} AI agent(s) as a starting point: {', '.join(suggested_agents)}
2. You may adjust the number and types of agents (1-4) based on actual business needs
3. Available template types: {', '.join(available_templates)}
4. Website: {'Yes — include if beneficial' if include_website else 'Decide based on business needs'}
5. Infer communication tone and city/region from the description
6. Maximum 4 agents total
7. All text in Russian
8. System prompts: 500-2000 chars, no placeholders

Generate a JSON response with this structure:
{{
  "project": {{
    "name": "Business name (keep original or slightly improved)",
    "description": "Brief business description",
    "industry": "{industry}"
  }},
  "agents": [
    {{
      "suggested_name": "Role name in Russian (e.g., 'Администратор салона')",
      "template_type": "One of: {', '.join(available_templates)}",
      "system_prompt": "Detailed system prompt in Russian describing the agent's role, responsibilities, tone, and how to handle various scenarios. 500-2000 characters.",
      "welcome_message": "Short friendly welcome message the agent sends first",
      "template_config": {{}} // For crm_admin: include suggested services if applicable
    }}
  ],
  "website": {{
    "enabled": {str(include_website).lower()},
    "title": "Website title in Russian",
    "suggested_slug": "url-friendly-slug-based-on-business-name",
    "generation_prompt": "Detailed prompt for AI website generation describing style, sections needed, color scheme based on industry"
  }},
  "knowledge_recommendations": [
    "List 3-5 specific documents the business should upload",
    "Examples: price list, service catalog, FAQ, regulations"
  ],
  "crm_hints": {{
    "booking_backend": "crm",
    "suggested_services": ["Service 1", "Service 2"] // If crm_admin agent suggested
  }}
}}

IMPORTANT: Ensure valid JSON with no trailing commas, no markdown code blocks, no comments."""

    return prompt
