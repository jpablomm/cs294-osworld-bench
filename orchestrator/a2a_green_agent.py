"""
A2A-Compliant Green Agent for OSWorld Assessment

This module wraps the existing OSWorld orchestrator to make it AgentBeats-compliant.
It implements the A2A protocol while preserving all existing orchestrator functionality.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel

# Import existing orchestrator components
from .vm_manager import VMManager
from .storage import StorageManager
from .task_executor import TaskExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# A2A Protocol Models (simplified implementation based on AgentBeats spec)
class AgentCard(BaseModel):
    """Agent self-description following A2A protocol"""
    name: str
    description: str
    version: str
    capabilities: list[str]
    protocols: list[str]
    assessment_types: list[str]


class A2ATask(BaseModel):
    """A2A Task format"""
    task_id: str
    context_id: Optional[str] = None
    message: str  # Natural language or structured description
    metadata: Optional[Dict[str, Any]] = None


class A2AMessage(BaseModel):
    """A2A Message response"""
    message_id: str
    task_id: str
    context_id: Optional[str] = None
    role: str  # "agent"
    content: str
    metadata: Optional[Dict[str, Any]] = None


# Create FastAPI app for A2A green agent
app = FastAPI(
    title="OSWorld Green Agent (A2A)",
    description="AgentBeats-compliant assessment agent for OSWorld benchmarks",
    version="0.1.0"
)

# Initialize managers (reuse existing orchestrator components)
vm_manager = VMManager()
storage_manager = StorageManager(use_gcs=False)  # Local storage for demo
task_executor = TaskExecutor()

# Track active assessments
active_assessments: Dict[str, Dict[str, Any]] = {}


@app.get("/agent-card")
def get_agent_card() -> AgentCard:
    """
    Return agent card - A2A protocol requirement

    This describes the green agent's capabilities for AgentBeats platform
    """
    return AgentCard(
        name="OSWorld Assessment Agent",
        description=(
            "Green agent for conducting OSWorld desktop automation assessments. "
            "Creates VMs from golden images, orchestrates task execution with white agents, "
            "and reports standardized metrics (success rate, steps, execution time)."
        ),
        version="0.1.0",
        capabilities=[
            "osworld-benchmarks",
            "desktop-automation-assessment",
            "vm-orchestration",
            "chrome-tasks",
            "os-tasks",
            "gnome-tasks"
        ],
        protocols=["a2a", "rest"],
        assessment_types=[
            "osworld-single-agent",  # One white agent performs desktop tasks
            "osworld-chrome",        # Chrome-specific tasks
            "osworld-os",           # OS-level tasks
            "osworld-custom"        # Custom task definitions
        ]
    )


@app.post("/task")
async def handle_a2a_task(task: A2ATask) -> A2AMessage:
    """
    Handle A2A task - main entry point for assessments

    Accepts:
    - Natural language task description
    - Structured JSON config in metadata

    Returns:
    - A2A Message with assessment results
    """
    logger.info(f"Received A2A task: {task.task_id}")

    # Parse task configuration
    try:
        config = _parse_task_config(task)
        logger.info(f"Parsed config: {config}")
    except Exception as e:
        error_msg = f"Failed to parse task config: {e}"
        logger.error(error_msg)
        return A2AMessage(
            message_id=f"msg-{task.task_id}",
            task_id=task.task_id,
            context_id=task.context_id,
            role="agent",
            content=error_msg,
            metadata={"status": "failed", "error": str(e)}
        )

    # Execute assessment
    try:
        result = await _execute_assessment(task.task_id, config)

        # Format results as A2A message
        return A2AMessage(
            message_id=f"msg-{task.task_id}",
            task_id=task.task_id,
            context_id=task.context_id,
            role="agent",
            content=_format_results_message(result),
            metadata={
                "status": "completed",
                "metrics": result
            }
        )

    except Exception as e:
        error_msg = f"Assessment failed: {e}"
        logger.error(error_msg, exc_info=True)
        return A2AMessage(
            message_id=f"msg-{task.task_id}",
            task_id=task.task_id,
            context_id=task.context_id,
            role="agent",
            content=error_msg,
            metadata={"status": "failed", "error": str(e)}
        )


def _parse_task_config(task: A2ATask) -> Dict[str, Any]:
    """
    Parse task configuration from A2A task

    Supports:
    1. Structured config in metadata
    2. JSON in natural language message
    3. Natural language description (future: LLM parsing)
    """
    # Option 1: Check metadata for structured config
    if task.metadata and "config" in task.metadata:
        return task.metadata["config"]

    # Option 2: Try parsing message as JSON
    try:
        config = json.loads(task.message)
        if isinstance(config, dict):
            return config
    except json.JSONDecodeError:
        pass

    # Option 3: Extract from natural language (simple keyword extraction)
    # For demo, we look for key fields in the message
    config = {}
    message_lower = task.message.lower()

    # Extract white_agent_url
    if "white_agent_url" in task.metadata:
        config["white_agent_url"] = task.metadata["white_agent_url"]
    elif "white agent" in message_lower:
        # Would parse URL from message in real implementation
        raise ValueError("white_agent_url must be provided in metadata")

    # Extract osworld_task_id
    if "osworld_task_id" in task.metadata:
        config["osworld_task_id"] = task.metadata["osworld_task_id"]
    elif "task_id" in task.metadata:
        config["osworld_task_id"] = task.metadata["task_id"]
    else:
        raise ValueError("osworld_task_id must be provided in metadata")

    # Extract optional parameters
    config["max_steps"] = task.metadata.get("max_steps", 15)
    config["vm_image"] = task.metadata.get("vm_image", "osworld-golden-v3-gnome")
    config["metrics"] = task.metadata.get("metrics", ["success", "steps", "time_sec"])

    return config


async def _execute_assessment(
    assessment_id: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute OSWorld assessment using existing orchestrator logic

    This is the core integration point that reuses all existing code.
    """
    import time
    from pathlib import Path

    logger.info(f"Starting assessment {assessment_id}")
    start_time = time.time()

    # Track assessment
    active_assessments[assessment_id] = {
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
        "config": config
    }

    vm_info = None

    try:
        # Step 1: Create VM (reuse existing VMManager)
        logger.info("Creating VM...")
        vm_info = await asyncio.to_thread(
            vm_manager.create_vm,
            assessment_id
        )
        logger.info(f"VM created: {vm_info['vm_name']} at {vm_info['vm_ip']}")

        # Step 2: Wait for VM ready
        logger.info("Waiting for VM to be ready...")
        vm_ready = await asyncio.to_thread(
            vm_manager.wait_for_vm_ready,
            vm_info["vm_ip"],
            timeout=120
        )

        if not vm_ready:
            raise Exception("VM did not become ready in time")

        # Step 3: Run assessment (reuse existing TaskExecutor)
        logger.info("Running assessment...")
        artifacts_dir = f"./temp_artifacts/{assessment_id}"
        Path(artifacts_dir).mkdir(parents=True, exist_ok=True)

        result = await asyncio.to_thread(
            task_executor.run_assessment,
            config["osworld_task_id"],
            vm_info["vm_ip"],
            config["white_agent_url"],
            artifacts_dir
        )

        # Step 4: Add metadata
        result["vm_cost"] = vm_manager.get_vm_cost(time.time() - start_time)
        result["vm_info"] = vm_info
        result["assessment_id"] = assessment_id
        result["total_time_sec"] = time.time() - start_time

        logger.info(f"Assessment completed: success={result.get('success')}")

        # Step 5: Cleanup VM
        logger.info("Cleaning up VM...")
        await asyncio.to_thread(
            vm_manager.delete_vm,
            assessment_id
        )

        active_assessments[assessment_id]["status"] = "completed"
        return result

    except Exception as e:
        logger.error(f"Assessment failed: {e}", exc_info=True)

        # Cleanup VM on failure
        if vm_info:
            try:
                await asyncio.to_thread(
                    vm_manager.delete_vm,
                    assessment_id
                )
            except Exception as cleanup_error:
                logger.error(f"Cleanup failed: {cleanup_error}")

        active_assessments[assessment_id]["status"] = "failed"
        active_assessments[assessment_id]["error"] = str(e)

        raise


def _format_results_message(result: Dict[str, Any]) -> str:
    """Format assessment results as human-readable message"""
    success = "✅ Success" if result.get("success") else "❌ Failed"
    steps = result.get("steps", 0)
    time_sec = result.get("time_sec", 0)
    vm_cost = result.get("vm_cost", 0)

    message = f"""
Assessment Complete

Status: {success}
Steps taken: {steps}
Execution time: {time_sec:.2f}s
VM cost: ${vm_cost:.4f}

""".strip()

    if result.get("failure_reason"):
        message += f"\nFailure reason: {result['failure_reason']}"

    return message


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent_type": "green",
        "protocol": "a2a",
        "assessment_types": ["osworld"],
        "active_assessments": len([a for a in active_assessments.values()
                                   if a["status"] == "running"])
    }


@app.get("/assessments")
def list_assessments():
    """List all assessments (for debugging)"""
    return {
        "assessments": active_assessments
    }
