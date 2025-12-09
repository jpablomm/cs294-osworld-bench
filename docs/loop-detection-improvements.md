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

We implemented a four-layer solution:

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
│  │         ElementBoundsParser                          │    │
│  │  - Parses accessibility tree XML                     │    │
│  │  - Extracts element coordinates and bounds           │    │
│  │  - Finds nearby elements when click misses           │    │
│  │  - Suggests correct center coordinates               │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │         Feedback Injection                           │    │
│  │  - Injects stuck warnings into observations          │    │
│  │  - Includes coordinate guidance from a11y tree       │    │
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

### 2. ElementBoundsParser (`green_agent/element_bounds.py`)

Parses accessibility tree XML to extract element bounds and provide coordinate guidance:

```python
from green_agent.element_bounds import (
    ElementBoundsParser,
    validate_click_coordinates,
    generate_coordinate_guidance
)

# Parse accessibility tree
parser = ElementBoundsParser(platform="ubuntu")
elements = parser.parse(a11y_tree_xml)

# Check if a click hits an element
hit = parser.find_element_at(elements, click_x, click_y)

# Find nearby elements if missed
nearby = parser.find_nearby_elements(elements, click_x, click_y, max_distance=100)

# Generate guidance message
guidance = generate_coordinate_guidance(elements, click_x, click_y)
```

**Features:**
- Parses XML accessibility tree format from OSWorld VM
- Extracts element tag, name, text, position, and size
- Calculates element center coordinates
- Finds elements containing a point
- Finds nearby elements sorted by distance
- Generates human-readable coordinate suggestions

**Example Guidance Output:**
```
Your click at (847, 686) missed all interactive elements.

Nearby clickable elements:
  - button "Save": click at (875, 700) [28px away]
  - button "Cancel": click at (750, 700) [103px away]

SUGGESTION: Try clicking at (875, 700) for "button "Save""
```

### 3. Reflection Protocol (Prompt Improvements)

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

### 4. Feedback Injection

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

### 5. Stuck Feedback Message (with Coordinate Guidance)

When 3+ consecutive similar actions are detected, the feedback now includes coordinate guidance from the accessibility tree:

```
=== STUCK LOOP DETECTED ===
WARNING: You have attempted the same click at coordinates (847, 686)
3 times without any visible change in the UI.

This action is NOT working. You MUST try a DIFFERENT approach.

=== COORDINATE ANALYSIS ===
Your click at (847, 686) missed all interactive elements.

Nearby clickable elements:
  - button "Save": click at (875, 700) [28px away]
  - button "Cancel": click at (750, 700) [103px away]
  - button "Print": click at (920, 700) [85px away]

SUGGESTION: Try clicking at (875, 700) for "button "Save""
=== END ANALYSIS ===

RECOVERY OPTIONS:
1. If a nearby element was suggested above, click its CENTER coordinates
2. Try using a keyboard shortcut instead (Tab to focus, Enter to confirm)
3. If a dialog/popup appeared, interact with it first
4. If the element is not visible, try scrolling to find it
5. If you cannot make progress, return FAIL

DO NOT repeat the same action again. The next action MUST be different.
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
| `green_agent/action_tracker.py` | **New file** - ActionTracker class with a11y integration |
| `green_agent/element_bounds.py` | **New file** - ElementBoundsParser for coordinate guidance |
| `green_agent/osworld_adapter.py` | Integrated ActionTracker, a11y tree passing, feedback injection |
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

### After (with loop detection + coordinate guidance):
```
Step 1: Click (847, 686) - misses Save button by 28px
Step 2: Click (847, 686) → Warning issued
Step 3: Click (847, 686) → STUCK DETECTED
        → Feedback: "Nearby: button 'Save' at (875, 700)"
Step 4: Agent clicks (875, 700) - correct coordinates!
Step 5: Save dialog opens, agent proceeds
...
Task completed successfully
```

## Comparison with OSWorld Maestro

Our implementation is inspired by OSWorld's Maestro architecture but simplified, with a unique addition:

| Feature | OSWorld Maestro | Our Implementation |
|---------|-----------------|-------------------|
| Loop detection | `rule_engine.py` | `action_tracker.py` |
| Threshold | Configurable | Configurable (default: 3) |
| Coordinate comparison | Excludes descriptive fields | Tolerance-based (20px) |
| **Coordinate guidance** | ❌ Not implemented | ✅ `element_bounds.py` - suggests correct coords |
| Quality gates | Full evaluator LLM | Prompt-based guidance |
| State machine | 7 states with transitions | Not implemented |
| Replanning | Full replan on failure | FAIL signal only |

**Note:** The coordinate guidance feature using accessibility tree parsing is our unique addition - OSWorld Maestro does not have this capability.

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
