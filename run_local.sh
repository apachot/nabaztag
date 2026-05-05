#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${NABAZTAG_VENV_DIR:-$ROOT_DIR/.venv}"
API_HOST="${NABAZTAG_API_HOST:-127.0.0.1}"
API_PORT="${NABAZTAG_API_PORT:-8000}"
PORTAL_HOST="${NABAZTAG_PORTAL_HOST:-127.0.0.1}"
PORTAL_PORT="${NABAZTAG_PORTAL_PORT:-5000}"
INSTALL_DEPS=1
USE_RELOAD=1

usage() {
  cat <<EOF
Usage: ./run_local.sh [--skip-install] [--no-reload]

Starts the local Nabaztag API and the local portal together.

Options:
  --skip-install  Reuse the existing virtualenv without running pip install.
  --no-reload     Disable auto-reload on both servers.
  --help          Show this help.

Environment overrides:
  NABAZTAG_VENV_DIR
  NABAZTAG_API_HOST / NABAZTAG_API_PORT
  NABAZTAG_PORTAL_HOST / NABAZTAG_PORTAL_PORT
  NABAZTAG_API_BASE_URL
  NABAZTAG_PORTAL_DATABASE_URL
  NABAZTAG_GATEWAY_DRIVER
EOF
}

while (($# > 0)); do
  case "$1" in
    --skip-install)
      INSTALL_DEPS=0
      ;;
    --no-reload)
      USE_RELOAD=0
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

if (( INSTALL_DEPS )); then
  python -m pip install -e "$ROOT_DIR/apps/api" -e "$ROOT_DIR/apps/portal"
fi

export NABAZTAG_API_BASE_URL="${NABAZTAG_API_BASE_URL:-http://$API_HOST:$API_PORT}"
export PYTHONUNBUFFERED=1

TMP_RUN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/nabaztag-local.XXXXXX")"
API_LOG="$TMP_RUN_DIR/api.log"
PORTAL_LOG="$TMP_RUN_DIR/portal.log"

wait_for_http() {
  local url="$1"
  local timeout_seconds="$2"
  local started_at
  started_at="$(date +%s)"

  while true; do
    if python - "$url" <<'PY' >/dev/null 2>&1
import sys
from urllib import request

url = sys.argv[1]
with request.urlopen(url, timeout=1):
    pass
PY
    then
      return 0
    fi

    if (( "$(date +%s)" - started_at >= timeout_seconds )); then
      return 1
    fi
    sleep 1
  done
}

cleanup() {
  local exit_code=$?
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" >/dev/null 2>&1; then
    kill "$API_PID" >/dev/null 2>&1 || true
    wait "$API_PID" >/dev/null 2>&1 || true
  fi
  exit "$exit_code"
}

trap cleanup EXIT INT TERM

cd "$ROOT_DIR"

API_CMD=(python -m uvicorn app.main:app --app-dir "$ROOT_DIR/apps/api" --host "$API_HOST" --port "$API_PORT")
PORTAL_CMD=(python -m flask --app portal_app:create_app run --host "$PORTAL_HOST" --port "$PORTAL_PORT")

if (( USE_RELOAD )); then
  API_CMD+=(--reload)
  PORTAL_CMD+=(--debug)
fi

echo "Starting API on http://$API_HOST:$API_PORT"
"${API_CMD[@]}" >"$API_LOG" 2>&1 &
API_PID=$!

if ! wait_for_http "http://$API_HOST:$API_PORT/health" 20; then
  echo "API did not become ready. Last log lines:" >&2
  tail -n 40 "$API_LOG" >&2 || true
  exit 1
fi

echo "API ready."
echo "Portal will use NABAZTAG_API_BASE_URL=$NABAZTAG_API_BASE_URL"
echo "API log: $API_LOG"
echo "Portal log: $PORTAL_LOG"
echo "Opening local portal on http://$PORTAL_HOST:$PORTAL_PORT"

"${PORTAL_CMD[@]}" 2>&1 | tee "$PORTAL_LOG"
