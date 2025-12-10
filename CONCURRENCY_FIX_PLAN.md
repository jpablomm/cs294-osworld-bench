# Implementation Plan: Fix White Agent Concurrency Issue

## Problem Summary

The White Agent server uses a **single global `PromptAgent` instance** that maintains mutable state (`observations`, `actions`, `thoughts` arrays). When multiple tasks run simultaneously, these arrays get corrupted by race conditions, causing the assertion error:

```
AssertionError: The number of observations and actions should be the same.
```

## Root Cause

```python
# server.py - Single global agent shared by ALL requests
_agent: PromptAgent | None = None

# prompt_agent.py - Mutable state on the shared instance
self.thoughts = []
self.actions = []
self.observations = []
```

When Task A and Task B run concurrently, both append to the same arrays, breaking the invariant that these arrays must stay synchronized.

## Solution: Per-Context Agent Instances

Instead of one global agent, create and store a separate `PromptAgent` instance for each task context. This isolates the trajectory state per-task.

---

## Implementation Steps

### Phase 1: Refactor Agent Management in `server.py`

**File: `white_agent/rest/server.py`**

#### 1.1 Replace global agent with per-context agent storage

```python
# REMOVE:
_agent: PromptAgent | None = None

def get_agent() -> PromptAgent:
    global _agent
    if _agent is None:
        _agent = PromptAgent(...)
    return _agent

# ADD:
from threading import Lock

# Per-context agent instances (context_id -> PromptAgent)
_context_agents: Dict[str, PromptAgent] = {}
_agents_lock = Lock()

def get_or_create_agent(context_id: str) -> PromptAgent:
    """Get or create a PromptAgent for the given context."""
    with _agents_lock:
        if context_id not in _context_agents:
            logger.info(f"Creating new PromptAgent for context {context_id}")
            _context_agents[context_id] = PromptAgent(
                model=MODEL,
                temperature=TEMPERATURE,
                observation_type=OBSERVATION_TYPE,
                action_space=ACTION_SPACE,
                max_trajectory_length=MAX_TRAJECTORY_LENGTH,
                max_tokens=MAX_TOKENS,
                top_p=TOP_P,
            )
        return _context_agents[context_id]

def cleanup_agent(context_id: str) -> None:
    """Remove agent instance when task completes."""
    with _agents_lock:
        if context_id in _context_agents:
            del _context_agents[context_id]
            logger.info(f"Cleaned up agent for context {context_id}")
```

#### 1.2 Update `/task` endpoint

```python
@app.post("/task")
def handle_task(task: A2ATask) -> A2AMessage:
    context_id = task.context_id or task.task_id

    try:
        # Get per-context agent (creates new one if needed)
        agent = get_or_create_agent(context_id)
    except Exception as e:
        return A2AMessage(...)

    # ... rest of handler ...

    # Cleanup on task completion
    if task_done:
        cleanup_agent(context_id)
        if context_id in conversation_contexts:
            del conversation_contexts[context_id]
```

#### 1.3 Update `/decide` endpoint

The `/decide` endpoint currently doesn't track context. We need to add context tracking:

```python
class Observation(BaseModel):
    frame_id: int
    image_png_b64: str
    instruction: str = ""
    accessibility_tree: str | None = None
    done: bool = False
    reset_before: bool = False
    stuck_feedback: str | None = None
    context_id: str | None = None  # NEW: Add context tracking

@app.post("/decide")
def decide(obs: Observation) -> Dict[str, Any]:
    # Use context_id if provided, otherwise generate one from instruction hash
    context_id = obs.context_id or f"decide_{hash(obs.instruction) % 10000}"

    try:
        agent = get_or_create_agent(context_id)
    except Exception as e:
        return {"op": "error", "args": {"message": str(e)}}

    # Handle reset_before by creating fresh agent
    if obs.reset_before:
        cleanup_agent(context_id)
        agent = get_or_create_agent(context_id)
        logger.info(f"Agent recreated for context {context_id}")

    # ... rest of handler ...

    # Cleanup if done
    if obs.done:
        cleanup_agent(context_id)
```

#### 1.4 Update `/reset` endpoint

```python
@app.post("/reset")
def reset():
    """Reset all agent state"""
    global _context_agents
    with _agents_lock:
        count = len(_context_agents)
        _context_agents = {}
    conversation_contexts.clear()
    logger.info(f"Reset complete: cleared {count} agent instances")
    return {"status": "reset", "model": MODEL, "cleared_agents": count}
```

#### 1.5 Update `/health` endpoint

```python
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "protocol": "rest",
        "model": MODEL,
        "observation_type": OBSERVATION_TYPE,
        "active_agents": len(_context_agents),
        "active_contexts": len(conversation_contexts)
    }
```

#### 1.6 Update debug endpoints

```python
@app.get("/debug/trajectory")
def debug_trajectory(context_id: str | None = None):
    """Debug endpoint to inspect agent trajectory history."""
    if not _context_agents:
        return {"status": "no_agents", "message": "No active agent instances"}

    if context_id:
        if context_id not in _context_agents:
            return {"status": "not_found", "context_id": context_id}
        agents_to_show = {context_id: _context_agents[context_id]}
    else:
        agents_to_show = _context_agents

    result = {}
    for ctx_id, agent in agents_to_show.items():
        result[ctx_id] = {
            "trajectory_length": len(agent.actions),
            "observations_count": len(agent.observations),
            "actions_count": len(agent.actions),
            "thoughts_count": len(agent.thoughts),
        }

    return {"status": "ok", "model": MODEL, "agents": result}
```

---

### Phase 2: Update Green Agent to Pass Context ID

**File: `green_agent/a2a/executor.py`** (or wherever white agent is called)

Ensure the green agent passes a unique `context_id` when calling the white agent's `/decide` endpoint:

```python
# When calling white agent
response = requests.post(
    f"{white_agent_url}/decide",
    json={
        "frame_id": step,
        "image_png_b64": screenshot_b64,
        "instruction": instruction,
        "accessibility_tree": a11y_tree,
        "done": done,
        "reset_before": step == 0,  # Reset on first step
        "stuck_feedback": stuck_feedback,
        "context_id": assessment_id,  # NEW: Pass assessment ID as context
    }
)
```

---

### Phase 3: Add Memory Management (Optional Enhancement)

To prevent memory leaks from abandoned contexts, add TTL-based cleanup:

```python
from datetime import datetime, timedelta
from threading import Thread
import time

# Track last access time
_agent_last_access: Dict[str, datetime] = {}
AGENT_TTL_MINUTES = 30

def get_or_create_agent(context_id: str) -> PromptAgent:
    with _agents_lock:
        _agent_last_access[context_id] = datetime.now()
        # ... existing logic ...

def cleanup_stale_agents():
    """Background task to clean up stale agents."""
    while True:
        time.sleep(300)  # Check every 5 minutes
        cutoff = datetime.now() - timedelta(minutes=AGENT_TTL_MINUTES)
        with _agents_lock:
            stale = [cid for cid, t in _agent_last_access.items() if t < cutoff]
            for cid in stale:
                if cid in _context_agents:
                    del _context_agents[cid]
                if cid in _agent_last_access:
                    del _agent_last_access[cid]
            if stale:
                logger.info(f"Cleaned up {len(stale)} stale agents")

# Start cleanup thread on startup
@app.on_event("startup")
async def startup_event():
    logger.info(f"White Agent (REST) starting - model={MODEL}")
    Thread(target=cleanup_stale_agents, daemon=True).start()
```

---

## Testing Plan

### Unit Tests

1. **Test concurrent requests don't interfere**
   - Launch two tasks simultaneously with different context IDs
   - Verify each maintains separate trajectory state

2. **Test context isolation**
   - Task A makes 3 predictions
   - Task B makes 2 predictions
   - Verify A has 3 observations/actions, B has 2

3. **Test cleanup on completion**
   - Complete a task
   - Verify agent instance is removed

### Integration Tests

1. **Multi-task batch test**
   - Launch 5 tasks simultaneously via webui
   - Verify all complete without assertion errors

2. **Stress test**
   - Launch 20 concurrent tasks
   - Monitor memory usage
   - Verify no assertion errors

---

## Rollback Plan

If issues arise, revert to the single-agent model with a mutex lock as a quick fix:

```python
from threading import Lock

_agent_lock = Lock()

@app.post("/decide")
def decide(obs: Observation) -> Dict[str, Any]:
    with _agent_lock:  # Serialize all requests
        # ... existing logic ...
```

This is slower but guarantees correctness while a proper fix is developed.

---

## Files to Modify

| File | Changes |
|------|---------|
| `white_agent/rest/server.py` | Replace global agent with per-context agents |
| `green_agent/a2a/executor.py` | Pass `context_id` (assessment_id) to white agent |
| `white_agent/rest/server.py` | Add TTL-based cleanup (optional) |

## Estimated Impact

- **Memory**: ~50MB per active agent instance (mostly model config, not weights)
- **Performance**: Slightly faster (no lock contention between tasks)
- **Correctness**: Eliminates race condition entirely
