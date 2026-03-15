#!/usr/bin/env bash
# Start dev services. Usage: ./dev.sh [service]
# Services: api, frontend, all (default)

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

[ -f "$ROOT/.env" ] && set -a && source "$ROOT/.env" && set +a

start_api() {
  echo "Starting API on :8000..."
  (cd "$ROOT/backend" && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) &
}

start_frontend() {
  echo "Starting frontend on :3000..."
  (cd "$ROOT/frontend" && npx next dev) &
}

SERVICE="${1:-all}"

case "$SERVICE" in
  api)      start_api ;;
  frontend) start_frontend ;;
  all)
    start_api
    start_frontend
    ;;
  *)
    echo "Unknown service: $SERVICE"
    echo "Usage: ./dev.sh [api|frontend|all]"
    exit 1
    ;;
esac

trap "kill 0" EXIT
wait
