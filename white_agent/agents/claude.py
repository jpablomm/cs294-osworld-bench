"""
Claude Agent Implementation.

Wraps Anthropic's Claude models for OSWorld tasks.
"""

import base64
import logging
from typing import Any, Dict, List, Tuple

from .base import BaseAgent
from ..config import AgentConfig

logger = logging.getLogger(__name__)

# System prompt for Claude (adapted from OSWorld's PromptAgent)
CLAUDE_SYSTEM_PROMPT = """You are a GUI agent. You are given a task and your action history. At each step, you should analyze the current screenshot and determine the best next action.

## Output Format
Your output must be in the following format:

Observation: <describe what you see on the screen>
Thought: <your reasoning about what action to take>
Action: <the action to execute>

## Action Space (pyautogui)
You can use the following actions:
- pyautogui.click(x, y) - Click at coordinates (x, y)
- pyautogui.doubleClick(x, y) - Double click at coordinates (x, y)
- pyautogui.rightClick(x, y) - Right click at coordinates (x, y)
- pyautogui.write('text') - Type text
- pyautogui.press('key') - Press a key (enter, tab, escape, etc.)
- pyautogui.hotkey('key1', 'key2') - Press key combination (e.g., ctrl, c)
- pyautogui.scroll(amount) - Scroll (positive=up, negative=down)
- DONE - Task is complete
- FAIL - Task cannot be completed

## Important Notes
- Coordinates are in pixels from top-left corner
- Always observe the screen carefully before acting
- If a task is impossible, output FAIL
- If a task is complete, output DONE
"""


class ClaudeAgent(BaseAgent):
    """
    Claude agent for OSWorld tasks.

    Supports Claude 3.5 Sonnet, Claude 3 Opus, and other Claude models
    with vision capabilities.
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._client = None
        self._conversation_history: List[Dict[str, Any]] = []

    def ensure_initialized(self) -> None:
        """Initialize the Anthropic client on first use."""
        if self._initialized:
            return

        # Validate API key
        api_key = self.config.get_api_key()

        # Lazy import
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package not installed. "
                "Install with: pip install anthropic"
            )

        logger.info(
            f"Initializing ClaudeAgent with model={self.config.model}, "
            f"temperature={self.config.temperature}"
        )

        # Initialize client
        client_kwargs = {"api_key": api_key}
        if self.config.api_base_url:
            client_kwargs["base_url"] = self.config.api_base_url

        self._client = anthropic.Anthropic(**client_kwargs)
        self._initialized = True
        logger.info("ClaudeAgent initialized successfully")

    def _build_message_content(
        self,
        instruction: str,
        observation: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build message content with image and text."""
        content = []

        # Add screenshot as base64 image
        screenshot_bytes = observation.get("screenshot")
        if screenshot_bytes:
            image_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image_b64
                }
            })

        # Build text content
        text_parts = [f"Task: {instruction}"]

        # Add accessibility tree if available
        a11y_tree = observation.get("accessibility_tree")
        if a11y_tree and self.config.observation_type in ("a11y_tree", "screenshot_a11y_tree"):
            text_parts.append(f"\nAccessibility Tree:\n{a11y_tree[:10000]}")  # Truncate if too long

        # Add trajectory context
        trajectory = self.get_trajectory_context()
        if trajectory:
            text_parts.append("\nPrevious actions:")
            for step in trajectory:
                text_parts.append(f"  Step {step['step']}: {step['action']}")

        content.append({
            "type": "text",
            "text": "\n".join(text_parts)
        })

        return content

    def predict(
        self,
        instruction: str,
        observation: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Get action prediction from Claude.

        Args:
            instruction: Task instruction
            observation: Dict with 'screenshot' (bytes) and optionally 'accessibility_tree' (str)

        Returns:
            Tuple of (reasoning_response, action_string)
        """
        self.ensure_initialized()

        # Build message content
        content = self._build_message_content(instruction, observation)

        # Build messages with conversation history for multi-turn
        messages = []

        # Add current message
        messages.append({
            "role": "user",
            "content": content
        })

        # Call Claude API
        try:
            # Check if thinking mode is enabled
            enable_thinking = self.config.provider_config.get("enable_thinking", False)

            if enable_thinking:
                # Use extended thinking (Claude 3.5+ feature)
                thinking_budget = self.config.provider_config.get("thinking_budget", 10000)
                response = self._client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens + thinking_budget,
                    system=CLAUDE_SYSTEM_PROMPT,
                    messages=messages,
                    temperature=1.0,  # Required for thinking
                    thinking={
                        "type": "enabled",
                        "budget_tokens": thinking_budget
                    }
                )
            else:
                response = self._client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    system=CLAUDE_SYSTEM_PROMPT,
                    messages=messages,
                    temperature=self.config.temperature,
                    top_p=self.config.top_p,
                )

            # Extract response text
            response_text = ""
            thinking_text = ""

            for block in response.content:
                if block.type == "thinking":
                    thinking_text = block.thinking
                elif block.type == "text":
                    response_text = block.text

            # Combine thinking and response for full reasoning
            full_reasoning = thinking_text + "\n" + response_text if thinking_text else response_text

            # Parse action from response
            action = self._parse_action(response_text)

            # Add to history
            self.add_to_history(thought=full_reasoning, action=action)

            return full_reasoning, action

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    def _parse_action(self, response: str) -> str:
        """Parse action from Claude's response."""
        # Look for Action: line
        lines = response.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.lower().startswith("action:"):
                action = line[7:].strip()
                return action

        # If no explicit Action: line, check for DONE/FAIL
        response_lower = response.lower()
        if "done" in response_lower:
            return "DONE"
        if "fail" in response_lower:
            return "FAIL"

        # Return the last non-empty line as fallback
        for line in reversed(lines):
            line = line.strip()
            if line and not line.startswith(("Observation:", "Thought:", "#")):
                return line

        return "FAIL"

    def reset(self) -> None:
        """Reset agent state."""
        super().reset()
        self._conversation_history.clear()
