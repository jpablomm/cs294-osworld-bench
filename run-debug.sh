#!/bin/bash
# AgentBeats controller integration script for Green Agent
# ENHANCED VERSION with debugging and PYTHONPATH setup

set -e

# AgentBeats controller sets these environment variables
HOST=${HOST:-0.0.0.0}
AGENT_PORT=${AGENT_PORT:-8001}

echo "========================================="
echo "Green Agent Startup - DEBUG MODE"
echo "========================================="
echo "HOST: $HOST"
echo "AGENT_PORT: $AGENT_PORT"
echo "PWD: $(pwd)"
echo "PYTHONPATH: ${PYTHONPATH:-<not set>}"
echo "Python version: $(python3 --version)"
echo ""

# Set PYTHONPATH to include vendor directory for OSWorld imports
export PYTHONPATH=/app:/app/vendor/OSWorld:${PYTHONPATH:-}
echo "Updated PYTHONPATH: $PYTHONPATH"
echo ""

# Check if critical files exist
echo "Checking critical files:"
[ -f "orchestrator/a2a_green_agent.py" ] && echo "✓ orchestrator/a2a_green_agent.py" || echo "✗ orchestrator/a2a_green_agent.py MISSING"
[ -d "vendor/OSWorld" ] && echo "✓ vendor/OSWorld/" || echo "✗ vendor/OSWorld/ MISSING"
[ -f "vendor/OSWorld/desktop_env/controllers/setup.py" ] && echo "✓ SetupController found" || echo "✗ SetupController MISSING"
echo ""

# Test import before starting uvicorn
echo "Testing Python imports..."
python3 -c "import sys; sys.path.insert(0, '/app'); sys.path.insert(0, '/app/vendor/OSWorld'); from desktop_env.controllers.setup import SetupController; print('✓ SetupController import successful')" 2>&1

if [ $? -eq 0 ]; then
    echo "✓ All imports successful!"
    echo ""
    echo "Starting Green Agent on $HOST:$AGENT_PORT"
    echo "========================================="

    # Start the green agent
    exec uvicorn green_agent.a2a.server:app --host $HOST --port $AGENT_PORT
else
    echo "✗ Import test failed!"
    echo "Agent will not start. Check logs above for errors."
    exit 1
fi
