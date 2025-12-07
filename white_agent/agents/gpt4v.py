"""
GPT-4V Agent Implementation.

Wraps OpenAI's GPT-4V/GPT-4o models for OSWorld tasks.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

from .base import BaseAgent
from ..config import AgentConfig

# Add vendor/OSWorld to path for PromptAgent
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "vendor" / "OSWorld"))

logger = logging.getLogger(__name__)


class GPT4VAgent(BaseAgent):
    """
    GPT-4V/GPT-4o agent for OSWorld tasks.

    Uses OSWorld's PromptAgent under the hood for compatibility
    with existing action/observation formats.
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._agent = None

    def ensure_initialized(self) -> None:
        """Initialize the PromptAgent on first use."""
        if self._initialized:
            return

        # Validate API key
        api_key = self.config.get_api_key()

        # Set environment variable for PromptAgent
        os.environ["OPENAI_API_KEY"] = api_key

        # Lazy import to avoid blocking subprocess startup
        from mm_agents.agent import PromptAgent

        logger.info(
            f"Initializing GPT4VAgent with model={self.config.model}, "
            f"temperature={self.config.temperature}, "
            f"observation_type={self.config.observation_type}"
        )

        self._agent = PromptAgent(
            model=self.config.model,
            observation_type=self.config.observation_type,
            action_space=self.config.action_space,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            max_trajectory_length=self.config.max_trajectory_length,
        )

        self._initialized = True
        logger.info("GPT4VAgent initialized successfully")

    def predict(
        self,
        instruction: str,
        observation: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Get action prediction from GPT-4V.

        Args:
            instruction: Task instruction
            observation: Dict with 'screenshot' (bytes) and optionally 'accessibility_tree' (str)

        Returns:
            Tuple of (reasoning_response, action_string)
        """
        self.ensure_initialized()

        # Call the underlying PromptAgent
        response, actions = self._agent.predict(instruction, observation)

        # Add to history
        self.add_to_history(thought=response, action=actions)

        return response, actions

    def reset(self) -> None:
        """Reset agent state."""
        super().reset()
        if self._agent is not None:
            self._agent.reset()
