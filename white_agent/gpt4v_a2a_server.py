#!/usr/bin/env python3
"""
GPT-4V White Agent with A2A Protocol (SDK-based)

Uses the a2a SDK directly for proper AgentBeats compliance.
Based on: https://github.com/agentbeats/agentify-example-tau-bench
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

import uvicorn
from dotenv import load_dotenv

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentSkill, AgentCard, AgentCapabilities
from a2a.utils import new_agent_text_message

# Load environment variables
load_dotenv()

# Add vendor/OSWorld to path
sys.path.insert(0, str(Path(__file__).parent.parent / "vendor" / "OSWorld"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def prepare_agent_card(url: str) -> AgentCard:
    """Prepare A2A-compliant agent card"""
    skills = [
        AgentSkill(
            id="desktop-automation",
            name="Desktop Automation",
            description="Execute desktop automation actions (click, type, hotkey, scroll) using GPT-4V vision",
            tags=["automation", "desktop", "gui", "osworld", "gpt-4v"],
            examples=[],
        ),
        AgentSkill(
            id="vision-reasoning",
            name="Vision-Language Reasoning",
            description="Analyze screenshots and determine appropriate actions using GPT-4V",
            tags=["vision", "gpt-4v", "reasoning", "screenshot"],
            examples=[],
        ),
    ]

    card = AgentCard(
        name="gpt4v_osworld_agent",
        description="White agent for executing desktop automation tasks using GPT-4V vision-language model. Receives observations (screenshots, instructions) and returns actions for OSWorld assessment workflows.",
        url=url,
        version="1.0.0",
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(),
        skills=skills,
    )
    return card


class GPT4VAgentExecutor(AgentExecutor):
    """
    Agent executor that uses GPT-4V (via OSWorld's PromptAgent) to process
    observations and return actions.
    """

    def __init__(self):
        self.agent = None
        self.ctx_id_to_history: Dict[str, list] = {}
        logger.info("GPT4VAgentExecutor initialized (agent will be created on first use)")

    def _ensure_agent_initialized(self):
        """Lazily initialize PromptAgent on first use"""
        if self.agent is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")

            # Lazy import to avoid blocking subprocess startup
            from mm_agents.agent import PromptAgent

            model = os.environ.get("GPT4V_MODEL", "gpt-4o")
            temperature = float(os.environ.get("GPT4V_TEMPERATURE", "1.0"))
            observation_type = os.environ.get("OSWORLD_OBS_TYPE", "screenshot")

            logger.info(f"Initializing PromptAgent with model={model}, temperature={temperature}")
            self.agent = PromptAgent(
                model=model,
                observation_type=observation_type,
                action_space="pyautogui",
                max_tokens=1500,
                temperature=temperature,
                top_p=0.9
            )
            logger.info("PromptAgent initialized successfully")

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute a task using GPT-4V"""
        try:
            # Initialize agent on first use
            self._ensure_agent_initialized()

            # Get user input (the task message)
            user_input = context.get_user_input()
            logger.info(f"Received task: {user_input[:100]}..." if len(user_input) > 100 else f"Received task: {user_input}")

            # Try to parse as JSON (for structured observation format)
            try:
                task_data = json.loads(user_input)
                observation = self._parse_observation(task_data)
            except json.JSONDecodeError:
                # Plain text instruction - no screenshot
                observation = None
                instruction = user_input

            if observation:
                instruction = observation["instruction"]
                screenshot_bytes = observation["screenshot"]
                accessibility_tree = observation.get("accessibility_tree")

                # Build observation dict for PromptAgent
                obs_for_agent = {"screenshot": screenshot_bytes}
                if accessibility_tree:
                    obs_for_agent["accessibility_tree"] = accessibility_tree

                logger.info(f"Calling GPT-4V with instruction: {instruction[:80]}...")
                response, actions_str = self.agent.predict(instruction, obs_for_agent)

                # Parse actions
                if isinstance(actions_str, list):
                    actions_str = actions_str[0] if actions_str else "DONE"
                action = self._parse_actions(actions_str)

                # Build response
                result = {
                    "action": action,
                    "reasoning": response,
                    "raw_actions": actions_str,
                    "done": action.get("op") == "done" or "DONE" in actions_str
                }
                response_text = json.dumps(result)
            else:
                # No observation - just respond with text
                response_text = f"Received instruction: {instruction}. Please provide an observation (screenshot) to proceed."

            # Send response through event queue
            await event_queue.enqueue_event(
                new_agent_text_message(
                    response_text,
                    context_id=context.context_id
                )
            )

        except Exception as e:
            logger.error(f"Error executing task: {e}", exc_info=True)
            error_response = json.dumps({
                "error": str(e),
                "status": "failed"
            })
            await event_queue.enqueue_event(
                new_agent_text_message(
                    error_response,
                    context_id=context.context_id
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel a running task"""
        logger.info(f"Task cancelled: {context.context_id}")
        # Clean up any state for this context
        if context.context_id in self.ctx_id_to_history:
            del self.ctx_id_to_history[context.context_id]

    def _parse_observation(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse observation from task data"""
        # Support both nested and flat formats
        if "observation" in task_data:
            obs_data = task_data["observation"]
        else:
            obs_data = task_data

        # Decode base64 screenshot
        image_b64 = obs_data.get("image_png_b64", "")
        if not image_b64:
            return None

        screenshot_bytes = base64.b64decode(image_b64)

        result = {
            "frame_id": obs_data.get("frame_id", 0),
            "screenshot": screenshot_bytes,
            "instruction": obs_data.get("instruction", obs_data.get("message", "")),
            "done": obs_data.get("done", False)
        }

        # Include accessibility tree if provided
        if "accessibility_tree" in obs_data and obs_data["accessibility_tree"]:
            result["accessibility_tree"] = obs_data["accessibility_tree"]

        return result

    def _parse_actions(self, actions_str: str) -> Dict[str, Any]:
        """Parse pyautogui action string into OSWorld action format"""
        actions_str = actions_str.strip()

        # Check for JSON format
        if actions_str.startswith('{') and actions_str.endswith('}'):
            try:
                action_dict = json.loads(actions_str)
                if "op" in action_dict:
                    if action_dict["op"] == "screenshot":
                        return {"op": "wait", "args": {"duration": 0.5}}
                    return action_dict
            except json.JSONDecodeError:
                pass

        # Check for DONE/FAIL
        if "DONE" in actions_str or "FAIL" in actions_str:
            return {"op": "done", "args": {}}

        # Extract first command from multi-line code blocks
        if '\n' in actions_str or 'import' in actions_str:
            lines = actions_str.split('\n')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('import') or line.startswith('time.'):
                    continue
                if line.startswith('pyautogui.') or any(line.startswith(f'{cmd}(') for cmd in ['click', 'type_text', 'hotkey', 'scroll', 'doubleClick', 'rightClick']):
                    actions_str = line
                    break
            else:
                return {"op": "wait", "args": {"duration": 1.0}}

        # Strip comments
        if '#' in actions_str:
            actions_str = actions_str.split('#')[0].strip()

        # Parse click actions
        if match := re.match(r'(?:pyautogui\.)?click\((?:x=)?(\d+),\s*(?:y=)?(\d+)\)', actions_str):
            return {"op": "click", "args": {"x": int(match.group(1)), "y": int(match.group(2))}}

        if match := re.match(r'(?:pyautogui\.)?click\(\)', actions_str):
            return {"op": "click", "args": {}}

        # Parse double click
        if match := re.match(r'(?:pyautogui\.)?doubleClick\((?:x=)?(\d+),\s*(?:y=)?(\d+)\)', actions_str):
            return {"op": "double_click", "args": {"x": int(match.group(1)), "y": int(match.group(2))}}

        # Parse right click
        if match := re.match(r'(?:pyautogui\.)?rightClick\((?:x=)?(\d+),\s*(?:y=)?(\d+)\)', actions_str):
            return {"op": "right_click", "args": {"x": int(match.group(1)), "y": int(match.group(2))}}

        # Parse type/write actions
        if match := re.match(r'(?:pyautogui\.)?(?:typewrite|write|type_text)\(["\'](.+?)["\']\)', actions_str):
            return {"op": "type", "args": {"text": match.group(1)}}

        # Parse hotkey actions
        if match := re.match(r'(?:pyautogui\.)?hotkey\(["\'](.+?)["\'],\s*["\'](.+?)["\']\)', actions_str):
            return {"op": "hotkey", "args": {"keys": [match.group(1), match.group(2)]}}

        # Parse hotkey with array syntax
        if match := re.match(r'(?:pyautogui\.)?hotkey\(\[([^\]]+)\]\)', actions_str):
            keys = [k.strip().strip("'\"") for k in match.group(1).split(',')]
            return {"op": "hotkey", "args": {"keys": keys}}

        # Parse press actions
        if match := re.match(r'(?:pyautogui\.)?press\(["\'](.+?)["\']', actions_str):
            return {"op": "hotkey", "args": {"keys": [match.group(1)]}}

        # Parse scroll
        if match := re.match(r'(?:pyautogui\.)?scroll\((-?\d+)\)', actions_str):
            return {"op": "scroll", "args": {"amount": int(match.group(1))}}

        # Default: wait
        logger.warning(f"Unknown action format: {actions_str}, defaulting to wait")
        return {"op": "wait", "args": {"duration": 1.0}}


def start_agent(host: str = "0.0.0.0", port: int = 8001):
    """Start the white agent server"""
    logger.info(f"Starting GPT-4V White Agent on {host}:{port}")

    # Get agent URL from environment (set by AgentBeats controller)
    agent_url = os.getenv("AGENT_URL", f"http://{host}:{port}")
    logger.info(f"Agent URL: {agent_url}")

    # Create agent card
    card = prepare_agent_card(agent_url)

    # Create request handler with our executor
    request_handler = DefaultRequestHandler(
        agent_executor=GPT4VAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    # Create A2A application
    a2a_app = A2AStarletteApplication(
        agent_card=card,
        http_handler=request_handler,
    )

    # Run the server
    uvicorn.run(a2a_app.build(), host=host, port=port)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("AGENT_PORT", os.environ.get("PORT", "8001")))
    start_agent(host=host, port=port)
