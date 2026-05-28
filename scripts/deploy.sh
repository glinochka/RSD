#!/usr/bin/env bash
# Production deploy on VPS: pull images, migrate DB, rolling update app services.
# Proxy (443) is updated last and usually stays up during app rolls.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env.deploy ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.deploy
  set +a
fi

: "${REGISTRY:?Set REGISTRY in .env.deploy (e.g. ghcr.io/your-github-user)}"
: "${IMAGE_TAG:?Set IMAGE_TAG (git SHA from CI or manual tag)}"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

echo "==> Syncing compose/config from git"
git pull --ff-only

if [[ -n "${GHCR_TOKEN:-}" ]]; then
  echo "==> Logging in to ghcr.io"
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "${GHCR_USER:-deploy}" --password-stdin
fi

echo "==> Pulling images (${REGISTRY}/*:${IMAGE_TAG})"
"${COMPOSE[@]}" pull

echo "==> Database migrations"
"${COMPOSE[@]}" run --rm --no-deps backend sh -c "cd app/alembic && alembic upgrade head"

ROLLING_SERVICES=(
  backend
  telephony_worker
  telephony_orchestrator
  wa_bridge
  telephony_bridge
  telephony_media_gateway
  bot
  frontend
)

for svc in "${ROLLING_SERVICES[@]}"; do
  echo "==> Updating ${svc}"
  "${COMPOSE[@]}" up -d --no-deps --wait --no-build "$svc"
done

echo "==> Ensuring proxy and data services"
"${COMPOSE[@]}" up -d --no-build

echo "==> Deploy finished (IMAGE_TAG=${IMAGE_TAG})"
