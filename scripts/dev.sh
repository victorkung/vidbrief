#!/usr/bin/env bash
# Start API (:8788) + Vite UI (:5174) from the repo root. Idempotent if already up.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Override to run a second instance (e.g. a demo library): VIDBRIEF_API_PORT / VIDBRIEF_UI_PORT.
API_PORT="${VIDBRIEF_API_PORT:-${PORT:-8788}}"
UI_PORT="${VIDBRIEF_UI_PORT:-5174}"
export PORT="$API_PORT" VIDBRIEF_API_PORT="$API_PORT" VIDBRIEF_UI_PORT="$UI_PORT"

port_in_use() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

started_pids=()

cleanup() {
  local pid
  for pid in ${started_pids[@]+"${started_pids[@]}"}; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup INT TERM

if [[ ! -d "${ROOT}/app/frontend/node_modules" ]]; then
  echo "error: missing app/frontend/node_modules. Run:" >&2
  echo "  cd app/frontend && npm install" >&2
  exit 1
fi

api_up=0
ui_up=0

if port_in_use "$API_PORT"; then
  echo "API already running → http://127.0.0.1:${API_PORT}"
  api_up=1
else
  "${ROOT}/scripts/serve.sh" &
  started_pids+=("$!")
fi

if port_in_use "$UI_PORT"; then
  echo "UI already running → http://127.0.0.1:${UI_PORT}"
  ui_up=1
else
  (
    cd "${ROOT}/app/frontend"
    exec npm run dev
  ) &
  started_pids+=("$!")
fi

if [[ "$api_up" -eq 1 && "$ui_up" -eq 1 ]]; then
  echo "Both already up. Nothing to start."
  exit 0
fi

sleep 0.4
for pid in "${started_pids[@]}"; do
  if ! kill -0 "$pid" 2>/dev/null; then
    wait "$pid" || true
    echo "error: a server process exited immediately (pid ${pid})" >&2
    exit 1
  fi
done

echo
echo "VidBrief"
echo "  UI  → http://127.0.0.1:${UI_PORT}"
echo "  API → http://127.0.0.1:${API_PORT}"
echo

wait
