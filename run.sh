#!/bin/bash
# AgentBeats controller integration script for Green Agent
# The controller sets HOST and AGENT_PORT environment variables

set -e

# AgentBeats controller sets these environment variables
HOST=${HOST:-0.0.0.0}
AGENT_PORT=${AGENT_PORT:-8001}

# Ensure PYTHONPATH is set for OSWorld imports
export PYTHONPATH="${PYTHONPATH:-/app:/app/vendor/OSWorld}"

echo "Starting Green Agent on $HOST:$AGENT_PORT"
echo "PYTHONPATH=$PYTHONPATH"

# Start the green agent
exec uvicorn orchestrator.a2a_green_agent:app --host $HOST --port $AGENT_PORT
