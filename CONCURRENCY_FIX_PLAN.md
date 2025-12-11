# Implementation Plan: Stateless White Agent for Cloud Run

## Problem Summary

The White Agent runs on **Cloud Run** which:
- Auto-scales multiple container instances under load
- Routes requests to any available instance (no sticky sessions)
- Expects stateless containers

The current white agent has a **global `PromptAgent` singleton** with mutable state (`observations`, `actions`, `thoughts` arrays). This causes:

1. **Intra-instance race conditions**: Multiple concurrent requests to same instance corrupt shared arrays
2. **Cross-instance inconsistency**: Request 1 hits Instance A, Request 2 hits Instance B - trajectory lost

```
AssertionError: The number of observations and actions should be the same.
```

## Solution: Stateless White Agent

Make the white agent **completely stateless** - pass trajectory in each request. The green agent owns all state.

### Why This Fits Cloud Run

| Cloud Run Behavior | Stateless Design |
|-------------------|------------------|
| Multiple instances | Any instance can handle any request |
| No sticky sessions | No session state needed |
| Scale to zero | No warm-up state required |
| Concurrent requests | Each request independent |

---

## Architecture

```
┌────────────────────────┐      ┌─────────────────────────────────┐
│     Green Agent        │      │    White Agent (Cloud Run)      │
│     (Cloud Run)        │      │    (stateless, auto-scaled)     │
│                        │      │                                 │
│  ┌──────────────────┐  │      │  ┌───────────────────────────┐  │
│  │ Task A           │  │      │  │ Instance 1                │  │
│  │  - trajectory[]  │──┼─────►│  │  - No global state        │  │
│  │  - vm_info       │  │      │  │  - Fresh agent per request│  │
│  └──────────────────┘  │      │  └───────────────────────────┘  │
│                        │      │                                 │
│  ┌──────────────────┐  │      │  ┌───────────────────────────┐  │
│  │ Task B           │──┼─────►│  │ Instance 2                │  │
│  │  - trajectory[]  │  │      │  │  - No global state        │  │
│  │  - vm_info       │  │      │  │  - Fresh agent per request│  │
│  └──────────────────┘  │      │  └───────────────────────────┘  │
│                        │      │                                 │
│  ┌──────────────────┐  │      │  ┌───────────────────────────┐  │
│  │ Task C           │──┼─────►│  │ Instance N (auto-scaled)  │  │
│  │  - trajectory[]  │  │      │  │  - No global state        │  │
│  │  - vm_info       │  │      │  │  - Fresh agent per request│  │
│  └──────────────────┘  │      │  └───────────────────────────┘  │
│                        │      │                                 │
└────────────────────────┘      └─────────────────────────────────┘
         │                                    │
         │         Per-request flow:          │
         │  1. POST /decide                   │
         │     {screenshot, instruction,      │
         │      trajectory: [...]}            │
         │                                    │
         │  2. Response                       │
         │     {action, thought}              │
         │                                    │
         ▼                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                        GCE VMs                                   │
│   VM-A (task-a)    VM-B (task-b)    VM-C (task-c)              │
│   OSWorld server   OSWorld server   OSWorld server              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Phase 1: Update White Agent (Cloud Run Service)

**File: `white_agent/rest/server.py`**

#### 1.1 Add trajectory models

```python
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class TrajectoryStep(BaseModel):
    """Single step in trajectory history (text only, no screenshots)."""
    accessibility_tree: Optional[str] = None  # Trimmed a11y tree summary
    action: Any  # The parsed action {op: str, args: dict}
    thought: str  # LLM response text


class Observation(BaseModel):
    """Request model - includes trajectory for stateless operation."""
    frame_id: int
    image_png_b64: str
    instruction: str = ""
    accessibility_tree: Optional[str] = None
    done: bool = False
    stuck_feedback: Optional[str] = None
    # Trajectory passed by green agent (no screenshots - text only)
    trajectory: List[TrajectoryStep] = []


class DecideResponse(BaseModel):
    """Response model - returns data for green agent to store."""
    action: Dict[str, Any]  # Parsed action {op: str, args: dict}
    thought: str  # Raw LLM response
    # Processed observation data for green agent to store in trajectory
    trajectory_step: TrajectoryStep
```

#### 1.2 Remove global state

```python
# REMOVE these:
_agent: PromptAgent | None = None
conversation_contexts: Dict[str, Dict[str, Any]] = {}

def get_agent() -> PromptAgent:  # REMOVE
    ...
```

#### 1.3 Rewrite `/decide` endpoint (stateless)

```python
@app.post("/decide", response_model=DecideResponse)
def decide(obs: Observation) -> DecideResponse:
    """
    Stateless action decision endpoint.

    - Creates fresh PromptAgent per request
    - Rebuilds trajectory from request payload
    - Returns action + data for caller to store

    This design supports Cloud Run auto-scaling and concurrent requests.
    """
    try:
        # Create fresh agent for this request (no shared state)
        agent = PromptAgent(
            model=MODEL,
            temperature=TEMPERATURE,
            observation_type=OBSERVATION_TYPE,
            action_space=ACTION_SPACE,
            max_trajectory_length=MAX_TRAJECTORY_LENGTH,
            max_tokens=MAX_TOKENS,
            top_p=TOP_P,
        )

        # Rebuild trajectory from request (last N steps only)
        # Note: Screenshots NOT included in trajectory - only current obs has screenshot
        for step in obs.trajectory[-MAX_TRAJECTORY_LENGTH:]:
            agent.observations.append({
                "screenshot": None,  # Not needed for history
                "accessibility_tree": step.accessibility_tree,
            })
            agent.actions.append(step.action)
            agent.thoughts.append(step.thought)

        # Build current observation (this one HAS the screenshot)
        obs_for_agent = {"screenshot": obs.image_png_b64}
        if obs.accessibility_tree:
            obs_for_agent["accessibility_tree"] = obs.accessibility_tree

        # Inject stuck feedback if present
        instruction = obs.instruction
        if obs.stuck_feedback:
            logger.warning(f"[LoopDetection] Stuck feedback for frame {obs.frame_id}")
            instruction = f"{obs.stuck_feedback}\n\nOriginal task: {obs.instruction}"

        # Get prediction from LLM
        response, actions = agent.predict(instruction, obs_for_agent)

        # Parse action using robust parser
        parsed_action = parse_actions(response)

        # Build trajectory step for green agent to store
        trajectory_step = TrajectoryStep(
            accessibility_tree=obs.accessibility_tree[:2000] if obs.accessibility_tree else None,
            action=parsed_action,
            thought=response,
        )

        return DecideResponse(
            action=parsed_action,
            thought=response,
            trajectory_step=trajectory_step,
        )

    except Exception as e:
        logger.error(f"Decide failed: {e}", exc_info=True)
        error_step = TrajectoryStep(
            accessibility_tree=None,
            action={"op": "error", "args": {"message": str(e)}},
            thought=f"Error: {e}",
        )
        return DecideResponse(
            action={"op": "error", "args": {"message": str(e)}},
            thought=f"Error: {e}",
            trajectory_step=error_step,
        )
```

#### 1.4 Update `/task` endpoint (A2A format, stateless)

```python
class A2ATask(BaseModel):
    """A2A-compatible task request."""
    task_id: str
    context_id: Optional[str] = None
    message: str
    metadata: Optional[Dict[str, Any]] = None
    trajectory: List[TrajectoryStep] = []  # For stateless operation


@app.post("/task")
def handle_task(task: A2ATask) -> A2AMessage:
    """Handle A2A task request (stateless)."""
    try:
        # Create fresh agent
        agent = PromptAgent(
            model=MODEL,
            temperature=TEMPERATURE,
            observation_type=OBSERVATION_TYPE,
            action_space=ACTION_SPACE,
            max_trajectory_length=MAX_TRAJECTORY_LENGTH,
            max_tokens=MAX_TOKENS,
            top_p=TOP_P,
        )

        # Rebuild trajectory
        for step in task.trajectory[-MAX_TRAJECTORY_LENGTH:]:
            agent.observations.append({
                "screenshot": None,
                "accessibility_tree": step.accessibility_tree,
            })
            agent.actions.append(step.action)
            agent.thoughts.append(step.thought)

        # Parse observation from metadata
        if not task.metadata or "observation" not in task.metadata:
            raise ValueError("Task must have observation in metadata")

        observation = parse_observation(task.metadata)
        obs_for_agent = {"screenshot": observation["screenshot"]}
        if observation.get("accessibility_tree"):
            obs_for_agent["accessibility_tree"] = observation["accessibility_tree"]

        # Get prediction
        response, actions = agent.predict(observation["instruction"], obs_for_agent)
        parsed_action = parse_actions(response)

        # Build trajectory step for response
        trajectory_step = TrajectoryStep(
            accessibility_tree=observation.get("accessibility_tree", "")[:2000] if observation.get("accessibility_tree") else None,
            action=parsed_action,
            thought=response,
        )

        return A2AMessage(
            message_id=str(uuid.uuid4()),
            task_id=task.task_id,
            context_id=task.context_id or task.task_id,
            role="agent",
            content=response,
            metadata={
                "action": parsed_action,
                "done": parsed_action.get("op") == "done",
                "trajectory_step": trajectory_step.dict(),
            }
        )

    except Exception as e:
        logger.error(f"Task failed: {e}", exc_info=True)
        return A2AMessage(
            message_id=str(uuid.uuid4()),
            task_id=task.task_id,
            context_id=task.context_id or task.task_id,
            role="agent",
            content=f"Error: {e}",
            metadata={"status": "error", "error": str(e)}
        )
```

#### 1.5 Simplify other endpoints

```python
@app.get("/health")
def health():
    """Health check - stateless service."""
    return {
        "status": "healthy",
        "protocol": "rest",
        "model": MODEL,
        "observation_type": OBSERVATION_TYPE,
        "stateless": True,
        "cloud_run_optimized": True,
    }


@app.post("/reset")
def reset():
    """Reset - no-op for stateless service."""
    return {"status": "ok", "message": "Stateless service - nothing to reset"}


@app.get("/debug/trajectory")
def debug_trajectory():
    """Debug - trajectory is managed by green agent."""
    return {
        "status": "stateless",
        "message": "Trajectory managed by green agent, not white agent",
    }
```

---

### Phase 2: Update Green Agent (Cloud Run Service)

**File: `green_agent/a2a/executor.py`**

#### 2.1 Add trajectory storage to assessment tracking

```python
# In GreenAgentExecutor.__init__ or assessment setup:
self.active_assessments: Dict[str, Dict[str, Any]] = {}

# Assessment structure now includes trajectory:
assessment = {
    "assessment_id": assessment_id,
    "status": "running",
    "vm_info": {...},
    "config": {...},
    "started_at": datetime.now().isoformat(),
    "trajectory": [],  # NEW: Green agent owns trajectory
}
```

#### 2.2 Update white agent call to pass/receive trajectory

```python
async def call_white_agent(
    self,
    white_agent_url: str,
    frame_id: int,
    screenshot_b64: str,
    instruction: str,
    accessibility_tree: Optional[str],
    stuck_feedback: Optional[str],
    trajectory: List[Dict[str, Any]],  # Pass trajectory
) -> Dict[str, Any]:
    """Call white agent with trajectory (stateless protocol)."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{white_agent_url}/decide",
            json={
                "frame_id": frame_id,
                "image_png_b64": screenshot_b64,
                "instruction": instruction,
                "accessibility_tree": accessibility_tree,
                "done": False,
                "stuck_feedback": stuck_feedback,
                "trajectory": trajectory,  # Pass accumulated trajectory
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()
```

#### 2.3 Update execution loop to maintain trajectory

```python
async def _execute_assessment(self, assessment_id: str, config: Dict[str, Any]):
    """Execute assessment with trajectory management."""

    # Get assessment record
    assessment = self.active_assessments[assessment_id]
    trajectory = assessment["trajectory"]  # Owned by green agent

    white_agent_url = config["white_agent_url"]
    instruction = config["instruction"]
    max_steps = config.get("max_steps", 15)

    for step in range(max_steps):
        # Get screenshot from VM
        screenshot_b64 = await self.get_screenshot(vm_ip)
        accessibility_tree = await self.get_accessibility_tree(vm_ip)

        # Check for stuck loop
        stuck_feedback = self.action_tracker.check_stuck(trajectory)

        # Call white agent WITH trajectory
        result = await self.call_white_agent(
            white_agent_url=white_agent_url,
            frame_id=step,
            screenshot_b64=screenshot_b64,
            instruction=instruction,
            accessibility_tree=accessibility_tree,
            stuck_feedback=stuck_feedback,
            trajectory=trajectory,  # Pass current trajectory
        )

        # Store step in trajectory (for next iteration)
        trajectory.append(result["trajectory_step"])

        # Execute action on VM
        action = result["action"]
        if action["op"] == "done":
            break

        await self.execute_action(vm_ip, action)

    # Save final trajectory to assessment record
    assessment["trajectory"] = trajectory
```

---

### Phase 3: Optimize Payload Size

Screenshots are ~1-2MB base64. The trajectory should NOT include screenshots.

#### 3.1 Trajectory contains text only

```python
class TrajectoryStep(BaseModel):
    """Text-only trajectory step (no screenshots)."""
    accessibility_tree: Optional[str] = None  # Trimmed to 2000 chars
    action: Any  # {op: str, args: dict}
    thought: str  # LLM response (trimmed if needed)
```

#### 3.2 Only current observation has screenshot

```python
# In /decide endpoint:
# Past observations - no screenshot
for step in obs.trajectory:
    agent.observations.append({
        "screenshot": None,  # Not included
        "accessibility_tree": step.accessibility_tree,
    })

# Current observation - HAS screenshot
obs_for_agent = {
    "screenshot": obs.image_png_b64,  # Only current
    "accessibility_tree": obs.accessibility_tree,
}
```

#### 3.3 Payload size comparison

| Scenario | Before (stateful) | After (stateless) |
|----------|------------------|-------------------|
| Request payload | ~2MB (screenshot) | ~2.05MB (screenshot + ~50KB trajectory text) |
| Server memory | ~50MB per task (stored screenshots) | ~0 (stateless) |
| Max concurrent | ~20 (memory bound) | Unlimited (Cloud Run scales) |

---

## Migration Path

### Step 1: Deploy White Agent Update (Backward Compatible)

The `trajectory` parameter defaults to empty list:
```python
trajectory: List[TrajectoryStep] = []
```

Old green agents send no trajectory → white agent works as before (no history).

### Step 2: Deploy Green Agent Update

Update green agent to:
1. Store trajectory per assessment
2. Pass trajectory in each white agent call
3. Store returned `trajectory_step` for next iteration

### Step 3: Verify & Scale

- Test concurrent tasks
- Verify no assertion errors
- Cloud Run auto-scales white agent instances as needed

---

## Files to Modify

| File | Changes |
|------|---------|
| `white_agent/rest/server.py` | Remove global state, accept trajectory, return trajectory_step |
| `green_agent/a2a/executor.py` | Own trajectory, pass to white agent, store results |
| `green_agent/a2a/server.py` | No changes (executor handles trajectory) |

---

## Testing Plan

### Unit Tests

1. **Stateless behavior**
   - Same trajectory + observation → same result
   - Empty trajectory → fresh context

2. **Trajectory reconstruction**
   - 5-step trajectory correctly rebuilds agent context

### Integration Tests

1. **Concurrent tasks on Cloud Run**
   - Deploy to Cloud Run
   - Launch 20 tasks simultaneously
   - Verify all complete without errors

2. **Cross-instance consistency**
   - Force requests to different instances
   - Verify trajectory maintains consistency

### Load Test

```bash
# Simulate 50 concurrent assessments
for i in {1..50}; do
  curl -X POST https://green-agent-xxx.run.app/api/assessments \
    -H "Content-Type: application/json" \
    -d '{"task_id": "test_'$i'"}' &
done
wait
```

---

## Cloud Run Configuration

### White Agent Service

```yaml
# cloud-run-white-agent.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: white-agent
spec:
  template:
    spec:
      containers:
        - image: gcr.io/PROJECT/white-agent:latest
          resources:
            limits:
              memory: "2Gi"
              cpu: "2"
          env:
            - name: MODEL
              value: "gpt-4o"
      # Allow concurrent requests per instance
      containerConcurrency: 10  # Multiple requests per instance OK (stateless)
      timeoutSeconds: 300
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"
        autoscaling.knative.dev/maxScale: "100"
```

### Green Agent Service

```yaml
# cloud-run-green-agent.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: green-agent
spec:
  template:
    spec:
      containers:
        - image: gcr.io/PROJECT/green-agent:latest
          resources:
            limits:
              memory: "4Gi"
              cpu: "4"
          env:
            - name: WHITE_AGENT_URL
              value: "https://white-agent-xxx.run.app"
      containerConcurrency: 20  # Each handles multiple assessments
      timeoutSeconds: 900  # Long timeout for VM operations
```

---

## Rollback Plan

If issues arise:

1. **Quick fix**: Revert green agent to not pass trajectory
   - White agent receives `trajectory=[]`
   - Behaves like original (stateless, no history)
   - Loses multi-turn context but works

2. **Full rollback**: Redeploy previous white agent version
   - Global state returns
   - Limit concurrency to 1 per instance via Cloud Run config

---

## Estimated Impact

| Metric | Before | After |
|--------|--------|-------|
| Concurrent tasks | ~10-20 (race conditions) | 100+ (stateless) |
| Cloud Run instances | 1 (concurrency=1 workaround) | N (auto-scaled) |
| Memory per instance | ~500MB (stored state) | ~100MB (stateless) |
| Request latency | Same | Same (+~5ms for trajectory parsing) |
| Fault tolerance | State lost on instance recycle | No state to lose |
| Cost | Higher (dedicated instances) | Lower (shared, auto-scaled) |
