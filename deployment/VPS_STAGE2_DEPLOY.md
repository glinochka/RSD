# Этап 2 — деплой исправлений на VPS

> VPS: `195.133.26.134` · Домен: `rsd-ai.ru`  
> Выполняйте по SSH **после бэкапа** (снимок + `pg_dump`).

## 1. Закрыть порты (F-001) — срочно

На VPS проверьте override:

```bash
cd ~/project/RSD
cat docker-compose.override.yml 2>/dev/null || echo "нет override"
docker ps --format 'table {{.Names}}\t{{.Ports}}'
ss -tulpn | grep -E ':(6333|8000|8001|8002|8100|8200)\b'
```

**Если видите `0.0.0.0:8000` и т.д.:**

```bash
# Сохраните копию на всякий случай
cp docker-compose.override.yml docker-compose.override.yml.bak.$(date +%F) 2>/dev/null || true

# Удалить опасный override (prod должен жить на docker-compose.yml без host-портов)
rm -f docker-compose.override.yml

docker compose up -d --remove-orphans
ss -tulpn | grep -E ':(6333|8000|8001|8002|8100|8200)\b' || echo "OK: внутренние порты не слушают 0.0.0.0"
```

Ожидаемо снаружи открыты только **22, 80, 443**.

Локальная отладка — только через `127.0.0.1` (см. `docker-compose.override.example.yml`).

## 2. Обновить код и пересобрать

```bash
cd ~/project/RSD
git pull
# .env: ENVIRONMENT=production
# .env: CORS_ALLOWED_ORIGINS=https://rsd-ai.ru,https://www.rsd-ai.ru,https://api.rsd-ai.ru

docker compose build frontend backend
docker compose up -d
```

## 3. Инструменты аудита и fail2ban

```bash
bash security-tools/install-vps.sh
bash security-tools/verify-vps.sh
```

## 4. SSH (F-002)

```bash
sudo sshd -T | grep -iE 'permitempty|passwordauth|pubkey|root|port'
sudo fail2ban-client status sshd
```

Рекомендуемые настройки `/etc/ssh/sshd_config`:

```
PermitRootLogin prohibit-password
PasswordAuthentication no
PubkeyAuthentication yes
```

После правок: `sudo systemctl reload sshd` (держите вторую SSH-сессию открытой).

## 5. Права на секреты (F-003)

```bash
chmod 600 .env
chmod 600 ssl/privkey.pem 2>/dev/null || true
rm -f .env.save  # если не нужен
```

## 6. Проверка с ПК после деплоя

```powershell
cd C:\Users\samat\project\RSD
powershell -ExecutionPolicy Bypass -File security-tools\run-stage1-missing.ps1
```

Ожидаемо:

- `Test-NetConnection` на 6333, 8000, 8100, 8200 → **False**
- `curl -I https://api.rsd-ai.ru/docs` → **404**
- CORS на `/api/users/me` с `Origin: https://evil.example` → **без** `access-control-allow-origin: evil`

## 7. TLS (F-010)

```bash
echo | openssl s_client -connect rsd-ai.ru:443 -servername rsd-ai.ru 2>/dev/null | openssl x509 -noout -dates
```

Убедитесь, что certbot обновляет сертификат до истечения.

---

*Находки: `FINDINGS.md` · Логи Этапа 1: `security-audit-logs/`*
