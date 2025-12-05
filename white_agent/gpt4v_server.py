#!/usr/bin/env python3
"""
GPT-4V White Agent with A2A Protocol
Wraps OSWorld's PromptAgent (GPT-4V) with AgentBeats A2A protocol
"""

import base64
import json
import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Dict, Any
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add vendor/OSWorld to path
sys.path.insert(0, str(Path(__file__).parent.parent / "vendor" / "OSWorld"))

from mm_agents.agent import PromptAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="GPT-4V White Agent with A2A")

# Global PromptAgent instance
agent: PromptAgent = None

# Conversation contexts (task_id -> context)
conversation_contexts: Dict[str, Dict[str, Any]] = {}


# A2A Protocol Models
class A2ATask(BaseModel):
    """A2A Task Model"""
    task_id: str
    context_id: str | None = None
    message: str
    metadata: Dict[str, Any] | None = None


class A2AMessage(BaseModel):
    """A2A Message Model"""
    message_id: str
    task_id: str
    context_id: str | None = None
    role: str
    content: str
    metadata: Dict[str, Any] | None = None


class AgentCard(BaseModel):
    """Agent Card for self-description"""
    name: str
    version: str
    description: str
    protocols: list[str]
    capabilities: list[str]
    metadata: Dict[str, Any] | None = None


def initialize_agent(model: str = "gpt-4o", temperature: float = 1.0, observation_type: str = "screenshot"):
    """Initialize GPT-4V PromptAgent

    Args:
        model: LLM model to use
        temperature: Sampling temperature
        observation_type: One of "screenshot", "a11y_tree", "screenshot_a11y_tree"
    """
    global agent

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    logger.info(f"Initializing PromptAgent with model={model}, temperature={temperature}, observation_type={observation_type}")
    agent = PromptAgent(
        model=model,
        observation_type=observation_type,
        action_space="pyautogui",
        max_tokens=1500,
        temperature=temperature,
        top_p=0.9
    )
    logger.info("✓ PromptAgent initialized")


@app.on_event("startup")
async def startup_event():
    """Initialize agent on startup"""
    try:
        model = os.environ.get("GPT4V_MODEL", "gpt-4o")
        temperature = float(os.environ.get("GPT4V_TEMPERATURE", "1.0"))
        # Support screenshot_a11y_tree mode via OSWORLD_OBS_TYPE env var
        observation_type = os.environ.get("OSWORLD_OBS_TYPE", "screenshot")
        initialize_agent(model=model, temperature=temperature, observation_type=observation_type)
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        logger.warning("Agent will need to be initialized via API call")


@app.get("/health")
def health():
    """Health check endpoint"""
    agent_ready = agent is not None
    return {
        "status": "healthy" if agent_ready else "initializing",
        "agent_type": "white",
        "protocol": "a2a",
        "model": "gpt-4v",
        "agent_ready": agent_ready,
        "active_contexts": len(conversation_contexts)
    }


@app.get("/agent-card")
def get_agent_card() -> AgentCard:
    """Return agent card describing capabilities"""
    return AgentCard(
        name="GPT-4V OSWorld Task Executor",
        version="1.0.0",
        description="Vision-language model for desktop automation using OSWorld",
        protocols=["a2a", "rest"],
        capabilities=[
            "desktop-automation",
            "vision-language-reasoning",
            "screen-observation",
            "mouse-control",
            "keyboard-control",
            "task-execution",
            "gpt-4v-powered"
        ],
        metadata={
            "model": os.environ.get("GPT4V_MODEL", "gpt-4o"),
            "action_space": "pyautogui",
            "observation_type": "screenshot"
        }
    )


@app.post("/task")
def handle_task(task: A2ATask) -> A2AMessage:
    """
    Handle A2A task - receives observation, returns action

    Expected task.metadata format:
    {
        "observation": {
            "frame_id": int,
            "image_png_b64": str,  # Base64 encoded PNG
            "instruction": str,
            "done": bool
        },
        "osworld_server": str  # Optional - OSWorld server URL
    }
    """
    if not agent:
        return A2AMessage(
            message_id=str(uuid.uuid4()),
            task_id=task.task_id,
            context_id=task.context_id or task.task_id,
            role="agent",
            content="Agent not initialized - OPENAI_API_KEY required",
            metadata={"status": "error", "error": "agent_not_initialized"}
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
        logger.info(f"New conversation context: {context_id}")

    context = conversation_contexts[context_id]
    step = context["step"]

    # Parse observation from task
    try:
        observation = _parse_observation(task)
        instruction = observation["instruction"]
        screenshot_bytes = observation["screenshot"]
        accessibility_tree = observation.get("accessibility_tree")  # XML string or None
        is_done = observation.get("done", False)

        # Store instruction on first step
        if context["instruction"] is None:
            context["instruction"] = instruction

        logger.info(f"Step {step}: Processing observation for task '{instruction[:80]}...'")
        if accessibility_tree:
            logger.info(f"Accessibility tree included ({len(accessibility_tree)} chars)")

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

    # Get action from GPT-4V
    try:
        logger.info(f"Calling GPT-4V PromptAgent...")
        # Build observation dict for PromptAgent
        obs_for_agent = {"screenshot": screenshot_bytes}
        if accessibility_tree:
            obs_for_agent["accessibility_tree"] = accessibility_tree
        response, actions_str = agent.predict(
            instruction,
            obs_for_agent
        )

        logger.info(f"GPT-4V response: {response[:150]}..." if len(response) > 150 else f"GPT-4V response: {response}")
        logger.info(f"GPT-4V actions: {actions_str}")

        # Parse actions into OSWorld format
        # Handle both string and list returns from PromptAgent
        if isinstance(actions_str, list):
            actions_str = actions_str[0] if actions_str else "DONE"
        action = _parse_actions(actions_str)
        logger.info(f"Parsed action: {action}")

        # Update context
        context["step"] += 1
        context["history"].append({
            "step": step,
            "response": response,
            "action": action
        })

        # Check if done
        task_done = action.get("op") == "done" or is_done or "DONE" in actions_str

        if task_done:
            logger.info(f"Task {task.task_id} completed after {step + 1} steps")
            del conversation_contexts[context_id]

        # Return A2A message
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
                "gpt4v_response": response,
                "raw_actions": actions_str
            }
        )

    except Exception as e:
        error_msg = f"GPT-4V prediction failed: {e}"
        logger.error(error_msg, exc_info=True)
        return A2AMessage(
            message_id=str(uuid.uuid4()),
            task_id=task.task_id,
            context_id=context_id,
            role="agent",
            content=error_msg,
            metadata={"status": "error", "error": str(e)}
        )


@app.post("/reset")
def reset():
    """Reset agent state and clear all conversation contexts"""
    global conversation_contexts
    if agent:
        agent.reset()
    conversation_contexts = {}
    logger.info("Agent reset - all contexts cleared")
    return {"status": "reset", "contexts_cleared": len(conversation_contexts)}


def _parse_observation(task: A2ATask) -> Dict[str, Any]:
    """Parse observation from A2A task"""
    if not task.metadata or "observation" not in task.metadata:
        raise ValueError("Task must have observation in metadata")

    obs_data = task.metadata["observation"]

    # Decode base64 screenshot
    image_b64 = obs_data.get("image_png_b64", "")
    if not image_b64:
        raise ValueError("Observation must have image_png_b64")

    screenshot_bytes = base64.b64decode(image_b64)

    result = {
        "frame_id": obs_data.get("frame_id", 0),
        "screenshot": screenshot_bytes,
        "instruction": obs_data.get("instruction", task.message),
        "done": obs_data.get("done", False)
    }

    # Include accessibility tree if provided (XML string from OSWorld)
    if "accessibility_tree" in obs_data and obs_data["accessibility_tree"]:
        result["accessibility_tree"] = obs_data["accessibility_tree"]

    return result


def _parse_actions(actions_str: str) -> Dict[str, Any]:
    """
    Parse pyautogui action string into OSWorld action format

    Converts from:
        "pyautogui.click(100, 200)"
    To:
        {"op": "click", "args": {"x": 100, "y": 200}}

    Also handles JSON format returned by GPT-4o:
        '{"op": "click", "args": {"x": 100, "y": 200}}'

    Handles multi-line code blocks by extracting the first pyautogui command.
    """
    actions_str = actions_str.strip()

    # Check for JSON format (GPT-4o sometimes returns this)
    if actions_str.startswith('{') and actions_str.endswith('}'):
        try:
            action_dict = json.loads(actions_str)
            if "op" in action_dict:
                # Handle screenshot action (convert to wait since screenshots are automatic)
                if action_dict["op"] == "screenshot":
                    logger.info("GPT-4V requested screenshot - converting to wait (screenshots are automatic)")
                    return {"op": "wait", "args": {"duration": 0.5}}
                # Already in correct format
                return action_dict
        except json.JSONDecodeError:
            pass  # Fall through to other parsers

    # Check for DONE
    if "DONE" in actions_str or "FAIL" in actions_str:
        return {"op": "done", "args": {}}

    # Extract first command from multi-line code blocks
    if '\n' in actions_str or 'import' in actions_str:
        lines = actions_str.split('\n')
        for line in lines:
            line = line.strip()
            # Skip empty lines, imports, and comments
            if not line or line.startswith('#') or line.startswith('import') or line.startswith('time.'):
                continue
            # Found a command - use it (with or without pyautogui prefix)
            if line.startswith('pyautogui.') or any(line.startswith(f'{cmd}(') for cmd in ['click', 'type_text', 'hotkey', 'scroll', 'doubleClick', 'rightClick']):
                actions_str = line
                break
        else:
            # No command found
            logger.warning(f"No command found in code block, defaulting to wait")
            return {"op": "wait", "args": {"duration": 1.0}}

    # Strip comments from action string
    if '#' in actions_str:
        actions_str = actions_str.split('#')[0].strip()

    # Parse move actions
    if match := re.match(r'pyautogui\.moveRel\((-?\d+),\s*(-?\d+)\)', actions_str):
        # moveRel is relative movement - for now, treat as wait since OSWorld API doesn't have mouse_move_relative
        logger.info("moveRel detected - treating as wait since OSWorld doesn't support relative movement")
        return {"op": "wait", "args": {"duration": 0.5}}

    # Parse click actions (with or without pyautogui prefix)
    if match := re.match(r'(?:pyautogui\.)?click\((?:x=)?(\d+),\s*(?:y=)?(\d+)\)', actions_str):
        x, y = int(match.group(1)), int(match.group(2))
        return {"op": "click", "args": {"x": x, "y": y}}

    if match := re.match(r'(?:pyautogui\.)?click\(\)', actions_str):
        return {"op": "click", "args": {}}

    # Parse double click
    if match := re.match(r'(?:pyautogui\.)?doubleClick\((?:x=)?(\d+),\s*(?:y=)?(\d+)\)', actions_str):
        x, y = int(match.group(1)), int(match.group(2))
        return {"op": "double_click", "args": {"x": x, "y": y}}

    # Parse right click
    if match := re.match(r'(?:pyautogui\.)?rightClick\((?:x=)?(\d+),\s*(?:y=)?(\d+)\)', actions_str):
        x, y = int(match.group(1)), int(match.group(2))
        return {"op": "right_click", "args": {"x": x, "y": y}}

    # Parse type/write actions
    if match := re.match(r'(?:pyautogui\.)?(?:typewrite|write|type_text)\(["\'](.+?)["\']\)', actions_str):
        text = match.group(1)
        return {"op": "type", "args": {"text": text}}

    # Parse hotkey actions
    if match := re.match(r'(?:pyautogui\.)?hotkey\(["\'](.+?)["\'],\s*["\'](.+?)["\']\)', actions_str):
        key1, key2 = match.group(1), match.group(2)
        return {"op": "hotkey", "args": {"keys": [key1, key2]}}

    # Parse hotkey with array syntax: hotkey(['super']) or hotkey(['ctrl', 'c'])
    if match := re.match(r'(?:pyautogui\.)?hotkey\(\[([^\]]+)\]\)', actions_str):
        keys_str = match.group(1)
        keys = [k.strip().strip("'\"") for k in keys_str.split(',')]
        return {"op": "hotkey", "args": {"keys": keys}}

    # Parse press actions (handles both simple and with presses parameter)
    if match := re.match(r'(?:pyautogui\.)?press\(["\'](.+?)["\'](?:,\s*presses=\d+)?(?:,\s*interval=[\d.]+)?\)', actions_str):
        key = match.group(1)
        return {"op": "hotkey", "args": {"keys": [key]}}

    # Parse scroll
    if match := re.match(r'(?:pyautogui\.)?scroll\((-?\d+)\)', actions_str):
        amount = int(match.group(1))
        return {"op": "scroll", "args": {"amount": amount}}

    # Default: wait
    logger.warning(f"Unknown action format: {actions_str}, defaulting to wait")
    return {"op": "wait", "args": {"duration": 1.0}}


@app.get("/debug/contexts")
def debug_contexts():
    """Debug endpoint to view conversation contexts"""
    return {
        "active_contexts": len(conversation_contexts),
        "contexts": {
            ctx_id: {
                "task_id": ctx["task_id"],
                "step": ctx["step"],
                "instruction": ctx["instruction"][:100] if ctx["instruction"] else None,
                "history_length": len(ctx["history"])
            }
            for ctx_id, ctx in conversation_contexts.items()
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "9002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
