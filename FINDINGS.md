# Этап 1 — сводка находок (RSD)

> Дата аудита: **2026-06-23**  
> Источник: пентест с ПК + внутренняя разведка VPS `195.133.26.134`  
> Логи: `security-audit-logs/00_README.txt`

## Резюме

Снаружи открыты внутренние сервисы (Qdrant, backend, telephony, bot) — вероятно из‑за `docker-compose.override.yml` с `0.0.0.0`. PostgreSQL и Redis с интернета закрыты. SSH принимает пароль root при активном брутфорсе; fail2ban/lynis/trivy не установлены. CORS отражает произвольный `Origin` с `credentials` на `/api/users/me`. Публичны OpenAPI/Swagger на `api.rsd-ai.ru`. Нет HSTS. Сертификат Let's Encrypt истекает **2026-06-25**.

---

## Таблица находок

| ID | Источник | Критичность | Статус Этап 2 | Описание | Где смотреть | Рекомендация |
|----|----------|-------------|---------------|----------|--------------|--------------|
| F-001 | ПК §1.2–1.3, VPS §2.2 | **Critical** | Исправлено в репо — **деплой на VPS** | Порты 6333, 8000–8002, 8100, 8200 открыты в интернет (uvicorn/Express/Qdrant) | `02_nmap.txt`, `03_external_db_ports.txt`, `ss -tulpn` | Удалить/заменить `docker-compose.override.yml` с `0.0.0.0`; см. `deployment/VPS_STAGE2_DEPLOY.md` |
| F-002 | VPS §2.1 | **Critical** | Ручной шаг VPS | SSH: `Accepted password for root`; постоянный брутфорс | `journalctl -u ssh` | `PasswordAuthentication no`, ключи, fail2ban — `security-tools/install-vps.sh` |
| F-003 | VPS §2.5 | **High** | Ручной шаг VPS | `.env` права `644`; в каталоге проекта `.env.save`, cookie-файлы | `16_files_permissions.txt` | `chmod 600 .env`; убрать секреты из git-tracked tree |
| F-004 | ПК §1.6, nuclei | **High** | Исправлено в коде | CORS: произвольный `Origin` + `allow-credentials` на `/api/users/me` | `06_cors.txt`, nuclei `cors-misconfig` | `backend/app/middleware/cors.py` — строгий CORS для auth |
| F-005 | ПК §1.5–1.6 | **High** | Исправлено в nginx + код | Публичны `/docs`, `/redoc`, `/openapi.json` на `api.rsd-ai.ru` | `04_tls_headers.txt`, nuclei `fastapi-docs` | nginx 404 + `ENVIRONMENT=production` (уже в коде) |
| F-006 | ПК §1.4–1.5 | **Medium** | Исправлено в nginx | Нет HSTS, CSP, Referrer-Policy на фронте | nuclei `http-missing-security-headers` | `frontend/nginx.conf` |
| F-007 | ПК §1.3 | **Low** | OK | PostgreSQL 5432, Redis 6379 с интернета закрыты | `03_external_db_ports.txt` | Поддерживать `127.0.0.1` bind |
| F-008 | ПК §1.10 | **Medium** | Исправлено в deps | `PyJWT 2.12.1` — 8 CVE | `09_pip_audit.txt` | Обновлено до `>=2.13.0` |
| F-009 | ПК §1.10 | **Medium** | Ручной шаг | frontend `npm audit`: 15 уязвимостей (8 high) | `09_npm_audit.txt` | `npm audit fix` в `frontend/` |
| F-010 | ПК §1.2 | **Medium** | Ручной шаг VPS | TLS-сертификат истекает 2026-06-25 | nmap `ssl-cert` | Проверить certbot / auto-renew |
| F-011 | VPS §2.3–2.4 | **Low** | Скрипт обновлён | lynis, trivy не установлены на VPS | `14_lynis.txt`, trivy output | `bash security-tools/install-vps.sh` |
| F-012 | ПК §1.6 | **Info** | Не выполнено | Публичные пути API — скрипт упал (PowerShell 5.1) | `06_public_paths.txt` | `security-tools/check-public-paths.ps1` |
| F-013 | ПК §1.7 | **Info** | Не выполнено | WebSocket handshake не проверен (wscat ExecutionPolicy) | `07_webhooks_ws.txt` | `security-tools/check-webhook-ws.ps1` |
| F-014 | ПК §1.9 | **Info** | По дизайну | `VITE_WIDGET_API_KEY` в frontend-бандле (публичный ключ виджета) | docker compose config на VPS | Ротация при утечке; не дублировать в логах |
| F-015 | ПК §1.2 | **Info** | OK | Ожидаемо открыты: 22, 80, 443 | `02_nmap.txt` | SSH rate-limit через UFW уже есть |

---

## Что сделано в Этапе 2 (репозиторий)

- [x] `FINDINGS.md` (этот файл)
- [x] CORS: селективный middleware (`backend/app/middleware/cors.py`)
- [x] nginx: HSTS, блок `/docs`/`/openapi.json`, Referrer-Policy
- [x] `docker-compose.override.example.yml` — только `127.0.0.1`, предупреждения
- [x] `deployment/VPS_STAGE2_DEPLOY.md` — чеклист деплоя на VPS
- [x] PowerShell 5.1 скрипты в `security-tools/`
- [x] `security-tools/install-vps.sh` — lynis, trivy, fail2ban + jail sshd
- [x] `PyJWT >= 2.13.0`

## Что осталось на VPS (вручную)

1. `git pull` + пересборка frontend/backend
2. Удалить опасный `docker-compose.override.yml` → `docker compose up -d`
3. `bash security-tools/install-vps.sh`
4. SSH: отключить пароль root
5. `npm audit fix` на ПК/CI при необходимости
6. Проверить продление TLS до 2026-06-25

---

*Следующий аудит: повторить §1.3 и §1.6 после деплоя.*
