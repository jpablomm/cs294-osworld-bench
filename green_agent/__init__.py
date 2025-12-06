# Green Agent Package
"""
Green Agent - OSWorld assessment orchestrator.

Structure:
- a2a/: AgentBeats-compliant A2A protocol server (uses orchestrator/)
- rest/: FastAPI REST server for local testing
- models.py: Shared data models
- storage.py: Assessment storage
- osworld_adapter.py: OSWorld integration
- osworld_client.py: OSWorld client
- osworld_evaluator.py: OSWorld evaluation
- white_client.py: White agent client

Usage:
    # A2A (Cloud deployment with VMs)
    from orchestrator.a2a_green_agent import app

    # REST (Local testing)
    from green_agent.rest import app
"""
