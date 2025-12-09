# Loop Detection & Stuck Recovery Improvements

## Overview

This document describes the improvements made to prevent the GUI agent from getting stuck in repetitive action loops (e.g., clicking the same coordinates repeatedly without making progress).

## Problem Statement

The white agent (based on OSWorld's PromptAgent) would frequently get stuck in loops:

```
Step 4: Click (847, 686) - "Click Save button"
Step 5: Click (847, 686) - "Click Save button again"
Step 6: Click (847, 686) - "Click Save button again"
Step 7: Click (847, 686) - "Click Save button again"
...continues until max steps
```

The LLM had no mechanism to detect that its actions weren't working and would repeat the same failed action indefinitely.

## Root Cause Analysis

| Issue | Description |
|-------|-------------|
| No action tracking | Previous actions weren't tracked or compared |
| No failure detection | No way to detect if an action succeeded or failed |
| No feedback loop | LLM received no signal that its action didn't work |
| Basic prompts | Prompts didn't instruct reflection on previous actions |

## Solution Architecture

We implemented a three-layer solution:

```
┌─────────────────────────────────────────────────────────────┐
│                     GREEN AGENT                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              ActionTracker                           │    │
│  │  - Tracks consecutive similar actions                │    │
│  │  - Detects loops after N repetitions                 │    │
│  │  - Generates feedback messages                       │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │         Feedback Injection                           │    │
│  │  - Injects stuck warnings into observations          │    │
│  │  - Modifies instruction with recovery guidance       │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     WHITE AGENT                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           Reflection Protocol (Prompts)              │    │
│  │  - Verify previous action result                     │    │
│  │  - Prevent repeating failed actions                  │    │
│  │  - Guide alternative approaches                      │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Details

### 1. ActionTracker (`green_agent/action_tracker.py`)

A new class that tracks actions and detects repetitive patterns:

```python
from green_agent.action_tracker import ActionTracker

tracker = ActionTracker(threshold=3, coordinate_tolerance=20)

# For each action from white agent:
status, feedback = tracker.add_action(action)

if status == "stuck":
    # Inject feedback into next observation
    observation["stuck_feedback"] = feedback
```

**Features:**
- Compares actions by type and parameters
- Uses coordinate tolerance for click comparisons (default: 20px)
- Configurable threshold (default: 3 consecutive similar actions)
- Generates detailed feedback messages for recovery

**Action Comparison Logic:**
- Click actions: Compare coordinates with tolerance
- Type actions: Compare text content
- Hotkey actions: Compare key combinations
- Other actions: Compare by type

### 2. Reflection Protocol (Prompt Improvements)

Added to `white_agent/prompts.py` in all main system prompts:

```
=== CRITICAL: REFLECTION BEFORE ACTION ===
Before deciding your next action, you MUST reflect on:

1. PREVIOUS ACTION VERIFICATION:
   - Did the last action achieve its intended result?
   - If the UI looks the same as before, your action likely FAILED.

2. LOOP PREVENTION:
   - NEVER repeat the exact same click coordinates more than twice.
   - If you've clicked the same location 2+ times with no change,
     try different coordinates or keyboard shortcuts.

3. STUCK RECOVERY:
   - If stuck, look for: popups, moved elements, wrong screen.
   - Consider keyboard navigation (Tab, Enter, Escape).
=== END REFLECTION ===
```

### 3. Feedback Injection

When stuck is detected, feedback is injected into the observation:

**In `green_agent/osworld_adapter.py`:**
```python
if stuck_feedback:
    obs_for_white["stuck_feedback"] = stuck_feedback
    obs_for_white["instruction"] = f"{stuck_feedback}\n\nOriginal task: {instruction}"
```

**In `white_agent/rest/server.py`:**
```python
if obs.stuck_feedback:
    instruction = f"{obs.stuck_feedback}\n\nOriginal task: {obs.instruction}"
```

### 4. Stuck Feedback Message

When 3+ consecutive similar actions are detected:

```
=== STUCK LOOP DETECTED ===
WARNING: You have attempted the same click at coordinates (847, 686)
3 times without any visible change in the UI.

This action is NOT working. You MUST try a DIFFERENT approach:
1. Look carefully at the current screenshot
2. Try clicking on a DIFFERENT element or location
3. Try using a keyboard shortcut instead (Tab, Enter, Escape)
4. If a dialog/popup appeared, interact with it first
5. If the element is not visible, try scrolling
6. If you cannot make progress, return FAIL

DO NOT repeat the same action again.
=== END WARNING ===
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ACTION_REPEAT_THRESHOLD` | 3 | Actions before triggering stuck detection |
| `ACTION_COORD_TOLERANCE` | 20 | Pixel tolerance for coordinate comparison |

## Files Modified

| File | Changes |
|------|---------|
| `green_agent/action_tracker.py` | **New file** - ActionTracker class |
| `green_agent/osworld_adapter.py` | Integrated ActionTracker, feedback injection |
| `white_agent/prompts.py` | Added reflection protocol to 3 prompts |
| `white_agent/rest/server.py` | Added `stuck_feedback` field, injection logic |

## Expected Behavior

### Before (stuck in loop):
```
Step 1: Click (847, 686)
Step 2: Click (847, 686)
Step 3: Click (847, 686)
Step 4: Click (847, 686)
...
Step 15: Max steps reached, task failed
```

### After (with loop detection):
```
Step 1: Click (847, 686)
Step 2: Click (847, 686) → Warning issued
Step 3: Click (847, 686) → STUCK DETECTED, feedback injected
Step 4: Agent receives feedback, tries keyboard shortcut (Ctrl+P)
Step 5: New dialog opens, agent proceeds
...
Task completed successfully
```

## Comparison with OSWorld Maestro

Our implementation is inspired by OSWorld's Maestro architecture but simplified:

| Feature | OSWorld Maestro | Our Implementation |
|---------|-----------------|-------------------|
| Loop detection | `rule_engine.py` | `action_tracker.py` |
| Threshold | Configurable | Configurable (default: 3) |
| Coordinate comparison | Excludes descriptive fields | Tolerance-based |
| Quality gates | Full evaluator LLM | Prompt-based guidance |
| State machine | 7 states with transitions | Not implemented |
| Replanning | Full replan on failure | FAIL signal only |

## Future Improvements (Phase 2-3)

1. **Memory System**: Store found information to avoid re-searching
2. **Action History in Prompts**: Show last N actions with success/failure
3. **State Machine**: Structured states (EXECUTE, REPLAN, DONE)
4. **Quality Check Gates**: Periodic evaluation of progress
5. **Screenshot Comparison**: Detect if UI actually changed

## Testing

To verify the implementation:

1. Run a task that triggers repeated clicking
2. Check logs for "STUCK LOOP DETECTED" message
3. Verify feedback is injected into observation
4. Confirm agent tries a different action after receiving feedback

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run assessment
python -m green_agent.a2a.server
```

## References

- OSWorld Maestro Rule Engine: `vendor/OSWorld/mm_agents/maestro/maestro/controller/rule_engine.py`
- OSWorld Evaluator Prompts: `vendor/OSWorld/mm_agents/maestro/prompts/module/evaluator/`
