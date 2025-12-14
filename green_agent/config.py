"""
Green Agent Configuration

Single source of truth for all Green Agent environment variables.
Import from here instead of using os.environ.get() directly.
"""
import os

# Loop Detection
ACTION_REPEAT_THRESHOLD = int(os.environ.get("ACTION_REPEAT_THRESHOLD", "3"))
ACTION_COORD_TOLERANCE = int(os.environ.get("ACTION_COORD_TOLERANCE", "20"))

# Server
GREEN_AGENT_HOST = os.environ.get("HOST", os.environ.get("AGENT_HOST", "0.0.0.0"))
GREEN_AGENT_PORT = int(os.environ.get("AGENT_PORT", os.environ.get("PORT", "8001")))

# External Services
WEBUI_SERVER_URL = os.environ.get("WEBUI_SERVER_URL", "http://localhost:3001")
GREEN_AGENT_API_KEY = os.environ.get("GREEN_AGENT_API_KEY")

# GCP
GCP_PROJECT = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")

# Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# Stabilization Waits (seconds)
SETUP_STABILIZATION_WAIT = int(os.environ.get("SETUP_STABILIZATION_WAIT", "30"))
EVAL_STABILIZATION_WAIT = int(os.environ.get("EVAL_STABILIZATION_WAIT", "10"))

# Cloud Run
CLOUDRUN_HOST = os.environ.get("CLOUDRUN_HOST")
HTTPS_ENABLED = os.environ.get("HTTPS_ENABLED", "").lower() in ("true", "1", "yes")

# VM Pool Configuration (for snapshot-based VM reuse)
# Re-exported from pool_config for convenience
from green_agent.a2a.pool_config import (
    VM_POOL_ENABLED,
    VM_POOL_SIZE,
    VM_POOL_SNAPSHOT_NAME,
    VM_POOL_ZONE,
    VM_POOL_MACHINE_TYPE,
    VM_POOL_MAX_TASKS_PER_VM,
    VM_POOL_MAX_CONSECUTIVE_FAILURES,
    VM_POOL_RESTORE_TIMEOUT,
    VM_POOL_ACQUIRE_TIMEOUT,
    VM_POOL_READY_TIMEOUT,
    VM_POOL_FALLBACK_TO_FRESH,
    get_pool_config,
)


def get_agent_url() -> str:
    """Build the Green Agent URL from environment or defaults."""
    if CLOUDRUN_HOST:
        protocol = "https" if HTTPS_ENABLED else "http"
        return f"{protocol}://{CLOUDRUN_HOST}"
    return os.environ.get("AGENT_URL", f"http://{GREEN_AGENT_HOST}:{GREEN_AGENT_PORT}")
