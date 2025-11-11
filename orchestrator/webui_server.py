"""
WebUI Server for OSWorld Green Agent

Provides a web interface for monitoring and launching assessments.
Serves static HTML/CSS/JS files and provides REST API for data.
"""

import asyncio
import os
import httpx
import json
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .database import AssessmentDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="OSWorld WebUI",
    description="Web interface for OSWorld Green Agent",
    version="1.0.0",
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
USE_POSTGRES = os.getenv("USE_POSTGRES", "0") == "1"

if USE_POSTGRES:
    try:
        from .database_postgres import PostgresDatabase

        db = PostgresDatabase()
        logger.info("Using PostgreSQL database")
    except Exception as e:
        logger.error("Failed to initialize PostgreSQL database: %s", e)
        raise
else:
    db = AssessmentDB("webui_assessments.db")
    logger.info("Using SQLite database at webui_assessments.db")

# Configuration
GREEN_AGENT_URL = "http://localhost:8001"
WHITE_AGENT_URL = "http://localhost:9002"
OSWORLD_EXAMPLES_DIR = (
    Path(__file__).parent.parent
    / "vendor"
    / "OSWorld"
    / "evaluation_examples"
    / "examples"
)

# Track active assessment streams
active_streams: Dict[str, asyncio.Queue] = {}


# ============================================================================
# Models
# ============================================================================


class LaunchRequest(BaseModel):
    """Request to launch new assessment"""

    task_id: str
    domain: Optional[str] = None
    max_steps: int = 15
    vm_image: str = "osworld-golden-v3-gnome"
    white_agent_url: Optional[str] = None
    num_runs: int = 1  # Number of parallel runs for rolling average


# ============================================================================
# Static Files
# ============================================================================

# Mount static files directory
static_dir = Path(__file__).parent.parent / "webui" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def serve_index():
    """Serve dashboard page"""
    html_path = static_dir / "dashboard.html"
    if html_path.exists():
        return FileResponse(html_path)
    return JSONResponse(
        {"error": "Dashboard not found. Static files not set up."}, status_code=404
    )


@app.get("/launch")
def serve_launch():
    """Serve launch page"""
    html_path = static_dir / "launch.html"
    if html_path.exists():
        return FileResponse(html_path)
    return JSONResponse({"error": "Launch page not found"}, status_code=404)


@app.get("/monitor/{assessment_id}")
def serve_monitor(assessment_id: str):
    """Serve monitor page"""
    html_path = static_dir / "monitor.html"
    if html_path.exists():
        return FileResponse(html_path)
    return JSONResponse({"error": "Monitor page not found"}, status_code=404)


@app.get("/results")
def serve_results():
    """Serve results browser page"""
    html_path = static_dir / "results.html"
    if html_path.exists():
        return FileResponse(html_path)
    return JSONResponse({"error": "Results page not found"}, status_code=404)


@app.get("/leaderboard")
def serve_leaderboard():
    """Serve leaderboard page"""
    html_path = static_dir / "leaderboard.html"
    if html_path.exists():
        return FileResponse(html_path)
    return JSONResponse({"error": "Leaderboard page not found"}, status_code=404)


@app.get("/batch/{batch_id}")
def serve_batch_monitor(batch_id: str):
    """Serve batch monitor page"""
    html_path = static_dir / "batch.html"
    if html_path.exists():
        return FileResponse(html_path)
    return JSONResponse({"error": "Batch monitor page not found"}, status_code=404)


# ============================================================================
# API Endpoints
# ============================================================================


@app.get("/api/health")
async def get_health():
    """Get system health status"""
    green_healthy = False
    white_healthy = False

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            # Check green agent
            try:
                response = await client.get(f"{GREEN_AGENT_URL}/health")
                green_healthy = response.status_code == 200
            except:
                pass

            # Check white agent
            try:
                response = await client.get(f"{WHITE_AGENT_URL}/health")
                white_healthy = response.status_code == 200
            except:
                pass

    except Exception as e:
        logger.error(f"Health check error: {e}")

    return {
        "green_agent": {"url": GREEN_AGENT_URL, "healthy": green_healthy},
        "white_agent": {"url": WHITE_AGENT_URL, "healthy": white_healthy},
        "database": {"healthy": True, "path": str(db.db_path)},
    }


@app.get("/api/stats")
def get_stats():
    """Get aggregate statistics"""
    return db.get_stats()


@app.get("/api/tasks")
def list_tasks(domain: Optional[str] = None):
    """List available OSWorld tasks"""
    tasks = []

    if not OSWORLD_EXAMPLES_DIR.exists():
        logger.warning(f"OSWorld examples directory not found: {OSWORLD_EXAMPLES_DIR}")
        return []

    # Iterate through domains
    for domain_dir in OSWORLD_EXAMPLES_DIR.iterdir():
        if not domain_dir.is_dir():
            continue

        # Skip if filtering by domain
        if domain and domain_dir.name != domain:
            continue

        # Load tasks from this domain
        for task_file in domain_dir.glob("*.json"):
            try:
                with open(task_file) as f:
                    task_data = json.load(f)

                tasks.append(
                    {
                        "id": task_file.stem,
                        "domain": domain_dir.name,
                        "instruction": task_data.get("instruction", "No description"),
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to load task {task_file}: {e}")

    return tasks


@app.get("/api/tasks/{task_id}")
def get_task_details(task_id: str, domain: Optional[str] = None):
    """Get full task details including evaluation configuration"""

    if not OSWORLD_EXAMPLES_DIR.exists():
        raise HTTPException(
            status_code=404, detail="OSWorld examples directory not found"
        )

    # If domain provided, search in that domain only
    if domain:
        task_file = OSWORLD_EXAMPLES_DIR / domain / f"{task_id}.json"
        if task_file.exists():
            with open(task_file) as f:
                return json.load(f)

    # Otherwise search all domains
    for domain_dir in OSWORLD_EXAMPLES_DIR.iterdir():
        if not domain_dir.is_dir():
            continue

        task_file = domain_dir / f"{task_id}.json"
        if task_file.exists():
            with open(task_file) as f:
                return json.load(f)

    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


@app.get("/api/assessments")
def list_assessments(
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
    domain: Optional[str] = None,
    task_id: Optional[str] = None,
):
    """List assessments with optional filtering"""
    assessments = db.list_assessments(
        limit=limit, offset=offset, status=status, domain=domain, task_id=task_id
    )
    return {"assessments": assessments, "limit": limit, "offset": offset}


@app.get("/api/assessments/{assessment_id}")
def get_assessment(assessment_id: str):
    """Get single assessment with full details"""
    assessment = db.get_assessment(assessment_id)

    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    return assessment


@app.post("/api/assessments")
async def launch_assessment(request: LaunchRequest):
    """Launch new assessment (or batch of parallel runs)"""
    batch_id = f"batch-{uuid.uuid4().hex[:8]}"
    assessment_ids = []

    logger.info(
        f"Launching batch {batch_id} with {request.num_runs} run(s) for task {request.task_id}"
    )

    # Create assessment IDs for each run
    for run_num in range(1, request.num_runs + 1):
        if request.num_runs == 1:
            # Single run: use simple ID
            assessment_id = f"assess-{uuid.uuid4().hex[:8]}"
        else:
            # Multiple runs: include run number in ID
            assessment_id = f"assess-{uuid.uuid4().hex[:8]}-run-{run_num}"

        assessment_ids.append(assessment_id)

        # Save initial assessment record
        db.save_assessment(
            {
                "id": assessment_id,
                "task_id": request.task_id,
                "domain": request.domain,
                "status": "running",
                "started_at": datetime.utcnow().isoformat(),
                "run_number": run_num,
                "batch_id": batch_id,
                "config": {
                    "max_steps": request.max_steps,
                    "vm_image": request.vm_image,
                    "white_agent_url": request.white_agent_url or WHITE_AGENT_URL,
                },
            }
        )

        # Create stream queue for this assessment
        active_streams[assessment_id] = asyncio.Queue()

    # Launch all runs in parallel
    tasks = [
        _run_assessment(assessment_id, request, run_num, batch_id)
        for run_num, assessment_id in enumerate(assessment_ids, 1)
    ]
    asyncio.gather(*tasks)  # Fire and forget

    # Return single ID for num_runs=1, batch_id for multiple runs
    if request.num_runs == 1:
        return {
            "assessment_id": assessment_ids[0],
            "batch_id": batch_id,
            "status": "running",
            "monitor_url": f"/monitor/{assessment_ids[0]}",
        }
    else:
        return {
            "batch_id": batch_id,
            "assessment_ids": assessment_ids,
            "status": "running",
            "num_runs": request.num_runs,
            "monitor_url": f"/batch/{batch_id}",
        }


async def _run_assessment(
    assessment_id: str, request: LaunchRequest, run_number: int, batch_id: str
):
    """Run assessment in background and update database"""
    try:
        # Build A2A task request
        a2a_task = {
            "task_id": assessment_id,
            "context_id": assessment_id,
            "message": f"Run OSWorld assessment for task '{request.task_id}'",
            "metadata": {
                "osworld_task_id": request.task_id,
                "white_agent_url": request.white_agent_url or WHITE_AGENT_URL,
                "max_steps": request.max_steps,
                "vm_image": request.vm_image,
                "metrics": ["success", "steps", "time_sec"],
            },
        }

        if request.domain:
            a2a_task["metadata"]["domain"] = request.domain

        # Send to green agent
        async with httpx.AsyncClient(timeout=900.0) as client:
            response = await client.post(f"{GREEN_AGENT_URL}/task", json=a2a_task)
            response.raise_for_status()
            result = response.json()

        # Extract metadata
        metadata = result.get("metadata", {})
        metrics = metadata.get("metrics", {})

        # Update database with completion
        db.save_assessment(
            {
                "id": assessment_id,
                "task_id": request.task_id,
                "domain": request.domain,
                "status": "completed",
                "started_at": datetime.utcnow().isoformat(),  # Should come from result
                "completed_at": datetime.utcnow().isoformat(),
                "steps": metrics.get("steps", 0),
                "success": metrics.get("success", 0),
                "evaluation_score": metrics.get("evaluation_score"),
                "evaluation_method": metrics.get("evaluation_method"),
                "failure_reason": metrics.get("failure_reason"),
                "time_sec": metrics.get("time_sec"),
                "vm_cost": metrics.get("vm_cost"),
                "run_number": run_number,
                "batch_id": batch_id,
                "config": {
                    "max_steps": request.max_steps,
                    "vm_image": request.vm_image,
                    "white_agent_url": request.white_agent_url or WHITE_AGENT_URL,
                },
                "result": metadata,
                "trajectory": metrics.get("trajectory", []),
            }
        )

        # Send completion event to stream
        if assessment_id in active_streams:
            await active_streams[assessment_id].put(
                {"type": "completed", "data": metrics}
            )

        logger.info(
            f"Assessment {assessment_id} completed: success={metrics.get('success')}"
        )

    except Exception as e:
        logger.error(f"Assessment {assessment_id} failed: {e}", exc_info=True)

        # Update database with failure
        db.save_assessment(
            {
                "id": assessment_id,
                "task_id": request.task_id,
                "domain": request.domain,
                "status": "failed",
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
                "failure_reason": str(e),
                "run_number": run_number,
                "batch_id": batch_id,
            }
        )

        # Send error to stream
        if assessment_id in active_streams:
            await active_streams[assessment_id].put({"type": "error", "error": str(e)})

    finally:
        # Cleanup stream
        if assessment_id in active_streams:
            await active_streams[assessment_id].put(None)  # Signal end of stream


@app.get("/api/stream/{assessment_id}")
async def stream_assessment(assessment_id: str):
    """Server-Sent Events stream for live assessment updates"""

    async def event_generator():
        # Get or create queue for this assessment
        if assessment_id not in active_streams:
            active_streams[assessment_id] = asyncio.Queue()

        queue = active_streams[assessment_id]

        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'assessment_id': assessment_id})}\n\n"

            # Stream events
            while True:
                event = await queue.get()

                if event is None:  # End of stream
                    break

                yield f"data: {json.dumps(event)}\n\n"

        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for {assessment_id}")
        finally:
            # Cleanup
            if (
                assessment_id in active_streams
                and active_streams[assessment_id] == queue
            ):
                del active_streams[assessment_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/artifacts/{assessment_id}/{filepath:path}")
def get_artifact(assessment_id: str, filepath: str):
    """Get assessment artifact (screenshot, etc.)"""
    artifacts_dir = Path(f"./temp_artifacts/{assessment_id}")
    file_path = artifacts_dir / filepath

    # Security: ensure the path is within artifacts_dir
    try:
        file_path = file_path.resolve()
        artifacts_dir = artifacts_dir.resolve()
        if not str(file_path).startswith(str(artifacts_dir)):
            raise HTTPException(status_code=403, detail="Access denied")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")

    return FileResponse(file_path)


# ============================================================================
# Batch and Statistics Endpoints
# ============================================================================


@app.get("/api/batches/{batch_id}")
def get_batch(batch_id: str):
    """Get all assessments in a batch with aggregate statistics"""
    assessments = db.get_batch_assessments(batch_id)

    if not assessments:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Calculate aggregate stats across batch
    completed = [a for a in assessments if a["status"] == "completed"]

    if completed:
        avg_success = sum(a.get("success", 0) for a in completed) / len(completed) * 100
        avg_steps = sum(a.get("steps", 0) for a in completed) / len(completed)
        avg_time = sum(a.get("time_sec", 0) for a in completed) / len(completed)
        avg_score = sum(a.get("evaluation_score", 0) or 0 for a in completed) / len(
            completed
        )
    else:
        avg_success = avg_steps = avg_time = avg_score = 0

    return {
        "batch_id": batch_id,
        "total_runs": len(assessments),
        "completed_runs": len(completed),
        "assessments": assessments,
        "aggregate_stats": {
            "success_rate": round(avg_success, 1),
            "avg_steps": round(avg_steps, 1),
            "avg_time_sec": round(avg_time, 1),
            "avg_evaluation_score": round(avg_score, 3) if avg_score else None,
        },
    }


@app.get("/api/tasks/{task_id}/stats")
def get_task_stats(task_id: str):
    """Get rolling average statistics for a task across all historical runs"""
    stats = db.get_task_statistics(task_id)
    return {"task_id": task_id, **stats}


# ============================================================================
# Leaderboard Endpoints
# ============================================================================


@app.get("/api/metrics")
def get_metrics():
    """Get available metrics for leaderboards"""
    return {"metrics": db.get_available_metrics()}


@app.get("/api/leaderboard")
def get_leaderboard(
    task_id: Optional[str] = None,
    metric: str = "success_rate",
    limit: int = 50,
    domain: Optional[str] = None,
):
    """
    Unified leaderboard endpoint

    Args:
        task_id: Optional task ID to filter by (per-task leaderboard)
        metric: Metric to rank by (success_rate, avg_steps, avg_time_sec, avg_evaluation_score)
        limit: Maximum number of entries
        domain: Optional domain filter (for global leaderboard)

    Returns:
        Leaderboard ranked by specified metric
    """
    try:
        if task_id:
            # Per-task leaderboard
            leaderboard = db.get_task_leaderboard(task_id, metric, limit)
            return {
                "type": "task",
                "task_id": task_id,
                "metric": metric,
                "leaderboard": leaderboard,
            }
        else:
            # Global leaderboard
            leaderboard = db.get_global_leaderboard(metric, limit, domain)
            return {
                "type": "global",
                "domain": domain,
                "metric": metric,
                "leaderboard": leaderboard,
            }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/leaderboard/tasks/{task_id}")
def get_task_leaderboard_shortcut(
    task_id: str, metric: str = "success_rate", limit: int = 50
):
    """Shortcut endpoint for per-task leaderboard"""
    try:
        leaderboard = db.get_task_leaderboard(task_id, metric, limit)
        return {"task_id": task_id, "metric": metric, "leaderboard": leaderboard}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/leaderboard/global")
def get_global_leaderboard_shortcut(
    metric: str = "success_rate", limit: int = 50, domain: Optional[str] = None
):
    """Shortcut endpoint for global leaderboard"""
    try:
        leaderboard = db.get_global_leaderboard(metric, limit, domain)
        return {"metric": metric, "domain": domain, "leaderboard": leaderboard}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Enhanced Visualization Endpoints (Phase 3)
# ============================================================================


@app.get("/api/assessments/{assessment_id}/messages")
def get_assessment_messages(assessment_id: str):
    """
    Get detailed A2A message history for an assessment
    
    Returns:
        Full A2A message exchange with timestamps, direction, validation status
    """
    assessment = db.get_assessment(assessment_id)
    
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Extract messages from trajectory
    messages = []
    
    # Check if trajectory has enhanced message data (Phase 3+)
    trajectory = assessment.get("trajectory", [])
    
    for idx, step in enumerate(trajectory):
        # Try to extract message data
        message_data = step.get("message_data", {})
        
        if message_data:
            # New format with detailed message tracking
            messages.append(message_data)
        else:
            # Legacy format - construct from available data
            messages.append({
                "id": f"msg-{assessment_id}-{idx}",
                "timestamp": assessment["started_at"],  # Approximate
                "direction": "white_to_green",  # Agent response
                "type": "response",
                "payload": {
                    "action": step.get("action", {}),
                    "content": step.get("content", "")
                },
                "validation": {
                    "valid": True,  # Assume valid if it's in trajectory
                    "errors": []
                },
                "latency_ms": 0  # Unknown
            })
    
    return {"messages": messages}


@app.get("/api/assessments/{assessment_id}/tools")
def get_tool_executions(assessment_id: str):
    """
    Get detailed tool execution log for an assessment
    
    Returns:
        Tool execution timeline with timing, parameters, results
    """
    assessment = db.get_assessment(assessment_id)
    
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    executions = []
    trajectory = assessment.get("trajectory", [])
    
    for step in trajectory:
        action = step.get("action", {})
        tool_data = step.get("tool_data", {})
        
        if tool_data:
            # New format with detailed tool tracking
            executions.append(tool_data)
        else:
            # Legacy format - construct from available data
            execution = {
                "step": step.get("step", 0),
                "timestamp": assessment["started_at"],  # Approximate
                "tool": action.get("op", "unknown"),
                "parameters": {k: v for k, v in action.items() if k != "op"},
                "status": "success",  # Assume success if in trajectory
                "duration_ms": 0,  # Unknown
                "result": None,
                "screenshot_before": None,
                "screenshot_after": f"/api/artifacts/{assessment_id}/step_{step.get('step', 0) + 1}.png"
            }
            executions.append(execution)
    
    return {"executions": executions}


@app.get("/api/assessments/{assessment_id}/agent-state")
def get_agent_state(assessment_id: str):
    """
    Get current or final state of both agents
    
    Returns:
        Agent state information (green agent + white agent)
    """
    assessment = db.get_assessment(assessment_id)
    
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Extract agent state from assessment metadata
    agent_state = assessment.get("agent_state", {})
    
    if agent_state:
        # New format with detailed state tracking
        return agent_state
    
    # Legacy format - construct from available data
    status = assessment.get("status", "unknown")
    steps = assessment.get("steps", 0)
    max_steps = assessment.get("config", {}).get("max_steps", 15)
    
    return {
        "green_agent": {
            "status": "idle" if status == "completed" else "evaluating" if status == "failed" else "executing_tool",
            "current_step": steps,
            "current_action": f"Step {steps}/{max_steps}",
            "vm_status": "ready" if status == "completed" else "running",
            "tools_available": 7  # Standard OSWorld tools
        },
        "white_agent": {
            "status": "idle" if status == "completed" else "analyzing",
            "thinking_time_ms": 0,  # Unknown
            "last_action": assessment.get("trajectory", [])[-1].get("action") if assessment.get("trajectory") else None,
            "tools_used": list(set([
                step.get("action", {}).get("op", "unknown") 
                for step in assessment.get("trajectory", [])
            ])),
            "message_count": len(assessment.get("trajectory", []))
        }
    }


@app.get("/api/assessments/{assessment_id}/evaluation")
def get_evaluation_details(assessment_id: str):
    """
    Get detailed evaluation information
    
    Returns:
        Evaluation method, expected vs actual, score breakdown
    """
    assessment = db.get_assessment(assessment_id)
    
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Extract evaluation details
    evaluation = assessment.get("evaluation_details", {})
    
    if evaluation:
        # New format with detailed evaluation tracking
        return evaluation
    
    # Legacy format - construct from available data
    return {
        "method": assessment.get("evaluation_method", "unknown"),
        "score": assessment.get("evaluation_score"),
        "success": bool(assessment.get("success", 0)),
        "expected": None,  # Not available in legacy format
        "actual": None,  # Not available in legacy format
        "details": assessment.get("result", {})
    }


# ============================================================================
# Internal Event Callback (for green agent to push events)
# ============================================================================


@app.post("/api/internal/events/{assessment_id}")
async def receive_assessment_event(assessment_id: str, event: Dict[str, Any]):
    """
    Internal endpoint for green agent to push real-time events
    
    This allows the green agent to push events to SSE subscribers
    """
    if assessment_id in active_streams:
        try:
            await active_streams[assessment_id].put(event)
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Failed to push event for {assessment_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Assessment not being monitored - that's ok, just acknowledge
    return {"status": "ok", "note": "no active subscribers"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3001)
