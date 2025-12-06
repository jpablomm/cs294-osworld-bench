#!/bin/bash
# AgentBeats controller integration script for White Agent
# Simplified to match tau-bench pattern exactly

export PYTHONPATH="${PYTHONPATH:-/app:/app/vendor/OSWorld}"
export PYTHONUNBUFFERED=1

# Simple like tau-bench: just call Python
python3 /app/white_agent/run_agent.py
