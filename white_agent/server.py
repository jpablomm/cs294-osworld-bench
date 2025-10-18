from __future__ import annotations
import argparse
import logging
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Observation(BaseModel):
    frame_id: int
    image_png_b64: str
    instruction: str = ""
    ui_hint: Optional[str] = None
    done: bool = False


app = FastAPI(title="White Agent (Native OSWorld)")

# State tracking
task_state = {
    "step": 0,
    "last_action": None,
    "task_done": False
}


@app.post("/reset")
def reset():
    """Reset agent state"""
    global task_state
    task_state = {
        "step": 0,
        "last_action": None,
        "task_done": False
    }
    logger.info("White Agent reset")
    return {"ok": True}


@app.post("/decide")
def decide(obs: Observation) -> Dict[str, Any]:
    """
    Decide next action based on observation.

    Returns action in OSWorld White Agent Bridge format:
    - op: "click", "type", "hotkey", "wait", "done", etc.
    - args: dict with operation-specific arguments
    """
    global task_state

    step = obs.frame_id
    instruction = obs.instruction if obs.instruction else ""
    task_state["step"] = step

    logger.info(f"Step {step}: Deciding action for instruction: {instruction[:100] if instruction else '(no instruction)'}")

    # For now, implement a simple strategy that just observes and finishes
    # This will be expanded later with actual task logic

    if step >= 10:
        logger.info(f"Step {step}: Max steps reached, finishing")
        return {"op": "done", "args": {}}

    # Wait and observe
    logger.info(f"Step {step}: Observing...")
    return {"op": "wait", "args": {"duration": 1.0}}


@app.get("/health")
def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent": "white-agent",
        "version": "0.2.0",
        "current_step": task_state["step"]
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="White Agent for OSWorld")
    parser.add_argument("--port", type=int, default=9000, help="Port to run on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()

    logger.info(f"Starting White Agent on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
