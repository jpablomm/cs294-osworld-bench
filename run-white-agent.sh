#!/bin/bash
# AgentBeats controller integration script for White Agent
# The controller sets HOST and AGENT_PORT environment variables

HOST=${HOST:-0.0.0.0}
AGENT_PORT=${AGENT_PORT:-8001}
export PYTHONPATH="${PYTHONPATH:-/app:/app/vendor/OSWorld}"
export PYTHONUNBUFFERED=1

echo "Starting White Agent on $HOST:$AGENT_PORT"

# Start uvicorn with stdbuf for proper output buffering in subprocess
stdbuf -oL -eL python3 -u -m uvicorn white_agent.gpt4v_server:app \
    --host "$HOST" \
    --port "$AGENT_PORT" \
    --log-level info 2>&1 || echo "Uvicorn exited with code: $?"
