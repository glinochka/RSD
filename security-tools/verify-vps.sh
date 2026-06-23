#!/usr/bin/env bash
# Быстрая проверка инструментов на VPS после install-vps.sh

set -euo pipefail

echo "=== RSD Security Tools: проверка VPS ==="

check() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "[OK]  ${name}"
  else
    echo "[FAIL]${name}"
  fi
}

check "lynis" lynis --version
check "trivy" trivy --version
check "fail2ban" sudo fail2ban-client ping
check "redis-cli" redis-cli --version
check "pg_isready" pg_isready --version
check "docker" docker --version

echo ""
echo "--- fail2ban sshd ---"
sudo fail2ban-client status sshd 2>/dev/null || echo "(jail sshd не активен)"

echo ""
echo "--- опасные порты (должно быть пусто для 0.0.0.0) ---"
ss -tulpn 2>/dev/null | grep -E '0\.0\.0\.0:(6333|8000|8001|8002|8100|8200)\b' || echo "OK"
