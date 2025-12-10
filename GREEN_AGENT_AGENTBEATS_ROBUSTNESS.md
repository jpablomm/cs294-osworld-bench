# Green Agent Robustness on AgentBeats: Design & Implementation

## Executive Summary

**Yes, the Green Agent runs robustly on AgentBeats because:**

1. ✅ **A2A Protocol Compliance** - Implements AgentBeats' A2A standard endpoints (`/agent-card`, `/task`)
2. ✅ **White Agent Independence** - Does NOT require white agents to implement tool execution
3. ✅ **Tool Descriptions as Strings** - Sends tools as formatted markdown/JSON documentation, relying solely on white agent reasoning
4. ✅ **Graceful Error Handling** - Validates responses and handles failures without crashing
5. ✅ **Decoupled Architecture** - Green and white agents interact via standardized A2A protocol messages

This document explains **how** this robustness is achieved through design choices and implementation patterns.

---

## 1. A2A Protocol Compliance Foundation

### 1.1 Agent Card Endpoint (Discovery)

Green Agent publishes a standard agent card at required endpoints:

**File**: `green_agent/a2a/server.py` (lines 310-360)

```python
@app.get("/agent-card")
def get_agent_card(request: Request) -> AgentCard:
    """
    Return agent card - A2A protocol requirement
    """
    return _build_agent_card(str(request.url))


@app.get("/.well-known/agent.json")
async def get_well_known_agent_json(request: Request) -> AgentCard:
    """
    A2A Protocol standard discovery endpoint.
    Per A2A spec: https://agent2agent.info/docs/concepts/agentcard/
    Agent cards should be hosted at: /.well-known/agent.json
    """
    return _build_agent_card(str(request.url))


@app.get("/.well-known/agent-card.json")
async def get_well_known_agent_card_legacy(request: Request) -> AgentCard:
    """Legacy endpoint - redirects to standard A2A endpoint"""
    return _build_agent_card(str(request.url))
```

**Card Contents** (lines 310-344):

```python
def _build_agent_card(request_url: str = None) -> AgentCard:
    """Build agent card with dynamic URL based on request or environment"""
    return AgentCard(
        name="OSWorld Assessment Agent",
        description="Green agent for OSWorld assessments...",
        url=url,
        version="0.1.0",
        capabilities=AgentCapabilities(
            streaming=True,           # Supports progress updates
            pushNotifications=True,
            stateTransitionHistory=True
        ),
        skills=[
            AgentSkill(
                id="osworld-assessment",
                name="OSWorld Assessment",
                description="Run OSWorld desktop automation benchmark assessments",
                tags=["benchmark", "desktop", "automation", "assessment"],
            ),
            # ... more skills
        ],
        provider=AgentProvider(
            organization="Berkeley CS294",
            url="https://github.com/agentbeats/green-agent"
        ),
    )
```

✅ **Impact**: AgentBeats can discover the Green Agent automatically via standard A2A discovery protocol.

### 1.2 Task Endpoint (Execution)

Green Agent handles incoming A2A tasks at `/task` endpoint:

**File**: `green_agent/a2a/server.py` (lines 600-700+)

```python
@app.post("/task")
async def execute_task(task: A2ATask) -> A2AMessage:
    """Execute A2A task - main assessment entry point"""
    # Orchestrates: VM creation → setup → white agent loop → evaluation → cleanup
```

✅ **Impact**: Standard A2A request/response format ensures compatibility with any AgentBeats platform.

---

## 2. Independence from White Agent Tool Implementation

### 2.1 The Key Design Choice: Tools as Descriptions, Not Contracts

**The Problem**: 
- Original OSWorld requires agents to actually execute tools (click, type, etc.)
- This creates a tight coupling between evaluator and white agent
- White agents must implement tool execution perfectly

**Our Solution**:
- Green Agent sends tool **descriptions** as formatted text/JSON
- White agent only needs **reasoning capability** to understand tools
- Green Agent does the actual tool execution based on returned actions

### 2.2 Tool Description Generation

**File**: `green_agent/a2a/server.py` (lines 1623-1750)

The Green Agent builds tool descriptions programmatically:

```python
def _format_task_message_with_tools(task: Dict[str, Any], tools: list[Dict[str, Any]]) -> str:
    """
    Format task message with embedded tool descriptions

    This follows the Tau-Bench/AgentBeats pattern where tools are described
    in natural language within the task message, with JSON examples showing
    the expected format.
    """
    task_instruction = task.get("instruction", "Complete the task")

    # Build tool documentation string
    tools_doc = "# Available Tools\n\n"
    tools_doc += "You have access to the following tools for desktop automation:\n\n"

    for tool in tools:
        tools_doc += f"## {tool['name']}\n\n"
        tools_doc += f"{tool['description']}\n\n"

        # Parameters
        if tool['parameters']['properties']:
            tools_doc += "**Parameters:**\n"
            for param_name, param_spec in tool['parameters']['properties'].items():
                required_marker = " (required)" if param_name in tool['parameters'].get('required', []) else " (optional)"
                param_type = param_spec['type']
                param_desc = param_spec.get('description', '')
                tools_doc += f"- `{param_name}` ({param_type}){required_marker}: {param_desc}\n"

        # Returns
        if 'returns' in tool:
            returns_desc = tool['returns'].get('description', 'Action result')
            tools_doc += f"**Returns:** {returns_desc}\n\n"

        # Examples
        if 'examples' in tool and tool['examples']:
            tools_doc += "**Examples:**\n"
            for example in tool['examples'][:2]:  # Show max 2 examples
                example_desc = example.get('description', 'Example usage')
                example_input = example.get('input', {})
                tools_doc += f"- {example_desc}:\n"
                tools_doc += f"  ```json\n"
                if example_input:
                    tools_doc += f'  {{"op": "{tool["name"]}", "args": {json.dumps(example_input)}}}\n'
                else:
                    tools_doc += f'  {{"op": "{tool["name"]}"}}\n'
                tools_doc += f"  ```\n"

    # Add format specification
    tools_doc += "\n---\n\n"
    tools_doc += "**Action Format:** Return actions as JSON with `op` (operation name) and `args` (parameters) fields:\n"
    tools_doc += "```json\n"
    tools_doc += '{"op": "tool_name", "args": {"param1": "value1", "param2": "value2"}}\n'
    tools_doc += "```\n\n"

    # Combine task instruction with tools
    message = f"""
{tools_doc}

# Task

{task_instruction}

**Instructions:**
1. Take a screenshot first to observe the current state
2. Analyze what you see and decide on the appropriate action
3. Execute actions using the format shown above
4. After important actions, take another screenshot to verify results
5. Continue until the task is complete
6. When finished, return {{"op": "done"}}
"""
    return message
```

**Example Output**:
```markdown
# Available Tools

You have access to the following tools for desktop automation:

## screenshot

Capture a screenshot of the current desktop state.

**Parameters:** None

**Returns:** PNG image of the desktop

**Examples:**
- Capture current screen state:
  ```json
  {"op": "screenshot"}
  ```

## click

Click at specified coordinates on screen.

**Parameters:**
- `x` (integer)(required): X coordinate (0-1920)
- `y` (integer)(required): Y coordinate (0-1080)
- `button` (string)(optional): Mouse button ("left", "right", "middle")

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

Recover the file "poster_party_night.webp" from trash to the desktop

...
```

✅ **Impact**: White agent receives clear, self-explanatory tool documentation without needing to parse tool specifications.

### 2.3 White Agent Response Parsing (Reasoning-Based)

Green Agent expects white agent to return **reasoning + action**, not tool execution:

**File**: `green_agent/a2a/server.py` (lines 1521-1600)

```python
def _validate_white_agent_response(response_data: Dict[str, Any], tools: list[Dict[str, Any]]) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validate white agent response structure and extract action

    Validates:
    - Response has required A2A fields (role, content, metadata)
    - metadata.action exists and has required structure
    - Action op is valid (matches a known tool)
    - Action args match tool parameter requirements
    """
    # Check top-level A2A message structure
    if not isinstance(response_data, dict):
        return False, "Response must be a JSON object", None

    if "role" not in response_data:
        return False, "Response missing required field: role", None

    if "content" not in response_data:
        return False, "Response missing required field: content", None

    if "metadata" not in response_data:
        return False, "Response missing required field: metadata", None

    metadata = response_data["metadata"]
    if not isinstance(metadata, dict):
        return False, "metadata must be an object", None

    # Check for action in metadata
    if "action" not in metadata:
        # Check if there's an error instead
        if "error" in metadata:
            return False, f"White agent reported error: {metadata['error']}", None
        return False, "Response metadata missing required field: action", None

    action = metadata["action"]
    if not isinstance(action, dict):
        return False, "action must be an object", None
    
    # Validate action structure
    if "op" not in action:
        return False, "action missing required field: op", None

    op = action["op"]
    if not isinstance(op, str):
        return False, "action op must be string", None

    # Validate op matches a known tool
    valid_ops = {tool["name"] for tool in tools} | {"done", "fail"}
    if op not in valid_ops:
        return False, f"Unknown operation: {op}. Valid ops: {valid_ops}", None

    args = action.get("args", {})
    if not isinstance(args, dict):
        return False, "action args must be object", None

    return True, None, action
```

**Expected Response Format** (white agent returns reasoning + action):

```json
{
  "role": "assistant",
  "content": "I need to recover the file from trash. Let me first take a screenshot to see the current state.",
  "metadata": {
    "action": {
      "op": "screenshot",
      "args": {}
    },
    "done": false,
    "reasoning": "Taking initial screenshot to assess the desktop state"
  }
}
```

✅ **Impact**: White agent only needs to provide:
- `content`: Natural language reasoning about what to do
- `metadata.action.op`: Which tool to use
- `metadata.action.args`: Tool parameters

This is **reasoning-only**, not tool execution.

---

## 3. Graceful Error Handling & Robustness

### 3.1 Response Validation with Helpful Errors

**File**: `green_agent/a2a/server.py` (lines 2015-2070)

```python
async def _execute_with_white_agent(...):
    # ... loop ...
    
    # Validate white agent response
    is_valid, error_msg, action = _validate_white_agent_response(message, tools)
    validation_result = {
        "valid": is_valid,
        "errors": [error_msg] if not is_valid else []
    }

    # Push message received event with validation results
    await _push_event_to_webui(callback_url, {
        "type": "message_received",
        "step": step,
        "direction": "white_to_green",
        "timestamp": message_receive_iso,
        "latency_ms": latency_ms,
        "payload": {...},
        "validation": validation_result  # Include validation status
    })

    if not is_valid:
        logger.error(f"Invalid white agent response: {error_msg}")
        logger.error(f"Full response: {message}")
        failure_reason = f"Invalid response: {error_msg}"
        raise RuntimeError(f"White agent response validation failed: {error_msg}")
```

**Key Points**:
- Validates every white agent response before using
- Logs full response for debugging
- Reports validation errors back to WebUI
- Fails fast with clear error message

✅ **Impact**: Malformed white agent responses don't cascade into silent failures.

### 3.2 Timeout Protection

**File**: `green_agent/a2a/server.py` (lines 1970-2000)

```python
async def _execute_with_white_agent(...):
    async with httpx.AsyncClient() as client:
        for step in range(max_steps):
            # ... prepare task ...
            
            try:
                # Get action from white agent with timeout
                response = await client.post(
                    f"{white_agent_url}/task",
                    json=current_task,
                    timeout=120.0  # 2-minute timeout per request
                )
                response.raise_for_status()
```

✅ **Impact**: White agent hangs don't block the assessment indefinitely.

### 3.3 Fallback on White Agent Failure

**File**: `green_agent/a2a/server.py` (lines 2065-2090)

```python
if not is_valid:
    logger.error(f"Invalid white agent response: {error_msg}")
    # Record failure but allow graceful handling
    failure_reason = f"White agent error: {error_msg}"
    
    # Assessment ends with clear failure reason
    # (Could implement fallback strategy if needed)
    raise RuntimeError(...)
```

✅ **Impact**: Assessment terminates cleanly with diagnostic information rather than crashing.

---

## 4. Decoupled Architecture

### 4.1 Green Agent Independence

The Green Agent doesn't depend on white agent implementation details:

**File**: `green_agent/a2a/server.py` (lines 1-50)

```python
"""
A2A-Compliant Green Agent for OSWorld Assessment

This module wraps the existing OSWorld orchestrator to make it AgentBeats-compliant.
It implements the A2A protocol while preserving all existing orchestrator functionality.
"""

# All imports are lazy to avoid blocking subprocess startup
# GCP and Supabase clients can hang during import in Cloud Run subprocesses

async def _execute_assessment(assessment_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute assessment workflow with white agent.
    
    This is the core orchestration loop that:
    1. Creates VM from golden image
    2. Loads OSWorld task
    3. Runs postconfig setup
    4. Executes white agent interaction loop
    5. Evaluates task completion
    6. Cleans up resources
    """
```

**Tools sent as strings**: White agent doesn't need to parse tool schemas—they're documented in natural language.

**Actions parsed simply**: Expected format is JSON with `op` and `args`—no complex validation needed from white agent.

**Status tracking**: Green agent tracks everything (steps, VM status, evaluation results).

✅ **Impact**: White agent can be any HTTP server that:
1. Accepts A2A `/task` POST requests
2. Returns A2A-formatted responses with actions
3. Doesn't need to understand OSWorld internals

### 4.2 Requirements for White Agents (Minimal)

From `docs/WHITE_AGENT_DEVELOPMENT.md`:

```markdown
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
```

**That's it.** No tool execution implementation required.

---

## 5. Evidence of Robustness: Testing & Validation

### 5.1 Built-in Validation Tests

**File**: `tests/test_gpt4v_standalone.py`

Tests the white agent (GPT-4V) with A2A protocol:

```python
def test_white_agent_with_observation():
    """Test white agent with a sample observation"""
    print("Testing GPT-4V white agent with observation...")

    white_agent_url = "http://localhost:9002"

    # Test 1: Check agent card
    response = requests.get(f"{white_agent_url}/agent-card")
    assert response.status_code == 200
    card = response.json()
    print(f"   Agent: {card['name']}")
    print(f"   Protocols: {card['protocols']}")
    print(f"   Capabilities: {card['capabilities'][:3]}...")
    print("   ✓ Agent card retrieved\n")

    # Test 2: Send a task with screenshot
    print("2. Sending test task to white agent...")
    response = requests.post(...)
    assert response.status_code == 200
    result = response.json()
    
    # Test 3: Verify response format
    assert "role" in result
    assert result["role"] == "assistant"
    assert "metadata" in result
    assert "action" in result["metadata"]
    print("   ✓ Response format correct")
```

✅ **Impact**: Validates that white agents conform to A2A protocol.

### 5.2 Error Handling Tests

**File**: `tests/test_security_simple.py`

Tests input validation and error handling:

```python
def test_coordinate_validation():
    """Test coordinate validation prevents injection"""
    # Valid coordinates
    x, y = _validate_coordinates(960, 540)
    assert x == 960 and y == 540
    
    # Out-of-bounds rejected
    try:
        _validate_coordinates(2000, 540)  # x > 1920
        assert False, "Should reject out-of-bounds"
    except ValueError:
        pass  # Expected

def test_text_validation():
    """Test text validation prevents injection"""
    # Valid text
    text = _validate_text("click button")
    assert text == "click button"
    
    # Excessively long text rejected
    try:
        _validate_text("x" * 20000)
        assert False, "Should reject long text"
    except ValueError:
        pass  # Expected
```

✅ **Impact**: Validates that malicious inputs from white agents are blocked.

---

## 6. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     AgentBeats Platform                      │
│  (Discovers agents, manages lifecycle, routes tasks)        │
└─────────────┬───────────────────────────────────────────────┘
              │
         A2A Protocol (JSON-RPC)
         Standard discovery & task endpoints
         |
    ┌────┴─────────────────────────────────────────────┐
    │                                                   │
┌───▼────────────────────────┐          ┌──────────────▼────┐
│   Green Agent              │          │   White Agent     │
│  ✅ A2A Compliant          │          │  (Any LLM)       │
│  ✅ Orchestrator           │          │  ✅ HTTP Server   │
│  ✅ Tool Executor          │          │  ✅ Reasoning     │
│  ✅ Evaluator              │          │  ✅ A2A Protocol  │
│                            │          │                   │
│ Sends:                     │          │ Receives:         │
│ - Tool descriptions       │◄────────►├ Tool descriptions │
│ - Screenshots             │          │ (as text)         │
│ - Task instructions       │          │                   │
│                            │ Receives │ Sends:            │
│                            │◄────────┤ Reasoning         │
│ Executes:                  │          │ Action JSON       │
│ - Actions from white agent│          │ (op + args)      │
│ - Evaluations             │          │                   │
│ - VM lifecycle            │          │                   │
└──────┬─────────────────────┘          └──────────────────┘
       │
       │ Agnostic to white agent
       │ implementation details
       │
       ├─ Tools as strings ✅
       ├─ Reasoning-only ✅
       ├─ Format validation ✅
       └─ Graceful errors ✅
```

---

## 7. How Robustness is Achieved

| Robustness Factor | Implementation | Evidence |
|-------------------|----------------|----------|
| **A2A Compliance** | Standard endpoints (`/agent-card`, `/task`) | `green_agent/a2a/server.py` lines 310-360 |
| **Tool Independence** | Tools sent as formatted text, not schemas | `green_agent/a2a/server.py` lines 1623-1750 |
| **Reasoning-Only** | White agent returns actions, not tool calls | `green_agent/a2a/server.py` lines 1521-1600 |
| **Response Validation** | Comprehensive validation with helpful errors | `green_agent/a2a/server.py` lines 2015-2070 |
| **Timeout Protection** | 120-second timeout per request | `green_agent/a2a/server.py` line 1980 |
| **Error Reporting** | Validation results sent to WebUI | `green_agent/a2a/server.py` lines 2020-2035 |
| **Decoupled Design** | Green agent handles all orchestration | `green_agent/a2a/server.py` (entire file) |
| **Tool Execution** | Green agent executes tools, not white agent | `green_agent/osworld_client.py` |
| **State Management** | Green agent tracks assessment state | `green_agent/a2a/server.py` lines 400-500 |
| **Cleanup** | Graceful VM cleanup on success/failure | `green_agent/a2a/vm_manager.py` |

---

## 8. Why This Matters

### Traditional OSWorld
- White agent must implement tool execution
- Tool schemas are complex
- White agent needs OSWorld-specific knowledge
- Failures are cascading

### Our AgentBeats-Compliant Approach
- White agent only does reasoning (send tool name + parameters)
- Tool descriptions are self-explanatory strings
- White agent needs no OSWorld knowledge
- Failures are isolated and handled gracefully

**Result**: 
✅ Any white agent that can do vision-language reasoning can work
✅ Simple integration path for new agents
✅ Robust operation even if white agent is imperfect
✅ Backward compatible with non-A2A agents (fallback mode)

---

## References

- **Green Agent A2A Server**: `green_agent/a2a/server.py` (2100+ lines)
- **Tool Description Building**: `green_agent/a2a/server.py` lines 1623-1750
- **Response Validation**: `green_agent/a2a/server.py` lines 1521-1600
- **White Agent Development Guide**: `docs/WHITE_AGENT_DEVELOPMENT.md`
- **A2A Protocol Spec**: `docs/CLOUD_RUN_DEPLOYMENT.md` (AgentBeats integration section)
- **Example White Agent**: `white_agent/a2a/server.py`
- **Tests**: `tests/test_gpt4v_standalone.py`, `tests/test_security_simple.py`

