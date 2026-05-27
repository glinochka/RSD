# Отказ от MailoPost: своя почта на rsd-ai.ru (REG.RU)

Документ описывает переход RSD с API [MailoPost](https://mailopost.ru) на отправку писем через **свой SMTP** на сервере REG.RU с адресом **`noreply@rsd-ai.ru`**.

**Причина перехода:** MailoPost помечает отправки как спам и блокирует доставку — контроль над репутацией домена и настройками DNS переходит к вам.

---

## 1. Текущее состояние в проекте RSD

Сейчас все письма уходят одним способом: HTTP `POST https://api.mailopost.ru/v1/email/messages` с Bearer-токеном.

| Сценарий | Модуль |
|----------|--------|
| Код подтверждения регистрации, сброс пароля, welcome | `backend/app/router_users/router.py` |
| Админские рассылки (все пользователи / группы), с паузой между письмами | `backend/app/router_admin/router.py` |
| Напоминания неактивным (onboarding) | `backend/app/services/onboarding_email_maintenance.py` |
| Уведомление владельцу агента (QA handoff) | `backend/app/services/qa_handoff_service.py` |

Переменные окружения (`.env`):

```env
MAILOPOST_API_URL=https://api.mailopost.ru/v1
MAILOPOST_API_TOKEN=...
MAILOPOST_FROM_EMAIL=noreply@rsd-ai.ru
MAILOPOST_FROM_NAME=...
MAILOPOST_SEND_TIMEOUT_SECONDS=10
MAILOPOST_BROADCAST_INTERVAL_SECONDS=900
MAILOPOST_REMINDER_BATCH_INTERVAL_SECONDS=1800
```

HTML-шаблоны писем уже формируются в коде RSD; MailoPost используется только как **транспорт**.

---

## 2. Целевая архитектура

```
┌─────────────────┐     SMTP (587/465)      ┌──────────────────────────┐
│  RSD backend    │ ──────────────────────► │  Postfix на VPS REG.RU   │
│  EmailService   │   noreply@rsd-ai.ru     │  + OpenDKIM              │
└─────────────────┘                         └────────────┬─────────────┘
                                                         │
                                                         ▼
                                              Получатели (Gmail, Mail.ru, …)
```

- **Домен:** `rsd-ai.ru` — DNS в панели REG.RU.
- **Сервер:** тот же VPS/выделенный сервер REG.RU, где уже крутится приложение (или отдельный хост — тогда PTR и SPF должны указывать на него).
- **Отправитель:** `noreply@rsd-ai.ru` (транзакционка + сервисные письма). Для массовых рассылок позже можно добавить `news@rsd-ai.ru` на отдельном поддомене.

---

## 3. Инфраструктура на REG.RU (до правок в коде)

### 3.1. DNS записи (панель REG.RU → домен `rsd-ai.ru`)

Подставьте IP вашего сервера вместо `YOUR_SERVER_IP`.

| Тип | Имя | Значение | Зачем |
|-----|-----|----------|--------|
| **A** | `mail` | `YOUR_SERVER_IP` | Хост для SMTP (если шлёте с `mail.rsd-ai.ru`) |
| **MX** | `@` | `10 mail.rsd-ai.ru` | Только если принимаете входящую почту на домен |
| **TXT** | `@` | `v=spf1 ip4:YOUR_SERVER_IP a:mail.rsd-ai.ru -all` | SPF — кто может слать от имени домена |
| **TXT** | `_dmarc` | `v=DMARC1; p=quarantine; rua=mailto:dmarc@rsd-ai.ru; pct=100` | Политика DMARC (сначала можно `p=none` на 2 недели) |
| **TXT** | `default._domainkey` | `v=DKIM1; k=rsa; p=...` | Публичный ключ DKIM (генерируется на сервере) |

**PTR (обратная DNS):** в REG.RU для IP сервера задайте имя вида `mail.rsd-ai.ru`. Без PTR Gmail и Mail.ru часто режут доставку.

### 3.2. Почтовый сервер на VPS (краткий чеклист)

На сервере (Ubuntu/Debian — типично для REG.RU):

1. Установить **Postfix** (исходящая почта), **OpenDKIM** (подпись).
2. В Postfix: `myhostname = mail.rsd-ai.ru`, `mydomain = rsd-ai.ru`, разрешить SASL-авторизацию для приложения.
3. Создать ящик или системного пользователя для SMTP-логина (например `noreply` / пароль только для приложения).
4. Сгенерировать DKIM-ключ, прописать селектор `default` в DNS (см. таблицу выше).
5. Открыть порты **25** (исходящий к миру), **587** (submission с TLS) — в firewall REG.RU и `ufw`.
6. TLS-сертификат: Let's Encrypt для `mail.rsd-ai.ru` (certbot).

Проверка после настройки:

- [mail-tester.com](https://www.mail-tester.com) — целевой балл 8+/10.
- [MXToolbox](https://mxtoolbox.com/SuperTool.aspx) — SPF, DKIM, blacklist, PTR.

### 3.3. Прогрев и лимиты

Новый IP/домен без истории — риск «спам» даже без MailoPost.

| Тип писем | Рекомендация на старте |
|-----------|-------------------------|
| Коды регистрации / сброс пароля | Сразу, объём низкий |
| Welcome, QA handoff | Сразу |
| Админские рассылки | Начать с паузы **≥ 15 мин** (`MAILOPOST_BROADCAST_INTERVAL_SECONDS` → позже `EMAIL_BROADCAST_INTERVAL_SECONDS`), не более **50–100 писем/день** первую неделю, наращивать постепенно |
| Onboarding-напоминания | Включить после стабильной доставки кодов |

Текущие лимиты MailoPost (429 в логах) исчезнут — **свой rate limit** нужно задать в коде/очереди, иначе IP попадёт в RBL.

---

## 4. Изменения в коде RSD (план работ)

### 4.1. Единый сервис отправки

Создать модуль, например `backend/app/services/email/service.py`:

- Метод `send_email(*, to, subject, text, html, from_name=None)`.
- Бэкенды: `smtp` (целевой), `mailopost` (временный fallback на время миграции).

Заменить прямые вызовы `httpx` → MailoPost в:

- `router_users/router.py`
- `router_admin/router.py` (`_post_mailopost_email_response` → общий сервис)
- `onboarding_email_maintenance.py`
- `qa_handoff_service.py`

### 4.2. Новые переменные окружения

```env
# backend
EMAIL_BACKEND=smtp          # smtp | mailopost (на переходный период)

EMAIL_FROM=noreply@rsd-ai.ru
EMAIL_FROM_NAME=RSD

SMTP_HOST=mail.rsd-ai.ru    # или 127.0.0.1, если Postfix на том же хосте, что и backend
SMTP_PORT=587
SMTP_USER=noreply@rsd-ai.ru
SMTP_PASSWORD=...           # секрет, не коммитить
SMTP_USE_TLS=true
SMTP_TIMEOUT_SECONDS=30

# интервалы рассылок (переименовать с MAILOPOST_*)
EMAIL_BROADCAST_INTERVAL_SECONDS=900
EMAIL_REMINDER_BATCH_INTERVAL_SECONDS=1800
```

Старые `MAILOPOST_*` удалить после успешного теста на production.

Зависимость: `aiosmtplib` в `backend/requirements.txt`.

### 4.3. Очередь для массовых рассылок (желательно во 2-й фазе)

Сейчас рассылка живёт в памяти процесса FastAPI (`_admin_mass_mail_jobs`). При перезапуске контейнера job теряется.

Рекомендация: Redis (уже есть в проекте) + worker для фоновой отправки с тем же `interval_seconds`.

### 4.4. Фронтенд

В `frontend/src/pages/ManagementPortal.jsx` обновить тексты: убрать ссылки на MailoPost API, указать «отправка через SMTP домена rsd-ai.ru».

### 4.5. Тесты

Обновить моки в `backend/app/tests/test_users_router.py` — патчить `EmailService.send_email` вместо `_send_registration_email_code` с привязкой к MailoPost.

---

## 5. Порядок миграции (пошагово)

| Шаг | Действие | Готово |
|-----|----------|--------|
| 1 | Настроить Postfix + DKIM + DNS на REG.RU | ☐ |
| 2 | Отправить тестовое письмо с сервера (`swaks` / `sendmail`) на Gmail и Mail.ru | ☐ |
| 3 | Реализовать `EmailService` + SMTP в backend | ☐ |
| 4 | На staging: `EMAIL_BACKEND=smtp`, проверить регистрацию и сброс пароля | ☐ |
| 5 | Production: переключить env, мониторить логи 24–48 ч | ☐ |
| 6 | Отключить MailoPost: убрать токен, удалить `MAILOPOST_*` из кода и `.env` | ☐ |
| 7 | Включить админские рассылки с консервативным лимитом | ☐ |

**Откат:** вернуть `EMAIL_BACKEND=mailopost` и старые `MAILOPOST_*` (пока аккаунт MailoPost ещё активен).

---

## 6. Риски и как их снизить

| Риск | Митигация |
|------|-----------|
| Письма в спам у получателей | SPF + DKIM + DMARC + PTR; mail-tester; не слать рассылки с `noreply@` |
| Блокировка IP REG.RU | Не слать тысячи писем сразу; свой throttling; отдельный поддомен для маркетинга |
| MailoPost перестанет быть запасным каналом | Держать fallback только на этапе 4–5 |
| Жалобы на рассылку | Ссылка «отписаться» в маркетинговых письмах; не слать неподтверждённым |
| Docker backend не видит localhost SMTP | `SMTP_HOST=host.docker.internal` или IP хоста / sidecar Postfix в compose |

---

## 7. Связь с REG.RU (практические заметки)

- **Домен и DNS** — раздел «Домены» → `rsd-ai.ru` → записи SPF/DKIM/DMARC.
- **VPS** — раздел «Облако» / «VPS» → тот сервер, где крутится RSD; там же ставится Postfix.
- Если почта «уже работает» на REG.RU как **почтовый хостинг** (не свой Postfix), можно использовать **их SMTP** (`smtp.hosting.reg.ru` или из справки REG.RU) с логином `noreply@rsd-ai.ru` — тогда в RSD достаточно `EMAIL_BACKEND=smtp` без установки Postfix, но DKIM/SPF всё равно настраиваются в панели REG.RU по их инструкции.

Уточните у себя: почта на сервере — **свой Postfix** или **почта REG.RU как сервис**. От этого зависит только `SMTP_HOST` / порты; код RSD одинаковый.

---

## 8. Контрольный список «готово к отключению MailoPost»

- [ ] Тестовое письмо с `noreply@rsd-ai.ru` доходит в Inbox (не Spam) в Gmail и Mail.ru
- [ ] SPF/DKIM/DMARC проходят проверку (MXToolbox / заголовки письма `Authentication-Results`)
- [ ] Регистрация и сброс пароля на production работают через SMTP
- [ ] Welcome и QA handoff проверены вручную
- [ ] Одна малая админ-рассылка (5–10 адресов) прошла без жалоб
- [ ] `MAILOPOST_API_TOKEN` удалён из `.env` и секретов CI
- [ ] В репозитории нет обращений к `api.mailopost.ru`

---

## 9. Ссылки

- [Документация MailoPost API](https://mailopost.ru/api.html) — только для сравнения при миграции
- [REG.RU — помощь по почте и DNS](https://www.reg.ru/support/)
- Текущие настройки приложения: `backend/app/config.py` (блок `MAILOPOST_*`)

---

*Документ создан для миграции проекта RSD. После реализации `EmailService` этот файл можно сократить до раздела «Эксплуатация» (DNS, лимиты, мониторинг).*
