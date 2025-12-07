"""
Qwen Agent Implementation.

Wraps Alibaba's Qwen VL models for OSWorld tasks via DashScope API.
"""

import base64
import logging
import os
from typing import Any, Dict, List, Tuple

from .base import BaseAgent
from ..config import AgentConfig

logger = logging.getLogger(__name__)

# System prompt for Qwen (adapted from OSWorld's qwen3vl_agent.py)
QWEN_SYSTEM_PROMPT = """You are a GUI agent. You are given a task and your action history. At each step, you should analyze the current screenshot and determine the best next action.

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


class QwenAgent(BaseAgent):
    """
    Qwen VL agent for OSWorld tasks.

    Supports Qwen-VL-Plus, Qwen-VL-Max, and Qwen3-VL models
    via DashScope API.
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._client = None
        self._conversation_history: List[Dict[str, Any]] = []

    def ensure_initialized(self) -> None:
        """Initialize the DashScope client on first use."""
        if self._initialized:
            return

        # Validate API key
        api_key = self.config.get_api_key()

        # Lazy import
        try:
            import dashscope
            from dashscope import MultiModalConversation
        except ImportError:
            raise ImportError(
                "dashscope package not installed. "
                "Install with: pip install dashscope"
            )

        logger.info(
            f"Initializing QwenAgent with model={self.config.model}, "
            f"temperature={self.config.temperature}"
        )

        # Set API key
        dashscope.api_key = api_key
        os.environ["DASHSCOPE_API_KEY"] = api_key

        self._client = MultiModalConversation
        self._initialized = True
        logger.info("QwenAgent initialized successfully")

    def _build_messages(
        self,
        instruction: str,
        observation: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build messages for Qwen API."""
        messages = []

        # Add system message
        messages.append({
            "role": "system",
            "content": [{"text": QWEN_SYSTEM_PROMPT}]
        })

        # Build user message content
        content = []

        # Add screenshot as base64 image
        screenshot_bytes = observation.get("screenshot")
        if screenshot_bytes:
            image_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            content.append({
                "image": f"data:image/png;base64,{image_b64}"
            })

        # Build text content
        text_parts = [f"Task: {instruction}"]

        # Add accessibility tree if available
        a11y_tree = observation.get("accessibility_tree")
        if a11y_tree and self.config.observation_type in ("a11y_tree", "screenshot_a11y_tree"):
            text_parts.append(f"\nAccessibility Tree:\n{a11y_tree[:10000]}")

        # Add trajectory context
        trajectory = self.get_trajectory_context()
        if trajectory:
            text_parts.append("\nPrevious actions:")
            for step in trajectory:
                text_parts.append(f"  Step {step['step']}: {step['action']}")

        content.append({"text": "\n".join(text_parts)})

        messages.append({
            "role": "user",
            "content": content
        })

        return messages

    def predict(
        self,
        instruction: str,
        observation: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Get action prediction from Qwen.

        Args:
            instruction: Task instruction
            observation: Dict with 'screenshot' (bytes) and optionally 'accessibility_tree' (str)

        Returns:
            Tuple of (reasoning_response, action_string)
        """
        self.ensure_initialized()

        # Build messages
        messages = self._build_messages(instruction, observation)

        try:
            # Check if thinking mode is enabled (Qwen3-VL feature)
            enable_thinking = self.config.provider_config.get("enable_thinking", False)

            call_kwargs = {
                "model": self.config.model,
                "messages": messages,
            }

            if enable_thinking:
                thinking_budget = self.config.provider_config.get("thinking_budget", 32768)
                call_kwargs["enable_thinking"] = True
                call_kwargs["thinking_budget"] = thinking_budget
                call_kwargs["max_tokens"] = self.config.max_tokens + thinking_budget
            else:
                call_kwargs["max_tokens"] = self.config.max_tokens

            # Call Qwen API
            response = self._client.call(**call_kwargs)

            if response.status_code != 200:
                error_msg = getattr(response, 'message', str(response))
                raise RuntimeError(f"Qwen API error: {error_msg}")

            # Extract response text
            response_text = ""
            thinking_text = ""

            output = response.output
            if hasattr(output, 'choices') and output.choices:
                choice = output.choices[0]
                message = choice.message

                # Handle thinking content
                if hasattr(message, 'thinking_content') and message.thinking_content:
                    thinking_text = message.thinking_content

                # Handle regular content
                if hasattr(message, 'content'):
                    if isinstance(message.content, list):
                        for item in message.content:
                            if isinstance(item, dict) and 'text' in item:
                                response_text = item['text']
                                break
                    else:
                        response_text = str(message.content)

            # Combine thinking and response
            full_reasoning = thinking_text + "\n" + response_text if thinking_text else response_text

            # Parse action from response
            action = self._parse_action(response_text)

            # Add to history
            self.add_to_history(thought=full_reasoning, action=action)

            return full_reasoning, action

        except Exception as e:
            logger.error(f"Qwen API error: {e}")
            raise

    def _parse_action(self, response: str) -> str:
        """Parse action from Qwen's response."""
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
