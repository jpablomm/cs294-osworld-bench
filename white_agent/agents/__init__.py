"""
White Agent Implementations.

Provides unified access to different model providers (GPT-4V, Claude, Qwen, etc.)
through a common factory pattern.
"""

import logging
from typing import Type

from .base import BaseAgent
from .gpt4v import GPT4VAgent
from .claude import ClaudeAgent
from .qwen import QwenAgent
from ..config import AgentConfig, AgentType

logger = logging.getLogger(__name__)

# Registry of agent implementations
AGENT_REGISTRY: dict[str, Type[BaseAgent]] = {
    AgentType.GPT4V: GPT4VAgent,
    AgentType.O3: GPT4VAgent,  # O3 uses same wrapper with different model
    AgentType.CLAUDE: ClaudeAgent,
    AgentType.QWEN: QwenAgent,
}


def create_agent(config: AgentConfig) -> BaseAgent:
    """
    Create an agent instance based on configuration.

    This is the main factory function for creating white agents.
    It routes to the appropriate implementation based on agent_type.

    Args:
        config: Agent configuration specifying type, model, and parameters

    Returns:
        BaseAgent instance ready for use

    Raises:
        ValueError: If agent type is not supported

    Example:
        >>> config = AgentConfig.from_env()
        >>> agent = create_agent(config)
        >>> reasoning, action = agent.predict(instruction, observation)
    """
    agent_type = config.agent_type

    # Get agent class from registry
    agent_class = AGENT_REGISTRY.get(agent_type)
    if agent_class is None:
        supported = ", ".join(AGENT_REGISTRY.keys())
        raise ValueError(
            f"Unsupported agent type: {agent_type}. "
            f"Supported types: {supported}"
        )

    logger.info(f"Creating agent: type={agent_type}, model={config.model}")
    return agent_class(config)


def get_supported_agents() -> list[str]:
    """Get list of supported agent types."""
    return list(AGENT_REGISTRY.keys())


def register_agent(agent_type: str, agent_class: Type[BaseAgent]) -> None:
    """
    Register a custom agent implementation.

    Args:
        agent_type: Unique identifier for the agent type
        agent_class: Agent class implementing BaseAgent

    Example:
        >>> from white_agent.agents import register_agent, BaseAgent
        >>> class MyCustomAgent(BaseAgent):
        ...     pass
        >>> register_agent("custom", MyCustomAgent)
    """
    if not issubclass(agent_class, BaseAgent):
        raise TypeError(f"{agent_class} must be a subclass of BaseAgent")

    AGENT_REGISTRY[agent_type] = agent_class
    logger.info(f"Registered custom agent: {agent_type}")


__all__ = [
    "BaseAgent",
    "GPT4VAgent",
    "ClaudeAgent",
    "QwenAgent",
    "create_agent",
    "get_supported_agents",
    "register_agent",
    "AGENT_REGISTRY",
]
