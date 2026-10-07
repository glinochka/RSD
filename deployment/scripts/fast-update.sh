#!/usr/bin/env bash
# Fast prod update: pull, then recreate/rebuild only what the new commits changed.
#
# On VPS:
#   cd /root/project/RSD
#   bash deployment/scripts/fast-update.sh
#   bash deployment/scripts/fast-update.sh --dry-run
#   bash deployment/scripts/fast-update.sh --branch feat/custom-ubt
#   bash deployment/scripts/fast-update.sh --force   # even if already up to date
#
# Mapping:
#   backend Python / alembic  →  recreate backend  (alembic upgrade head on start)
#   backend Dockerfile / requirements*.txt  →  build backend, then recreate
#   frontend  →  build frontend, then up frontend
#   tests-only  →  no container work
#
# Does NOT: compose down, prune, copy override, restart telephony, scale backend.
set -euo pipefail

BRANCH=""
DRY_RUN=0
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    --branch) BRANCH="${2:-}"; shift 2 ;;
    -h|--help)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown flag: $1" >&2
      exit 1
      ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ -f docker-compose.override.yml ]]; then
  echo "STOP: docker-compose.override.yml exists. Prod must run compose.yml only." >&2
  exit 1
fi

if [[ ! -f docker-compose.yml ]]; then
  echo "STOP: not a compose repo root: $ROOT" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "STOP: tracked files are dirty on the server. Commit/stash locally, do not mix with prod pull." >&2
  git status -sb --untracked-files=no
  exit 1
fi

git fetch origin
if [[ -n "$BRANCH" ]]; then
  git checkout "$BRANCH"
else
  UPSTREAM="$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true)"
  if [[ -z "$UPSTREAM" ]]; then
    echo "STOP: current branch has no upstream. Pass --branch feat/custom-ubt" >&2
    exit 1
  fi
fi

BEFORE="$(git rev-parse HEAD)"
if [[ -n "$BRANCH" ]]; then
  git pull --ff-only origin "$BRANCH"
else
  git pull --ff-only
fi
AFTER="$(git rev-parse HEAD)"

echo "HEAD: $BEFORE -> $AFTER"
git log --oneline "$BEFORE..$AFTER" || true

if [[ "$BEFORE" == "$AFTER" && "$FORCE" -eq 0 ]]; then
  echo "Already up to date. Nothing to deploy. Use --force to recreate anyway."
  exit 0
fi

RANGE="$BEFORE..$AFTER"
if [[ "$BEFORE" == "$AFTER" ]]; then
  RANGE="${AFTER}^..${AFTER}"
fi

mapfile -t CHANGED < <(git diff --name-only "$RANGE")
if [[ ${#CHANGED[@]} -eq 0 ]]; then
  echo "No file diff in range. Nothing to deploy."
  exit 0
fi

NEED_BACKEND_RECREATE=0
NEED_BACKEND_BUILD=0
NEED_FRONTEND=0
NEED_COMPOSE=0
SKIP_ONLY=1

is_test_path() {
  case "$1" in
    backend/app/tests/*|*/__pycache__/*|*.pyc) return 0 ;;
    *) return 1 ;;
  esac
}

for path in "${CHANGED[@]}"; do
  if is_test_path "$path"; then
    continue
  fi
  SKIP_ONLY=0
  case "$path" in
    backend/requirements*.txt|backend/Dockerfile)
      NEED_BACKEND_BUILD=1
      NEED_BACKEND_RECREATE=1
      ;;
    backend/*)
      NEED_BACKEND_RECREATE=1
      ;;
    frontend/*)
      NEED_FRONTEND=1
      ;;
    docker-compose.yml)
      NEED_COMPOSE=1
      ;;
  esac
done

echo ""
echo "Plan:"
if [[ "$SKIP_ONLY" -eq 1 ]]; then
  echo "  tests/cache only — skip containers"
elif [[ "$NEED_BACKEND_RECREATE$NEED_BACKEND_BUILD$NEED_FRONTEND$NEED_COMPOSE" == "0000" ]]; then
  echo "  other paths changed, no backend/frontend/compose hit — skip containers"
  printf '    %s\n' "${CHANGED[@]}"
else
  [[ "$NEED_BACKEND_BUILD" -eq 1 ]] && echo "  build backend image (deps/Dockerfile)"
  [[ "$NEED_BACKEND_RECREATE" -eq 1 ]] && echo "  recreate backend (code + alembic upgrade head)"
  [[ "$NEED_FRONTEND" -eq 1 ]] && echo "  build + up frontend"
  [[ "$NEED_COMPOSE" -eq 1 ]] && echo "  compose up -d --remove-orphans"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry run. No docker commands."
  exit 0
fi

if [[ "$SKIP_ONLY" -eq 1 ]]; then
  exit 0
fi

run() {
  echo "+" "$@"
  "$@"
}

if [[ "$NEED_BACKEND_BUILD" -eq 1 ]]; then
  run docker compose build backend
fi

if [[ "$NEED_BACKEND_RECREATE" -eq 1 ]]; then
  run docker compose up -d --force-recreate --no-deps backend
fi

if [[ "$NEED_FRONTEND" -eq 1 ]]; then
  run docker compose build frontend
  run docker compose up -d --no-deps frontend
fi

if [[ "$NEED_COMPOSE" -eq 1 ]]; then
  run docker compose up -d --remove-orphans
fi

if [[ "$NEED_BACKEND_RECREATE" -eq 1 ]]; then
  echo ""
  echo "Alembic:"
  docker compose exec -T backend sh -c "cd app/alembic && alembic current" || true
  echo "Backend may 502 for 1–2 min while embeddings load. Telegram sessions reconnect once."
fi

echo "Done."
