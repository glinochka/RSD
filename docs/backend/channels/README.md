# Backend — каналы сообщений

Долгоживущие менеджеры userbot/bot для Telegram, MAX и WhatsApp. Приём и отправка сообщений в runtime агента.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| Telegram userbot | `backend/app/channels/userbot_manager.py` |
| MAX bot | `backend/app/channels/max_bot_manager.py` |
| MAX userbot | `backend/app/channels/max_userbot_manager.py` |
| WhatsApp userbot | `backend/app/channels/whatsapp_userbot_manager.py` |
| Обработчик сообщений | `backend/app/channels/message_processor.py` |
| Telephony-диалог | `backend/app/channels/telephony_dialogue.py` |
| Базовые типы | `backend/app/channels/base.py` |
| Leader lock | `backend/app/channels/leader_lock.py` |
| Telegram auth | `backend/app/services/telegram_userbot_auth.py` |
| MAX auth / session | `backend/app/services/max_userbot_auth.py`, `max_userbot_session.py` |
| WA bridge (вне backend) | `wa_bridge/` |

## Жизненный цикл

Все менеджеры стартуют в `server.py` → `lifespan` как `asyncio.Task` с `run_forever()`.

## Связанные модули

- [agents](../agents/) — настройки канала на агенте, runtime
- [telephony](../../telephony/) — голосовой канал (отдельный стек)

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| Telegram userbot | `TELEGRAM.md` | TODO |
| MAX | `MAX.md` | TODO |
| WhatsApp | `WHATSAPP.md` | TODO |
| Протокол message_processor | `MESSAGE_PROCESSOR.md` | TODO |
| Runbook | `RUNBOOK.md` | TODO |
