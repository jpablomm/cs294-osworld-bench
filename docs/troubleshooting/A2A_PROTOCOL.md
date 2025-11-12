# A2A Protocol Troubleshooting Guide

**Version:** 1.0
**Date:** November 11, 2025
**Last Updated:** November 11, 2025

---

## Quick Diagnostic Steps

When encountering A2A protocol issues, follow these steps:

1. **Check service health:**
   ```bash
   curl http://localhost:8001/health  # Green agent
   curl http://localhost:9002/health  # White agent
   ```

2. **Verify connectivity:**
   ```bash
   curl http://localhost:9002/agent-card
   ```

3. **Check logs:**
   - Green agent: Console output from uvicorn
   - White agent: Console output from uvicorn
   - OSWorld: SSH to VM → `journalctl -u osworld-server`

4. **Test minimal request:**
   ```bash
   curl -X POST http://localhost:9002/task \
     -H "Content-Type: application/json" \
     -d '{"task_id":"test","context_id":"test","message":"test","metadata":{"observation":{"frame_id":0,"image_png_b64":"","instruction":"test","done":false}}}'
   ```

---

## Common Issues

### 1. White Agent Not Responding

#### Symptoms
- `Connection refused` errors
- Timeout errors during assessment
- No response from `/agent-card` endpoint

#### Diagnostic Commands
```bash
# Check if white agent is running
lsof -i :9002
ps aux | grep "white_agent"

# Test connectivity
curl -v http://localhost:9002/health
```

#### Solutions

**If not running:**
```bash
# Start white agent
cd /path/to/green_agent
.venv/bin/uvicorn white_agent.gpt4v_server:app --port 9002
```

**If running but not responding:**
1. Check logs for errors
2. Verify port 9002 is not blocked by firewall
3. Restart the service:
   ```bash
   pkill -f "white_agent.gpt4v_server"
   .venv/bin/uvicorn white_agent.gpt4v_server:app --port 9002
   ```

**If running on different host:**
```bash
# Verify URL is correct
curl http://<white-agent-host>:9002/agent-card

# Check network connectivity
ping <white-agent-host>
telnet <white-agent-host> 9002
```

---

### 2. Invalid White Agent Response

#### Symptoms
- Error: `Response missing required field: role`
- Error: `Response missing required field: metadata`
- Error: `action missing required field: op`

#### Example Error Log
```
ERROR Invalid white agent response: Response missing required field: metadata
Full response: {'role': 'assistant', 'content': '...'}
```

#### Root Cause
White agent not returning proper A2A message format.

#### Solutions

**Check response structure:**
```python
# WRONG - Missing metadata
{
    "role": "assistant",
    "content": "I'll take a screenshot"
}

# CORRECT
{
    "role": "assistant",
    "content": "I'll take a screenshot",
    "metadata": {
        "action": {
            "op": "screenshot"
        }
    }
}
```

**Validate your response:**
```python
from pydantic import BaseModel, ValidationError

class A2AMessage(BaseModel):
    role: str
    content: str
    metadata: dict

# Test your response
try:
    response = A2AMessage(**your_response_dict)
    print("✓ Valid A2A message")
except ValidationError as e:
    print(f"✗ Invalid: {e}")
```

**Debug white agent:**
1. Add logging before returning response
2. Print the response JSON
3. Verify structure matches specification
4. Check that `metadata.action` exists

---

### 3. Unknown Operation Error

#### Symptoms
- Error: `Unknown operation: tool_name`
- Error: `Tool specification not found for: tool_name`

#### Example Error Log
```
ERROR Invalid white agent response: Unknown operation: mouse_click. Valid operations: screenshot, click, type_text, hotkey, execute_python, execute_command, wait
```

#### Root Cause
Action `op` field doesn't match any available tool name.

#### Solutions

**Valid tool names:**
- `screenshot`
- `click`
- `type_text`
- `hotkey`
- `execute_python`
- `execute_command`
- `wait`
- `done`

**Check your action:**
```python
# WRONG - Invalid tool name
{"op": "mouse_click", "args": {"x": 100, "y": 100}}

# CORRECT
{"op": "click", "args": {"x": 100, "y": 100}}
```

**Parse tool names from message:**
```python
import re

def extract_tool_names(task_message: str) -> list[str]:
    """Extract available tool names from task message"""
    pattern = r'^## (\w+)$'
    matches = re.findall(pattern, task_message, re.MULTILINE)
    return matches

# Use this to validate your op
tools = extract_tool_names(task.message)
if action["op"] not in tools and action["op"] != "done":
    print(f"Invalid op: {action['op']}. Valid: {tools}")
```

---

### 4. Parameter Type Mismatch

#### Symptoms
- Error: `Parameter x must be integer, got string`
- Error: `Parameter text must be string, got int`

#### Example Error Log
```
ERROR Invalid white agent response: Parameter x must be integer, got string
```

#### Root Cause
Parameter value type doesn't match tool specification.

#### Solutions

**Common type errors:**
```python
# WRONG - Coordinates as strings
{"op": "click", "args": {"x": "960", "y": "540"}}

# CORRECT - Coordinates as integers
{"op": "click", "args": {"x": 960, "y": 540}}

# WRONG - Text as number
{"op": "type_text", "args": {"text": 123}}

# CORRECT - Text as string
{"op": "type_text", "args": {"text": "123"}}

# WRONG - Keys as string
{"op": "hotkey", "args": {"keys": "ctrl+c"}}

# CORRECT - Keys as array
{"op": "hotkey", "args": {"keys": ["ctrl", "c"]}}
```

**Type conversion:**
```python
# Ensure correct types
action = {
    "op": "click",
    "args": {
        "x": int(x_value),  # Force integer
        "y": int(y_value),
        "button": str(button)  # Force string
    }
}
```

---

### 5. Missing Required Parameter

#### Symptoms
- Error: `Missing required parameter for click: x`
- Error: `Missing required parameter for type_text: text`

#### Example Error Log
```
ERROR Invalid white agent response: Missing required parameter for click: y
Full response action: {'op': 'click', 'args': {'x': 960}}
```

#### Root Cause
Required parameter not provided in `args`.

#### Solutions

**Check required parameters:**

| Tool | Required Parameters |
|------|---------------------|
| `screenshot` | None |
| `click` | `x`, `y` |
| `type_text` | `text` |
| `hotkey` | `keys` |
| `execute_python` | `code` |
| `execute_command` | `command` |
| `wait` | None (`duration` is optional) |
| `done` | None |

**Validate before sending:**
```python
def validate_action(op: str, args: dict) -> tuple[bool, str]:
    """Validate action has required parameters"""
    required = {
        "click": ["x", "y"],
        "type_text": ["text"],
        "hotkey": ["keys"],
        "execute_python": ["code"],
        "execute_command": ["command"]
    }

    if op in required:
        for param in required[op]:
            if param not in args:
                return False, f"Missing required parameter: {param}"

    return True, ""

# Use before returning action
is_valid, error = validate_action(action["op"], action["args"])
if not is_valid:
    print(f"Invalid action: {error}")
```

---

### 6. Parameter Out of Bounds

#### Symptoms
- Error: `X coordinate out of bounds`
- Error: `Y coordinate out of bounds`
- Action execution fails

#### Example Error Log
```
ERROR Action execution failed: X coordinate 2500 out of bounds (0-1920)
```

#### Root Cause
Coordinate or numeric parameter exceeds allowed range.

#### Parameter Bounds

| Parameter | Min | Max | Tool |
|-----------|-----|-----|------|
| `x` | 0 | 1920 | `click` |
| `y` | 0 | 1080 | `click` |
| `duration` | 0.1 | 30.0 | `wait` |

#### Solutions

**Clamp coordinates:**
```python
def clamp_coordinate(value: int, min_val: int, max_val: int) -> int:
    """Clamp value to valid range"""
    return max(min_val, min(max_val, value))

x = clamp_coordinate(x, 0, 1920)
y = clamp_coordinate(y, 0, 1080)

action = {"op": "click", "args": {"x": x, "y": y}}
```

**Screen resolution assumptions:**
- Width: 1920 pixels (typical)
- Height: 1080 pixels (typical)
- Origin: (0, 0) at top-left

---

### 7. VM Not Ready

#### Symptoms
- Error: `VM did not become ready within 600 seconds`
- Timeout during VM startup
- OSWorld server not responding

#### Example Error Log
```
ERROR VM 10.128.0.50 did not become ready within 600 seconds
INFO Will cleanup VM assessment-123 due to timeout
```

#### Diagnostic Commands

**Check VM status:**
```bash
# List VMs
gcloud compute instances list

# Check specific VM
gcloud compute instances describe <vm-name> --zone=us-central1-a

# Check OSWorld server
VM_IP=$(gcloud compute instances describe <vm-name> --zone=us-central1-a --format="get(networkInterfaces[0].accessConfigs[0].natIP)")
curl http://$VM_IP:5000/platform
```

**SSH to VM and check logs:**
```bash
gcloud compute ssh <vm-name> --zone=us-central1-a

# On VM:
sudo systemctl status osworld-server
sudo journalctl -u osworld-server --since "5 minutes ago"
```

#### Solutions

**If VM is slow to start:**
1. Increase timeout (currently 600s):
   ```python
   # In a2a_green_agent.py line 313
   timeout=900  # Increase to 15 minutes
   ```

**If OSWorld service not running:**
```bash
# SSH to VM
gcloud compute ssh <vm-name> --zone=us-central1-a

# Start service
sudo systemctl start osworld-server
sudo systemctl status osworld-server
```

**If firewall blocking:**
```bash
# Check firewall rules
gcloud compute firewall-rules list | grep 5000

# Create rule if missing
gcloud compute firewall-rules create allow-osworld \
  --allow=tcp:5000 \
  --source-ranges=0.0.0.0/0
```

**If VM stuck:**
1. Stop assessment
2. Manually delete VM:
   ```bash
   gcloud compute instances delete <vm-name> --zone=us-central1-a
   ```
3. Retry assessment

---

### 8. Evaluation Failed

#### Symptoms
- Error: `Evaluation error: ...`
- Error: `missing_evaluator_config`
- Incorrect success/failure determination

#### Example Error Log
```
ERROR Evaluation error: No evaluator config found
INFO Task marked as failed due to missing evaluator
```

#### Root Cause
- OSWorld task missing evaluator configuration
- Evaluator execution failed
- Ground truth check error

#### Solutions

**Check task has evaluator:**
```python
# Load task
task = task_executor.load_osworld_task(task_id)

# Verify evaluator exists
if "evaluator" not in task:
    print("❌ Task missing evaluator config")
else:
    print(f"✓ Evaluator: {task['evaluator']}")
```

**Check evaluator structure:**
```json
{
  "task_id": "...",
  "instruction": "...",
  "evaluator": {
    "func": "check_file_exists",
    "result": {
      "type": "vm_file",
      "path": "/home/user/test.txt"
    },
    "expected": true
  }
}
```

**Test evaluator manually:**
```python
from green_agent.osworld_evaluator import evaluate_task

# Test evaluation
score = evaluate_task(
    vm_ip="<vm-ip>",
    evaluator_config=task["evaluator"],
    trajectory=[]
)
print(f"Score: {score}")
```

**Common evaluator errors:**
- File path doesn't exist
- Database query fails
- UI element not found
- Timeout waiting for condition

---

### 9. Assessment Timeout

#### Symptoms
- Assessment runs longer than expected
- White agent takes too long to respond
- Stuck in assessment loop

#### Example Error Log
```
WARNING Step 14/15
WARNING Step 15/15
INFO Max steps reached
```

#### Root Cause
- Too many steps taken
- White agent slow to respond
- Infinite loop in decision making

#### Solutions

**Increase max steps:**
```bash
# In launcher
.venv/bin/python launcher_a2a.py \
  --max-steps 30  # Increase from default 15
```

**Optimize white agent:**
1. Cache vision model
2. Reduce image processing time
3. Use faster LLM
4. Implement timeout on LLM calls:
   ```python
   import asyncio

   async def call_llm_with_timeout(prompt, timeout=30):
       try:
           return await asyncio.wait_for(
               llm.generate(prompt),
               timeout=timeout
           )
       except asyncio.TimeoutError:
           return default_action()
   ```

**Monitor step usage:**
```python
# In white agent
if ctx["step"] >= 10:
    logger.warning(f"High step count: {ctx['step']}")
    # Consider finishing task
```

**Detect loops:**
```python
def detect_action_loop(history: list, window=3) -> bool:
    """Detect if repeating same actions"""
    if len(history) < window * 2:
        return False

    recent = history[-window:]
    previous = history[-window*2:-window]

    return all(
        r["action"] == p["action"]
        for r, p in zip(recent, previous)
    )

if detect_action_loop(ctx["history"]):
    logger.warning("Action loop detected, finishing task")
    return done_action()
```

---

### 10. Screenshot Issues

#### Symptoms
- Base64 decode errors
- Image format errors
- Empty screenshots

#### Example Error Log
```
ERROR Screenshot decode error: Invalid base64 string
ERROR PIL.UnidentifiedImageError: cannot identify image file
```

#### Solutions

**Validate screenshot data:**
```python
import base64
from PIL import Image
import io

def validate_screenshot(screenshot_b64: str) -> tuple[bool, str]:
    """Validate screenshot data"""
    if not screenshot_b64:
        return False, "Empty screenshot data"

    try:
        # Decode base64
        img_data = base64.b64decode(screenshot_b64)

        # Try to open as image
        image = Image.open(io.BytesIO(img_data))

        # Check dimensions
        if image.size == (0, 0):
            return False, "Zero-size image"

        return True, "Valid screenshot"
    except Exception as e:
        return False, f"Validation error: {e}"

# Use in white agent
is_valid, msg = validate_screenshot(obs["image_png_b64"])
if not is_valid:
    logger.error(f"Screenshot invalid: {msg}")
```

**Handle missing screenshots:**
```python
obs = task.metadata.get("observation", {})
screenshot_b64 = obs.get("image_png_b64", "")

if not screenshot_b64:
    # First step - no screenshot yet
    # Just request one
    return A2AMessage(
        role="assistant",
        content="Requesting screenshot",
        metadata={"action": {"op": "screenshot"}}
    )
```

---

## Debugging Tools

### 1. Manual Response Testing

Test white agent responses:

```python
#!/usr/bin/env python3
"""Test white agent response validation"""
import sys
sys.path.insert(0, ".")

from orchestrator.a2a_green_agent import _validate_white_agent_response, _build_osworld_tool_descriptions

# Build tools
tools = _build_osworld_tool_descriptions("10.128.0.10")

# Test response
response = {
    "role": "assistant",
    "content": "I'll click the button",
    "metadata": {
        "action": {
            "op": "click",
            "args": {"x": 960, "y": 540}
        }
    }
}

is_valid, error, action = _validate_white_agent_response(response, tools)

if is_valid:
    print(f"✓ Valid response")
    print(f"Action: {action}")
else:
    print(f"✗ Invalid: {error}")
```

### 2. Log Analysis

Extract errors from logs:

```bash
# Green agent errors
grep "ERROR" green_agent.log | tail -20

# White agent errors
grep "ERROR" white_agent.log | tail -20

# Find validation errors
grep "Invalid white agent response" green_agent.log
```

### 3. Network Debugging

Test connectivity:

```bash
# Test white agent from green agent host
curl -v http://localhost:9002/agent-card

# Test with verbose output
curl -v -X POST http://localhost:9002/task \
  -H "Content-Type: application/json" \
  -d @test_task.json

# Check response time
time curl http://localhost:9002/agent-card
```

### 4. Response Capture

Capture actual responses:

```python
# In white agent - add logging
@app.post("/task")
async def task(task: A2ATask) -> A2AMessage:
    # ... your logic ...

    response = A2AMessage(...)

    # Log the response
    import json
    print("=== RESPONSE ===")
    print(json.dumps(response.dict(), indent=2))
    print("===============")

    return response
```

---

## Health Check Commands

### System Health

```bash
# Check all services
curl http://localhost:8001/health  # Green agent
curl http://localhost:9002/health  # White agent
curl http://<vm-ip>:5000/platform  # OSWorld

# Check ports
lsof -i :8001  # Green agent port
lsof -i :9002  # White agent port

# Check processes
ps aux | grep uvicorn
```

### VM Health

```bash
# List VMs
gcloud compute instances list

# Check VM details
gcloud compute instances describe <vm-name> \
  --zone=us-central1-a

# Test OSWorld
VM_IP=$(gcloud compute instances describe <vm-name> \
  --zone=us-central1-a \
  --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

curl http://$VM_IP:5000/platform
# Should return: {"platform": "ubuntu"}
```

---

## Prevention Best Practices

### 1. Input Validation

Always validate before sending:

```python
def validate_before_send(response: dict) -> bool:
    """Validate response structure"""
    required_fields = ["role", "content", "metadata"]

    for field in required_fields:
        if field not in response:
            print(f"Missing field: {field}")
            return False

    if "action" not in response["metadata"]:
        print("Missing metadata.action")
        return False

    action = response["metadata"]["action"]
    if "op" not in action:
        print("Missing action.op")
        return False

    return True
```

### 2. Error Handling

Wrap all operations:

```python
@app.post("/task")
async def task(task: A2ATask) -> A2AMessage:
    try:
        # Your logic
        action = select_action(task)

        return A2AMessage(
            role="assistant",
            content="...",
            metadata={"action": action}
        )
    except Exception as e:
        logger.error(f"Task error: {e}", exc_info=True)

        # Return error response
        return A2AMessage(
            role="assistant",
            content=f"Error: {str(e)}",
            metadata={
                "error": str(e),
                "done": False
            }
        )
```

### 3. Logging

Log key events:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@app.post("/task")
async def task(task: A2ATask) -> A2AMessage:
    logger.info(f"Received task: {task.task_id}")
    logger.info(f"Step: {task.metadata['observation']['frame_id']}")

    action = select_action(task)

    logger.info(f"Selected action: {action['op']}")
    logger.debug(f"Full action: {action}")

    return ...
```

---

## Getting Help

If you're still stuck:

1. **Check logs** for detailed error messages
2. **Review documentation:**
   - [White Agent Development Guide](../WHITE_AGENT_DEVELOPMENT.md)
   - [Tool Description Format](../TOOL_DESCRIPTION_FORMAT.md)
   - [A2A Protocol README](../../README.md)
3. **Test components individually:**
   - Agent card endpoint
   - Task endpoint with minimal request
   - Response validation
4. **Compare with working example:**
   - `white_agent/gpt4v_server.py`
5. **Run tests:**
   - `tests/test_gpt4v_standalone.py`
   - `tests/test_security_simple.py`

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-11 | Initial release |
