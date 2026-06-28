# Backend — каналы сообщений

Долгоживущие менеджеры userbot/bot для Telegram, MAX и WhatsApp. Приём и отправка сообщений в runtime агента.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| **Polling loop (общий)** | `backend/app/channels/polling_manager.py` |
| Telegram userbot | `backend/app/channels/userbot_manager.py` |
| MAX bot | `backend/app/channels/max_bot_manager.py` |
| MAX userbot | `backend/app/channels/max_userbot_manager.py` |
| WhatsApp userbot | `backend/app/channels/whatsapp_userbot_manager.py` |
| Обработчик сообщений | `backend/app/channels/message_processor.py` |
| Telephony-диалог | `backend/app/channels/telephony_dialogue.py` |
| Базовые типы | `backend/app/channels/base.py` (`ChannelManager` ABC) |
| Leader lock | `backend/app/channels/leader_lock.py` |
| Telegram auth | `backend/app/services/telegram_userbot_auth.py` |
| MAX auth / session | `backend/app/services/max_userbot_auth.py`, `max_userbot_session.py` |
| WhatsApp JID utils | `backend/app/utils/whatsapp_jid.py` |
| Загрузка конфигов каналов | `backend/app/router_agents/dao.py` → `AgentChannelConnectionDAO.fetch_active_channel_configs` |
| WA bridge (вне backend) | `wa_bridge/` |

## PollingChannelManager

Userbot-менеджеры (Telegram, MAX, WhatsApp) наследуют `PollingChannelManager`:

1. Postgres leader lock — один инстанс backend ведёт polling.
2. Периодический poll БД через `fetch_configs()` → `AgentChannelConnectionDAO.fetch_active_channel_configs(provider)`.
3. На каждое подключение — asyncio worker; при смене fingerprint конфига worker перезапускается (WhatsApp — явный override).

`MaxBotManager` использует тот же DAO для fetch, но свой transport (не наследует `PollingChannelManager`).

## Жизненный цикл

Все менеджеры стартуют в `server.py` → `lifespan` как `asyncio.Task` с `run_forever()`.

## Связанные модули

- [agents](../agents/) — настройки канала на агенте, runtime, API userbot auth
- [telephony](../../telephony/) — голосовой канал (отдельный стек)

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| Sub-routers каналов | [agents/ROUTERS.md](../agents/ROUTERS.md) | готово |
| Telegram userbot | `TELEGRAM.md` | TODO |
| MAX | `MAX.md` | TODO |
| WhatsApp | `WHATSAPP.md` | TODO |
| Протокол message_processor | `MESSAGE_PROCESSOR.md` | TODO |
| Runbook | `RUNBOOK.md` | TODO |
