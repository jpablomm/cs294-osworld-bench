#!/usr/bin/env python3
"""
White Agent - REST API Server (Unified Multi-Model)

FastAPI-based REST server for custom orchestrator integration.
Supports multiple model providers: GPT-4V, Claude, Qwen, etc.
"""

import logging
import os
import uuid
from typing import Dict, Any

from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

from white_agent.config import AgentConfig
from white_agent.agents import create_agent, BaseAgent
from white_agent.core import parse_observation, parse_actions, build_agent_url

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration from environment
config = AgentConfig.from_env()

# FastAPI app
app = FastAPI(
    title=f"White Agent (REST) - {config.agent_type}",
    description=f"Unified white agent server using {config.model}"
)

# Global agent instance (created via factory)
agent: BaseAgent = create_agent(config)

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


class AgentCardResponse(BaseModel):
    """Agent card for discovery"""
    name: str
    description: str
    url: str
    version: str
    agent_type: str
    model: str


@app.on_event("startup")
async def startup_event():
    """Startup - agent initializes lazily on first request"""
    logger.info(
        f"White Agent (REST) starting - type={config.agent_type}, model={config.model}"
    )
    logger.info("Agent will initialize on first request")


@app.get("/health")
def health():
    """Health check endpoint"""
    return {
        "status": "healthy" if agent.is_initialized else "initializing",
        "agent_type": config.agent_type,
        "protocol": "rest",
        "model": config.model,
        "agent_ready": agent.is_initialized,
        "active_contexts": len(conversation_contexts)
    }


@app.get("/status")
def status():
    """Status endpoint"""
    return {
        "status": "running" if agent.is_initialized else "initializing",
        "agent_type": config.agent_type,
        "model": config.model,
        "protocol": "rest"
    }


@app.get("/agent-card")
@app.get("/.well-known/agent-card.json")
def get_agent_card() -> AgentCardResponse:
    """Agent card for discovery"""
    model_descriptions = {
        "gpt4v": "GPT-4V vision-language model",
        "claude": "Claude vision-language model",
        "qwen": "Qwen VL vision-language model",
        "o3": "OpenAI O3 reasoning model",
        "gemini": "Google Gemini vision-language model",
    }
    model_desc = model_descriptions.get(config.agent_type, f"{config.agent_type} model")

    return AgentCardResponse(
        name=f"{config.agent_type.upper()} OSWorld Agent",
        description=f"White agent for desktop automation using {model_desc}",
        url=build_agent_url(),
        version="1.0.0",
        agent_type=config.agent_type,
        model=config.model
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
        agent.ensure_initialized()
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
        response, actions_str = agent.predict(instruction, obs_for_agent)

        # Parse actions
        if isinstance(actions_str, list):
            actions_str = actions_str[0] if actions_str else "DONE"
        action = parse_actions(actions_str)

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
                "raw_actions": actions_str
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
        agent.ensure_initialized()
    except Exception as e:
        return {"op": "error", "args": {"message": str(e)}}

    try:
        # Reset agent trajectory if requested (should be True for first step of new task)
        if obs.reset_before:
            agent.reset()
            logger.info(f"Agent trajectory reset before processing frame {obs.frame_id}")

        obs_for_agent = {"screenshot": obs.image_png_b64}  # Will need to decode
        if obs.accessibility_tree:
            obs_for_agent["accessibility_tree"] = obs.accessibility_tree

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

        response, actions_str = agent.predict(obs.instruction, obs_for_agent)

        if isinstance(actions_str, list):
            actions_str = actions_str[0] if actions_str else "DONE"

        return parse_actions(actions_str)

    except Exception as e:
        logger.error(f"Decide failed: {e}", exc_info=True)
        return {"op": "error", "args": {"message": str(e)}}


@app.post("/reset")
def reset():
    """Reset agent state"""
    global conversation_contexts
    agent.reset()
    conversation_contexts = {}
    logger.info("Agent reset")
    return {"status": "reset", "agent_type": config.agent_type}


@app.get("/debug/contexts")
def debug_contexts():
    """Debug endpoint to view conversation contexts"""
    return {
        "active_contexts": len(conversation_contexts),
        "agent_type": config.agent_type,
        "model": config.model,
        "contexts": {
            ctx_id: {
                "task_id": ctx["task_id"],
                "step": ctx["step"],
                "instruction": ctx["instruction"][:100] if ctx["instruction"] else None,
            }
            for ctx_id, ctx in conversation_contexts.items()
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "9002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
