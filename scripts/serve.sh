#!/usr/bin/env bash
# Start VidBrief API on :8788
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "error: missing .venv. Create it with:" >&2
  echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
PORT="${PORT:-8788}"

echo "VidBrief API → http://127.0.0.1:${PORT}"
echo "  UI: ./scripts/dev.sh  (or: cd app/frontend && npm run dev)"
echo

if [[ "${RELOAD:-0}" == "1" ]]; then
  echo "warning: RELOAD=1 — long STT jobs will die if you edit backend code" >&2
  exec "$PY" -m uvicorn vidbrief.api:app \
    --app-dir "${ROOT}" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --reload \
    --reload-dir "${ROOT}/vidbrief"
else
  exec "$PY" -m uvicorn vidbrief.api:app \
    --app-dir "${ROOT}" \
    --host 127.0.0.1 \
    --port "$PORT"
fi
