# Green Agent Package
"""
Green Agent - OSWorld assessment orchestrator.

Structure:
- a2a/: A2A protocol server with VM orchestration
  - server.py: Main A2A FastAPI server (includes assessment loop)
  - vm_manager.py: GCP VM lifecycle management
  - task_executor.py: Task loading from JSON configs
  - supabase_storage.py: Supabase storage for screenshots
- action_tracker.py: Loop detection for stuck agents
- element_bounds.py: UI element coordinate extraction from a11y tree
- osworld_evaluator.py: OSWorld evaluation
- llm_judge.py: LLM-based evaluation fallback

Usage:
    from green_agent.a2a import app
    uvicorn green_agent.a2a.server:app --host 0.0.0.0 --port 8001
"""
