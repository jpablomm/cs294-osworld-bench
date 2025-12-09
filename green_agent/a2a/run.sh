#!/bin/bash
# Green Agent - A2A Protocol Runner (for AgentBeats)
# This script is called by earthshaker controller
#
# Uses the A2A SDK compliant server (server_a2a.py) which handles:
# - JSON-RPC at POST /
# - Agent card at GET /.well-known/agent-card.json
# - Health check at GET /health

HOST=${HOST:-0.0.0.0}
AGENT_PORT=${AGENT_PORT:-8001}
export PYTHONPATH="${PYTHONPATH:-/app:/app/vendor/OSWorld}"
export PYTHONUNBUFFERED=1

echo "=== Green Agent (A2A SDK) Starting ===" >&2
echo "HOST: $HOST" >&2
echo "AGENT_PORT: $AGENT_PORT" >&2
echo "Protocol: A2A JSON-RPC" >&2

# Use stdbuf to force line-buffered output
# Using server_a2a which is A2A SDK compliant
stdbuf -oL -eL python3 -u -m uvicorn green_agent.a2a.server_a2a:app \
    --host "$HOST" \
    --port "$AGENT_PORT" \
    --log-level info 2>&1
