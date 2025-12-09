# Green Agent - A2A Protocol Implementation
"""
AgentBeats-compliant A2A protocol server for OSWorld assessments.
Uses VM orchestration for cloud deployment.

Components:
- server.py: Main A2A FastAPI server
- vm_manager.py: GCP VM lifecycle management
- task_executor.py: OSWorld task execution
- supabase_storage.py: Supabase storage for screenshots
"""

from .server import app

__all__ = ["app"]
