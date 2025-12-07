# Custom White Agent Guide

This guide explains how to create and register a custom white agent using the unified agent architecture.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Input/Output Specification](#inputoutput-specification)
3. [Creating a Custom Agent](#creating-a-custom-agent)
4. [Registering Your Agent](#registering-your-agent)
5. [Running Your Agent](#running-your-agent)
6. [Example: LangChain Agent](#example-langchain-agent)

---

## Architecture Overview

The white agent architecture uses a factory pattern to support multiple model providers:

```
white_agent/
├── config.py           # AgentConfig - unified configuration
├── core.py             # Shared utilities (parse_observation, parse_actions)
├── agents/
│   ├── __init__.py     # Factory: create_agent(), register_agent()
│   ├── base.py         # BaseAgent abstract class
│   ├── gpt4v.py        # GPT-4V implementation
│   ├── claude.py       # Claude implementation
│   └── qwen.py         # Qwen implementation
├── a2a/
│   └── server.py       # A2A protocol server
└── rest/
    └── server.py       # REST API server
```

### Key Components

| Component | Purpose |
|-----------|---------|
| `AgentConfig` | Pydantic model for agent configuration |
| `BaseAgent` | Abstract base class all agents must implement |
| `create_agent()` | Factory function that creates agents from config |
| `register_agent()` | Register custom agent implementations |
| `parse_actions()` | Convert action strings to OSWorld format |

---

## Input/Output Specification

### `predict()` Method Signature

```python
def predict(
    self,
    instruction: str,
    observation: Dict[str, Any]
) -> Tuple[str, str]:
```

### Input Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `instruction` | `str` | Task instruction/goal (e.g., "Turn on Bluetooth") |
| `observation` | `Dict[str, Any]` | Current state observation (see below) |

#### Observation Dictionary

```python
{
    "screenshot": bytes,              # PNG image data (required)
    "accessibility_tree": str | None  # XML accessibility tree (optional)
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `screenshot` | `bytes` | Yes | Raw PNG image bytes of the current screen |
| `accessibility_tree` | `str` | No | XML string containing UI element hierarchy |

### Output

```python
Tuple[str, str]  # (reasoning, action_string)
```

| Return Value | Type | Description |
|--------------|------|-------------|
| `reasoning` | `str` | Model's reasoning/thought process explaining the action |
| `action_string` | `str` | Action to execute (pyautogui format or JSON) |

### Action String Formats

Your agent can return actions in either format:

#### Format 1: PyAutoGUI Syntax (Recommended)

```python
# Mouse actions
"pyautogui.click(100, 200)"
"pyautogui.doubleClick(100, 200)"
"pyautogui.rightClick(100, 200)"

# Keyboard actions
"pyautogui.write('hello world')"
"pyautogui.press('enter')"
"pyautogui.hotkey('ctrl', 'c')"

# Scroll
"pyautogui.scroll(-3)"  # Negative = down, Positive = up

# Task completion
"DONE"  # Task completed successfully
"FAIL"  # Task cannot be completed
```

#### Format 2: JSON Format

```python
'{"op": "click", "args": {"x": 100, "y": 200}}'
'{"op": "type", "args": {"text": "hello"}}'
'{"op": "hotkey", "args": {"keys": ["ctrl", "c"]}}'
'{"op": "done", "args": {}}'
```

### Parsed Action Format (OSWorld)

Actions are automatically converted to this format by `parse_actions()`:

```python
{
    "op": str,       # Operation type
    "args": Dict     # Operation arguments
}
```

#### Supported Operations

| op | args | Description |
|----|------|-------------|
| `click` | `{"x": int, "y": int}` | Left click at coordinates |
| `double_click` | `{"x": int, "y": int}` | Double click at coordinates |
| `right_click` | `{"x": int, "y": int}` | Right click at coordinates |
| `type` | `{"text": str}` | Type text |
| `hotkey` | `{"keys": List[str]}` | Press key combination |
| `scroll` | `{"amount": int}` | Scroll (negative=down) |
| `wait` | `{"duration": float}` | Wait for duration |
| `done` | `{}` | Task completed |

---

## Creating a Custom Agent

### Step 1: Create Agent File

Create a new file in `white_agent/agents/`:

```python
# white_agent/agents/my_agent.py

"""
My Custom Agent Implementation.
"""

import logging
from typing import Any, Dict, Tuple

from .base import BaseAgent
from ..config import AgentConfig

logger = logging.getLogger(__name__)


class MyCustomAgent(BaseAgent):
    """
    Custom agent implementation.
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._client = None  # Your model client

    def ensure_initialized(self) -> None:
        """Initialize the agent on first use (lazy initialization)."""
        if self._initialized:
            return

        # Get API key from config
        api_key = self.config.get_api_key()

        # Initialize your model client here
        # Example:
        # from my_library import MyClient
        # self._client = MyClient(api_key=api_key, model=self.config.model)

        logger.info(f"Initialized MyCustomAgent with model={self.config.model}")
        self._initialized = True

    def predict(
        self,
        instruction: str,
        observation: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Get action prediction from the model.

        Args:
            instruction: Task instruction/goal
            observation: Dict with 'screenshot' (bytes) and optionally 'accessibility_tree' (str)

        Returns:
            Tuple of (reasoning, action_string)
        """
        self.ensure_initialized()

        # Extract observation data
        screenshot_bytes = observation.get("screenshot")
        accessibility_tree = observation.get("accessibility_tree")

        # -----------------------------------------
        # YOUR INFERENCE LOGIC HERE
        # -----------------------------------------
        # 1. Convert screenshot bytes to your model's expected format
        # 2. Build prompt with instruction and observation
        # 3. Call your model
        # 4. Parse response into reasoning and action

        # Example placeholder:
        reasoning = "I analyzed the screen and decided to click the button."
        action = "pyautogui.click(100, 200)"

        # -----------------------------------------

        # Track history (optional but recommended)
        self.add_to_history(thought=reasoning, action=action)

        return reasoning, action

    def reset(self) -> None:
        """Reset agent state for a new task."""
        super().reset()
        # Reset any custom state here
```

### Step 2: Implement Core Logic

The key method is `predict()`. Here's what you need to do:

```python
def predict(self, instruction: str, observation: Dict[str, Any]) -> Tuple[str, str]:
    self.ensure_initialized()

    # 1. Get screenshot (required)
    screenshot_bytes: bytes = observation["screenshot"]

    # 2. Get accessibility tree (optional)
    a11y_tree: str | None = observation.get("accessibility_tree")

    # 3. Convert screenshot for your model
    #    Common conversions:
    #    - Base64: base64.b64encode(screenshot_bytes).decode('utf-8')
    #    - PIL Image: Image.open(io.BytesIO(screenshot_bytes))
    #    - File path: Save to temp file and pass path

    # 4. Build your prompt/messages
    #    Include: instruction, screenshot, optionally a11y_tree

    # 5. Call your model
    response = self._client.generate(...)

    # 6. Parse response into reasoning and action
    reasoning = extract_reasoning(response)
    action = extract_action(response)  # Should be pyautogui format

    return reasoning, action
```

---

## Registering Your Agent

### Option 1: Add to Registry (Permanent)

Edit `white_agent/agents/__init__.py`:

```python
from .my_agent import MyCustomAgent

# Add to registry
AGENT_REGISTRY = {
    "gpt4v": GPT4VAgent,
    "claude": ClaudeAgent,
    "qwen": QwenAgent,
    "my_agent": MyCustomAgent,  # Add this line
}
```

### Option 2: Register at Runtime (Dynamic)

```python
from white_agent.agents import register_agent
from white_agent.agents.my_agent import MyCustomAgent

# Register before creating the agent
register_agent("my_agent", MyCustomAgent)
```

### Option 3: Add to AgentType Enum (Optional)

For IDE autocomplete support, edit `white_agent/config.py`:

```python
class AgentType(str, Enum):
    GPT4V = "gpt4v"
    CLAUDE = "claude"
    QWEN = "qwen"
    O3 = "o3"
    GEMINI = "gemini"
    MY_AGENT = "my_agent"  # Add this
```

---

## Running Your Agent

### Via Environment Variables

```bash
# Set agent type and model
export AGENT_TYPE=my_agent
export MODEL=my-model-name
export API_KEY=your-api-key

# Run REST server
python -m white_agent.rest.server

# Or run A2A server
python -m white_agent.a2a.server
```

### Via Code

```python
from white_agent.config import AgentConfig
from white_agent.agents import create_agent

# Create configuration
config = AgentConfig(
    agent_type="my_agent",
    model="my-model-name",
    api_key="your-api-key",
    temperature=0.7,
    max_tokens=1500,
)

# Create agent
agent = create_agent(config)

# Use agent
observation = {
    "screenshot": screenshot_bytes,
    "accessibility_tree": a11y_xml,  # optional
}
reasoning, action = agent.predict("Turn on Bluetooth", observation)
```

---

## Example: LangChain Agent

Here's a complete example using LangChain with GPT-4V:

```python
# white_agent/agents/langchain_agent.py

"""
LangChain Agent Implementation.
"""

import base64
import logging
from typing import Any, Dict, Tuple

from .base import BaseAgent
from ..config import AgentConfig

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a GUI automation agent. Analyze the screenshot and determine the next action.

Output format:
Thought: <your reasoning>
Action: <pyautogui command>

Available actions:
- pyautogui.click(x, y)
- pyautogui.doubleClick(x, y)
- pyautogui.write('text')
- pyautogui.hotkey('key1', 'key2')
- pyautogui.scroll(amount)
- DONE (task complete)
- FAIL (task impossible)
"""


class LangChainAgent(BaseAgent):
    """LangChain-based agent for OSWorld tasks."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._llm = None

    def ensure_initialized(self) -> None:
        if self._initialized:
            return

        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError("Install langchain-openai: pip install langchain-openai")

        api_key = self.config.get_api_key()

        self._llm = ChatOpenAI(
            model=self.config.model,
            api_key=api_key,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        logger.info(f"Initialized LangChainAgent with model={self.config.model}")
        self._initialized = True

    def predict(
        self,
        instruction: str,
        observation: Dict[str, Any]
    ) -> Tuple[str, str]:
        self.ensure_initialized()

        from langchain_core.messages import HumanMessage, SystemMessage

        # Convert screenshot to base64
        screenshot_bytes = observation["screenshot"]
        image_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        # Build messages
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=[
                {"type": "text", "text": f"Task: {instruction}"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                },
            ]),
        ]

        # Add trajectory context
        trajectory = self.get_trajectory_context()
        if trajectory:
            history_text = "\n".join(
                f"Step {s['step']}: {s['action']}" for s in trajectory
            )
            messages[1].content.insert(0, {
                "type": "text",
                "text": f"Previous actions:\n{history_text}"
            })

        # Call LLM
        response = self._llm.invoke(messages)
        response_text = response.content

        # Parse response
        reasoning, action = self._parse_response(response_text)

        self.add_to_history(thought=reasoning, action=action)
        return reasoning, action

    def _parse_response(self, response: str) -> Tuple[str, str]:
        """Parse LLM response into reasoning and action."""
        lines = response.strip().split("\n")

        reasoning = ""
        action = "FAIL"

        for line in lines:
            line = line.strip()
            if line.lower().startswith("thought:"):
                reasoning = line[8:].strip()
            elif line.lower().startswith("action:"):
                action = line[7:].strip()

        # Fallback: use full response as reasoning
        if not reasoning:
            reasoning = response

        return reasoning, action

    def reset(self) -> None:
        super().reset()
```

### Register and Use

```python
# Register
from white_agent.agents import register_agent
from white_agent.agents.langchain_agent import LangChainAgent
register_agent("langchain", LangChainAgent)

# Use
from white_agent.config import AgentConfig
from white_agent.agents import create_agent

config = AgentConfig(agent_type="langchain", model="gpt-4o")
agent = create_agent(config)
reasoning, action = agent.predict(instruction, observation)
```

---

## REST API Reference

When using the REST server, here's the API format:

### Request: `POST /task`

```json
{
    "task_id": "task_123",
    "context_id": "ctx_456",
    "message": "optional message",
    "metadata": {
        "observation": {
            "frame_id": 0,
            "image_png_b64": "<base64 encoded PNG>",
            "instruction": "Turn on Bluetooth",
            "accessibility_tree": "<xml>...</xml>",
            "done": false
        }
    }
}
```

### Response

```json
{
    "message_id": "uuid-string",
    "task_id": "task_123",
    "context_id": "ctx_456",
    "role": "agent",
    "content": "Step 0: I see the settings panel and will click on Bluetooth toggle.",
    "metadata": {
        "action": {
            "op": "click",
            "args": {"x": 150, "y": 300}
        },
        "step": 0,
        "done": false,
        "raw_actions": "pyautogui.click(150, 300)"
    }
}
```

---

## Configuration Reference

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENT_TYPE` | Agent type (gpt4v, claude, qwen, etc.) | `gpt4v` |
| `MODEL` | Model name/ID | Varies by agent type |
| `API_KEY` | API key (or use provider-specific) | - |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `DASHSCOPE_API_KEY` | DashScope API key | - |
| `TEMPERATURE` | Sampling temperature | `1.0` |
| `MAX_TOKENS` | Maximum tokens to generate | `1500` |
| `TOP_P` | Top-p sampling | `0.9` |
| `OSWORLD_OBS_TYPE` | Observation type | `screenshot` |
| `ENABLE_THINKING` | Enable thinking mode (Claude/Qwen) | `false` |

### AgentConfig Fields

```python
AgentConfig(
    agent_type: str = "gpt4v",
    model: str = "gpt-4o",
    api_key: str | None = None,
    api_base_url: str | None = None,
    temperature: float = 1.0,
    max_tokens: int = 1500,
    top_p: float = 0.9,
    observation_type: str = "screenshot",
    action_space: str = "pyautogui",
    max_trajectory_length: int = 3,
    provider_config: Dict[str, Any] = {},
)
```

---

## Tips & Best Practices

1. **Lazy Initialization**: Always use `ensure_initialized()` pattern to avoid blocking on startup.

2. **Track History**: Use `self.add_to_history()` to enable trajectory context in prompts.

3. **Handle Both Observation Types**: Support both screenshot-only and screenshot+a11y_tree.

4. **Return Valid Actions**: Ensure your action string is in pyautogui format or valid JSON.

5. **Error Handling**: Return `"FAIL"` action if the task cannot be completed.

6. **Logging**: Use the logger to help debug issues:
   ```python
   logger.info(f"Processing instruction: {instruction[:50]}...")
   logger.debug(f"Full response: {response}")
   ```

7. **Reset State**: Implement `reset()` to clear any conversation history between tasks.
