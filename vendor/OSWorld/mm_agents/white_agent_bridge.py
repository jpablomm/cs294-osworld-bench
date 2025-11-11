"""
White Agent Bridge for OSWorld

This agent acts as a bridge between OSWorld and an external White Agent
that communicates via HTTP REST API.
"""

import base64
import logging
import httpx
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger("desktopenv.agent")


class WhiteAgentBridge:
    """
    Bridge agent that forwards OSWorld observations to a White Agent HTTP endpoint
    and converts White Agent actions back to OSWorld-compatible format.
    """

    def __init__(
        self,
        white_agent_url: str,
        action_space: str = "pyautogui",
        platform: str = "ubuntu",
        **kwargs
    ):
        """
        Initialize the White Agent Bridge.

        Args:
            white_agent_url: Base URL of the White Agent HTTP API (e.g., "http://localhost:8090")
            action_space: Action format ("pyautogui" or "computer_13")
            platform: Platform type ("ubuntu" or "windows")
        """
        self.white_agent_url = white_agent_url.rstrip("/")
        self.action_space = action_space
        self.platform = platform
        self.frame_counter = 0

        # HTTP client with reasonable timeouts
        self.client = httpx.Client(
            timeout=httpx.Timeout(60.0, connect=10.0),
            follow_redirects=True
        )

        logger.info(
            f"WhiteAgentBridge initialized: url={self.white_agent_url}, "
            f"action_space={self.action_space}, platform={self.platform}"
        )

    def reset(self, _logger=None):
        """
        Reset the agent state.

        Args:
            _logger: Optional logger instance to use
        """
        global logger
        if _logger:
            logger = _logger
        else:
            logger = logging.getLogger("desktopenv.agent")

        self.frame_counter = 0

        # Call White Agent reset endpoint
        try:
            response = self.client.post(f"{self.white_agent_url}/reset", timeout=10)
            response.raise_for_status()
            logger.info("White Agent reset successful")
        except Exception as e:
            logger.warning(f"White Agent reset failed (continuing anyway): {e}")

    def predict(self, instruction: str, obs: Dict) -> Tuple[str, List]:
        """
        Predict the next action(s) based on the current observation.

        Args:
            instruction: Task instruction/goal
            obs: Observation dictionary with 'screenshot' (bytes) and optionally 'accessibility_tree'

        Returns:
            Tuple of (response_text, actions_list)
        """
        self.frame_counter += 1

        # Convert observation to White Agent format
        try:
            observation_payload = self._convert_observation(obs, instruction)
        except Exception as e:
            logger.error(f"Failed to convert observation: {e}")
            return f"Error converting observation: {e}", ["FAIL"]

        # Send to White Agent
        try:
            logger.debug(f"Sending observation to White Agent (frame {self.frame_counter})")
            response = self.client.post(
                f"{self.white_agent_url}/decide",
                json=observation_payload,
                timeout=60
            )
            response.raise_for_status()
            action_response = response.json()
            logger.info(f"Received action from White Agent: {action_response}")

        except httpx.TimeoutException as e:
            logger.error(f"White Agent timeout: {e}")
            return "White Agent timeout", ["FAIL"]
        except httpx.HTTPStatusError as e:
            logger.error(f"White Agent HTTP error: {e}")
            return f"White Agent HTTP error: {e.response.status_code}", ["FAIL"]
        except Exception as e:
            logger.error(f"Error communicating with White Agent: {e}")
            return f"Error: {e}", ["FAIL"]

        # Convert White Agent action to OSWorld format
        try:
            actions = self._convert_action(action_response)
            response_text = f"White Agent decision: {action_response.get('op', 'unknown')}"
            logger.info(f"Converted to OSWorld actions: {actions}")
            return response_text, actions

        except Exception as e:
            logger.error(f"Failed to convert action: {e}")
            return f"Error converting action: {e}", ["FAIL"]

    def _convert_observation(self, obs: Dict, instruction: str) -> Dict[str, Any]:
        """
        Convert OSWorld observation to White Agent format.

        Args:
            obs: OSWorld observation with 'screenshot' (bytes)
            instruction: Task instruction

        Returns:
            Dictionary matching White Agent's expected Observation format
        """
        # Encode screenshot to base64
        screenshot_bytes = obs.get("screenshot")
        if not screenshot_bytes:
            raise ValueError("Observation missing 'screenshot' field")

        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("ascii")

        # Create observation payload
        # Based on green_agent/models.py Observation schema
        return {
            "frame_id": self.frame_counter,
            "image_png_b64": screenshot_b64,
            "ui_hint": None,  # We don't have hints in real OSWorld observations
            "done": False
        }

    def _convert_action(self, white_agent_action: Dict[str, Any]) -> List[str]:
        """
        Convert White Agent action to OSWorld/pyautogui action format.

        Args:
            white_agent_action: Action dict from White Agent with 'op' and 'args'

        Returns:
            List of action strings (usually containing a single action)
        """
        op = white_agent_action.get("op", "").lower()
        args = white_agent_action.get("args", {})

        if not op:
            logger.warning("White Agent returned action without 'op' field")
            return ["WAIT"]

        # Map White Agent operations to pyautogui commands
        if op == "click":
            x = args.get("x", 0)
            y = args.get("y", 0)
            return [f"pyautogui.click({x}, {y})"]

        elif op == "double_click":
            x = args.get("x", 0)
            y = args.get("y", 0)
            return [f"pyautogui.doubleClick({x}, {y})"]

        elif op == "right_click":
            x = args.get("x", 0)
            y = args.get("y", 0)
            return [f"pyautogui.rightClick({x}, {y})"]

        elif op == "hotkey":
            keys = args.get("keys", [])
            if not keys:
                logger.warning("hotkey action missing 'keys' argument")
                return ["WAIT"]
            # Convert list like ["ctrl", "s"] to pyautogui.hotkey('ctrl', 's')
            keys_str = ", ".join(f"'{k}'" for k in keys)
            return [f"pyautogui.hotkey({keys_str})"]

        elif op == "type":
            text = args.get("text", "")
            if not text:
                logger.warning("type action missing 'text' argument")
                return ["WAIT"]
            # Escape triple quotes and use typewrite with interval
            text_escaped = text.replace('"""', r'\"\"\"')
            return [f'pyautogui.typewrite("""{text_escaped}""", interval=0.01)']

        elif op == "press":
            key = args.get("key", "")
            if not key:
                logger.warning("press action missing 'key' argument")
                return ["WAIT"]
            return [f"pyautogui.press('{key}')"]

        elif op == "scroll":
            amount = args.get("amount", 0)
            x = args.get("x")
            y = args.get("y")
            if x is not None and y is not None:
                return [f"pyautogui.scroll({amount}, {x}, {y})"]
            else:
                return [f"pyautogui.scroll({amount})"]

        elif op == "move":
            x = args.get("x", 0)
            y = args.get("y", 0)
            duration = args.get("duration", 0.5)
            return [f"pyautogui.moveTo({x}, {y}, duration={duration})"]

        elif op == "drag":
            x = args.get("x", 0)
            y = args.get("y", 0)
            duration = args.get("duration", 0.5)
            return [f"pyautogui.dragTo({x}, {y}, duration={duration})"]

        elif op == "wait":
            duration = args.get("duration", 0.5)
            return [f"pyautogui.sleep({duration})"]

        elif op == "done":
            return ["DONE"]

        elif op == "fail":
            return ["FAIL"]

        else:
            logger.warning(f"Unknown operation from White Agent: {op}")
            return ["WAIT"]

    def __del__(self):
        """Cleanup HTTP client on deletion."""
        try:
            self.client.close()
        except Exception:
            pass
