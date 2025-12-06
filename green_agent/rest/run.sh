#!/bin/bash
# Green Agent - REST API Runner (for local testing)

export PYTHONPATH="${PYTHONPATH:-/app:/app/vendor/OSWorld}"
export PYTHONUNBUFFERED=1

PORT=${PORT:-8080}
HOST=${HOST:-0.0.0.0}

echo "=== Green Agent (REST) Starting ===" >&2
echo "HOST: $HOST" >&2
echo "PORT: $PORT" >&2

python3 -m uvicorn green_agent.rest.server:app --host "$HOST" --port "$PORT"
