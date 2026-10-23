"""Parent prompts that write the project skills.

These instructions never go to Telegram. They tell the author model how to
build or revise the runtime prompt attached to one activity.
"""
from __future__ import annotations

from typing import Any


SKILLBASE_AUTHOR = """Ты собираешь скиллбейз одного проекта. Скилл — это рабочая инструкция, которую потом получит другая модель в конкретной активности Telegram-фермы. Ты не пишешь сообщение клиенту и не пишешь пост. Ты пишешь инструкцию для той модели.

Как думать:
- Сначала вытащи из брифа бизнес, продукт, процесс, воронку и жёсткие условия. Это единственный источник фактов.
- Не выдумывай цены, скидки, сроки, гарантии, лицензии, кейсы и имена клиентов. Если факта нет в брифе или базе знаний — запрети модели его утверждать и вели задать вопрос.
- Голос живой и конкретный для этого бизнеса, не «универсальный маркетолог». Табу и оффер бери из брифа.
- Инструкция на русском. Коротко и плотно: роль, что делать, чего не делать, как звучать, затем контракт ответа.
- Каждый плейсхолдер из списка активности оставь дословно, в фигурных скобках, один раз в том месте, куда модель должна подставить данные. Не переводи имена, не удваивай скобки, не прячь их в пример.
- Контракт ответа сохрани буквально: те же ключи JSON или тот же вид текста, который указан в активности. Не добавляй markdown и не оборачивай ответ в ``` .
- Не ссылайся на «базу знаний» и «бриф» внутри готового скилла. Перенеси нужные факты прямо в инструкцию.
- Шиллинг — это две готовые реплики людей, не инструкция. Нейроблог — это памятка автору постов, не сам пост.

Верни один JSON-объект:
{"skills":[{"key":"...","content":"..."}]}
Для шиллинга у объекта нет content, есть "setup" и "reply".
Ключи — только из списка активностей. Никакого текста вне JSON."""


SKILLBASE_EDITOR = """Ты правишь один скилл проекта. Человек описал, что ему не нравится в активности, где этот скилл уже работает. Внеси правку в инструкцию, а не в переписку с клиентом.

Правила:
- Сохрани все плейсхолдеры {имя} дословно и контракт ответа (те же ключи JSON или тот же вид текста).
- Поменяй только то, о чём просит человек, и то, без чего инструкция станет противоречивой.
- Факты бери из брифа. Не добавляй цены, гарантии и кейсы, которых там нет.
- Если человек просит тон, длину, частоту упоминания продукта или запрет — пропиши это явно.
- Верни JSON {"content":"..."} .
- Для шиллинга верни JSON {"setup":"...","reply":"..."} без content.
- Никакого текста вне JSON."""


ACTIVITIES: list[dict[str, Any]] = [
    {
        "key": "chat_monitoring_trigger",
        "title": "Перехват заявок: триггер",
        "where": "Решает, является ли сообщение в чате заявкой на продукт проекта.",
        "variables": ["text"],
        "anchors": ["{text}", '"is_lead"', '"confidence"', '"reason"', '"contact_type"', '"contact_value"'],
        "contract": 'Только JSON: {"is_lead": true/false, "confidence": 0.0-1.0, "reason": "...", "contact_type": "telegram", "contact_value": "..."}.',
        "shape": "content",
    },
    {
        "key": "chat_monitoring_response",
        "title": "Перехват заявок: первое ЛС",
        "where": "Пишет первое личное сообщение человеку, чьё сообщение в чате признали заявкой.",
        "variables": ["text"],
        "anchors": ["{text}", '"message"'],
        "contract": 'Только JSON: {"message": "текст ЛС"}. 1–3 коротких предложения, без ссылки в первом касании.',
        "shape": "content",
    },
    {
        "key": "neurocommenting",
        "title": "Нейрокомментинг",
        "where": "Комментарий под чужим постом канала. Нативный, без рекламной плашки.",
        "variables": ["post_text", "chat_title"],
        "anchors": ["{post_text}", "{chat_title}", '"comment"'],
        "contract": 'Только JSON: {"comment": "1-2 предложения"}. Без хештегов и без ссылки.',
        "shape": "content",
    },
    {
        "key": "discussion_reply",
        "title": "Нейрочаттинг",
        "where": "Ответ в обсуждении чата, когда к аккаунту обратились.",
        "variables": ["message_text", "chat_title"],
        "anchors": ["{message_text}", "{chat_title}", '"reply"'],
        "contract": 'Только JSON: {"reply": "1-3 предложения"}. Без ссылки и без навязанного оффера.',
        "shape": "content",
    },
    {
        "key": "dmp_outreach",
        "title": "DMP: первое сообщение",
        "where": "Первое ЛС человеку, который был на сайте. Не признаваться, что его отследили.",
        "variables": ["name", "company", "website", "page", "partner_utm_url", "partner_promo_code", "registered"],
        "anchors": [
            "{name}",
            "{company}",
            "{website}",
            "{page}",
            "{partner_utm_url}",
            "{partner_promo_code}",
            "{registered}",
            '"message"',
        ],
        "contract": 'Только JSON: {"message": "..."}. URL и промокод не вставлять, пока человек сам не попросил.',
        "shape": "content",
    },
    {
        "key": "lead_qualification",
        "title": "Квалификация лида",
        "where": "Ведёт переписку и решает: ещё греть, передать менеджеру или закрыть как отказ.",
        "variables": ["history", "last_incoming", "partner_utm_url", "partner_promo_code"],
        "anchors": [
            "{history}",
            "{last_incoming}",
            "{partner_utm_url}",
            "{partner_promo_code}",
            '"qualified"',
            '"lost"',
            '"continue"',
            '"reply"',
        ],
        "contract": 'Только JSON: {"qualified": true/false, "lost": true/false, "continue": true/false, "reply": "..."}.',
        "shape": "content",
    },
    {
        "key": "chat_relevance",
        "title": "Релевантность чата",
        "where": "Оценивает, подходит ли чат или канал под кампанию проекта.",
        "variables": ["query", "title", "description", "chat_type", "participants_count"],
        "anchors": ["{query}", "{title}", "{description}", "{chat_type}", "{participants_count}", '"score"', '"reason"', '"relevant"'],
        "contract": 'Только JSON: {"score": 0.0-1.0, "reason": "...", "relevant": true/false}.',
        "shape": "content",
    },
    {
        "key": "profile_bio",
        "title": "Описание профиля",
        "where": "Пишет короткое bio аккаунта в тематике проекта, без ссылки на канал.",
        "variables": ["industry", "name"],
        "anchors": ["{industry}", "{name}", '"bio"'],
        "contract": 'Только JSON: {"bio": "до 140 символов"}.',
        "shape": "content",
    },
    {
        "key": "shilling",
        "title": "Шиллинг",
        "where": "Две реплики: первый аккаунт спрашивает, второй отвечает как пользователь продукта.",
        "variables": [],
        "anchors": [],
        "contract": "Две живые реплики на русском, без ссылки и без слова «скилл». Вопрос сомневающийся, ответ по делу и без рекламного напора.",
        "shape": "pair",
    },
    {
        "key": "inbound_dm",
        "title": "Входящее ЛС",
        "where": "Отвечает на входящее личное сообщение. Модель должна вернуть голый текст, не JSON.",
        "variables": ["incoming", "product_context", "partner_utm_url", "partner_promo_code"],
        "anchors": ["{incoming}", "{product_context}", "{partner_utm_url}", "{partner_promo_code}"],
        "contract": "В конце инструкции прямо напиши: верни только текст ответа, без JSON и без кавычек. Ссылку давать только после прямой просьбы.",
        "shape": "content",
    },
    {
        "key": "neuroblog",
        "title": "Нейроблог",
        "where": "Памятка автору постов: ниша, какие новости обыгрывать, табу, когда уместны злость, сатира и мат.",
        "variables": [],
        "anchors": [],
        "contract": "Связный текст памятки на 120–220 слов. Потребуй повод из новости ниши и живой голос. Это не пост и не JSON.",
        "shape": "content",
        "storage": "neuroblog",
    },
]


def activity_by_key(key: str) -> dict[str, Any] | None:
    for item in ACTIVITIES:
        if item["key"] == key:
            return item
    return None


def activity_public(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": item["key"],
        "title": item["title"],
        "where": item["where"],
        "variables": list(item["variables"]),
        "storage": item.get("storage") or "prompt",
    }
