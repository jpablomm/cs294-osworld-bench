# White Agent Development Guide

**Version:** 1.0
**Date:** November 11, 2025
**Target Audience:** Developers creating white agents for AgentBeats A2A assessments

---

## Overview

This guide explains how to develop a "white agent" (agent under test) that works with the Green Agent assessment system. White agents are evaluated by the Green Agent using the A2A (Agent-to-Agent) protocol for standardized, benchmark-agnostic assessment.

**Key Concepts:**
- **Green Agent:** Assessment orchestrator that coordinates testing
- **White Agent:** Your agent being tested (the system under evaluation)
- **A2A Protocol:** Standardized communication protocol for agent assessment
- **OSWorld:** Desktop automation benchmark used for evaluation

---

## Table of Contents

1. [Requirements](#requirements)
2. [A2A Protocol Overview](#a2a-protocol-overview)
3. [Required Endpoints](#required-endpoints)
4. [Request/Response Format](#requestresponse-format)
5. [Tool Usage](#tool-usage)
6. [Complete Examples](#complete-examples)
7. [Testing Your Agent](#testing-your-agent)
8. [Common Issues](#common-issues)
9. [Best Practices](#best-practices)

---

## Requirements

### Technical Requirements

- **Protocol:** HTTP REST API
- **Format:** JSON request/response bodies
- **Endpoints:** Must implement `/agent-card` and `/task`
- **Concurrency:** Must handle sequential requests (context management)
- **Timeout:** Respond to each request within 120 seconds

### Functional Requirements

- **Tool Understanding:** Parse tool descriptions from task messages
- **Action Selection:** Choose appropriate actions based on observations
- **Format Compliance:** Return actions in specified JSON format
- **Statefulness:** Maintain conversation context across requests

---

## A2A Protocol Overview

The A2A protocol defines how assessment systems (green agents) communicate with agents under test (white agents). The protocol is:

- **Self-Explanatory:** Task messages include all necessary information (tools, format, instructions)
- **Benchmark-Agnostic:** No OSWorld-specific knowledge required
- **Standardized:** Consistent request/response format
- **Observation-Driven:** Agents receive screenshots and make decisions

### Communication Flow

```
┌─────────────┐                           ┌──────────────┐
│   Green     │                           │    White     │
│   Agent     │                           │    Agent     │
└──────┬──────┘                           └──────┬───────┘
       │                                          │
       │  1. POST /task                           │
       │  (task description + tools)              │
       ├─────────────────────────────────────────>│
       │                                          │
       │  2. A2A Message Response                 │
       │  (action to execute)                     │
       │<─────────────────────────────────────────┤
       │                                          │
       │  3. [Execute action on VM]               │
       │                                          │
       │  4. POST /task                           │
       │  (new observation/screenshot)            │
       ├─────────────────────────────────────────>│
       │                                          │
       │  5. A2A Message Response                 │
       │  (next action)                           │
       │<─────────────────────────────────────────┤
       │                                          │
       │  ... repeat until done ...               │
```

---

## Required Endpoints

### 1. Agent Card Endpoint

**URL:** `GET /agent-card`

**Purpose:** Provide metadata about your agent's capabilities.

**Response Format:**
```json
{
  "name": "Your Agent Name",
  "version": "1.0.0",
  "description": "Brief description of your agent",
  "protocols": ["a2a", "rest"],
  "capabilities": [
    "desktop-automation",
    "vision-language-reasoning",
    "screen-observation"
  ],
  "supported_domains": ["chrome", "libreoffice", "os", "multi-app"],
  "max_steps": 15,
  "metadata": {
    "model": "gpt-4v",
    "temperature": 0.7
  }
}
```

**Required Fields:**
- `name` (string): Human-readable agent name
- `version` (string): Semantic version
- `protocols` (array): Must include `"a2a"`
- `capabilities` (array): List of capabilities

**Example:**
```bash
curl http://localhost:9002/agent-card
```

### 2. Task Endpoint

**URL:** `POST /task`

**Purpose:** Receive tasks and observations, return actions.

**Request Format:**
```json
{
  "task_id": "unique-task-identifier",
  "context_id": "conversation-context-id",
  "message": "Task description with tool documentation...",
  "metadata": {
    "observation": {
      "frame_id": 0,
      "image_png_b64": "base64-encoded-screenshot",
      "instruction": "Task instruction",
      "done": false
    },
    "tools": [ /* tool specifications */ ],
    "max_steps": 15
  }
}
```

**Response Format:**
```json
{
  "role": "assistant",
  "content": "Natural language explanation of action",
  "metadata": {
    "action": {
      "op": "tool_name",
      "args": {
        "param1": "value1",
        "param2": "value2"
      }
    },
    "done": false,
    "reasoning": "Optional: Why this action was chosen"
  }
}
```

**Required Response Fields:**
- `role` (string): Must be `"assistant"`
- `content` (string): Human-readable explanation
- `metadata` (object): Must contain `action`
- `metadata.action` (object): Must have `op` and `args` fields

---

## Request/Response Format

### Task Request Structure

#### Top-Level Fields

```json
{
  "task_id": "string",      // Unique identifier for this assessment
  "context_id": "string",   // Conversation context (may be same as task_id)
  "message": "string",      // Task description with embedded tool docs
  "metadata": { ... }       // Additional data (observations, tools, config)
}
```

#### Metadata Structure

```json
{
  "observation": {
    "frame_id": 0,                    // Step number
    "image_png_b64": "base64...",     // Screenshot as base64 PNG
    "instruction": "string",           // Task instruction
    "done": false                      // Whether task is complete
  },
  "tools": [                          // Available tool specifications
    {
      "name": "tool_name",
      "description": "...",
      "parameters": { /* JSON Schema */ },
      "returns": { /* return spec */ },
      "examples": [ /* usage examples */ ]
    }
  ],
  "max_steps": 15                     // Maximum steps allowed
}
```

#### Message Format (Tool Documentation)

The `message` field contains a formatted description of available tools and the task:

```markdown
# Available Tools

You have access to the following tools for desktop automation:

## screenshot

Capture a screenshot of the current desktop state...

**Parameters:** None

**Returns:** PNG image of the desktop

**Examples:**
- Capture current screen state:
  ```json
  {"op": "screenshot"}
  ```

## click

Perform a mouse click at specific screen coordinates...

**Parameters:**
- `x` (integer, required) [min: 0, max: 1920]: Horizontal position...
- `y` (integer, required) [min: 0, max: 1080]: Vertical position...

**Returns:** Confirmation of click execution

**Examples:**
- Click center of screen:
  ```json
  {"op": "click", "args": {"x": 960, "y": 540}}
  ```

---

**Action Format:** Return actions as JSON with `op` (operation name) and `args` (parameters) fields:
```json
{"op": "tool_name", "args": {"param1": "value1", "param2": "value2"}}
```

# Task

Open the Chrome browser and navigate to google.com

**Instructions:**
1. Take a screenshot first to observe the current state
2. Analyze what you see and decide on the appropriate action
3. Execute actions using the format shown above
4. After important actions, take another screenshot to verify results
5. Continue until the task is complete
6. When finished, return {"op": "done"}

You have a maximum of 15 steps to complete the task.
```

### Response Structure

Your agent must return an A2A message with this structure:

```json
{
  "role": "assistant",
  "content": "I'll click on the Chrome icon to launch the browser.",
  "metadata": {
    "action": {
      "op": "click",
      "args": {
        "x": 150,
        "y": 800
      }
    },
    "done": false,
    "reasoning": "Observed Chrome icon in dock at bottom-left of screen",
    "confidence": 0.95
  }
}
```

**Field Descriptions:**

- **`role`** (required, string): Must be `"assistant"`
- **`content`** (required, string): Natural language explanation of what you're doing
- **`metadata`** (required, object):
  - **`action`** (required, object):
    - **`op`** (required, string): Tool name (must match a tool from the task message)
    - **`args`** (required, object): Parameters for the tool (keys must match tool parameter names)
  - **`done`** (optional, boolean): Set to `true` when task is complete
  - **`reasoning`** (optional, string): Why you chose this action
  - **`confidence`** (optional, number): Confidence score 0.0-1.0

### Error Response

If your agent encounters an error, return:

```json
{
  "role": "assistant",
  "content": "I encountered an error processing this request.",
  "metadata": {
    "error": "Error description",
    "error_type": "ValueError|RuntimeError|TimeoutError|...",
    "done": false
  }
}
```

---

## Tool Usage

### Available Tools

The green agent provides these tools for desktop automation:

| Tool | Purpose | Required Parameters |
|------|---------|---------------------|
| `screenshot` | Capture screen | None |
| `click` | Mouse click | `x`, `y` |
| `type_text` | Keyboard input | `text` |
| `hotkey` | Keyboard shortcut | `keys` (array) |
| `execute_python` | Run Python code | `code` |
| `execute_command` | Run shell command | `command` |
| `wait` | Pause execution | `duration` (optional) |

### Tool Calling Format

All actions must be returned in this format:

```json
{
  "op": "tool_name",
  "args": {
    "param1": "value1",
    "param2": "value2"
  }
}
```

### Tool Examples

#### 1. Screenshot (Observation)

```json
{
  "role": "assistant",
  "content": "Taking a screenshot to see the current state of the desktop.",
  "metadata": {
    "action": {
      "op": "screenshot"
    }
  }
}
```

#### 2. Click (Mouse Action)

```json
{
  "role": "assistant",
  "content": "Clicking the Chrome icon in the dock.",
  "metadata": {
    "action": {
      "op": "click",
      "args": {
        "x": 150,
        "y": 800,
        "button": "left"
      }
    }
  }
}
```

#### 3. Type Text (Keyboard Input)

```json
{
  "role": "assistant",
  "content": "Typing 'google.com' in the address bar.",
  "metadata": {
    "action": {
      "op": "type_text",
      "args": {
        "text": "google.com"
      }
    }
  }
}
```

#### 4. Hotkey (Keyboard Shortcut)

```json
{
  "role": "assistant",
  "content": "Pressing Ctrl+L to focus the address bar.",
  "metadata": {
    "action": {
      "op": "hotkey",
      "args": {
        "keys": ["ctrl", "l"]
      }
    }
  }
}
```

#### 5. Wait (Timing)

```json
{
  "role": "assistant",
  "content": "Waiting 2 seconds for the page to load.",
  "metadata": {
    "action": {
      "op": "wait",
      "args": {
        "duration": 2.0
      }
    }
  }
}
```

#### 6. Done (Task Completion)

```json
{
  "role": "assistant",
  "content": "Task completed successfully. Chrome is open and showing google.com.",
  "metadata": {
    "action": {
      "op": "done"
    },
    "done": true
  }
}
```

### Parameter Validation

The green agent validates all parameters. Ensure:

- **Type matching:** String params must be strings, integers must be integers
- **Required params:** All required parameters must be provided
- **Bounds:** Numeric parameters must be within specified ranges
  - `x`: 0-1920 (screen width)
  - `y`: 0-1080 (screen height)
  - `duration`: 0.1-30.0 seconds
- **Enums:** String parameters must match allowed values
  - `button`: "left", "right", or "middle"

---

## Complete Examples

### Example 1: Minimal Python Agent

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import base64
from PIL import Image
import io

app = FastAPI()

class A2ATask(BaseModel):
    task_id: str
    context_id: str
    message: str
    metadata: Dict[str, Any]

class A2AMessage(BaseModel):
    role: str
    content: str
    metadata: Dict[str, Any]

# Simple context storage
contexts = {}

@app.get("/agent-card")
async def agent_card():
    return {
        "name": "Minimal White Agent",
        "version": "1.0.0",
        "protocols": ["a2a"],
        "capabilities": ["desktop-automation"]
    }

@app.post("/task")
async def task(task: A2ATask) -> A2AMessage:
    context_id = task.context_id

    # Initialize context if new
    if context_id not in contexts:
        contexts[context_id] = {"step": 0, "history": []}

    ctx = contexts[context_id]
    ctx["step"] += 1

    # Get observation
    obs = task.metadata.get("observation", {})
    screenshot_b64 = obs.get("image_png_b64")

    # Decode screenshot
    if screenshot_b64:
        img_data = base64.b64decode(screenshot_b64)
        image = Image.open(io.BytesIO(img_data))
        # TODO: Analyze image with your model
        # analysis = your_vlm_model(image, task.message)

    # Simple logic: take screenshot, then click, then done
    if ctx["step"] == 1:
        action = {"op": "screenshot"}
        content = "Taking initial screenshot"
    elif ctx["step"] == 2:
        action = {"op": "click", "args": {"x": 960, "y": 540}}
        content = "Clicking center of screen"
    else:
        action = {"op": "done"}
        content = "Task complete"

    return A2AMessage(
        role="assistant",
        content=content,
        metadata={"action": action, "done": (ctx["step"] >= 3)}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9002)
```

### Example 2: Vision-Language Model Agent

See `white_agent/gpt4v_server.py` for a complete production example using GPT-4V.

Key components:
1. **Context Management:** Track conversation history per `context_id`
2. **Vision Processing:** Decode base64 screenshots and analyze with VLM
3. **Action Parsing:** Extract structured actions from LLM responses
4. **Error Handling:** Return proper error responses
5. **Health Checks:** Implement `/health` endpoint for monitoring

---

## Testing Your Agent

### 1. Standalone Testing

Test your agent endpoints directly:

```bash
# Test agent card
curl http://localhost:9002/agent-card

# Test task endpoint with minimal request
curl -X POST http://localhost:9002/task \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "test-1",
    "context_id": "test-1",
    "message": "Test task",
    "metadata": {
      "observation": {
        "frame_id": 0,
        "image_png_b64": "",
        "instruction": "Test",
        "done": false
      }
    }
  }'
```

### 2. Integration Testing

Use the provided test script:

```bash
# Run white agent tests
.venv/bin/python tests/test_gpt4v_standalone.py
```

### 3. End-to-End Assessment

Run a full assessment with the green agent:

```bash
# Start your white agent
uvicorn your_agent.server:app --port 9002 &

# Start green agent
uvicorn orchestrator.a2a_green_agent:app --port 8001 &

# Run assessment
.venv/bin/python launcher_a2a.py \
  --task-id <osworld-task-id> \
  --white-agent-url http://localhost:9002 \
  --green-agent-url http://localhost:8001 \
  --max-steps 15
```

### 4. Response Validation

The green agent validates all responses. Common validation errors:

- **Missing required field:** `Response missing required field: role`
- **Invalid action structure:** `action missing required field: op`
- **Unknown operation:** `Unknown operation: invalid_tool`
- **Type mismatch:** `Parameter x must be integer, got string`
- **Missing parameter:** `Missing required parameter for click: x`

---

## Common Issues

### Issue 1: "Response missing required field: metadata"

**Cause:** Your response doesn't include the `metadata` field.

**Fix:**
```python
# WRONG
return {"role": "assistant", "content": "..."}

# CORRECT
return {
    "role": "assistant",
    "content": "...",
    "metadata": {"action": {"op": "screenshot"}}
}
```

### Issue 2: "Unknown operation: tool_name"

**Cause:** The `op` field doesn't match any available tool.

**Fix:** Check the tool names in the task message. Valid operations:
- `screenshot`, `click`, `type_text`, `hotkey`, `execute_python`, `execute_command`, `wait`, `done`

### Issue 3: "Parameter x must be integer, got string"

**Cause:** Parameter type mismatch.

**Fix:**
```python
# WRONG
{"op": "click", "args": {"x": "960", "y": "540"}}

# CORRECT
{"op": "click", "args": {"x": 960, "y": 540}}
```

### Issue 4: Context Not Maintained

**Cause:** Not tracking `context_id` across requests.

**Fix:** Store conversation history keyed by `context_id`:
```python
contexts = {}

@app.post("/task")
async def task(task: A2ATask):
    ctx_id = task.context_id
    if ctx_id not in contexts:
        contexts[ctx_id] = {"history": []}

    # Use context for decision making
    history = contexts[ctx_id]["history"]
    # ...
```

### Issue 5: Screenshot Decoding Errors

**Cause:** Incorrect base64 decoding or missing image data.

**Fix:**
```python
import base64
from PIL import Image
import io

screenshot_b64 = obs.get("image_png_b64", "")
if screenshot_b64:
    try:
        img_data = base64.b64decode(screenshot_b64)
        image = Image.open(io.BytesIO(img_data))
    except Exception as e:
        print(f"Screenshot decode error: {e}")
        # Return error response
```

---

## Best Practices

### 1. Tool Usage Patterns

**Always start with observation:**
```
Step 1: screenshot → See what's on screen
Step 2: click/type/etc → Take action
Step 3: screenshot → Verify result
```

**Use wait after async actions:**
```python
# After clicking a button that triggers loading
{"op": "click", "args": {"x": 500, "y": 300}}
# Next step:
{"op": "wait", "args": {"duration": 2.0}}
# Then verify:
{"op": "screenshot"}
```

### 2. Error Handling

Always wrap your logic in try-except:

```python
@app.post("/task")
async def task(task: A2ATask) -> A2AMessage:
    try:
        # Your logic here
        action = select_action(task)
        return A2AMessage(
            role="assistant",
            content="...",
            metadata={"action": action}
        )
    except Exception as e:
        return A2AMessage(
            role="assistant",
            content=f"Error: {str(e)}",
            metadata={"error": str(e), "done": False}
        )
```

### 3. Context Management

Track conversation state properly:

```python
contexts = {
    "context-id-1": {
        "step": 5,
        "history": [
            {"step": 0, "action": "screenshot", "observation": "..."},
            {"step": 1, "action": "click", "result": "..."},
            # ...
        ],
        "task_state": "in_progress",
        "completed": False
    }
}
```

### 4. Logging

Log key events for debugging:

```python
import logging

logger = logging.getLogger(__name__)

@app.post("/task")
async def task(task: A2ATask) -> A2AMessage:
    logger.info(f"Received task: {task.task_id}, step: {task.metadata['observation']['frame_id']}")

    action = select_action(task)

    logger.info(f"Selected action: {action['op']}")

    return A2AMessage(...)
```

### 5. Health Monitoring

Implement health check:

```python
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "agent_type": "white",
        "protocol": "a2a",
        "active_contexts": len(contexts),
        "model_loaded": True  # Check if your model is ready
    }
```

---

## Performance Optimization

### 1. Response Time

- Target: < 10 seconds per action
- Screenshot analysis: < 5 seconds
- Action selection: < 2 seconds
- Network overhead: < 1 second

### 2. Memory Management

```python
# Limit context history size
MAX_HISTORY_LENGTH = 50

if len(contexts[ctx_id]["history"]) > MAX_HISTORY_LENGTH:
    contexts[ctx_id]["history"] = contexts[ctx_id]["history"][-MAX_HISTORY_LENGTH:]

# Clean up old contexts
import time
CONTEXT_TIMEOUT = 3600  # 1 hour

def cleanup_old_contexts():
    now = time.time()
    to_delete = []
    for ctx_id, ctx in contexts.items():
        if now - ctx.get("last_access", 0) > CONTEXT_TIMEOUT:
            to_delete.append(ctx_id)
    for ctx_id in to_delete:
        del contexts[ctx_id]
```

### 3. Concurrency

The green agent sends sequential requests, but you should handle:

- Multiple concurrent assessments (different `task_id`)
- Proper context isolation (keyed by `context_id`)
- Thread-safe context storage (use locks if needed)

---

## Debugging Checklist

- [ ] Agent card endpoint returns valid JSON with required fields
- [ ] Task endpoint accepts A2ATask format
- [ ] Responses include `role`, `content`, and `metadata.action`
- [ ] Action `op` matches available tool names
- [ ] Action `args` match tool parameter types and names
- [ ] Required parameters are always provided
- [ ] Coordinate parameters are within screen bounds (0-1920, 0-1080)
- [ ] Context is maintained across requests (by `context_id`)
- [ ] Screenshots are properly decoded from base64
- [ ] Errors return proper error response format
- [ ] Health endpoint responds (if implemented)
- [ ] Logs show action selection reasoning

---

## References

- [A2A Protocol Specification](../README.md)
- [Tool Description Format](./TOOL_DESCRIPTION_FORMAT.md)
- [AgentBeats Guidelines](https://agentbeats.org)
- [Example: GPT-4V White Agent](../white_agent/gpt4v_server.py)
- [Troubleshooting Guide](./troubleshooting/A2A_PROTOCOL.md)

---

## Support

For issues or questions:
- Check the troubleshooting guide
- Review example implementations
- Examine green agent logs for validation errors
- Test endpoints individually before integration

---

**Version History:**

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-11 | Initial release |
