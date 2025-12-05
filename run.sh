#!/bin/bash
# AgentBeats controller integration script for Green Agent

HOST=${HOST:-0.0.0.0}
AGENT_PORT=${AGENT_PORT:-8001}
export PYTHONPATH="${PYTHONPATH:-/app:/app/vendor/OSWorld}"
export PYTHONUNBUFFERED=1

echo "Starting Green Agent on $HOST:$AGENT_PORT"
echo "Starting Python..."

# Use stdbuf to force line-buffered output, redirect stderr to stdout
stdbuf -oL -eL python3 -u -m uvicorn orchestrator.a2a_green_agent:app \
    --host "$HOST" \
    --port "$AGENT_PORT" \
    --log-level info 2>&1 || echo "Uvicorn exited with code: $?"
