#!/usr/bin/env bash
# Starts admin-web-ui + admin-console-api with env loading and PID tracking.
# Channel hosts (WeCom/QQBot) are started on-demand from the console UI, not by this script.
# Usage: ./scripts/start-console.sh [--dry-run]

set -euo pipefail

# --- --dry-run support (CI testing without port binding) ---
if [[ "${1:-}" == "--dry-run" ]]; then
  ENV_FILE="${CONSOLE_ENV_FILE:-.env}"
  PID_FILE="${HOME}/.inkstatute/console-pids.json"
  echo "DRY-RUN — commands that would be executed:"
  echo "  ENV_FILE: $ENV_FILE"
  echo "  PID_FILE: $PID_FILE"
  echo "  python -m admin_console_api & API_PID=\$!"
  echo "  python -m admin_web_ui & UI_PID=\$!"
  echo "  printf '{\"api\": %s, \"ui\": %s}\\n' \"\$API_PID\" \"\$UI_PID\" > \"\$PID_FILE\""
  echo "  Console UI: http://${ADMIN_WEB_UI_HOST:-127.0.0.1}:${ADMIN_WEB_UI_PORT:-8080}"
  echo "  Console API: http://${ADMIN_CONSOLE_API_HOST:-127.0.0.1}:${ADMIN_CONSOLE_API_PORT:-8081}"
  exit 0
fi

# --- Env loading ---
ENV_FILE="${CONSOLE_ENV_FILE:-.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
else
  echo "WARNING: $ENV_FILE not found, using current environment" >&2
fi

# --- Runtime state directory ---
mkdir -p "${HOME}/.inkstatute"

# --- Launch services ---
python -m admin_console_api & API_PID=$!
python -m admin_web_ui & UI_PID=$!

# --- Write JSON PID file ---
printf '{"api": %s, "ui": %s}\n' "$API_PID" "$UI_PID" > "${HOME}/.inkstatute/console-pids.json"

# --- Trap cleanup: kill children and remove PID file on exit ---
trap 'kill ${API_PID} ${UI_PID} 2>/dev/null || true; rm -f "${HOME}/.inkstatute/console-pids.json"' EXIT

# --- Success message ---
echo "Console UI: http://${ADMIN_WEB_UI_HOST:-127.0.0.1}:${ADMIN_WEB_UI_PORT:-8080}"
echo "Console API: http://${ADMIN_CONSOLE_API_HOST:-127.0.0.1}:${ADMIN_CONSOLE_API_PORT:-8081}"
echo "PID file: ${HOME}/.inkstatute/console-pids.json"

# --- Wait for both child processes to exit ---
wait
