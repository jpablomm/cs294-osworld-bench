#!/usr/bin/env python3
"""
GPT-4V White Agent - A2A Protocol Server

Uses the a2a SDK (A2AStarletteApplication) for AgentBeats compliance.
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

from white_agent.core import GPT4VAgent, parse_observation, parse_actions, build_agent_url

load_dotenv()

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

    return AgentCard(
        name="gpt4v_osworld_agent",
        description="White agent for executing desktop automation tasks using GPT-4V vision-language model. "
                    "Receives observations (screenshots, instructions) and returns actions for OSWorld workflows.",
        url=url,
        version="1.0.0",
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(),
        skills=skills,
    )


class GPT4VAgentExecutor(AgentExecutor):
    """
    A2A Agent executor using GPT-4V (via shared core.GPT4VAgent).
    """

    def __init__(self):
        self.agent = GPT4VAgent()
        self.ctx_id_to_history: Dict[str, list] = {}
        logger.info("GPT4VAgentExecutor initialized (agent will be created on first use)")

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute a task using GPT-4V"""
        try:
            # Initialize agent on first use
            self.agent.ensure_initialized()

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

                # Build observation dict for PromptAgent
                obs_for_agent = {"screenshot": screenshot_bytes}
                if accessibility_tree:
                    obs_for_agent["accessibility_tree"] = accessibility_tree

                logger.info(f"Calling GPT-4V with instruction: {instruction[:80]}...")
                response, actions_str = self.agent.predict(instruction, obs_for_agent)

                # Parse actions
                if isinstance(actions_str, list):
                    actions_str = actions_str[0] if actions_str else "DONE"
                action = parse_actions(actions_str)

                # Build response
                result = {
                    "action": action,
                    "reasoning": response,
                    "raw_actions": actions_str,
                    "done": action.get("op") == "done" or "DONE" in actions_str
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
        """Cancel a running task"""
        logger.info(f"Task cancelled: {context.context_id}")
        if context.context_id in self.ctx_id_to_history:
            del self.ctx_id_to_history[context.context_id]


def start_agent(host: str = "0.0.0.0", port: int = 8001):
    """Start the white agent server using A2A SDK"""
    logger.info(f"Starting GPT-4V White Agent (A2A) on {host}:{port}")

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
