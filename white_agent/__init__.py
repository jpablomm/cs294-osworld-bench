# White Agent Package
"""
White Agent - GPT-4V based desktop automation agent.

Structure:
- core.py: Shared logic (GPT4VAgent, action parsing, observation parsing)
- a2a/: AgentBeats-compliant A2A protocol server
- rest/: FastAPI REST server for custom orchestrators

Usage:
    # A2A (AgentBeats)
    from white_agent.a2a import start_agent
    start_agent(host="0.0.0.0", port=8001)

    # REST (Custom)
    from white_agent.rest import app
    uvicorn.run(app, host="0.0.0.0", port=8080)
"""

from .core import GPT4VAgent, parse_actions, parse_observation

__all__ = ["GPT4VAgent", "parse_actions", "parse_observation"]
