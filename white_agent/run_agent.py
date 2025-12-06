#!/usr/bin/env python3
"""
White Agent entry point - matches tau-bench pattern exactly.
earthshaker sets: HOST, AGENT_PORT, AGENT_URL, ROLE

Uses the a2a SDK directly (NOT FastAPI) for proper AgentBeats compliance.
"""

import os
import sys

# Ensure paths are set before any imports
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/vendor/OSWorld")


def run():
    """Start the white agent server using a2a SDK"""
    # Read settings from environment
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("AGENT_PORT", os.environ.get("PORT", "8001")))
    agent_url = os.environ.get("AGENT_URL", f"http://{host}:{port}")

    print(f"=== White Agent Starting (a2a SDK) ===", flush=True)
    print(f"HOST: {host}", flush=True)
    print(f"AGENT_PORT: {port}", flush=True)
    print(f"AGENT_URL: {agent_url}", flush=True)
    print(f"========================================", flush=True)

    # Import and start the a2a SDK-based server
    from white_agent.gpt4v_a2a_server import start_agent
    start_agent(host=host, port=port)


if __name__ == "__main__":
    run()
