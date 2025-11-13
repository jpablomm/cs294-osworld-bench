#!/bin/bash
# AgentBeats controller integration script for White Agent
# The controller sets HOST and AGENT_PORT environment variables

set -e

# AgentBeats controller sets these environment variables
HOST=${HOST:-0.0.0.0}
AGENT_PORT=${AGENT_PORT:-9001}

echo "Starting White Agent on $HOST:$AGENT_PORT"

# Start the white agent (you can switch between different implementations)
# Default: A2A adapter wrapper
uvicorn white_agent.a2a_adapter:app --host $HOST --port $AGENT_PORT

# Alternative: GPT-4V white agent
# uvicorn white_agent.gpt4v_server:app --host $HOST --port $AGENT_PORT
