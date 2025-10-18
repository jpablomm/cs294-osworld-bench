"""
OSWorld Native REST API Client

This client communicates with the OSWorld server running natively on GCE VMs
via the REST API on port 5000.
"""

import requests
import base64
from typing import Dict, Any, Optional, List
from io import BytesIO
from PIL import Image


class OSWorldClient:
    """Client for OSWorld native REST API (port 5000)"""

    def __init__(self, base_url: str = "http://localhost:5000"):
        """
        Initialize OSWorld client.

        Args:
            base_url: Base URL of OSWorld server (e.g., "http://34.10.199.148:5000")
        """
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()

    def health_check(self) -> bool:
        """
        Check if OSWorld server is responding.

        Returns:
            True if server is healthy, False otherwise
        """
        try:
            response = self._session.get(f"{self.base_url}/platform", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def get_platform(self) -> str:
        """
        Get platform information.

        Returns:
            Platform name (e.g., "Linux")
        """
        response = self._session.get(f"{self.base_url}/platform")
        response.raise_for_status()
        return response.text.strip()

    def screenshot(self) -> bytes:
        """
        Capture screenshot and return PNG bytes.

        Returns:
            PNG image bytes
        """
        response = self._session.get(f"{self.base_url}/screenshot")
        response.raise_for_status()
        return response.content

    def screenshot_base64(self) -> str:
        """
        Capture screenshot and return base64-encoded PNG.

        Returns:
            Base64-encoded PNG string
        """
        png_bytes = self.screenshot()
        return base64.b64encode(png_bytes).decode("ascii")

    def screenshot_image(self) -> Image.Image:
        """
        Capture screenshot and return PIL Image.

        Returns:
            PIL Image object
        """
        png_bytes = self.screenshot()
        return Image.open(BytesIO(png_bytes))

    def execute(
        self,
        command: List[str] | str,
        shell: bool = False,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Execute a command in the desktop environment.

        Args:
            command: Command to execute (list of args or string if shell=True)
            shell: Whether to use shell execution
            timeout: Timeout in seconds

        Returns:
            Dictionary with:
                - status: "success" or "error"
                - output: stdout
                - error: stderr
                - returncode: exit code
        """
        payload = {
            "command": command,
            "shell": shell
        }
        response = self._session.post(
            f"{self.base_url}/execute",
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()

    def get_accessibility_tree(self) -> Dict[str, Any]:
        """
        Get UI element tree (windows, buttons, text fields, etc.).

        Returns:
            Accessibility tree as nested dictionary
        """
        response = self._session.get(f"{self.base_url}/accessibility")
        response.raise_for_status()
        return response.json()

    def get_cursor_position(self) -> tuple[int, int]:
        """
        Get current cursor position.

        Returns:
            Tuple of (x, y) coordinates
        """
        response = self._session.get(f"{self.base_url}/cursor_position")
        response.raise_for_status()
        data = response.json()
        return (data[0], data[1])

    def get_screen_size(self) -> Dict[str, int]:
        """
        Get screen dimensions.

        Returns:
            Dictionary with 'width' and 'height'
        """
        response = self._session.post(
            f"{self.base_url}/screen_size",
            json={}
        )
        response.raise_for_status()
        return response.json()

    def launch_chrome(self, url: Optional[str] = None) -> Dict[str, Any]:
        """
        Launch Google Chrome.

        Args:
            url: Optional URL to open

        Returns:
            Execution result dictionary
        """
        command = ["google-chrome", "--no-sandbox", "--new-window"]
        if url:
            command.append(url)
        return self.execute(command)

    def run_python(self, code: str) -> Dict[str, Any]:
        """
        Execute Python code on the OSWorld VM.

        Args:
            code: Python code to execute

        Returns:
            Execution result
        """
        response = self._session.post(
            f"{self.base_url}/run_python",
            json={"code": code},
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def type_text(self, text: str) -> Dict[str, Any]:
        """
        Type text using pyautogui.

        Args:
            text: Text to type

        Returns:
            Execution result
        """
        # Escape single quotes in text
        escaped_text = text.replace("'", "\\'")
        code = f"import pyautogui\npyautogui.write('{escaped_text}')"
        return self.run_python(code)

    def mouse_move(self, x: int, y: int) -> Dict[str, Any]:
        """
        Move mouse to specific coordinates.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Execution result
        """
        code = f"import pyautogui\npyautogui.moveTo({x}, {y})"
        return self.run_python(code)

    def click_at(self, x: int, y: int) -> Dict[str, Any]:
        """
        Click at specific coordinates.

        Args:
            x: X coordinate (None to click at current position)
            y: Y coordinate (None to click at current position)

        Returns:
            Execution result
        """
        if x is None or y is None:
            code = "import pyautogui\npyautogui.click()"
        else:
            code = f"import pyautogui\npyautogui.click({x}, {y})"
        return self.run_python(code)

    def double_click_at(self, x: int, y: int) -> Dict[str, Any]:
        """
        Double-click at specific coordinates.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Execution result
        """
        code = f"import pyautogui\npyautogui.doubleClick({x}, {y})"
        return self.run_python(code)

    def right_click_at(self, x: int, y: int) -> Dict[str, Any]:
        """
        Right-click at specific coordinates.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Execution result
        """
        code = f"import pyautogui\npyautogui.rightClick({x}, {y})"
        return self.run_python(code)

    def press_key(self, key: str) -> Dict[str, Any]:
        """
        Press a keyboard key.

        Args:
            key: Key name (e.g., "enter", "esc", "a")

        Returns:
            Execution result
        """
        code = f"import pyautogui\npyautogui.press('{key}')"
        return self.run_python(code)

    def hotkey(self, *keys: str) -> Dict[str, Any]:
        """
        Press a combination of keys simultaneously.

        Args:
            *keys: Key names to press together (e.g., "ctrl", "c")

        Returns:
            Execution result
        """
        keys_str = ", ".join([f"'{k}'" for k in keys])
        code = f"import pyautogui\npyautogui.hotkey({keys_str})"
        return self.run_python(code)

    def get_terminal_output(self) -> str:
        """
        Get terminal output (if terminal is open).

        Returns:
            Terminal text content
        """
        response = self._session.get(f"{self.base_url}/terminal")
        response.raise_for_status()
        return response.text

    def close(self):
        """Close the session."""
        self._session.close()


class OSWorldObservation:
    """
    Observation from OSWorld for the White Agent.
    Compatible with OSWorld's observation format.
    """

    def __init__(
        self,
        screenshot_b64: str,
        accessibility_tree: Optional[Dict[str, Any]] = None,
        cursor_position: Optional[tuple[int, int]] = None,
        screen_size: Optional[Dict[str, int]] = None,
    ):
        self.screenshot_b64 = screenshot_b64
        self.accessibility_tree = accessibility_tree
        self.cursor_position = cursor_position
        self.screen_size = screen_size

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for White Agent."""
        return {
            "screenshot": self.screenshot_b64,
            "accessibility_tree": self.accessibility_tree,
            "cursor_position": self.cursor_position,
            "screen_size": self.screen_size,
        }


def create_observation(client: OSWorldClient, include_a11y: bool = False) -> OSWorldObservation:
    """
    Create an observation from OSWorld client.

    Args:
        client: OSWorld client
        include_a11y: Whether to include accessibility tree (slower)

    Returns:
        OSWorldObservation object
    """
    screenshot_b64 = client.screenshot_base64()

    accessibility_tree = None
    if include_a11y:
        try:
            accessibility_tree = client.get_accessibility_tree()
        except Exception:
            # A11y tree is optional
            pass

    cursor_position = None
    try:
        cursor_position = client.get_cursor_position()
    except Exception:
        pass

    screen_size = None
    try:
        screen_size = client.get_screen_size()
    except Exception:
        pass

    return OSWorldObservation(
        screenshot_b64=screenshot_b64,
        accessibility_tree=accessibility_tree,
        cursor_position=cursor_position,
        screen_size=screen_size,
    )
