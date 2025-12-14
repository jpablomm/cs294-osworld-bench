"""
VM Pool Configuration

Environment variables for VM pool with sensible defaults.
Pool is disabled by default for backward compatibility.
"""

import os
from typing import Dict, Any

# Pool enable/disable (disabled by default for backward compatibility)
VM_POOL_ENABLED = os.environ.get(
    "VM_POOL_ENABLED", "false"
).lower() in ("true", "1", "yes")

# Pool sizing (1 VM for sequential batch processing)
VM_POOL_SIZE = int(os.environ.get("VM_POOL_SIZE", "1"))

# GCP configuration
VM_POOL_ZONE = os.environ.get("VM_POOL_ZONE", "us-central1-a")
VM_POOL_MACHINE_TYPE = os.environ.get("VM_POOL_MACHINE_TYPE", "n1-standard-4")

# Snapshot configuration
VM_POOL_SNAPSHOT_NAME = os.environ.get(
    "VM_POOL_SNAPSHOT_NAME", "osworld-golden-snapshot"
)

# Lifecycle thresholds
VM_POOL_MAX_TASKS_PER_VM = int(os.environ.get("VM_POOL_MAX_TASKS_PER_VM", "50"))
VM_POOL_MAX_CONSECUTIVE_FAILURES = int(
    os.environ.get("VM_POOL_MAX_CONSECUTIVE_FAILURES", "3")
)

# Timeouts (seconds)
VM_POOL_RESTORE_TIMEOUT = int(os.environ.get("VM_POOL_RESTORE_TIMEOUT", "180"))
VM_POOL_ACQUIRE_TIMEOUT = int(os.environ.get("VM_POOL_ACQUIRE_TIMEOUT", "300"))
VM_POOL_READY_TIMEOUT = int(os.environ.get("VM_POOL_READY_TIMEOUT", "300"))

# Fallback behavior
VM_POOL_FALLBACK_TO_FRESH = os.environ.get(
    "VM_POOL_FALLBACK_TO_FRESH", "true"
).lower() in ("true", "1", "yes")


def get_pool_config() -> Dict[str, Any]:
    """
    Return all pool configuration as a dict.

    Useful for logging and debugging pool settings.
    """
    return {
        "enabled": VM_POOL_ENABLED,
        "pool_size": VM_POOL_SIZE,
        "zone": VM_POOL_ZONE,
        "machine_type": VM_POOL_MACHINE_TYPE,
        "snapshot_name": VM_POOL_SNAPSHOT_NAME,
        "max_tasks_per_vm": VM_POOL_MAX_TASKS_PER_VM,
        "max_consecutive_failures": VM_POOL_MAX_CONSECUTIVE_FAILURES,
        "restore_timeout": VM_POOL_RESTORE_TIMEOUT,
        "acquire_timeout": VM_POOL_ACQUIRE_TIMEOUT,
        "ready_timeout": VM_POOL_READY_TIMEOUT,
        "fallback_to_fresh": VM_POOL_FALLBACK_TO_FRESH,
    }
