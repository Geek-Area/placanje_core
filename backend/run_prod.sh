#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

HOST="${API_HOST:-0.0.0.0}"
PORT_VALUE="${PORT:-${API_PORT:-8000}}"
WORKERS="${UVICORN_WORKERS:-1}"

exec python3 -m uvicorn app.main:app \
  --host "$HOST" \
  --port "$PORT_VALUE" \
  --workers "$WORKERS"
