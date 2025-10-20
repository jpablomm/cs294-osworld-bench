"""
OSWorld VM Orchestrator - Cloud Run Service

Manages OSWorld VM lifecycle and task execution with async workflows.
"""

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from .vm_manager import VMManager
from .storage import StorageManager
from .task_executor import TaskExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="OSWorld VM Orchestrator",
    description="Cloud Run service for managing OSWorld VM lifecycle and task execution",
    version="0.1.0"
)

# Initialize managers
vm_manager = VMManager()
storage_manager = StorageManager(
    bucket_name=os.environ.get("GCS_BUCKET_NAME"),
    use_gcs=os.environ.get("USE_GCS", "true").lower() == "true"
)
task_executor = TaskExecutor()

# In-memory task state (use Cloud Firestore in production)
tasks_state: Dict[str, Dict[str, Any]] = {}


# Request/Response Models
class TaskRequest(BaseModel):
    """Request to start a new task"""
    task_id: str
    white_agent_url: str


class TaskResponse(BaseModel):
    """Response with task ID"""
    task_id: str
    orchestrator_task_id: str
    status: str


class TaskStatus(BaseModel):
    """Task status response"""
    orchestrator_task_id: str
    osworld_task_id: str
    status: str  # pending, running, completed, failed
    progress: float  # 0.0 to 1.0
    vm_name: Optional[str] = None
    vm_ip: Optional[str] = None
    created_at: str
    updated_at: str
    error: Optional[str] = None


class TaskResults(BaseModel):
    """Task results response"""
    orchestrator_task_id: str
    osworld_task_id: str
    white_agent: str
    success: int
    steps: int
    time_sec: float
    vm_cost: float
    failure_reason: Optional[str] = None
    results_url: Optional[str] = None
    artifacts: list


@app.get("/health")
def health() -> Dict[str, Any]:
    """Health check endpoint for Cloud Run"""
    return {
        "status": "healthy",
        "service": "osworld-orchestrator",
        "version": "0.1.0",
        "vm_manager": "gce",
        "storage": "gcs" if storage_manager.use_gcs else "local",
        "active_tasks": len([t for t in tasks_state.values() if t["status"] == "running"]),
    }


@app.post("/tasks", response_model=TaskResponse)
async def create_task(
    request: TaskRequest,
    background_tasks: BackgroundTasks
) -> TaskResponse:
    """
    Create and start a new OSWorld task

    This endpoint:
    1. Validates the task
    2. Returns a task ID immediately
    3. Starts VM creation and task execution in background
    """
    orchestrator_task_id = str(uuid.uuid4())
    logger.info(
        f"Creating task {orchestrator_task_id} for OSWorld task {request.task_id}, "
        f"white_agent={request.white_agent_url}"
    )

    # Initialize task state
    task_state = {
        "orchestrator_task_id": orchestrator_task_id,
        "osworld_task_id": request.task_id,
        "white_agent_url": request.white_agent_url,
        "status": "pending",
        "progress": 0.0,
        "vm_name": None,
        "vm_ip": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "results": None,
        "error": None,
    }
    tasks_state[orchestrator_task_id] = task_state

    # Start task execution in background
    background_tasks.add_task(
        execute_task_workflow,
        orchestrator_task_id,
        request.task_id,
        request.white_agent_url
    )

    return TaskResponse(
        task_id=request.task_id,
        orchestrator_task_id=orchestrator_task_id,
        status="pending"
    )


@app.get("/tasks/{orchestrator_task_id}", response_model=TaskStatus)
def get_task_status(orchestrator_task_id: str) -> TaskStatus:
    """Get status of a task"""
    task_state = tasks_state.get(orchestrator_task_id)
    if not task_state:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatus(
        orchestrator_task_id=orchestrator_task_id,
        osworld_task_id=task_state["osworld_task_id"],
        status=task_state["status"],
        progress=task_state["progress"],
        vm_name=task_state.get("vm_name"),
        vm_ip=task_state.get("vm_ip"),
        created_at=task_state["created_at"],
        updated_at=task_state["updated_at"],
        error=task_state.get("error"),
    )


@app.get("/tasks/{orchestrator_task_id}/results", response_model=TaskResults)
def get_task_results(orchestrator_task_id: str) -> TaskResults:
    """Get results of a completed task"""
    task_state = tasks_state.get(orchestrator_task_id)
    if not task_state:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_state["status"] not in ["completed", "failed"]:
        raise HTTPException(status_code=400, detail="Task not yet completed")

    results = task_state.get("results", {})

    return TaskResults(
        orchestrator_task_id=orchestrator_task_id,
        osworld_task_id=task_state["osworld_task_id"],
        white_agent=task_state["white_agent_url"],
        success=results.get("success", 0),
        steps=results.get("steps", 0),
        time_sec=results.get("time_sec", 0.0),
        vm_cost=results.get("vm_cost", 0.0),
        failure_reason=results.get("failure_reason"),
        results_url=results.get("results_url"),
        artifacts=results.get("artifacts", []),
    )


@app.get("/tasks")
def list_tasks(limit: int = 50) -> Dict[str, Any]:
    """List all tasks"""
    tasks_list = sorted(
        tasks_state.values(),
        key=lambda t: t["created_at"],
        reverse=True
    )[:limit]

    return {
        "tasks": [
            {
                "orchestrator_task_id": t["orchestrator_task_id"],
                "osworld_task_id": t["osworld_task_id"],
                "status": t["status"],
                "progress": t["progress"],
                "created_at": t["created_at"],
            }
            for t in tasks_list
        ],
        "total": len(tasks_list),
    }


async def execute_task_workflow(
    orchestrator_task_id: str,
    osworld_task_id: str,
    white_agent_url: str
):
    """
    Execute complete task workflow:
    1. Create VM
    2. Wait for VM ready
    3. Run assessment
    4. Store results
    5. Delete VM
    """
    task_state = tasks_state[orchestrator_task_id]

    def update_state(status: str, progress: float, **kwargs):
        """Helper to update task state"""
        task_state["status"] = status
        task_state["progress"] = progress
        task_state["updated_at"] = datetime.utcnow().isoformat()
        task_state.update(kwargs)
        logger.info(f"Task {orchestrator_task_id}: {status} ({progress*100:.0f}%)")

    vm_info = None
    start_time = time.time()

    try:
        # Step 1: Create VM (0% -> 20%)
        update_state("running", 0.0, step="creating_vm")
        logger.info(f"Creating VM for task {orchestrator_task_id}")

        vm_info = await asyncio.to_thread(
            vm_manager.create_vm,
            orchestrator_task_id
        )

        update_state(
            "running",
            0.2,
            vm_name=vm_info["vm_name"],
            vm_ip=vm_info["vm_ip"],
            step="waiting_for_vm"
        )

        # Step 2: Wait for VM ready (20% -> 30%)
        logger.info(f"Waiting for VM {vm_info['vm_ip']} to be ready")
        vm_ready = await asyncio.to_thread(
            vm_manager.wait_for_vm_ready,
            vm_info["vm_ip"],
            timeout=120
        )

        if not vm_ready:
            raise Exception("VM did not become ready in time")

        update_state("running", 0.3, step="running_assessment")

        # Step 3: Run assessment (30% -> 80%)
        logger.info(f"Running assessment on VM {vm_info['vm_ip']}")
        artifacts_dir = f"./temp_artifacts/{orchestrator_task_id}"
        Path(artifacts_dir).mkdir(parents=True, exist_ok=True)

        results = await asyncio.to_thread(
            task_executor.run_assessment,
            osworld_task_id,
            vm_info["vm_ip"],
            white_agent_url,
            artifacts_dir
        )

        update_state("running", 0.8, step="storing_results")

        # Step 4: Store results (80% -> 90%)
        logger.info(f"Storing results for task {orchestrator_task_id}")

        # Add metadata to results
        results["vm_info"] = vm_info
        results["vm_cost"] = vm_manager.get_vm_cost(time.time() - start_time)
        results["orchestrator_task_id"] = orchestrator_task_id
        results["osworld_task_id"] = osworld_task_id

        # Save results to storage
        results_url = await asyncio.to_thread(
            storage_manager.save_task_results,
            orchestrator_task_id,
            results
        )
        results["results_url"] = results_url

        # Upload artifacts
        artifacts = await asyncio.to_thread(
            storage_manager.upload_artifacts,
            orchestrator_task_id,
            artifacts_dir
        )
        results["artifacts"] = artifacts

        update_state("running", 0.9, step="cleaning_up")

        # Step 5: Delete VM (90% -> 100%)
        logger.info(f"Deleting VM {vm_info['vm_name']}")
        await asyncio.to_thread(
            vm_manager.delete_vm,
            orchestrator_task_id
        )

        # Task complete
        update_state("completed", 1.0, results=results)
        logger.info(
            f"Task {orchestrator_task_id} completed successfully: "
            f"success={results.get('success')}, steps={results.get('steps')}"
        )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Task {orchestrator_task_id} failed: {error_msg}", exc_info=True)

        # Attempt VM cleanup on failure
        if vm_info:
            try:
                logger.info(f"Attempting to delete VM after failure: {vm_info['vm_name']}")
                await asyncio.to_thread(
                    vm_manager.delete_vm,
                    orchestrator_task_id
                )
            except Exception as cleanup_error:
                logger.error(f"VM cleanup failed: {cleanup_error}")

        # Mark task as failed
        update_state(
            "failed",
            1.0,
            error=error_msg,
            results={
                "success": 0,
                "steps": 0,
                "time_sec": time.time() - start_time,
                "failure_reason": error_msg,
                "vm_cost": vm_manager.get_vm_cost(time.time() - start_time) if vm_info else 0.0,
            }
        )
