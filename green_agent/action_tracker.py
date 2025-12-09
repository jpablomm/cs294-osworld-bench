"""
Action Tracker for Loop Detection

Detects when the agent is stuck in a loop by tracking repeated similar actions.
Based on OSWorld's rule_engine.py repeated action detection mechanism.

Enhanced with coordinate validation using accessibility tree to suggest
correct click coordinates when the agent misses its target.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

from .element_bounds import (
    ElementBoundsParser,
    ElementBounds,
    generate_coordinate_guidance,
    validate_click_coordinates
)

logger = logging.getLogger(__name__)


class ActionTracker:
    """
    Tracks actions and detects repeated/stuck patterns.

    When the same action is repeated multiple times without progress,
    triggers a "stuck" detection that can be used to inject feedback
    or force the agent to try something different.
    """

    def __init__(self, threshold: int = 3, coordinate_tolerance: int = 20, platform: str = "ubuntu"):
        """
        Args:
            threshold: Number of consecutive similar actions before triggering stuck detection
            coordinate_tolerance: Pixel tolerance for comparing click coordinates
            platform: "ubuntu" or "windows" for a11y tree parsing
        """
        self.threshold = threshold
        self.coordinate_tolerance = coordinate_tolerance
        self.platform = platform
        self.actions: List[Dict[str, Any]] = []
        self.repeat_count = 0
        self.last_action: Optional[Dict[str, Any]] = None
        self.stuck_triggered = False
        self.current_a11y_tree: Optional[str] = None
        self.element_parser = ElementBoundsParser(platform=platform)

    def reset(self):
        """Reset the tracker state (e.g., for a new task)."""
        self.actions = []
        self.repeat_count = 0
        self.last_action = None
        self.stuck_triggered = False
        self.current_a11y_tree = None
        logger.debug("ActionTracker reset")

    def set_accessibility_tree(self, a11y_tree: Optional[str]):
        """
        Set the current accessibility tree for coordinate validation.
        Should be called before add_action() with each new observation.
        """
        self.current_a11y_tree = a11y_tree

    def add_action(self, action: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """
        Add an action and check if we're stuck in a loop.

        Args:
            action: Action dictionary in format {"op": "click", "args": {"x": 100, "y": 200}}

        Returns:
            Tuple of (status, feedback_message)
            - status: "ok", "warning", or "stuck"
            - feedback_message: Message to inject into prompt if stuck/warning
        """
        self.actions.append(action)

        # Debug: Log action being tracked
        coords = self._extract_coordinates(action)
        op = action.get("op", "unknown")
        if coords[0] is not None:
            logger.debug(f"[ActionTracker] Tracking action: {op} at ({int(coords[0])}, {int(coords[1])})")
        else:
            logger.debug(f"[ActionTracker] Tracking action: {op}")

        if self.last_action is None:
            self.last_action = action
            self.repeat_count = 1
            logger.debug(f"[ActionTracker] First action recorded, repeat_count=1")
            return ("ok", None)

        if self._are_actions_similar(action, self.last_action):
            self.repeat_count += 1
            logger.info(f"[ActionTracker] SIMILAR ACTION detected! repeat_count={self.repeat_count}/{self.threshold}")

            if self.repeat_count >= self.threshold:
                self.stuck_triggered = True
                feedback = self._generate_stuck_feedback(action)
                logger.warning(f"[ActionTracker] === STUCK LOOP TRIGGERED === after {self.repeat_count} repeated actions")
                logger.info(f"[ActionTracker] Generating feedback with coordinate guidance...")
                return ("stuck", feedback)
            elif self.repeat_count == self.threshold - 1:
                # Warning before stuck
                logger.info(f"[ActionTracker] WARNING: One more repeat will trigger stuck detection")
                feedback = self._generate_warning_feedback(action)
                return ("warning", feedback)
        else:
            # Different action, reset counter
            logger.debug(f"[ActionTracker] Different action detected, resetting repeat_count to 1")
            self.repeat_count = 1
            self.stuck_triggered = False

        self.last_action = action
        return ("ok", None)

    def _are_actions_similar(self, action1: Dict[str, Any], action2: Dict[str, Any]) -> bool:
        """
        Compare two actions to determine if they are similar.

        Follows OSWorld's approach: compare action types and execution parameters,
        but exclude descriptive fields.

        Expected format: {"op": "click", "args": {"x": 100, "y": 200}}
        """
        # Get operation types
        op1 = action1.get("op", "").lower()
        op2 = action2.get("op", "").lower()

        if op1 != op2:
            return False

        args1 = action1.get("args", {})
        args2 = action2.get("args", {})

        # For click actions, compare coordinates with tolerance
        if op1 in ["click", "left_click", "right_click", "double_click"]:
            x1, y1 = self._extract_coordinates(action1)
            x2, y2 = self._extract_coordinates(action2)

            if x1 is not None and x2 is not None and y1 is not None and y2 is not None:
                x_diff = abs(x1 - x2)
                y_diff = abs(y1 - y2)
                return x_diff <= self.coordinate_tolerance and y_diff <= self.coordinate_tolerance

        # For type/text actions, compare the text
        if op1 in ["type", "type_text", "typing", "text"]:
            text1 = args1.get("text", "")
            text2 = args2.get("text", "")
            return text1 == text2

        # For hotkey actions, compare keys
        if op1 in ["hotkey", "key", "press"]:
            keys1 = args1.get("keys") or args1.get("key", "")
            keys2 = args2.get("keys") or args2.get("key", "")
            return keys1 == keys2

        # For other actions, they're similar if same type
        return True

    def _extract_coordinates(self, action: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        """Extract x, y coordinates from an action.

        Expected format: {"op": "click", "args": {"x": 100, "y": 200}}
        """
        # Standard format: args.x, args.y
        args = action.get("args", {})
        x = args.get("x")
        y = args.get("y")

        if x is not None and y is not None:
            return (float(x), float(y))

        return (None, None)

    def _generate_stuck_feedback(self, action: Dict[str, Any]) -> str:
        """Generate feedback message when stuck is detected, with coordinate guidance."""
        coords = self._extract_coordinates(action)
        op = action.get("op", "action")

        if coords[0] is not None:
            coord_str = f"at coordinates ({int(coords[0])}, {int(coords[1])})"
            click_x, click_y = int(coords[0]), int(coords[1])
        else:
            coord_str = ""
            click_x, click_y = None, None

        # Generate coordinate guidance if we have accessibility tree and coordinates
        coordinate_guidance = ""
        if click_x is not None and self.current_a11y_tree:
            logger.info(f"[ActionTracker] Parsing accessibility tree for coordinate guidance...")
            try:
                elements = self.element_parser.parse(self.current_a11y_tree)
                logger.info(f"[ActionTracker] Found {len(elements)} interactive elements in a11y tree")
                if elements:
                    # Check if click hit any element
                    hit = self.element_parser.find_element_at(elements, click_x, click_y)
                    if hit:
                        logger.info(f"[ActionTracker] Click at ({click_x}, {click_y}) HIT element: {hit.display_name}")
                    else:
                        logger.info(f"[ActionTracker] Click at ({click_x}, {click_y}) MISSED all elements")
                        nearby = self.element_parser.find_nearby_elements(elements, click_x, click_y, max_distance=150)
                        if nearby:
                            logger.info(f"[ActionTracker] Found {len(nearby)} nearby elements:")
                            for elem, dist in nearby[:3]:
                                logger.info(f"[ActionTracker]   - {elem.display_name} at ({elem.center_x}, {elem.center_y}), {int(dist)}px away")

                    guidance = generate_coordinate_guidance(elements, click_x, click_y)
                    coordinate_guidance = f"\n\n=== COORDINATE ANALYSIS ===\n{guidance}\n=== END ANALYSIS ==="
                    logger.debug(f"[ActionTracker] Coordinate guidance generated successfully")
            except Exception as e:
                logger.warning(f"[ActionTracker] Failed to generate coordinate guidance: {e}")
        elif click_x is not None and not self.current_a11y_tree:
            logger.debug(f"[ActionTracker] No accessibility tree available for coordinate guidance")

        return f"""
=== STUCK LOOP DETECTED ===
WARNING: You have attempted the same {op} {coord_str} {self.repeat_count} times without any visible change in the UI.

This action is NOT working. You MUST try a DIFFERENT approach.
{coordinate_guidance}

RECOVERY OPTIONS:
1. If a nearby element was suggested above, click its CENTER coordinates
2. Try using a keyboard shortcut instead (e.g., Tab to focus, Enter to confirm, Escape to cancel)
3. If a dialog/popup appeared, interact with it first
4. If the element is not visible, try scrolling to find it
5. If you cannot make progress, return FAIL

DO NOT repeat the same action again. The next action MUST be different.
=== END WARNING ===
""".strip()

    def _generate_warning_feedback(self, action: Dict[str, Any]) -> str:
        """Generate warning message before stuck threshold is reached."""
        coords = self._extract_coordinates(action)
        op = action.get("op", "action")

        if coords[0] is not None:
            coord_str = f"at ({int(coords[0])}, {int(coords[1])})"
        else:
            coord_str = ""

        return f"""
NOTE: You've tried the same {op} {coord_str} {self.repeat_count} times.
If the screen hasn't changed, consider trying a different approach.
""".strip()

    def get_action_history_summary(self, last_n: int = 5) -> str:
        """Get a summary of recent actions for context."""
        if not self.actions:
            return "No previous actions."

        recent = self.actions[-last_n:]
        lines = ["Recent actions:"]

        for i, action in enumerate(recent, 1):
            op = action.get("op", "unknown")
            args = action.get("args", {})
            coords = self._extract_coordinates(action)

            if coords[0] is not None:
                lines.append(f"  {i}. {op} at ({int(coords[0])}, {int(coords[1])})")
            else:
                text = args.get("text", "")
                if text:
                    lines.append(f"  {i}. {op}: {text[:30]}...")
                else:
                    lines.append(f"  {i}. {op}")

        return "\n".join(lines)

    @property
    def is_stuck(self) -> bool:
        """Check if currently in stuck state."""
        return self.stuck_triggered

    @property
    def action_count(self) -> int:
        """Get total number of tracked actions."""
        return len(self.actions)
