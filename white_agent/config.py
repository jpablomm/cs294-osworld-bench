"""
White Agent Configuration Module.

Provides unified configuration for all agent types (GPT-4V, Claude, Qwen, etc.)
"""

import os
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Supported agent types."""
    GPT4V = "gpt4v"
    CLAUDE = "claude"
    QWEN = "qwen"
    O3 = "o3"
    GEMINI = "gemini"
    LANGCHAIN = "langchain"


class AgentConfig(BaseModel):
    """
    Unified configuration for white agents.

    Supports multiple model providers through a common interface.
    """

    # Core settings
    agent_type: AgentType = Field(
        default=AgentType.GPT4V,
        description="Type of agent to use"
    )
    model: str = Field(
        default="gpt-4o",
        description="Model name/ID for the provider"
    )

    # API configuration
    api_key: Optional[str] = Field(
        default=None,
        description="API key for the provider (falls back to env vars)"
    )
    api_base_url: Optional[str] = Field(
        default=None,
        description="Custom API base URL (for proxies or self-hosted)"
    )

    # Generation parameters
    temperature: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature"
    )
    max_tokens: int = Field(
        default=1500,
        gt=0,
        description="Maximum tokens to generate"
    )
    top_p: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Top-p sampling parameter"
    )

    # OSWorld-specific settings
    observation_type: str = Field(
        default="screenshot",
        description="Observation type: screenshot, a11y_tree, screenshot_a11y_tree, som"
    )
    action_space: str = Field(
        default="pyautogui",
        description="Action space: pyautogui, computer_13"
    )
    max_trajectory_length: int = Field(
        default=3,
        description="Maximum trajectory history to include in context"
    )

    # Provider-specific configuration
    provider_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific settings (e.g., thinking mode for Claude/Qwen)"
    )

    class Config:
        use_enum_values = True

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """
        Create configuration from environment variables.

        Environment variables:
            AGENT_TYPE: Agent type (gpt4v, claude, qwen, o3, gemini)
            MODEL: Model name
            API_KEY: Provider API key (or provider-specific like OPENAI_API_KEY)
            API_BASE_URL: Custom API base URL
            TEMPERATURE: Sampling temperature
            MAX_TOKENS: Maximum tokens
            TOP_P: Top-p sampling
            OSWORLD_OBS_TYPE: Observation type
            ACTION_SPACE: Action space
            MAX_TRAJECTORY_LENGTH: Trajectory history length

            Provider-specific:
            ENABLE_THINKING: Enable thinking mode (Claude/Qwen)
            THINKING_BUDGET: Token budget for thinking
        """
        agent_type_str = os.environ.get("AGENT_TYPE", "gpt4v").lower()

        # Map agent type to appropriate API key env var
        api_key = os.environ.get("API_KEY")
        if not api_key:
            api_key_map = {
                "gpt4v": "OPENAI_API_KEY",
                "o3": "OPENAI_API_KEY",
                "claude": "ANTHROPIC_API_KEY",
                "qwen": "DASHSCOPE_API_KEY",
                "gemini": "GOOGLE_API_KEY",
            }
            env_var = api_key_map.get(agent_type_str, "API_KEY")
            api_key = os.environ.get(env_var)

        # Default model per agent type
        default_models = {
            "gpt4v": "gpt-4o",
            "o3": "o3",
            "claude": "claude-sonnet-4-20250514",
            "qwen": "qwen-vl-max",
            "gemini": "gemini-1.5-pro",
        }
        model = os.environ.get("MODEL", default_models.get(agent_type_str, "gpt-4o"))

        # Build provider config from env vars
        provider_config = {}
        if os.environ.get("ENABLE_THINKING", "").lower() in ("true", "1", "yes"):
            provider_config["enable_thinking"] = True
            provider_config["thinking_budget"] = int(
                os.environ.get("THINKING_BUDGET", "10000")
            )

        return cls(
            agent_type=agent_type_str,
            model=model,
            api_key=api_key,
            api_base_url=os.environ.get("API_BASE_URL"),
            temperature=float(os.environ.get("TEMPERATURE", "1.0")),
            max_tokens=int(os.environ.get("MAX_TOKENS", "1500")),
            top_p=float(os.environ.get("TOP_P", "0.9")),
            observation_type=os.environ.get("OSWORLD_OBS_TYPE", "screenshot"),
            action_space=os.environ.get("ACTION_SPACE", "pyautogui"),
            max_trajectory_length=int(os.environ.get("MAX_TRAJECTORY_LENGTH", "3")),
            provider_config=provider_config,
        )

    def get_api_key(self) -> str:
        """Get API key, raising if not configured."""
        if self.api_key:
            return self.api_key

        # Try provider-specific env vars as fallback
        env_vars = {
            AgentType.GPT4V: "OPENAI_API_KEY",
            AgentType.O3: "OPENAI_API_KEY",
            AgentType.CLAUDE: "ANTHROPIC_API_KEY",
            AgentType.QWEN: "DASHSCOPE_API_KEY",
            AgentType.GEMINI: "GOOGLE_API_KEY",
            AgentType.LANGCHAIN: "OPENAI_API_KEY",
        }
        env_var = env_vars.get(AgentType(self.agent_type))
        if env_var:
            key = os.environ.get(env_var)
            if key:
                return key

        raise ValueError(
            f"API key not configured for {self.agent_type}. "
            f"Set API_KEY or {env_var} environment variable."
        )
