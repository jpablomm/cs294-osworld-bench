#!/usr/bin/env python3
"""
White Agent Core - Shared utilities for A2A and REST implementations.

This module contains:
- Action parsing (pyautogui -> OSWorld action format)
- Observation parsing (base64 screenshots, accessibility trees)
- URL building utilities
"""

import base64
import json
import logging
import os
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)


def parse_observation(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse observation from request data.

    Supports multiple formats:
    - Nested: {"observation": {"image_png_b64": ..., "instruction": ...}}
    - Flat: {"image_png_b64": ..., "instruction": ...}

    Returns:
        Dict with 'screenshot' (bytes), 'instruction' (str), 'frame_id' (int),
        'done' (bool), and optionally 'accessibility_tree' (str)
    """
    # Support both nested and flat formats
    if "observation" in data:
        obs_data = data["observation"]
    else:
        obs_data = data

    # Decode base64 screenshot
    image_b64 = obs_data.get("image_png_b64", "")
    if not image_b64:
        raise ValueError("Observation must have image_png_b64")

    screenshot_bytes = base64.b64decode(image_b64)

    result = {
        "frame_id": obs_data.get("frame_id", 0),
        "screenshot": screenshot_bytes,
        "instruction": obs_data.get("instruction", obs_data.get("message", "")),
        "done": obs_data.get("done", False)
    }

    # Include accessibility tree if provided (XML string from OSWorld VM)
    if "accessibility_tree" in obs_data and obs_data["accessibility_tree"]:
        result["accessibility_tree"] = obs_data["accessibility_tree"]

    return result


def parse_actions(actions_str: str) -> Dict[str, Any]:
    """
    Parse pyautogui action string into OSWorld action format.

    Converts from:
        "pyautogui.click(100, 200)"
    To:
        {"op": "click", "args": {"x": 100, "y": 200}}

    Also handles:
    - JSON format: '{"op": "click", "args": {"x": 100, "y": 200}}'
    - Multi-line code blocks
    - DONE/FAIL markers
    """
    actions_str = actions_str.strip()

    # Check for JSON format (GPT-4o sometimes returns this)
    if actions_str.startswith('{') and actions_str.endswith('}'):
        try:
            action_dict = json.loads(actions_str)
            if "op" in action_dict:
                # Handle screenshot action (convert to wait since screenshots are automatic)
                if action_dict["op"] == "screenshot":
                    logger.info("Model requested screenshot - converting to wait")
                    return {"op": "wait", "args": {"duration": 0.5}}
                return action_dict
        except json.JSONDecodeError:
            pass

    # Check for DONE/FAIL
    if "DONE" in actions_str or "FAIL" in actions_str:
        return {"op": "done", "args": {}}

    # Extract first command from multi-line code blocks
    if '\n' in actions_str or 'import' in actions_str:
        lines = actions_str.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('import') or line.startswith('time.'):
                continue
            if line.startswith('pyautogui.') or any(line.startswith(f'{cmd}(') for cmd in
                ['click', 'type_text', 'hotkey', 'scroll', 'doubleClick', 'rightClick']):
                actions_str = line
                break
        else:
            logger.warning("No command found in code block, defaulting to wait")
            return {"op": "wait", "args": {"duration": 1.0}}

    # Strip comments
    if '#' in actions_str:
        actions_str = actions_str.split('#')[0].strip()

    # Parse move actions
    if match := re.match(r'pyautogui\.moveRel\((-?\d+),\s*(-?\d+)\)', actions_str):
        logger.info("moveRel detected - treating as wait")
        return {"op": "wait", "args": {"duration": 0.5}}

    # Parse click actions
    if match := re.match(r'(?:pyautogui\.)?click\((?:x=)?(\d+),\s*(?:y=)?(\d+)\)', actions_str):
        return {"op": "click", "args": {"x": int(match.group(1)), "y": int(match.group(2))}}

    if match := re.match(r'(?:pyautogui\.)?click\(\)', actions_str):
        return {"op": "click", "args": {}}

    # Parse double click
    if match := re.match(r'(?:pyautogui\.)?doubleClick\((?:x=)?(\d+),\s*(?:y=)?(\d+)\)', actions_str):
        return {"op": "double_click", "args": {"x": int(match.group(1)), "y": int(match.group(2))}}

    # Parse right click
    if match := re.match(r'(?:pyautogui\.)?rightClick\((?:x=)?(\d+),\s*(?:y=)?(\d+)\)', actions_str):
        return {"op": "right_click", "args": {"x": int(match.group(1)), "y": int(match.group(2))}}

    # Parse type/write actions
    if match := re.match(r'(?:pyautogui\.)?(?:typewrite|write|type_text)\(["\'](.+?)["\']\)', actions_str):
        return {"op": "type", "args": {"text": match.group(1)}}

    # Parse hotkey actions
    if match := re.match(r'(?:pyautogui\.)?hotkey\(["\'](.+?)["\'],\s*["\'](.+?)["\']\)', actions_str):
        return {"op": "hotkey", "args": {"keys": [match.group(1), match.group(2)]}}

    # Parse hotkey with array syntax
    if match := re.match(r'(?:pyautogui\.)?hotkey\(\[([^\]]+)\]\)', actions_str):
        keys = [k.strip().strip("'\"") for k in match.group(1).split(',')]
        return {"op": "hotkey", "args": {"keys": keys}}

    # Parse press actions
    if match := re.match(r'(?:pyautogui\.)?press\(["\'](.+?)["\']', actions_str):
        return {"op": "hotkey", "args": {"keys": [match.group(1)]}}

    # Parse scroll
    if match := re.match(r'(?:pyautogui\.)?scroll\((-?\d+)\)', actions_str):
        return {"op": "scroll", "args": {"amount": int(match.group(1))}}

    # Default: wait
    logger.warning(f"Unknown action format: {actions_str}, defaulting to wait")
    return {"op": "wait", "args": {"duration": 1.0}}


def build_agent_url() -> str:
    """Build agent URL from environment variables."""
    # Check for AGENT_URL first (set by AgentBeats controller)
    agent_url = os.getenv("AGENT_URL")
    if agent_url:
        return agent_url

    # Build from components
    cloudrun_host = os.getenv("CLOUDRUN_HOST")
    https_enabled = os.getenv("HTTPS_ENABLED", "").lower() in ("true", "1", "yes")

    if cloudrun_host:
        protocol = "https" if https_enabled else "http"
        return f"{protocol}://{cloudrun_host}"
    else:
        host = os.getenv("AGENT_HOST", os.getenv("HOST", "0.0.0.0"))
        port = os.getenv("PORT", os.getenv("AGENT_PORT", "8080"))
        protocol = "https" if https_enabled else "http"
        return f"{protocol}://{host}:{port}"
