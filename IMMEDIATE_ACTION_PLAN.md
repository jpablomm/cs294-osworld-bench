# Immediate Action Plan - Week 1 Priorities

**Goal:** Get system working end-to-end with real assessments
**Timeline:** 20 hours (1 week)
**Target Compliance:** 65% (from current 47%)

---

## Day 1-2: Fix White Agent (8 hours)

### Task 1.1: Choose and Set Up VLM (1 hour)

**Options:**
1. **GPT-4V (Recommended)** - Best vision+tool calling
2. **Claude 3.5 Sonnet** - Strong reasoning
3. **Gemini Pro Vision** - Cost-effective

**Action Items:**
```bash
# Choose one and set up API key
export OPENAI_API_KEY="sk-..."  # For GPT-4V
# OR
export ANTHROPIC_API_KEY="sk-ant-..."  # For Claude
```

**Files to check:**
- `white_agent/gpt4v_server.py` - Existing implementation?

### Task 1.2: Implement Vision Processing (3 hours)

**File:** `white_agent/server.py` (or create new `white_agent/vlm_server.py`)

**Code to write:**
```python
import base64
from openai import OpenAI  # or anthropic

client = OpenAI()

def analyze_screenshot(image_b64: str, instruction: str) -> dict:
    """
    Analyze screenshot and decide next action.

    Returns:
        {"op": "click", "args": {"x": 100, "y": 200}}
    """
    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Task: {instruction}\n\nWhat action should I take next?"
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                    }
                ]
            }
        ],
        max_tokens=300
    )

    # Parse response and return action
    return parse_vlm_response(response.choices[0].message.content)
```

**Testing:**
```bash
# Start white agent
python -m white_agent.vlm_server --port 9001

# Test with sample observation
curl -X POST http://localhost:9001/decide \
  -H "Content-Type: application/json" \
  -d '{
    "frame_id": 0,
    "image_png_b64": "..."
    "instruction": "Open Chrome",
    "done": false
  }'
```

### Task 1.3: Implement Tool Calling Logic (3 hours)

**Add to `white_agent/vlm_server.py`:**

```python
TOOL_PROMPT = """
Available actions:
- click(x, y): Click at coordinates
- type(text): Type text
- hotkey(keys): Press keyboard shortcut (e.g., ["ctrl", "c"])
- wait(duration): Wait N seconds
- done(): Task complete

Respond in JSON:
<json>
{
  "action": "click",
  "reasoning": "Need to click Chrome icon at position...",
  "x": 100,
  "y": 200
}
</json>

Or for typing:
<json>
{
  "action": "type",
  "reasoning": "Need to type the URL",
  "text": "https://google.com"
}
</json>

Or when done:
<json>
{
  "action": "done",
  "reasoning": "Task completed successfully"
}
</json>
"""

def decide(obs: Observation) -> dict:
    """Enhanced decide with tool calling"""

    # Build prompt
    messages = [
        {"role": "system", "content": TOOL_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"Step {obs.frame_id}\nTask: {obs.instruction}"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{obs.image_png_b64}"}}
            ]
        }
    ]

    # Get VLM response
    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=messages,
        max_tokens=500
    )

    # Parse JSON from response
    content = response.choices[0].message.content
    action_json = extract_json(content)  # Extract from <json> tags

    # Convert to OSWorld action format
    action = convert_to_osworld_action(action_json)

    return action

def extract_json(content: str) -> dict:
    """Extract JSON from <json>...</json> tags"""
    import json
    import re

    match = re.search(r'<json>(.*?)</json>', content, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    # Fallback: try to parse entire content
    return json.loads(content)

def convert_to_osworld_action(action_json: dict) -> dict:
    """Convert VLM action format to OSWorld format"""
    action_type = action_json["action"]

    if action_type == "click":
        return {
            "op": "click",
            "args": {"x": action_json["x"], "y": action_json["y"]}
        }
    elif action_type == "type":
        return {
            "op": "type",
            "args": {"text": action_json["text"]}
        }
    elif action_type == "hotkey":
        return {
            "op": "hotkey",
            "args": {"keys": action_json["keys"]}
        }
    elif action_type == "done":
        return {"op": "done", "args": {}}
    else:
        # Default to wait if unknown
        return {"op": "wait", "args": {"duration": 1.0}}
```

### Task 1.4: Test White Agent (1 hour)

**Create test script `test_white_agent.py`:**
```python
import base64
from pathlib import Path
from white_agent.vlm_server import decide
from white_agent.server import Observation

# Load test screenshot
test_image = Path("test_data/ubuntu_desktop.png").read_bytes()
image_b64 = base64.b64encode(test_image).decode()

# Test observation
obs = Observation(
    frame_id=0,
    image_png_b64=image_b64,
    instruction="Open Chrome browser",
    done=False
)

# Get decision
action = decide(obs)
print(f"Action: {action}")

# Verify action makes sense
assert action["op"] in ["click", "type", "hotkey", "wait", "done"]
print("✓ White agent test passed")
```

**Run test:**
```bash
python test_white_agent.py
```

---

## Day 3: Fix Evaluation (6 hours)

### Task 2.1: Review OSWorld Evaluator (1 hour)

**File:** `green_agent/osworld_evaluator.py`

**Questions to answer:**
1. Does `evaluate_task()` function exist?
2. Does it call OSWorld's SetupController.evaluate()?
3. Does it return scores between 0.0 and 1.0?

**Action:**
```bash
# Read the file
cat green_agent/osworld_evaluator.py

# Check imports
grep "SetupController\|evaluate" green_agent/osworld_evaluator.py
```

### Task 2.2: Fix Evaluation Integration (3 hours)

**File:** `orchestrator/a2a_green_agent.py`

**Change 1: Remove simplified fallback (Lines 418-419)**

**Before:**
```python
else:
    logger.info("No evaluator config found, using simplified success check")
    result["evaluation_method"] = "simplified"
```

**After:**
```python
else:
    logger.error("No evaluator config found - cannot validate results!")
    result["success"] = 0
    result["evaluation_method"] = "no_evaluator"
    result["failure_reason"] = "missing_evaluator_config"
```

**Change 2: Don't trust white agent (Lines 776-780)**

**Before:**
```python
if is_done or action["op"] == "done":
    success = True  # WRONG - trusts white agent
    logger.info(f"Task completed successfully at step {step}")
    break
```

**After:**
```python
if is_done or action["op"] == "done":
    logger.info(f"White agent reports task done at step {step}")
    logger.info("Will validate with OSWorld evaluator...")
    break  # Don't set success=True here!
```

**Change 3: Always require evaluation (After Line 819)**

**Add:**
```python
# After the assessment loop ends, success should ONLY be set by evaluation
# If we reach here without evaluation, that's a failure
if "success" not in result:
    logger.error("Assessment ended without evaluation - marking as failed")
    result["success"] = 0
    result["failure_reason"] = "no_evaluation_performed"
```

### Task 2.3: Verify OSWorld Evaluator Works (2 hours)

**Create `test_evaluation.py`:**
```python
import asyncio
from green_agent.osworld_evaluator import evaluate_task

# Load a known task
task_id = "bb5e4c0d-f964-439c-97b6-bdb9747de3f4"  # From test_small.json
# Assuming this is a Chrome task: "Search for 'OSWorld' on Google"

# Test evaluation with correct end state
score = asyncio.run(evaluate_task(
    vm_ip="10.128.0.10",  # Your test VM
    evaluator_config={
        "func": "check_chrome_search",  # OSWorld evaluator function
        "result": {"query": "OSWorld"}
    },
    task_id=task_id,
    server_port=5000,
    cache_dir="cache"
))

print(f"Evaluation score: {score}")
assert 0.0 <= score <= 1.0, "Score should be between 0 and 1"

# Test with incorrect end state (should fail)
# ... manually test by not completing task ...
```

**Run tests with real VM:**
```bash
# Create test VM first
gcloud compute instances create osworld-test \
  --image=osworld-golden-v3-gnome \
  --zone=us-central1-a

# Get IP
VM_IP=$(gcloud compute instances describe osworld-test \
  --zone=us-central1-a \
  --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

# Run test
python test_evaluation.py
```

---

## Day 4: Fix Security + Task Format (6 hours)

### Task 3.1: Fix Code Injection (2 hours)

**File:** `orchestrator/a2a_green_agent.py:839-949`

**Problem:** String concatenation creates injection risk

**Solution: Use JSON-based API instead of Python code generation**

**Before:**
```python
if op == "type":
    escaped_text = text.replace("\\", "\\\\").replace('"', '\\"')
    python_code = f'import pyautogui\npyautogui.typewrite("{escaped_text}")'
```

**After:**
```python
if op == "type":
    # Use structured API instead of code generation
    response = await client.post(
        f"{base_url}/type_text",
        json={"text": args["text"]},  # JSON serialization is safe
        timeout=30.0
    )
```

**Check if OSWorld has JSON endpoints:**
```bash
# SSH to VM and check
gcloud compute ssh osworld-test --zone=us-central1-a

# Check OSWorld server code
cat /home/user/osworld/desktop_env/server/main.py | grep "@app.route"
```

**If OSWorld doesn't have JSON endpoints, use parameterized execution:**
```python
def execute_safe_python(client, base_url, action_type, **kwargs):
    """
    Execute Python code safely using parameterized templates
    """
    # Pre-approved templates only
    SAFE_TEMPLATES = {
        "click": "import pyautogui\npyautogui.click(%d, %d)",
        "type": "import pyautogui\npyautogui.write(%r)",  # %r properly escapes
        "hotkey": "import pyautogui\npyautogui.hotkey(*%r)"
    }

    template = SAFE_TEMPLATES.get(action_type)
    if not template:
        raise ValueError(f"Unknown action type: {action_type}")

    # Validate inputs
    if action_type == "click":
        x, y = int(kwargs["x"]), int(kwargs["y"])
        if not (0 <= x <= 1920 and 0 <= y <= 1080):
            raise ValueError("Coordinates out of bounds")
        code = template % (x, y)

    elif action_type == "type":
        text = str(kwargs["text"])
        if len(text) > 1000:  # Reasonable limit
            raise ValueError("Text too long")
        code = template % text  # %r handles escaping

    # Execute
    response = await client.post(f"{base_url}/run_python", json={"code": code})
    return response
```

### Task 3.2: Add Tool Format Specification (3 hours)

**File:** `orchestrator/a2a_green_agent.py:627-671`

**Enhance `_format_task_message_with_tools()`:**

**Before:**
```python
# Available Tools

## screenshot
Capture a screenshot of the current desktop state

Parameters: (none)
```

**After:**
```python
# How to Use Tools

You must respond with actions in JSON format. Wrap your JSON in <json>...</json> tags.

## Response Format

<json>
{
  "action": "click",
  "reasoning": "Brief explanation of why this action",
  "x": 100,
  "y": 200
}
</json>

## Available Actions

### click
Click the mouse at specific coordinates.
Parameters:
- x (integer, required): X coordinate (0-1920)
- y (integer, required): Y coordinate (0-1080)

Example:
<json>
{
  "action": "click",
  "reasoning": "Click the Chrome icon in the dock",
  "x": 100,
  "y": 1050
}
</json>

### type
Type text using the keyboard.
Parameters:
- text (string, required): Text to type

Example:
<json>
{
  "action": "type",
  "reasoning": "Enter the URL",
  "text": "https://google.com"
}
</json>

### hotkey
Press a keyboard shortcut.
Parameters:
- keys (array of strings, required): Keys to press together

Example:
<json>
{
  "action": "hotkey",
  "reasoning": "Copy selected text",
  "keys": ["ctrl", "c"]
}
</json>

### done
Indicate task completion.

Example:
<json>
{
  "action": "done",
  "reasoning": "Task completed successfully - file saved to Desktop"
}
</json>

# Your Task

{task_instruction}

# Environment
- OS: Ubuntu 22.04 Desktop
- Screen: 1920x1080
- Apps: Chrome, Firefox, LibreOffice, GIMP, Files (Nautilus)
- Desktop: GNOME with dock on left side

# Success Criteria
You must complete the task exactly as described. When done, use the "done" action.
The system will verify your work automatically.

# Process
1. Take a screenshot (provided automatically)
2. Analyze the current state
3. Decide next action
4. Execute the action
5. Repeat until task complete

You have a maximum of {max_steps} steps.
```

### Task 3.3: Update White Agent to Follow Format (1 hour)

Update the `TOOL_PROMPT` in `white_agent/vlm_server.py` to match the green agent's format exactly.

**Test:**
```python
# Send task to white agent
# Verify response matches expected JSON format
```

---

## Day 5: Integration Testing (5 hours)

### Task 4.1: End-to-End Test (2 hours)

**Create `test_e2e.py`:**
```python
import asyncio
import subprocess
import time

# Start green agent
green_proc = subprocess.Popen([
    "uvicorn", "orchestrator.a2a_green_agent:app",
    "--port", "8001"
])

# Start white agent
white_proc = subprocess.Popen([
    "uvicorn", "white_agent.vlm_server:app",
    "--port", "9001"
])

# Wait for startup
time.sleep(5)

try:
    # Run assessment via launcher
    result = subprocess.run([
        "python", "launcher_a2a.py",
        "--task-id", "bb5e4c0d-f964-439c-97b6-bdb9747de3f4",
        "--white-agent-url", "http://localhost:9001",
        "--green-agent-url", "http://localhost:8001",
        "--max-steps", "15"
    ], capture_output=True, text=True)

    print(result.stdout)
    print(result.stderr)

    # Check result
    assert result.returncode in [0, 1], "Launcher should exit 0 or 1"
    assert "Assessment Complete" in result.stdout
    assert "success" in result.stdout.lower()

    print("✓ End-to-end test passed!")

finally:
    # Cleanup
    green_proc.terminate()
    white_proc.terminate()
```

### Task 4.2: Multiple Task Test (1 hour)

Test with 5 different OSWorld tasks:
1. Chrome task
2. LibreOffice task
3. GIMP task
4. OS task
5. Multi-app task

### Task 4.3: Failure Handling Test (1 hour)

Test error scenarios:
- VM not responding
- White agent crashes
- Network timeout
- Evaluation failure

### Task 4.4: Documentation Update (1 hour)

Update README.md with:
1. How to use A2A mode
2. White agent requirements
3. Expected tool format
4. Troubleshooting

---

## Success Criteria

After completing this week's work, you should be able to:

1. ✅ Run a full assessment end-to-end
2. ✅ White agent makes intelligent decisions using vision
3. ✅ Evaluation uses OSWorld ground truth (not self-assessment)
4. ✅ Security vulnerabilities fixed
5. ✅ Task format is clear and documented
6. ✅ Basic tests passing

**Compliance Score Target: 65%**
- A2A Protocol: 85%
- Tool Handling: 70%
- Task Description: 60%
- Evaluation: 80%
- White Agent: 60%
- Overall: **65%**

---

## Troubleshooting

### White Agent Issues

**Problem:** VLM doesn't return valid JSON
```python
# Add retry logic
def parse_vlm_response(content: str, max_retries: int = 3) -> dict:
    for attempt in range(max_retries):
        try:
            return extract_json(content)
        except json.JSONDecodeError:
            if attempt < max_retries - 1:
                # Try again with clarification
                continue
            else:
                # Fallback to safe action
                return {"op": "wait", "args": {"duration": 1.0}}
```

**Problem:** VLM is too slow
- Use GPT-4V instead of GPT-4V-preview
- Reduce max_tokens
- Cache system prompts

### Evaluation Issues

**Problem:** Evaluator not found
```bash
# Check OSWorld evaluator directory
ls vendor/OSWorld/desktop_env/evaluators/

# Verify evaluator function exists
grep "def check_" vendor/OSWorld/desktop_env/evaluators/*.py
```

**Problem:** Evaluation always fails
- Check VM can access required files
- Verify setup phase completed successfully
- Check evaluator config matches task

### Security Issues

**Problem:** Actions still vulnerable
- Review parameterized execution carefully
- Add more input validation
- Consider sandboxing Python execution

---

## Next Week (Week 2)

After completing Week 1 priorities, proceed to:
1. Task abstraction improvements (remove infrastructure details)
2. Evaluation validation (compare with OSWorld benchmark)
3. Error handling refinements
4. Comprehensive testing

---

## Quick Commands

```bash
# Start green agent
uvicorn orchestrator.a2a_green_agent:app --port 8001

# Start white agent
uvicorn white_agent.vlm_server:app --port 9001

# Run assessment
python launcher_a2a.py \
  --task-id <task-id> \
  --white-agent-url http://localhost:9001 \
  --max-steps 15

# Check compliance
python check_compliance.py  # TODO: Create this script
```

---

**Remember:** Focus on getting it **working** first (Week 1), then make it **correct** (Week 2), then make it **robust** (Week 3+).

Good luck! 🚀
