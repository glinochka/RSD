#!/usr/bin/env bash
# Emergency: block Docker-published ports from the public internet (UFW does not apply).
# Run on VPS as root BEFORE or AFTER docker-compose port fix.
#
# Usage:
#   sudo bash deployment/scripts/lock-exposed-docker-ports.sh
#   sudo bash deployment/scripts/lock-exposed-docker-ports.sh eth0
#
set -euo pipefail

IFACE="${1:-}"
if [[ -z "${IFACE}" ]]; then
  IFACE="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="dev") {print $(i+1); exit}}')"
fi
if [[ -z "${IFACE}" ]]; then
  echo "Could not detect public interface. Usage: $0 <iface>" >&2
  exit 1
fi

PORTS=(6333 6334 8000 8001 8002 8100 8200 8090)

echo "Blocking TCP ports ${PORTS[*]} on interface ${IFACE} via DOCKER-USER chain..."

if ! iptables -L DOCKER-USER -n &>/dev/null; then
  iptables -N DOCKER-USER 2>/dev/null || true
fi

for port in "${PORTS[@]}"; do
  if ! iptables -C DOCKER-USER -i "${IFACE}" -p tcp --dport "${port}" -j DROP 2>/dev/null; then
    iptables -I DOCKER-USER -i "${IFACE}" -p tcp --dport "${port}" -j DROP
    echo "  DROP ${port}"
  else
    echo "  already blocked ${port}"
  fi
done

# Allow established traffic back (standard Docker hardening pattern).
if ! iptables -C DOCKER-USER -j RETURN 2>/dev/null; then
  iptables -A DOCKER-USER -j RETURN
fi

echo ""
echo "Current DOCKER-USER rules:"
iptables -L DOCKER-USER -n -v

if command -v netfilter-persistent &>/dev/null; then
  netfilter-persistent save
  echo "Saved via netfilter-persistent."
elif [[ -d /etc/iptables ]]; then
  iptables-save > /etc/iptables/rules.v4
  echo "Saved to /etc/iptables/rules.v4"
else
  echo "Install iptables-persistent to survive reboot: apt install -y iptables-persistent"
fi

echo "Done. Verify from your PC: curl -m 5 http://<VPS_IP>:8000/docs should fail."
