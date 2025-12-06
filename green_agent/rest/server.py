from __future__ import annotations
import os, json, uuid, time, base64, logging
from fastapi import FastAPI, HTTPException
from typing import Dict, Any

# Import from parent green_agent package
from green_agent.models import StartAssessmentRequest, AssessmentStatus, RunMetrics
from green_agent import storage
from green_agent.white_client import WhiteClient
from green_agent.osworld_adapter import run_osworld

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Green Agent (OSWorld MVP)")


@app.get("/health")
def health() -> Dict[str, Any]:
    """Health check endpoint for monitoring and load balancers."""
    use_fake = os.environ.get("USE_FAKE_OSWORLD", "1") == "1"
    use_native = os.environ.get("USE_NATIVE_OSWORLD", "0") == "1"
    osworld_server_url = os.environ.get("OSWORLD_SERVER_URL", "http://localhost:5000")

    # Determine mode
    if use_fake:
        mode = "fake"
    elif use_native:
        mode = "native"
    else:
        mode = "docker"

    return {
        "status": "healthy",
        "service": "green-agent",
        "version": "0.2.0",  # Bumped for native mode support
        "osworld_mode": mode,
        "osworld_server_url": osworld_server_url if mode == "native" else None,
        "max_steps": int(os.environ.get("OSWORLD_MAX_STEPS", "15")),
    }


@app.get("/card")
def card() -> Dict[str, Any]:
    return {
        "name": "Green-OSWorld-MVP",
        "version": "0.1.0",
        "assessments": ["osworld-ubuntu-tiny"],
        "fake_osworld": os.environ.get("USE_FAKE_OSWORLD", "1"),
    }


@app.get("/assessments")
def list_assessments(limit: int = 50) -> Dict[str, Any]:
    """List all assessments, newest first."""
    runs = storage.list_runs(limit=limit)
    return {
        "assessments": [
            {
                "assessment_id": r["assessment_id"],
                "task_id": r["task_id"],
                "status": r["status"],
                "success": r["success"],
                "steps": r["steps"],
                "time_sec": r["time_sec"],
                "created_at": r["created_at"],
            }
            for r in runs
        ],
        "total": len(runs),
    }


@app.post("/reset")
def reset():
    # stateless MVP; extend with caches if needed
    return {"ok": True}


@app.post("/assessments/start")
def start_assessment(req: StartAssessmentRequest) -> Dict[str, Any]:
    assess_id = str(uuid.uuid4())
    logger.info(f"Starting assessment {assess_id} for task={req.task_id}, white_agent={req.white_agent_url}")

    artifacts_dir = storage.create_run(assess_id, req.task_id, req.white_agent_url)
    logger.info(f"Created artifacts directory: {artifacts_dir}")

    # Load task JSON (MVP: tasks/<task_id>.json)
    task_path = os.path.join("tasks", f"{req.task_id}.json")
    if not os.path.exists(task_path):
        logger.error(f"Task not found: {req.task_id}")
        raise HTTPException(404, f"Task not found: {req.task_id}")
    with open(task_path, "r") as f:
        task = json.load(f)
    logger.info(f"Loaded task: {task.get('id', req.task_id)}")

    # White client
    white = WhiteClient(req.white_agent_url)
    white.reset()
    logger.info("White agent reset completed")

    t0 = time.time()
    steps = 0
    failure = None

    def white_decide(obs: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal steps
        steps += 1
        logger.debug(f"Step {steps}: Requesting decision from white agent")
        return white.decide(obs)

    try:
        logger.info("Starting OSWorld execution...")
        result = run_osworld(
            task,
            white_decide,
            artifacts_dir,
            white_agent_url=req.white_agent_url
        )
        logger.info(f"OSWorld execution completed: success={result.get('success')}, steps={result.get('steps')}")
    except Exception as e:
        logger.error(f"OSWorld execution error: {e}", exc_info=True)
        failure = f"adapter_error: {e}"
        result = {
            "success": 0,
            "steps": steps,
            "time_sec": time.time() - t0,
            "failure_reason": failure,
            "artifacts": {},
        }

    storage.update_status(
        assess_id,
        status="completed",
        success=int(result.get("success", 0)),
        steps=int(result.get("steps", 0)),
        time_sec=float(result.get("time_sec", 0.0)),
        failure_reason=result.get("failure_reason"),
    )

    logger.info(f"Assessment {assess_id} completed: success={result.get('success')}, time={result.get('time_sec'):.2f}s")

    return {
        "assessment_id": assess_id,
        "status": "running" if failure is None else "completed",
    }


@app.get("/assessments/{assessment_id}/status")
def status(assessment_id: str) -> AssessmentStatus:
    row = storage.fetch_run(assessment_id)
    if not row:
        raise HTTPException(404, "assessment not found")
    done = row["status"] == "completed"
    return AssessmentStatus(
        assessment_id=assessment_id,
        status=row["status"],
        progress=1.0 if done else 0.5,
        last_step=row.get("steps") or 0,
    )


@app.get("/assessments/{assessment_id}/results")
def results(assessment_id: str) -> RunMetrics:
    row = storage.fetch_run(assessment_id)
    if not row:
        raise HTTPException(404, "assessment not found")
    return RunMetrics(
        assessment_id=assessment_id,
        task_id=row["task_id"],
        white_agent=row["white_agent"],
        success=row["success"] or 0,
        steps=row["steps"] or 0,
        time_sec=row["time_sec"] or 0.0,
        failure_reason=row["failure_reason"],
        artifacts_dir=row["artifacts_dir"],
    )


@app.get("/assessments/{assessment_id}/artifacts")
def list_artifacts(assessment_id: str) -> Dict[str, Any]:
    """List all artifacts (screenshots, logs, etc.) for an assessment."""
    row = storage.fetch_run(assessment_id)
    if not row:
        raise HTTPException(404, "assessment not found")

    artifacts_dir = row["artifacts_dir"]
    if not os.path.exists(artifacts_dir):
        return {"assessment_id": assessment_id, "artifacts": [], "artifacts_dir": artifacts_dir}

    # List all files in the artifacts directory
    artifacts = []
    for root, dirs, files in os.walk(artifacts_dir):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, artifacts_dir)
            file_stat = os.stat(file_path)
            artifacts.append({
                "filename": rel_path,
                "size_bytes": file_stat.st_size,
                "modified": file_stat.st_mtime,
            })

    # Sort by filename
    artifacts.sort(key=lambda x: x["filename"])

    return {
        "assessment_id": assessment_id,
        "artifacts_dir": artifacts_dir,
        "total_files": len(artifacts),
        "artifacts": artifacts,
    }
