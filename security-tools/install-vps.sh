#!/usr/bin/env bash
# Установка инструментов Этапа 1–2 на VPS (Ubuntu/Debian)
# Запуск: bash security-tools/install-vps.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== RSD Security Tools: установка на VPS ==="

if ! command -v apt-get >/dev/null 2>&1; then
  echo "Ожидается Debian/Ubuntu. Установите пакеты вручную."
  exit 1
fi

sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  lynis fail2ban jq curl ca-certificates gnupg \
  redis-tools postgresql-client-common

# Trivy — сканирование Docker-образов
if ! command -v trivy >/dev/null 2>&1; then
  echo "--- Установка trivy ---"
  curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sudo sh -s -- -b /usr/local/bin
fi

# fail2ban: jail для sshd
JAIL_EXAMPLE="${SCRIPT_DIR}/fail2ban-jail.local.example"
JAIL_LOCAL="/etc/fail2ban/jail.local"
if [[ -f "${JAIL_EXAMPLE}" ]]; then
  if [[ ! -f "${JAIL_LOCAL}" ]]; then
    echo "--- Копирование fail2ban jail.local ---"
    sudo cp "${JAIL_EXAMPLE}" "${JAIL_LOCAL}"
  else
    echo "--- jail.local уже существует, пропуск ---"
  fi
fi

sudo systemctl enable fail2ban
sudo systemctl restart fail2ban

mkdir -p ~/security-audit-logs

echo ""
echo "=== Проверка ==="
command -v lynis >/dev/null && lynis --version 2>/dev/null | head -1 || echo "lynis: не найден"
command -v trivy >/dev/null && trivy --version 2>/dev/null | head -1 || echo "trivy: не найден"
command -v fail2ban-client >/dev/null && sudo fail2ban-client status 2>/dev/null | head -5 || echo "fail2ban: ошибка статуса"
command -v redis-cli >/dev/null && echo "redis-cli: OK" || true
command -v pg_isready >/dev/null && echo "pg_isready: OK" || true
docker --version 2>/dev/null || echo "docker: не найден"
echo ""
echo "Готово. Логи аудита: ~/security-audit-logs/"
echo "Проверка: bash security-tools/verify-vps.sh"
