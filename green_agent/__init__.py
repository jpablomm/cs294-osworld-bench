# Green Agent Package
"""
Green Agent - OSWorld assessment orchestrator.

Structure:
- a2a/: A2A protocol server with VM orchestration
  - server.py: Main A2A FastAPI server
  - vm_manager.py: GCP VM lifecycle management
  - task_executor.py: Task execution
  - supabase_storage.py: Supabase storage for screenshots
- models.py: Shared data models
- osworld_adapter.py: OSWorld integration
- osworld_client.py: OSWorld client
- osworld_evaluator.py: OSWorld evaluation
- llm_judge.py: LLM-based evaluation
- task_converter.py: Task format conversion
- white_client.py: White agent REST client

Usage:
    from green_agent.a2a import app
    uvicorn green_agent.a2a.server:app --host 0.0.0.0 --port 8001
"""
