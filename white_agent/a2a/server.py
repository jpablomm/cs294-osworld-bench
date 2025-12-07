#!/usr/bin/env python3
"""
White Agent - A2A Protocol Server (Unified Multi-Model)

Uses the a2a SDK (A2AStarletteApplication) for AgentBeats compliance.
Supports multiple model providers: GPT-4V, Claude, Qwen, etc.

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

from white_agent.config import AgentConfig
from white_agent.agents import create_agent, BaseAgent
from white_agent.core import parse_observation, parse_actions, build_agent_url

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def prepare_agent_card(url: str, config: AgentConfig) -> AgentCard:
    """Prepare A2A-compliant agent card based on configuration."""
    # Build agent name from config
    agent_name = f"{config.agent_type}_osworld_agent"

    # Build description based on agent type
    model_descriptions = {
        "gpt4v": "GPT-4V vision-language model",
        "claude": "Claude vision-language model",
        "qwen": "Qwen VL vision-language model",
        "o3": "OpenAI O3 reasoning model",
        "gemini": "Google Gemini vision-language model",
    }
    model_desc = model_descriptions.get(config.agent_type, f"{config.agent_type} model")

    skills = [
        AgentSkill(
            id="desktop-automation",
            name="Desktop Automation",
            description=f"Execute desktop automation actions (click, type, hotkey, scroll) using {model_desc}",
            tags=["automation", "desktop", "gui", "osworld", config.agent_type],
            examples=[],
        ),
        AgentSkill(
            id="vision-reasoning",
            name="Vision-Language Reasoning",
            description=f"Analyze screenshots and determine appropriate actions using {model_desc}",
            tags=["vision", config.agent_type, "reasoning", "screenshot"],
            examples=[],
        ),
    ]

    return AgentCard(
        name=agent_name,
        description=f"White agent for executing desktop automation tasks using {model_desc} ({config.model}). "
                    "Receives observations (screenshots, instructions) and returns actions for OSWorld workflows.",
        url=url,
        version="1.0.0",
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(),
        skills=skills,
    )


class UnifiedAgentExecutor(AgentExecutor):
    """
    A2A Agent executor supporting multiple model providers.

    Uses the agent factory to create the appropriate agent based on configuration.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.agent: BaseAgent = create_agent(config)
        self.ctx_id_to_history: Dict[str, list] = {}
        logger.info(
            f"UnifiedAgentExecutor initialized with {config.agent_type} "
            f"(model={config.model}, agent will be created on first use)"
        )

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute a task using the configured agent."""
        try:
            # Initialize agent on first use
            self.agent.ensure_initialized()

            # Reset agent trajectory if this is a new context (new task)
            # This prevents cross-task contamination where trajectory from
            # previous assessments would be included in the LLM prompt
            if context.context_id not in self.ctx_id_to_history:
                self.agent.reset()
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

                logger.info(f"Calling {self.config.agent_type} agent with instruction: {instruction[:80]}...")
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
        """Cancel a running task."""
        logger.info(f"Task cancelled: {context.context_id}")
        if context.context_id in self.ctx_id_to_history:
            del self.ctx_id_to_history[context.context_id]


# Backwards compatibility alias
GPT4VAgentExecutor = UnifiedAgentExecutor


def start_agent(host: str = "0.0.0.0", port: int = 8001, config: AgentConfig = None):
    """
    Start the white agent server using A2A SDK.

    Args:
        host: Host to bind to
        port: Port to listen on
        config: Agent configuration (defaults to AgentConfig.from_env())
    """
    # Load configuration from environment if not provided
    if config is None:
        config = AgentConfig.from_env()

    logger.info(f"Starting White Agent (A2A) on {host}:{port}")
    logger.info(f"Agent type: {config.agent_type}, Model: {config.model}")

    # Get agent URL from environment (set by AgentBeats controller)
    agent_url = os.getenv("AGENT_URL", f"http://{host}:{port}")
    logger.info(f"Agent URL: {agent_url}")

    # Create agent card
    card = prepare_agent_card(agent_url, config)

    # Create request handler with our executor
    request_handler = DefaultRequestHandler(
        agent_executor=UnifiedAgentExecutor(config),
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
