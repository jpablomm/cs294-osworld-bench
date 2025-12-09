"""
Action Tracker for Loop Detection

Detects when the agent is stuck in a loop by tracking repeated similar actions.
Based on OSWorld's rule_engine.py repeated action detection mechanism.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ActionTracker:
    """
    Tracks actions and detects repeated/stuck patterns.

    When the same action is repeated multiple times without progress,
    triggers a "stuck" detection that can be used to inject feedback
    or force the agent to try something different.
    """

    def __init__(self, threshold: int = 3, coordinate_tolerance: int = 20):
        """
        Args:
            threshold: Number of consecutive similar actions before triggering stuck detection
            coordinate_tolerance: Pixel tolerance for comparing click coordinates
        """
        self.threshold = threshold
        self.coordinate_tolerance = coordinate_tolerance
        self.actions: List[Dict[str, Any]] = []
        self.repeat_count = 0
        self.last_action: Optional[Dict[str, Any]] = None
        self.stuck_triggered = False

    def reset(self):
        """Reset the tracker state (e.g., for a new task)."""
        self.actions = []
        self.repeat_count = 0
        self.last_action = None
        self.stuck_triggered = False
        logger.debug("ActionTracker reset")

    def add_action(self, action: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """
        Add an action and check if we're stuck in a loop.

        Args:
            action: Action dictionary with action_type, coordinates, etc.

        Returns:
            Tuple of (status, feedback_message)
            - status: "ok", "warning", or "stuck"
            - feedback_message: Message to inject into prompt if stuck/warning
        """
        self.actions.append(action)

        if self.last_action is None:
            self.last_action = action
            self.repeat_count = 1
            return ("ok", None)

        if self._are_actions_similar(action, self.last_action):
            self.repeat_count += 1
            logger.debug(f"Similar action detected, repeat count: {self.repeat_count}")

            if self.repeat_count >= self.threshold:
                self.stuck_triggered = True
                feedback = self._generate_stuck_feedback(action)
                logger.warning(f"STUCK DETECTED: {self.repeat_count} repeated actions")
                return ("stuck", feedback)
            elif self.repeat_count == self.threshold - 1:
                # Warning before stuck
                feedback = self._generate_warning_feedback(action)
                return ("warning", feedback)
        else:
            # Different action, reset counter
            self.repeat_count = 1
            self.stuck_triggered = False

        self.last_action = action
        return ("ok", None)

    def _are_actions_similar(self, action1: Dict[str, Any], action2: Dict[str, Any]) -> bool:
        """
        Compare two actions to determine if they are similar.

        Follows OSWorld's approach: compare action types and execution parameters,
        but exclude descriptive fields.
        """
        # Get action types (handle different key names)
        type1 = action1.get("action_type") or action1.get("type", "")
        type2 = action2.get("action_type") or action2.get("type", "")

        # Normalize action types
        type1 = type1.lower() if isinstance(type1, str) else ""
        type2 = type2.lower() if isinstance(type2, str) else ""

        if type1 != type2:
            return False

        # For click actions, compare coordinates with tolerance
        if type1 in ["click", "left_click", "right_click", "double_click"]:
            x1, y1 = self._extract_coordinates(action1)
            x2, y2 = self._extract_coordinates(action2)

            if x1 is not None and x2 is not None and y1 is not None and y2 is not None:
                x_diff = abs(x1 - x2)
                y_diff = abs(y1 - y2)
                return x_diff <= self.coordinate_tolerance and y_diff <= self.coordinate_tolerance

        # For type/text actions, compare the text
        if type1 in ["type", "typing", "text"]:
            text1 = action1.get("text", "")
            text2 = action2.get("text", "")
            return text1 == text2

        # For hotkey actions, compare keys
        if type1 in ["hotkey", "key", "press"]:
            keys1 = action1.get("keys") or action1.get("key", "")
            keys2 = action2.get("keys") or action2.get("key", "")
            return keys1 == keys2

        # For other actions, they're similar if same type
        return True

    def _extract_coordinates(self, action: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        """Extract x, y coordinates from an action, handling various formats."""
        # Direct x, y keys
        x = action.get("x")
        y = action.get("y")

        if x is not None and y is not None:
            return (float(x), float(y))

        # Coordinate array format
        coord = action.get("coordinate")
        if coord and len(coord) >= 2:
            return (float(coord[0]), float(coord[1]))

        # Try to extract from raw_response if it contains pyautogui code
        raw = action.get("raw_response", "")
        if raw:
            coords = self._extract_coords_from_code(raw)
            if coords:
                return coords

        return (None, None)

    def _extract_coords_from_code(self, code: str) -> Optional[Tuple[float, float]]:
        """Extract coordinates from pyautogui code like 'pyautogui.click(847, 686)'."""
        # Match pyautogui.click(x, y) or pyautogui.click(x=847, y=686)
        patterns = [
            r'pyautogui\.(?:click|doubleClick|rightClick)\s*\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)',
            r'pyautogui\.(?:click|doubleClick|rightClick)\s*\([^)]*x\s*=\s*(\d+(?:\.\d+)?)[^)]*y\s*=\s*(\d+(?:\.\d+)?)',
        ]

        for pattern in patterns:
            match = re.search(pattern, code)
            if match:
                return (float(match.group(1)), float(match.group(2)))

        return None

    def _generate_stuck_feedback(self, action: Dict[str, Any]) -> str:
        """Generate feedback message when stuck is detected."""
        coords = self._extract_coordinates(action)
        action_type = action.get("action_type") or action.get("type", "action")

        if coords[0] is not None:
            coord_str = f"at coordinates ({int(coords[0])}, {int(coords[1])})"
        else:
            coord_str = ""

        return f"""
=== STUCK LOOP DETECTED ===
WARNING: You have attempted the same {action_type} {coord_str} {self.repeat_count} times without any visible change in the UI.

This action is NOT working. You MUST try a DIFFERENT approach:
1. Look carefully at the current screenshot - the UI may have changed or the element may be elsewhere
2. Try clicking on a DIFFERENT element or location
3. Try using a keyboard shortcut instead (e.g., Tab, Enter, Escape)
4. If a dialog/popup appeared, interact with it first
5. If the element is not visible, try scrolling or navigating to find it
6. If you cannot make progress, return FAIL to signal the task cannot be completed

DO NOT repeat the same action again. The next action MUST be different.
=== END WARNING ===
""".strip()

    def _generate_warning_feedback(self, action: Dict[str, Any]) -> str:
        """Generate warning message before stuck threshold is reached."""
        coords = self._extract_coordinates(action)
        action_type = action.get("action_type") or action.get("type", "action")

        if coords[0] is not None:
            coord_str = f"at ({int(coords[0])}, {int(coords[1])})"
        else:
            coord_str = ""

        return f"""
NOTE: You've tried the same {action_type} {coord_str} {self.repeat_count} times.
If the screen hasn't changed, consider trying a different approach.
""".strip()

    def get_action_history_summary(self, last_n: int = 5) -> str:
        """Get a summary of recent actions for context."""
        if not self.actions:
            return "No previous actions."

        recent = self.actions[-last_n:]
        lines = ["Recent actions:"]

        for i, action in enumerate(recent, 1):
            action_type = action.get("action_type") or action.get("type", "unknown")
            coords = self._extract_coordinates(action)

            if coords[0] is not None:
                lines.append(f"  {i}. {action_type} at ({int(coords[0])}, {int(coords[1])})")
            else:
                text = action.get("text", "")
                if text:
                    lines.append(f"  {i}. {action_type}: {text[:30]}...")
                else:
                    lines.append(f"  {i}. {action_type}")

        return "\n".join(lines)

    @property
    def is_stuck(self) -> bool:
        """Check if currently in stuck state."""
        return self.stuck_triggered

    @property
    def action_count(self) -> int:
        """Get total number of tracked actions."""
        return len(self.actions)
