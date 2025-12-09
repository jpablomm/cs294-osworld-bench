#!/usr/bin/env python3
"""
White Agent - REST API Server

FastAPI-based REST server for custom orchestrator integration.
Uses PromptAgent for multi-model support (GPT-4V, Claude, Gemini, Qwen, etc.)
"""

import logging
import uuid
from typing import Dict, Any

from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

from white_agent.prompt_agent import PromptAgent
from white_agent.core import parse_observation, parse_actions
from white_agent.config import (
    MODEL,
    TEMPERATURE,
    OBSERVATION_TYPE,
    ACTION_SPACE,
    MAX_TRAJECTORY_LENGTH,
    MAX_TOKENS,
    TOP_P,
    WHITE_AGENT_HOST,
    WHITE_AGENT_PORT,
    get_agent_url,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# NOTE: Loop detection is handled by the Green Agent (orchestrator), not here.
# The Green Agent tracks actions and injects stuck_feedback into observations.
# See: green_agent/a2a/server.py for A2A flow.

# FastAPI app
app = FastAPI(
    title=f"White Agent (REST) - {MODEL}",
    description=f"White agent server using PromptAgent with {MODEL}"
)

# Global agent instance - lazy initialization
_agent: PromptAgent | None = None


def get_agent() -> PromptAgent:
    """Get or create the PromptAgent instance."""
    global _agent
    if _agent is None:
        logger.info(f"Initializing PromptAgent: model={MODEL}, obs_type={OBSERVATION_TYPE}")
        _agent = PromptAgent(
            model=MODEL,
            temperature=TEMPERATURE,
            observation_type=OBSERVATION_TYPE,
            action_space=ACTION_SPACE,
            max_trajectory_length=MAX_TRAJECTORY_LENGTH,
            max_tokens=MAX_TOKENS,
            top_p=TOP_P,
        )
        logger.info("PromptAgent initialized successfully")
    return _agent


# Conversation contexts (task_id -> context)
conversation_contexts: Dict[str, Dict[str, Any]] = {}


# Request/Response Models
class A2ATask(BaseModel):
    """Task request model (A2A-compatible format)"""
    task_id: str
    context_id: str | None = None
    message: str
    metadata: Dict[str, Any] | None = None


class A2AMessage(BaseModel):
    """Response message model (A2A-compatible format)"""
    message_id: str
    task_id: str
    context_id: str | None = None
    role: str
    content: str
    metadata: Dict[str, Any] | None = None


class Observation(BaseModel):
    """Direct observation request (simpler format)"""
    frame_id: int
    image_png_b64: str
    instruction: str = ""
    accessibility_tree: str | None = None
    done: bool = False
    reset_before: bool = False  # If True, reset agent trajectory before processing
    stuck_feedback: str | None = None  # Feedback when agent is stuck in a loop


class AgentCardResponse(BaseModel):
    """Agent card for discovery"""
    name: str
    description: str
    url: str
    version: str
    model: str


def build_agent_url() -> str:
    """Build the agent URL from environment."""
    return get_agent_url()


@app.on_event("startup")
async def startup_event():
    """Startup - agent initializes lazily on first request"""
    logger.info(f"White Agent (REST) starting - model={MODEL}")
    logger.info("Agent will initialize on first request")


@app.get("/health")
def health():
    """Health check endpoint"""
    return {
        "status": "healthy" if _agent is not None else "initializing",
        "protocol": "rest",
        "model": MODEL,
        "observation_type": OBSERVATION_TYPE,
        "agent_ready": _agent is not None,
        "active_contexts": len(conversation_contexts)
    }


@app.get("/status")
def status():
    """Status endpoint"""
    return {
        "status": "running" if _agent is not None else "initializing",
        "model": MODEL,
        "protocol": "rest"
    }


@app.get("/agent-card")
@app.get("/.well-known/agent-card.json")
def get_agent_card() -> AgentCardResponse:
    """Agent card for discovery"""
    return AgentCardResponse(
        name=f"OSWorld Agent ({MODEL})",
        description=f"White agent for desktop automation using {MODEL}",
        url=build_agent_url(),
        version="2.0.0",
        model=MODEL
    )


@app.post("/task")
def handle_task(task: A2ATask) -> A2AMessage:
    """
    Handle task request (A2A-compatible format).

    Expected task.metadata:
    {
        "observation": {
            "frame_id": int,
            "image_png_b64": str,
            "instruction": str,
            "done": bool
        }
    }
    """
    try:
        agent = get_agent()
    except Exception as e:
        return A2AMessage(
            message_id=str(uuid.uuid4()),
            task_id=task.task_id,
            context_id=task.context_id or task.task_id,
            role="agent",
            content=f"Agent initialization failed: {e}",
            metadata={"status": "error", "error": "agent_init_failed"}
        )

    context_id = task.context_id or task.task_id

    # Initialize conversation context if needed
    if context_id not in conversation_contexts:
        # Reset agent for new context to prevent cross-task contamination
        agent.reset()
        conversation_contexts[context_id] = {
            "task_id": task.task_id,
            "step": 0,
            "history": [],
            "instruction": None
        }

    context = conversation_contexts[context_id]
    step = context["step"]

    try:
        # Parse observation
        if not task.metadata or "observation" not in task.metadata:
            raise ValueError("Task must have observation in metadata")

        observation = parse_observation(task.metadata)
        instruction = observation["instruction"]
        screenshot_bytes = observation["screenshot"]
        accessibility_tree = observation.get("accessibility_tree")

        if context["instruction"] is None:
            context["instruction"] = instruction

        logger.info(f"Step {step}: Processing observation for '{instruction[:80]}...'")

        # Build observation for agent
        obs_for_agent = {"screenshot": screenshot_bytes}
        if accessibility_tree:
            obs_for_agent["accessibility_tree"] = accessibility_tree

        # Get prediction
        response, actions = agent.predict(instruction, obs_for_agent)

        # Parse actions using core.py's robust parser directly on raw response
        # It handles JSON, pyautogui code, DONE/FAIL, and code blocks
        action = parse_actions(response)

        # Update context
        context["step"] += 1
        context["history"].append({"step": step, "response": response, "action": action})

        # Check if done
        task_done = action.get("op") == "done" or observation.get("done", False)
        if task_done:
            del conversation_contexts[context_id]

        return A2AMessage(
            message_id=str(uuid.uuid4()),
            task_id=task.task_id,
            context_id=context_id,
            role="agent",
            content=f"Step {step}: {response}",
            metadata={
                "action": action,
                "step": step,
                "done": task_done,
                "raw_response": response
            }
        )

    except Exception as e:
        logger.error(f"Task processing failed: {e}", exc_info=True)
        return A2AMessage(
            message_id=str(uuid.uuid4()),
            task_id=task.task_id,
            context_id=context_id,
            role="agent",
            content=f"Error: {e}",
            metadata={"status": "error", "error": str(e)}
        )


@app.post("/decide")
def decide(obs: Observation) -> Dict[str, Any]:
    """
    Direct action decision endpoint (simpler format).

    Returns OSWorld action format:
    {"op": "click", "args": {"x": 100, "y": 200}}

    Set reset_before=True in the request to clear agent trajectory before processing.
    This should be used for the first observation of a new task to prevent
    cross-task contamination from previous assessments.
    """
    try:
        agent = get_agent()
    except Exception as e:
        return {"op": "error", "args": {"message": str(e)}}

    try:
        # Reset agent trajectory if requested (should be True for first step of new task)
        if obs.reset_before:
            agent.reset()
            logger.info(f"Agent trajectory reset before processing frame {obs.frame_id}")

        # Parse observation properly
        observation = parse_observation({
            "image_png_b64": obs.image_png_b64,
            "instruction": obs.instruction,
            "frame_id": obs.frame_id,
            "done": obs.done
        })

        obs_for_agent = {"screenshot": observation["screenshot"]}
        if obs.accessibility_tree:
            obs_for_agent["accessibility_tree"] = obs.accessibility_tree

        # Inject stuck feedback into instruction if present
        instruction = obs.instruction
        if obs.stuck_feedback:
            logger.warning(f"[LoopDetection] === STUCK FEEDBACK RECEIVED === Frame {obs.frame_id}")
            logger.info(f"[LoopDetection] Modifying instruction to include recovery guidance")
            logger.debug(f"[LoopDetection] Stuck feedback preview: {obs.stuck_feedback[:200]}...")
            instruction = f"{obs.stuck_feedback}\n\nOriginal task: {obs.instruction}"

        response, actions = agent.predict(instruction, obs_for_agent)

        # Parse actions using core.py's robust parser directly on raw response
        # It handles JSON, pyautogui code, DONE/FAIL, and code blocks
        return parse_actions(response)

    except Exception as e:
        logger.error(f"Decide failed: {e}", exc_info=True)
        return {"op": "error", "args": {"message": str(e)}}


@app.post("/reset")
def reset():
    """Reset agent state"""
    global conversation_contexts, _agent
    if _agent is not None:
        _agent.reset()
    conversation_contexts = {}
    logger.info("Agent reset")
    return {"status": "reset", "model": MODEL}


@app.get("/debug/contexts")
def debug_contexts():
    """Debug endpoint to view conversation contexts"""
    return {
        "active_contexts": len(conversation_contexts),
        "model": MODEL,
        "contexts": {
            ctx_id: {
                "task_id": ctx["task_id"],
                "step": ctx["step"],
                "instruction": ctx["instruction"][:100] if ctx["instruction"] else None,
            }
            for ctx_id, ctx in conversation_contexts.items()
        }
    }


@app.get("/debug/trajectory")
def debug_trajectory():
    """
    Debug endpoint to inspect agent trajectory history.

    This shows the internal state of the PromptAgent that determines
    what context is sent to the LLM on each prediction.
    """
    if _agent is None:
        return {
            "status": "agent_not_initialized",
            "message": "Agent has not been initialized yet. Make a prediction first."
        }

    observations = _agent.observations
    actions = _agent.actions
    thoughts = _agent.thoughts
    max_traj = _agent.max_trajectory_length

    # Truncate for readability
    def truncate(s, max_len=200):
        if isinstance(s, str):
            return s[:max_len] + "..." if len(s) > max_len else s
        elif isinstance(s, list):
            return [truncate(item, max_len) for item in s[-5:]]
        return str(s)[:max_len]

    return {
        "status": "ok",
        "model": MODEL,
        "trajectory_length": len(actions),
        "max_trajectory_length": max_traj,
        "context_sent_to_llm": min(len(actions), max_traj),
        "observations_count": len(observations),
        "actions_count": len(actions),
        "thoughts_count": len(thoughts),
        "recent_actions": truncate(actions),
        "recent_thoughts": truncate(thoughts),
        "observation_has_screenshot": [
            bool(obs.get("screenshot")) if isinstance(obs, dict) else False
            for obs in observations[-5:]
        ] if observations else [],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=WHITE_AGENT_HOST, port=WHITE_AGENT_PORT)
