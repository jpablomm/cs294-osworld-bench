#!/usr/bin/env python3
"""
White Agent - A2A Protocol Server

Uses the a2a SDK (A2AStarletteApplication) for AgentBeats compliance.
Directly uses PromptAgent for multi-model support (GPT-4V, Claude, Gemini, Qwen, etc.)

Based on: https://github.com/agentbeats/agentify-example-tau-bench
"""

import json
import logging
import os
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

from white_agent.prompt_agent import PromptAgent
from white_agent.core import parse_observation, parse_actions

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment
MODEL = os.environ.get("MODEL", os.environ.get("GPT5_MODEL", "gpt-5.1"))
TEMPERATURE = float(os.environ.get("TEMPERATURE", os.environ.get("GPT4V_TEMPERATURE", "1.0")))
OBSERVATION_TYPE = os.environ.get("OSWORLD_OBS_TYPE", "screenshot_a11y_tree")
ACTION_SPACE = os.environ.get("ACTION_SPACE", "pyautogui")
MAX_TRAJECTORY_LENGTH = int(os.environ.get("MAX_TRAJECTORY_LENGTH", "3"))
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "1500"))
TOP_P = float(os.environ.get("TOP_P", "0.9"))


def prepare_agent_card(url: str, model: str) -> AgentCard:
    """Prepare A2A-compliant agent card."""
    skills = [
        AgentSkill(
            id="desktop-automation",
            name="Desktop Automation",
            description=f"Execute desktop automation actions (click, type, hotkey, scroll) using {model}",
            tags=["automation", "desktop", "gui", "osworld"],
            examples=[],
        ),
        AgentSkill(
            id="vision-reasoning",
            name="Vision-Language Reasoning",
            description=f"Analyze screenshots and determine appropriate actions using {model}",
            tags=["vision", "reasoning", "screenshot"],
            examples=[],
        ),
    ]

    return AgentCard(
        name=f"osworld_agent_{model.replace('-', '_')}",
        description=f"White agent for executing desktop automation tasks using {model}. "
                    "Receives observations (screenshots, instructions) and returns actions for OSWorld workflows.",
        url=url,
        version="2.0.0",
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(),
        skills=skills,
    )


class PromptAgentExecutor(AgentExecutor):
    """
    A2A Agent executor using PromptAgent directly.

    Supports all models that PromptAgent supports (GPT-4V, Claude, Gemini, Qwen, etc.)
    """

    def __init__(self):
        self.agent: PromptAgent | None = None
        self.ctx_id_to_history: Dict[str, list] = {}
        logger.info(
            f"PromptAgentExecutor initialized "
            f"(model={MODEL}, obs_type={OBSERVATION_TYPE}, agent will be created on first use)"
        )

    def _get_agent(self) -> PromptAgent:
        """Get or create the PromptAgent instance."""
        if self.agent is None:
            logger.info(f"Creating PromptAgent: model={MODEL}, obs_type={OBSERVATION_TYPE}")
            self.agent = PromptAgent(
                model=MODEL,
                temperature=TEMPERATURE,
                observation_type=OBSERVATION_TYPE,
                action_space=ACTION_SPACE,
                max_trajectory_length=MAX_TRAJECTORY_LENGTH,
                max_tokens=MAX_TOKENS,
                top_p=TOP_P,
            )
            logger.info("PromptAgent created successfully")
        return self.agent

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute a task using PromptAgent."""
        try:
            agent = self._get_agent()

            # Reset agent trajectory if this is a new context (new task)
            # This prevents cross-task contamination where trajectory from
            # previous assessments would be included in the LLM prompt
            if context.context_id not in self.ctx_id_to_history:
                agent.reset()
                self.ctx_id_to_history[context.context_id] = []
                logger.info(f"Reset agent trajectory for new context: {context.context_id}")

            # Get user input (the task message)
            user_input = context.get_user_input()
            logger.info(f"Received task: {user_input[:100]}..." if len(user_input) > 100 else f"Received task: {user_input}")

            # Try to parse as JSON (for structured observation format)
            try:
                task_data = json.loads(user_input)
                observation = parse_observation(task_data)
            except json.JSONDecodeError:
                # Plain text instruction - no screenshot
                observation = None
                instruction = user_input

            if observation:
                instruction = observation["instruction"]
                screenshot_bytes = observation["screenshot"]
                accessibility_tree = observation.get("accessibility_tree")

                # Build observation dict for agent
                obs_for_agent = {"screenshot": screenshot_bytes}
                if accessibility_tree:
                    obs_for_agent["accessibility_tree"] = accessibility_tree

                # Log trajectory state before prediction (for debugging)
                traj_len = len(agent.observations)
                max_traj = agent.max_trajectory_length
                logger.info(
                    f"Trajectory state: {traj_len} steps in history, "
                    f"sending last {min(traj_len, max_traj)} to LLM"
                )

                logger.info(f"Calling PromptAgent ({MODEL}) with instruction: {instruction[:80]}...")
                response, actions = agent.predict(instruction, obs_for_agent)

                # Parse actions
                if isinstance(actions, list):
                    actions_str = actions[0] if actions else "DONE"
                else:
                    actions_str = actions
                action = parse_actions(actions_str)

                # Build response
                result = {
                    "action": action,
                    "reasoning": response,
                    "raw_actions": actions_str,
                    "done": action.get("op") == "done" or "DONE" in str(actions_str)
                }
                response_text = json.dumps(result)
            else:
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
        """Cancel a running task."""
        logger.info(f"Task cancelled: {context.context_id}")
        if context.context_id in self.ctx_id_to_history:
            del self.ctx_id_to_history[context.context_id]


# Backwards compatibility aliases
UnifiedAgentExecutor = PromptAgentExecutor
GPT4VAgentExecutor = PromptAgentExecutor


def start_agent(host: str = "0.0.0.0", port: int = 8001):
    """
    Start the white agent server using A2A SDK.

    Args:
        host: Host to bind to
        port: Port to listen on
    """
    logger.info(f"Starting White Agent (A2A) on {host}:{port}")
    logger.info(f"Model: {MODEL}, Observation type: {OBSERVATION_TYPE}")

    # Get agent URL from environment (set by AgentBeats controller)
    agent_url = os.getenv("AGENT_URL", f"http://{host}:{port}")
    logger.info(f"Agent URL: {agent_url}")

    # Create agent card
    card = prepare_agent_card(agent_url, MODEL)

    # Create request handler with our executor
    request_handler = DefaultRequestHandler(
        agent_executor=PromptAgentExecutor(),
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
