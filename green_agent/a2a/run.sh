#!/bin/bash
# Green Agent - A2A Protocol Runner (for AgentBeats)
# This script is called by earthshaker controller

HOST=${HOST:-0.0.0.0}
AGENT_PORT=${AGENT_PORT:-8001}
export PYTHONPATH="${PYTHONPATH:-/app:/app/vendor/OSWorld}"
export PYTHONUNBUFFERED=1

echo "=== Green Agent (A2A) Starting ===" >&2
echo "HOST: $HOST" >&2
echo "AGENT_PORT: $AGENT_PORT" >&2

# Use stdbuf to force line-buffered output
stdbuf -oL -eL python3 -u -m uvicorn orchestrator.a2a_green_agent:app \
    --host "$HOST" \
    --port "$AGENT_PORT" \
    --log-level info 2>&1
