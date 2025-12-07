"""
Base Agent Abstract Class.

Defines the common interface for all white agent implementations.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from ..config import AgentConfig

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all white agent implementations.

    All agent types (GPT-4V, Claude, Qwen, etc.) must implement this interface
    to ensure compatibility with the A2A and REST servers.
    """

    def __init__(self, config: AgentConfig):
        """
        Initialize the agent with configuration.

        Args:
            config: Agent configuration including model, API keys, and parameters
        """
        self.config = config
        self._initialized = False

        # Trajectory history (shared across all agents)
        self.thoughts: List[str] = []
        self.actions: List[str] = []
        self.observations: List[Dict[str, Any]] = []

    @property
    def is_initialized(self) -> bool:
        """Check if the agent has been initialized."""
        return self._initialized

    @property
    def model_name(self) -> str:
        """Get the model name for logging/display."""
        return self.config.model

    @property
    def agent_type(self) -> str:
        """Get the agent type for logging/display."""
        return self.config.agent_type

    @abstractmethod
    def ensure_initialized(self) -> None:
        """
        Lazily initialize the agent on first use.

        This allows the agent to be created without blocking on API client
        initialization, which is important for subprocess contexts.

        Implementations should:
        1. Check if already initialized
        2. Validate API key availability
        3. Initialize the underlying model client
        4. Set self._initialized = True
        """
        pass

    @abstractmethod
    def predict(
        self,
        instruction: str,
        observation: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Get action prediction from the model.

        Args:
            instruction: Task instruction/goal
            observation: Dictionary containing:
                - screenshot: bytes (PNG image data)
                - accessibility_tree: str (optional, XML a11y tree)

        Returns:
            Tuple of (reasoning_response, action_string)
            - reasoning_response: Model's reasoning/thought process
            - action_string: Action to execute (pyautogui format or JSON)
        """
        pass

    def reset(self) -> None:
        """
        Reset agent state for a new task.

        Clears trajectory history. Subclasses may override to perform
        additional cleanup (e.g., resetting conversation history).
        """
        self.thoughts.clear()
        self.actions.clear()
        self.observations.clear()
        logger.info(f"Agent {self.agent_type} reset")

    def add_to_history(
        self,
        thought: Optional[str] = None,
        action: Optional[str] = None,
        observation: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an entry to the trajectory history.

        Args:
            thought: Model's reasoning for this step
            action: Action taken
            observation: Observation received
        """
        if thought is not None:
            self.thoughts.append(thought)
        if action is not None:
            self.actions.append(action)
        if observation is not None:
            self.observations.append(observation)

    def get_trajectory_context(self) -> List[Dict[str, Any]]:
        """
        Get recent trajectory for context.

        Returns the last N steps based on max_trajectory_length config.
        """
        max_len = self.config.max_trajectory_length
        trajectory = []

        # Zip together thoughts, actions, observations
        for i in range(len(self.actions)):
            step = {
                "step": i + 1,
                "action": self.actions[i] if i < len(self.actions) else None,
                "thought": self.thoughts[i] if i < len(self.thoughts) else None,
            }
            trajectory.append(step)

        # Return last N steps
        return trajectory[-max_len:] if max_len > 0 else trajectory

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"model={self.config.model}, "
            f"initialized={self._initialized})"
        )
