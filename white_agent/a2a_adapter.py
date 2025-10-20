"""
A2A-Compliant White Agent Adapter

This module wraps the existing white agent to make it AgentBeats-compliant.
It implements the A2A protocol while preserving the existing /decide interface.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI
from pydantic import BaseModel
import uuid

# Import existing white agent logic
from .server import decide, reset, Observation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# A2A Protocol Models
class AgentCard(BaseModel):
    """Agent self-description following A2A protocol"""
    name: str
    description: str
    version: str
    capabilities: list[str]
    protocols: list[str]


class A2ATask(BaseModel):
    """A2A Task format"""
    task_id: str
    context_id: Optional[str] = None
    message: str  # Task description or observation
    metadata: Optional[Dict[str, Any]] = None


class A2AMessage(BaseModel):
    """A2A Message response"""
    message_id: str
    task_id: str
    context_id: Optional[str] = None
    role: str  # "agent"
    content: str  # Human-readable action description
    metadata: Optional[Dict[str, Any]] = None  # Contains actual action


# Create FastAPI app for A2A white agent
app = FastAPI(
    title="OSWorld White Agent (A2A)",
    description="AgentBeats-compliant white agent for OSWorld desktop automation",
    version="0.1.0"
)

# Track conversation context for multi-turn interactions
conversation_contexts: Dict[str, Dict[str, Any]] = {}


@app.get("/agent-card")
def get_agent_card() -> AgentCard:
    """
    Return agent card - A2A protocol requirement

    This describes the white agent's capabilities for AgentBeats platform
    """
    return AgentCard(
        name="OSWorld Task Executor",
        description=(
            "White agent for executing desktop automation tasks in OSWorld environments. "
            "Receives observations (screenshots, instructions) and returns actions "
            "(clicks, typing, navigation). Designed for OSWorld assessment workflows."
        ),
        version="0.1.0",
        capabilities=[
            "desktop-automation",
            "screen-observation",
            "mouse-control",
            "keyboard-control",
            "task-execution"
        ],
        protocols=["a2a", "rest", "osworld-decide"]
    )


@app.post("/task")
async def handle_a2a_task(task: A2ATask) -> A2AMessage:
    """
    Handle A2A task - agent decision-making

    This endpoint translates between A2A protocol and the OSWorld decide interface.

    The task.message contains either:
    1. A task instruction (first turn)
    2. An observation from the green agent (subsequent turns)

    Returns an A2A message with the action to take.
    """
    logger.info(f"Received A2A task: {task.task_id} (context: {task.context_id})")

    # Initialize or retrieve conversation context
    context_id = task.context_id or task.task_id
    if context_id not in conversation_contexts:
        # Extract tool descriptions if provided (Approach II)
        tools = task.metadata.get("tools", []) if task.metadata else []

        conversation_contexts[context_id] = {
            "step": 0,
            "task_id": task.task_id,
            "created_at": str(uuid.uuid4()),
            "tools": tools,
            "osworld_server": task.metadata.get("osworld_server") if task.metadata else None
        }
        # Reset internal state for new task
        reset()

        if tools:
            logger.info(f"New conversation context created: {context_id} with {len(tools)} tools")
        else:
            logger.info(f"New conversation context created: {context_id}")

    context = conversation_contexts[context_id]
    step = context["step"]

    # Parse observation from task metadata
    try:
        observation = _parse_observation(task, step)
        logger.info(f"Parsed observation for step {step}")
    except Exception as e:
        error_msg = f"Failed to parse observation: {e}"
        logger.error(error_msg)
        return A2AMessage(
            message_id=str(uuid.uuid4()),
            task_id=task.task_id,
            context_id=context_id,
            role="agent",
            content=error_msg,
            metadata={"status": "error", "error": str(e)}
        )

    # Get action from existing decide logic
    try:
        action = decide(observation)
        logger.info(f"Step {step}: Action decided - {action['op']}")

        # Update conversation context
        context["step"] += 1
        context["last_action"] = action

        # Check if task is done
        is_done = action.get("op") == "done" or observation.done

        if is_done:
            logger.info(f"Task {task.task_id} completed after {step} steps")
            # Clean up context
            del conversation_contexts[context_id]

        # Format response as A2A message
        return A2AMessage(
            message_id=str(uuid.uuid4()),
            task_id=task.task_id,
            context_id=context_id,
            role="agent",
            content=_format_action_message(action, step),
            metadata={
                "action": action,
                "step": step,
                "done": is_done
            }
        )

    except Exception as e:
        error_msg = f"Decision failed: {e}"
        logger.error(error_msg, exc_info=True)
        return A2AMessage(
            message_id=str(uuid.uuid4()),
            task_id=task.task_id,
            context_id=context_id,
            role="agent",
            content=error_msg,
            metadata={"status": "error", "error": str(e)}
        )


def _parse_observation(task: A2ATask, step: int) -> Observation:
    """
    Parse A2A task into Observation format expected by decide()

    Supports:
    1. Structured observation in metadata
    2. Base64 image in metadata with instruction in message
    """
    # Option 1: Full observation object in metadata
    if task.metadata and "observation" in task.metadata:
        obs_data = task.metadata["observation"]
        return Observation(
            frame_id=obs_data.get("frame_id", step),
            image_png_b64=obs_data["image_png_b64"],
            instruction=obs_data.get("instruction", task.message),
            ui_hint=obs_data.get("ui_hint"),
            done=obs_data.get("done", False)
        )

    # Option 2: Image in metadata, instruction in message
    if task.metadata and "image_png_b64" in task.metadata:
        return Observation(
            frame_id=step,
            image_png_b64=task.metadata["image_png_b64"],
            instruction=task.message,
            ui_hint=task.metadata.get("ui_hint"),
            done=task.metadata.get("done", False)
        )

    # Option 3: Just instruction (for testing without actual observations)
    return Observation(
        frame_id=step,
        image_png_b64="",  # Empty for text-only testing
        instruction=task.message,
        done=False
    )


def _format_action_message(action: Dict[str, Any], step: int) -> str:
    """
    Format action as human-readable message

    This makes the A2A response interpretable by humans and other agents
    """
    op = action.get("op", "unknown")
    args = action.get("args", {})

    if op == "click":
        x, y = args.get("x", 0), args.get("y", 0)
        return f"Step {step}: Click at position ({x}, {y})"

    elif op == "type":
        text = args.get("text", "")
        return f"Step {step}: Type '{text}'"

    elif op == "hotkey":
        keys = args.get("keys", [])
        return f"Step {step}: Press hotkey {'+'.join(keys)}"

    elif op == "wait":
        duration = args.get("duration", 1.0)
        return f"Step {step}: Wait {duration}s"

    elif op == "done":
        return f"Step {step}: Task completed"

    else:
        return f"Step {step}: {op} with args {args}"


@app.post("/reset")
def reset_a2a():
    """
    A2A-compatible reset endpoint

    Clears all conversation contexts and resets internal state
    """
    global conversation_contexts
    conversation_contexts.clear()
    reset()  # Call existing reset
    logger.info("White agent reset (A2A)")
    return {"status": "reset", "message": "All contexts cleared"}


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent_type": "white",
        "protocol": "a2a",
        "active_contexts": len(conversation_contexts)
    }


@app.get("/contexts")
def list_contexts():
    """List active conversation contexts (for debugging)"""
    return {
        "contexts": {
            ctx_id: {
                "step": ctx["step"],
                "task_id": ctx["task_id"],
                "tools_count": len(ctx.get("tools", [])),
                "osworld_server": ctx.get("osworld_server")
            }
            for ctx_id, ctx in conversation_contexts.items()
        }
    }


# Backward compatibility: Re-export original endpoints
# This allows the agent to work with both A2A and legacy interfaces

from .server import app as original_app

@app.post("/decide")
async def decide_endpoint(obs: Observation):
    """Backward compatibility endpoint - delegates to original decide()"""
    return decide(obs)


@app.post("/reset_legacy")
async def reset_legacy_endpoint():
    """Backward compatibility endpoint - delegates to original reset()"""
    return reset()
