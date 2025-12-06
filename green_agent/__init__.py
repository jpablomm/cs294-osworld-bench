# Green Agent Package
"""
Green Agent - OSWorld assessment orchestrator.

Structure:
- a2a/: AgentBeats-compliant A2A protocol server with VM orchestration
  - server.py: Main A2A FastAPI server
  - vm_manager.py: GCP VM lifecycle management
  - task_executor.py: Task execution
  - storage.py, supabase_storage.py, gcs_storage.py: Storage backends
  - database.py, database_postgres.py: Assessment databases
  - webui_server.py: Web UI server
- rest/: FastAPI REST server for local testing
- models.py: Shared data models
- storage.py: Local assessment storage
- osworld_adapter.py: OSWorld integration
- osworld_client.py: OSWorld client
- osworld_evaluator.py: OSWorld evaluation
- white_client.py: White agent client

Usage:
    # A2A (Cloud deployment with VMs)
    from green_agent.a2a import app

    # REST (Local testing)
    from green_agent.rest import app
"""
