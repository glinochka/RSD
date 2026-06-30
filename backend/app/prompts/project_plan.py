"""Prompts for AI project plan generation."""

from typing import List


def get_project_plan_system_prompt() -> str:
    """System prompt for project plan generation."""
    return """You are an expert business automation consultant specializing in AI solutions for small and medium businesses.

Your task is to analyze the business brief provided by the user and generate a comprehensive AI automation plan in JSON format.

RULES:
1. Generate 1-4 AI agents maximum, depending on business needs
2. Only use these template types: qa, crm_admin, sales_manager
3. Do NOT suggest content_factory or ai_manager unless explicitly requested in settings
4. System prompts must be in Russian, 500-2000 characters, without {{}} placeholders
5. Welcome messages should be friendly and professional
6. For crm_admin, include minimal template_config with services if booking is mentioned
7. Suggest a website ONLY if "website" is in automation_goals
8. Knowledge recommendations should be practical documents the business likely has

CRITICAL: Respond ONLY with valid JSON matching the schema. No markdown, no explanations."""


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
    
    tone_descriptions = {
        "friendly": "дружелюбный, теплый, обращение на 'ты'",
        "business": "деловой, профессиональный, обращение на 'вы'",
        "premium": "премиальный, вежливый, изысканный, обращение на 'вы'",
    }
    
    tone_desc = tone_descriptions.get(communication_tone, tone_descriptions["friendly"])
    
    # Map goals to agent types
    goal_mapping = {
        "support": "qa agent for customer support",
        "booking": "crm_admin agent for appointments and scheduling",
        "sales": "sales_manager agent for sales and lead qualification",
        "content": "content_factory agent for content generation" if content_factory_enabled else None,
    }
    
    # Build available template types
    available_templates = ["qa", "crm_admin", "sales_manager"]
    if content_factory_enabled:
        available_templates.append("content_factory")
    if ai_mop_enabled:
        available_templates.append("ai_manager")
    
    # Determine required agents based on goals
    suggested_agents = []
    if "support" in automation_goals or "поддержка" in description.lower():
        suggested_agents.append("qa")
    if "booking" in automation_goals or "запись" in description.lower() or "crm" in description.lower():
        suggested_agents.append("crm_admin")
    if "sales" in automation_goals or "продаж" in description.lower():
        suggested_agents.append("sales_manager")
    
    # Ensure at least one agent
    if not suggested_agents:
        suggested_agents = ["qa"]
    
    include_website = "website" in automation_goals or "сайт" in description.lower()
    
    prompt = f"""Generate an AI automation plan for the following business:

BUSINESS INFORMATION:
- Name: {name}
- Industry: {industry}
- Location: {city or "Not specified"}
- Description: {description}
- Automation Goals: {', '.join(automation_goals)}
- Communication Channels: {', '.join(channels) if channels else "Not specified"}
- Communication Tone: {tone_desc}

REQUIREMENTS:
1. Create {len(suggested_agents)} AI agent(s): {', '.join(suggested_agents)}
2. Available template types: {', '.join(available_templates)}
3. Website: {'Yes' if include_website else 'No - only if website in goals'}
4. Maximum 4 agents total
5. All text in Russian
6. System prompts: 500-2000 chars, no placeholders

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
