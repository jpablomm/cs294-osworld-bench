"""
WebUI Server for OSWorld Green Agent

Provides a web interface for monitoring and launching assessments.
Serves static HTML/CSS/JS files and provides REST API for data.
"""

import asyncio
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
    description="Web interface for OSWorld assessment system",
    version="1.0.0"
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
db = AssessmentDB("webui_assessments.db")

# Configuration
GREEN_AGENT_URL = "http://localhost:8001"
WHITE_AGENT_URL = "http://localhost:9002"
OSWORLD_EXAMPLES_DIR = Path(__file__).parent.parent / "vendor" / "OSWorld" / "evaluation_examples" / "examples"

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
    return JSONResponse({"error": "Dashboard not found. Static files not set up."}, status_code=404)


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
        "green_agent": {
            "url": GREEN_AGENT_URL,
            "healthy": green_healthy
        },
        "white_agent": {
            "url": WHITE_AGENT_URL,
            "healthy": white_healthy
        },
        "database": {
            "healthy": True,
            "path": str(db.db_path)
        }
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

                tasks.append({
                    "id": task_file.stem,
                    "domain": domain_dir.name,
                    "instruction": task_data.get("instruction", "No description")
                })
            except Exception as e:
                logger.warning(f"Failed to load task {task_file}: {e}")

    return tasks


@app.get("/api/assessments")
def list_assessments(
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
    domain: Optional[str] = None,
    task_id: Optional[str] = None
):
    """List assessments with optional filtering"""
    assessments = db.list_assessments(
        limit=limit,
        offset=offset,
        status=status,
        domain=domain,
        task_id=task_id
    )
    return {
        "assessments": assessments,
        "limit": limit,
        "offset": offset
    }


@app.get("/api/assessments/{assessment_id}")
def get_assessment(assessment_id: str):
    """Get single assessment with full details"""
    assessment = db.get_assessment(assessment_id)

    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    return assessment


@app.post("/api/assessments")
async def launch_assessment(request: LaunchRequest):
    """Launch new assessment"""
    assessment_id = f"assess-{uuid.uuid4().hex[:8]}"

    logger.info(f"Launching assessment {assessment_id} for task {request.task_id}")

    # Save initial assessment record
    db.save_assessment({
        "id": assessment_id,
        "task_id": request.task_id,
        "domain": request.domain,
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
        "config": {
            "max_steps": request.max_steps,
            "vm_image": request.vm_image,
            "white_agent_url": request.white_agent_url or WHITE_AGENT_URL
        }
    })

    # Create stream queue for this assessment
    active_streams[assessment_id] = asyncio.Queue()

    # Launch assessment in background
    asyncio.create_task(_run_assessment(assessment_id, request))

    return {
        "assessment_id": assessment_id,
        "status": "running",
        "monitor_url": f"/monitor/{assessment_id}"
    }


async def _run_assessment(assessment_id: str, request: LaunchRequest):
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
                "metrics": ["success", "steps", "time_sec"]
            }
        }

        if request.domain:
            a2a_task["metadata"]["domain"] = request.domain

        # Send to green agent
        async with httpx.AsyncClient(timeout=900.0) as client:
            response = await client.post(
                f"{GREEN_AGENT_URL}/task",
                json=a2a_task
            )
            response.raise_for_status()
            result = response.json()

        # Extract metadata
        metadata = result.get("metadata", {})
        metrics = metadata.get("metrics", {})

        # Update database with completion
        db.save_assessment({
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
            "config": {
                "max_steps": request.max_steps,
                "vm_image": request.vm_image,
                "white_agent_url": request.white_agent_url or WHITE_AGENT_URL
            },
            "result": metadata,
            "trajectory": metrics.get("trajectory", [])
        })

        # Send completion event to stream
        if assessment_id in active_streams:
            await active_streams[assessment_id].put({
                "type": "completed",
                "data": metrics
            })

        logger.info(f"Assessment {assessment_id} completed: success={metrics.get('success')}")

    except Exception as e:
        logger.error(f"Assessment {assessment_id} failed: {e}", exc_info=True)

        # Update database with failure
        db.save_assessment({
            "id": assessment_id,
            "task_id": request.task_id,
            "domain": request.domain,
            "status": "failed",
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "failure_reason": str(e)
        })

        # Send error to stream
        if assessment_id in active_streams:
            await active_streams[assessment_id].put({
                "type": "error",
                "error": str(e)
            })

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
            if assessment_id in active_streams and active_streams[assessment_id] == queue:
                del active_streams[assessment_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
