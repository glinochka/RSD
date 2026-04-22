def escape_md(text: str) -> str:
    """Экранирует нижнее подчеркивание для стандартного Markdown."""
    if not text:
        return ""
    return text.replace("_", "\\_")


def build_start_menu_text(first_name: str | None = None) -> str:
    if first_name:
        return (
            f"Привет, {first_name}! Это конструктор AI-агентов.\n\n"
            "Здесь ты можешь создать своего бота с кастомными промптами и базой знаний."
        )
    return (
        "Привет! Это конструктор AI-агентов.\n\n"
        "Здесь ты можешь создать своего бота с кастомными промптами и базой знаний."
    )


def format_price_rub_month(price_rub_month: int) -> str:
    if not price_rub_month:
        return "0\u20bd/\u043c\u0435\u0441"
    return f"{price_rub_month:,}".replace(",", " ") + "\u20bd/\u043c\u0435\u0441"


def format_kb_limit(limit) -> str:
    if limit is None:
        return "\u0411\u0435\u0437\u043b\u0438\u043c\u0438\u0442"
    return f"{limit} \u0447\u0430\u043d\u043a\u043e\u0432"


def build_tariffs_text(plans: list[dict], current_plan_code: str) -> str:
    order = {"Free": 1, "Advanced": 2, "Pro": 3}
    plans_sorted = sorted(plans, key=lambda p: order.get(p.get("code"), 999))

    lines: list[str] = [
        "\U0001F48E *\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u043e\u0439*",
        "",
        f"\u0412\u0430\u0448 \u0442\u0435\u043a\u0443\u0449\u0438\u0439 \u0442\u0430\u0440\u0438\u0444: *{current_plan_code}*",
        "",
        "\U0001F680 *\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0435 \u043f\u043b\u0430\u043d\u044b:*",
        "",
    ]

    emoji_by_code = {"Free": "1\ufe0f\u20e3", "Advanced": "2\ufe0f\u20e3", "Pro": "3\ufe0f\u20e3"}

    for plan in plans_sorted:
        code = plan.get("code")
        title = plan.get("title") or code
        max_agents = plan.get("max_active_agents")
        kb_limit = plan.get("knowledge_base_chunk_limit")
        price = plan.get("price_rub_month", 0)

        if not code:
            continue

        lines.extend(
            [
                f"{emoji_by_code.get(code, '')} *{title}*".strip(),
                f"\u2014 \u0414\u043e {max_agents} \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445 \u0430\u0433\u0435\u043d\u0442\u043e\u0432"
                if code != "Free"
                else f"\u2014 {max_agents} \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0439 \u0430\u0433\u0435\u043d\u0442",
                f"\u2014 \u041b\u0438\u043c\u0438\u0442 \u0431\u0430\u0437\u044b \u0437\u043d\u0430\u043d\u0438\u0439: {format_kb_limit(kb_limit)}",
                f"\u2014 \u0426\u0435\u043d\u0430: {format_price_rub_month(int(price or 0))}",
                "",
            ]
        )

    return "\n".join(lines).strip()
