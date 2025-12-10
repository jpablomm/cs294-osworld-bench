# White Agent Evaluation Methodology

## Overview

The Green Agent evaluates white agents using a **multi-level evaluation system** that combines:
1. **OSWorld's rule-based evaluators** (binary correctness checks)
2. **Efficiency-adjusted scoring** (penalizes inefficient solutions)
3. **Trajectory analysis** (behavioral insights from agent action sequences)
4. **Loop detection** (identifies stuck patterns)

This document describes each evaluation dimension, metrics, and provides concrete examples of how different trajectories are scored.

---

## Part 1: Core Evaluation Layers

### Layer 1: OSWorld Rule-Based Evaluation

**Purpose**: Determine if the white agent correctly completed the task.

**How it works**:
1. White agent executes actions on the VM desktop
2. After task completion (or max_steps reached), Green Agent runs the OSWorld evaluator
3. Evaluator uses **getters** to extract task results and **metrics** to compare against expected outcomes

**Getters** (result extraction):
- `file_exists`: Check if a file was created/deleted
- `file_content`: Read file contents
- `command_output`: Run shell command and capture output
- `ui_element`: Check UI state via accessibility tree
- `screenshot`: Visual similarity matching

**Metrics** (comparison functions):
- `exact_match`: Character-by-character equality
- `fuzzy_match`: String similarity with tolerance
- `regex_match`: Pattern matching
- `contains`: Substring presence
- `file_size_match`: Numeric comparison

**Example evaluator config from task JSON**:
```json
{
  "evaluator": {
    "func": "file_exists",
    "result": {"type": "file", "path": "/home/user/Documents/report.pdf"},
    "options": {"should_exist": true}
  }
}
```

**Output**: `base_score` (0.0 to 1.0)
- 1.0 = Task goal achieved
- 0.0 = Task goal not achieved

---

### Layer 2: Efficiency-Adjusted Scoring

**Purpose**: Distinguish between efficient and inefficient solutions.

**Why it matters**: 
- Two agents completing the same task in 5 vs 50 steps should not get identical scores
- Efficiency is a measure of agent capability: faster solutions show better understanding

**Formula**:
```
efficiency_ratio = min(1.0, expected_steps / steps_taken)
adjusted_score = (0.8 × base_score) + (0.2 × efficiency_ratio × base_score)
```

**Components**:
- **Baseline (expected_steps)**: Provided by task metadata, or estimated as `max_steps × 0.4`
- **Efficiency weight**: Fixed at 0.2 (efficiency is 20% of final score)
- **Correction weight**: Fixed at 0.8 (correctness is 80% of final score)

**Efficiency ratio calculation**:
- If steps ≤ baseline: ratio = 1.0 (optimal)
- If steps > baseline: ratio = baseline / steps (gradual decay)
- Maximum ratio: 1.0 (never exceeds optimal)

**Examples**:

| Steps Taken | Expected (Baseline) | Efficiency Ratio | Base Score | Adjusted Score | Interpretation |
|---|---|---|---|---|---|
| 5 | 6 | 1.0 (5 ≤ 6) | 1.0 | 1.0 | Perfect efficiency, full credit |
| 10 | 6 | 0.6 (6/10) | 1.0 | 0.92 | Good solution, slight penalty |
| 15 | 6 | 0.4 (6/15) | 1.0 | 0.88 | Works but inefficient |
| 20 | 6 | 0.3 (6/20) | 1.0 | 0.86 | Very inefficient solution |
| 10 | 6 | 0.6 | 0.5 | 0.56 | Partially correct, penalized |
| 10 | 6 | 0.6 | 0.0 | 0.0 | Failed task, no efficiency credit |

**Default baselines** (when expected_steps not specified):
- max_steps=15 → baseline = 6 steps
- max_steps=10 → baseline = 4 steps
- max_steps=20 → baseline = 8 steps

---

### Layer 3: Trajectory Analysis

**Purpose**: Understand agent behavior patterns and identify failure modes.

**What's tracked**:
- Sequence of actions taken
- Action frequencies
- Failed action executions
- Loop patterns
- Screenshot/thinking ratio

**Analysis function**: `analyze_trajectory(trajectory)`

**Output structure**:
```python
{
    # Basic metrics
    "total_steps": 12,                         # Total actions taken
    "action_counts": {                         # Frequency of each action type
        "click": 5,
        "type": 3,
        "screenshot": 2,
        "done": 1,
        "scroll": 1
    },
    "action_sequence": [                       # Chronological action list
        "click", "type", "click", "screenshot", "click", "click", "click", ...
    ],
    "unique_actions": 5,                       # Count of distinct action types
    
    # Loop detection
    "has_loops": True,
    "loop_details": [
        {
            "action": "click",                 # Which action repeated
            "start_index": 3,                  # Where it started
            "repeat_count": 4,                 # How many times consecutively
            "type": "consecutive_repeat"       # Or "pattern_repeat"
        }
    ],
    
    # Quality metrics
    "final_action": "done",                    # Last action taken
    "screenshot_ratio": 0.167,                 # Proportion of screenshot actions
    "error_count": 1,                          # Failed tool executions
    "avg_action_duration_ms": 245.3,           # Average action latency
    
    # Diagnostic warnings
    "warnings": [                              # Potential issues detected
        "Detected 1 action loop(s)",
        "High screenshot ratio may indicate agent confusion"
    ]
}
```

**Loop types**:

1. **Consecutive repeat**: Same action repeated 3+ times in a row
   - Example: `click, click, click, click` (agent clicking same location repeatedly)
   - Indicator: Agent stuck or confused

2. **Pattern repeat**: Short pattern repeated 3+ times
   - Example: `click, screenshot, click, screenshot, click, screenshot`
   - Indicator: Agent following repetitive strategy without progress

**Warning triggers**:
- **High screenshot ratio** (>50%): May indicate agent is confused or unsure of state
- **Action loops**: Detected 3+ repetitions of same action or pattern
- **High error rate** (>30% of actions failed): Tool execution issues or invalid actions

**Interpretation guide**:

| Metric | Good | Concerning | Bad |
|---|---|---|---|
| Total steps (with base_score=1.0) | 4-8 | 10-15 | 20+ |
| Screenshot ratio | <30% | 30-50% | >50% |
| Error count | 0 | 1-2 | >3 |
| Has loops | No | 1 loop | 2+ loops |
| Final action | "done" | - | Other |

---

## Part 2: Evaluation Flow

### Step-by-Step Process

```
1. TASK EXECUTION (White Agent)
   ├─ Green Agent sends task instruction to white agent
   ├─ White agent observes desktop state
   ├─ White agent reasons and executes actions
   ├─ Green Agent tracks trajectory (action sequences)
   └─ White agent returns when done or hits max_steps

2. RULE-BASED EVALUATION (OSWorld evaluator)
   ├─ Extract result using getter (file check, command output, etc.)
   ├─ Extract expected value using getter
   ├─ Apply metric function (exact_match, fuzzy_match, contains, etc.)
   └─ Return base_score (0.0 or 1.0, or intermediate for partial credit)

3. EFFICIENCY SCORING
   ├─ Count steps taken by white agent
   ├─ Get expected_steps from task metadata (or estimate)
   ├─ Calculate efficiency_ratio
   └─ Return adjusted_score incorporating efficiency

4. TRAJECTORY ANALYSIS
   ├─ Extract action sequences from trajectory
   ├─ Detect loops and patterns
   ├─ Calculate screenshot ratio and error counts
   ├─ Generate warnings
   └─ Return analysis report

5. FINAL RESULT STRUCTURE
   {
       "score": 0.92,                    # Final adjusted score (0.0-1.0)
       "base_score": 1.0,                # Raw correctness score
       "efficiency": {
           "adjusted_score": 0.92,
           "efficiency_ratio": 0.6,
           "steps_taken": 10,
           "expected_steps": 6
       },
       "trajectory_analysis": {
           "total_steps": 10,
           "action_counts": {...},
           "has_loops": False,
           "warnings": [...]
       }
   }
```

---

## Part 3: Trajectory Examples

### Example 1: Perfect Execution (Efficient, No Loops)

**Task**: "Create a file named 'test.txt' in the home directory with content 'Hello World'"

**White Agent Trajectory**:
```
Step 0: action={"op": "screenshot", "args": {}}
        → Observes desktop with file manager icon visible

Step 1: action={"op": "click", "args": {"x": 100, "y": 200}}
        → Clicks file manager icon

Step 2: action={"op": "type", "args": {"text": "test.txt"}}
        → Types filename in "New File" dialog

Step 3: action={"op": "click", "args": {"x": 300, "y": 400}}
        → Clicks "Create" button

Step 4: action={"op": "type", "args": {"text": "Hello World"}}
        → Types file content

Step 5: action={"op": "hotkey", "args": {"keys": "ctrl+s"}}
        → Saves file with Ctrl+S

Step 6: action={"op": "done", "args": {}}
        → Reports task completion
```

**Evaluation Results**:

**Rule-Based Evaluation**:
- Evaluator runs: `file_exists("/home/user/test.txt")`
- Result: File exists with correct content
- Base score: **1.0**

**Efficiency Scoring**:
- Steps taken: 7
- Expected steps: 5 (metadata or estimated from max_steps=15 → 6 baseline, but agent was slightly faster)
- Efficiency ratio: min(1.0, 5/7) = 0.71
- Adjusted score: 0.8 × 1.0 + 0.2 × 0.71 × 1.0 = **0.942**

**Trajectory Analysis**:
```json
{
    "total_steps": 7,
    "action_counts": {
        "screenshot": 1,
        "click": 2,
        "type": 2,
        "hotkey": 1,
        "done": 1
    },
    "action_sequence": ["screenshot", "click", "type", "click", "type", "hotkey", "done"],
    "unique_actions": 6,
    "has_loops": false,
    "loop_details": null,
    "final_action": "done",
    "screenshot_ratio": 0.143,
    "error_count": 0,
    "avg_action_duration_ms": 320.5,
    "warnings": [],
    "analysis_status": "complete"
}
```

**Final Score: 0.942** ✅ Efficient and correct

---

### Example 2: Correct but Inefficient (Loops Detected)

**Task**: "Create a file named 'test.txt' in the home directory"

**White Agent Trajectory**:
```
Step 0: action={"op": "screenshot", "args": {}}
Step 1: action={"op": "click", "args": {"x": 100, "y": 200}}
Step 2: action={"op": "type", "args": {"text": "test.txt"}}
Step 3: action={"op": "screenshot", "args": {}}
Step 4: action={"op": "click", "args": {"x": 300, "y": 400}}     ← Wrong button
Step 5: action={"op": "screenshot", "args": {}}
Step 6: action={"op": "click", "args": {"x": 300, "y": 400}}     ← Clicks same button again
Step 7: action={"op": "screenshot", "args": {}}
Step 8: action={"op": "click", "args": {"x": 300, "y": 400}}     ← Still clicking same button
Step 9: action={"op": "screenshot", "args": {}}
        → Green Agent detects loop, injects "STUCK LOOP DETECTED" warning
Step 10: action={"op": "click", "args": {"x": 350, "y": 400}}    ← Tries different location
Step 11: action={"op": "screenshot", "args": {}}
Step 12: action={"op": "done", "args": {}}
```

**Evaluation Results**:

**Rule-Based Evaluation**:
- File exists: Yes
- Base score: **1.0**

**Efficiency Scoring**:
- Steps taken: 13
- Expected steps: 6
- Efficiency ratio: 6/13 ≈ 0.46
- Adjusted score: 0.8 × 1.0 + 0.2 × 0.46 × 1.0 = **0.892**

**Trajectory Analysis**:
```json
{
    "total_steps": 13,
    "action_counts": {
        "screenshot": 5,
        "click": 7,
        "done": 1
    },
    "action_sequence": [
        "screenshot", "click", "type", "screenshot", "click", "screenshot",
        "click", "screenshot", "click", "screenshot", "click", "screenshot", "done"
    ],
    "unique_actions": 3,
    "has_loops": true,
    "loop_details": [
        {
            "action": "click",
            "start_index": 4,
            "repeat_count": 3,
            "type": "consecutive_repeat"
        }
    ],
    "final_action": "done",
    "screenshot_ratio": 0.385,
    "error_count": 0,
    "avg_action_duration_ms": 450.2,
    "warnings": [
        "Detected 1 action loop(s)",
        "High screenshot ratio may indicate agent confusion"
    ],
    "analysis_status": "complete"
}
```

**Interpretation**:
- ✅ Task completed (correct file created)
- ⚠️ Inefficient execution (13 vs 6 steps)
- ⚠️ Got stuck in loop (repeated click)
- ⚠️ High screenshot ratio (38.5%) suggests confusion
- ✅ Recovered from loop after Green Agent feedback

**Final Score: 0.892** ⚠️ Correct but inefficient

---

### Example 3: Failed Task (No Correctness)

**Task**: "Create a file named 'test.txt' in the home directory"

**White Agent Trajectory**:
```
Step 0: action={"op": "screenshot", "args": {}}
Step 1: action={"op": "click", "args": {"x": 500, "y": 200}}
Step 2: action={"op": "screenshot", "args": {}}
Step 3: action={"op": "click", "args": {"x": 500, "y": 200}}     ← Repeatedly clicking wrong location
Step 4: action={"op": "screenshot", "args": {}}
Step 5: action={"op": "click", "args": {"x": 500, "y": 200}}
Step 6: action={"op": "screenshot", "args": {}}
Step 7: action={"op": "click", "args": {"x": 500, "y": 200}}
Step 8: action={"op": "screenshot", "args": {}}
Step 9: action={"op": "click", "args": {"x": 500, "y": 200}}
Step 10: action={"op": "screenshot", "args": {}}
        → Max steps reached, agent didn't complete task
```

**Evaluation Results**:

**Rule-Based Evaluation**:
- File exists: No
- Base score: **0.0**

**Efficiency Scoring**:
- Steps taken: 11
- Expected steps: 6
- Even with efficiency: 0.8 × 0.0 + 0.2 × (6/11) × 0.0 = **0.0**
  - When base_score=0, efficiency doesn't matter (failed task gets 0)

**Trajectory Analysis**:
```json
{
    "total_steps": 11,
    "action_counts": {
        "screenshot": 6,
        "click": 5
    },
    "action_sequence": [
        "screenshot", "click", "screenshot", "click", "screenshot", "click",
        "screenshot", "click", "screenshot", "click", "screenshot"
    ],
    "unique_actions": 2,
    "has_loops": true,
    "loop_details": [
        {
            "action": "click",
            "start_index": 1,
            "repeat_count": 5,
            "type": "consecutive_repeat"
        }
    ],
    "final_action": "screenshot",
    "screenshot_ratio": 0.545,
    "error_count": 0,
    "avg_action_duration_ms": 400.0,
    "warnings": [
        "Detected 1 action loop(s)",
        "High screenshot ratio may indicate agent confusion"
    ],
    "analysis_status": "complete"
}
```

**Interpretation**:
- ❌ Task failed (file not created)
- ❌ Severe inefficiency (11 steps with no progress)
- ❌ Stuck in loop (repeated same click)
- ❌ Very high screenshot ratio (54.5%) indicates complete confusion
- ❌ Never called "done" action

**Final Score: 0.0** ❌ Task failed

---

### Example 4: Partial Credit (Intermediate Score)

**Task**: "Save a text document with specific formatting"

**White Agent Trajectory** (simplified):
```
Step 0: action={"op": "screenshot", "args": {}}
Step 1: action={"op": "click", "args": {"x": 100, "y": 200}}     ← Open text editor
Step 2: action={"op": "type", "args": {"text": "Document content"}}
Step 3: action={"op": "hotkey", "args": {"keys": "ctrl+s"}}
Step 4: action={"op": "done", "args": {}}
```

**Evaluation Results**:

**Rule-Based Evaluation**:
- Evaluator has multiple sub-metrics:
  1. File created: ✅ Yes (1.0)
  2. Contains text: ✅ Yes (1.0)
  3. Formatting correct: ❌ No (0.0)
- Multiple metrics with AND conjunction: average = (1.0 + 1.0 + 0.0) / 3 = **0.667**

**Efficiency Scoring**:
- Steps taken: 4
- Expected steps: 5
- Efficiency ratio: 5/4 = 1.0 (better than expected)
- Adjusted score: 0.8 × 0.667 + 0.2 × 1.0 × 0.667 = **0.667** (no efficiency bonus, only penalty)

**Trajectory Analysis**:
```json
{
    "total_steps": 4,
    "action_counts": {
        "screenshot": 1,
        "click": 1,
        "type": 1,
        "hotkey": 1,
        "done": 1
    },
    "has_loops": false,
    "screenshot_ratio": 0.2,
    "error_count": 0,
    "warnings": []
}
```

**Final Score: 0.667** ⚠️ Partial success

---

## Part 4: Score Interpretation Guide

### Score Ranges

| Score Range | Assessment | Interpretation |
|---|---|---|
| 0.95-1.0 | Excellent | Perfect or near-perfect execution |
| 0.90-0.95 | Very Good | Minor inefficiency, but correct |
| 0.85-0.90 | Good | Correct with moderate inefficiency |
| 0.75-0.85 | Fair | Correct but significant inefficiency or some issues |
| 0.50-0.75 | Poor | Major issues: loops, confusion, partial completion |
| 0.0-0.50 | Failed | Task not completed, agent stuck |

### How Efficiency Affects Score

The 20/80 split means:
- **Correctness is paramount** (80%): Getting the right result is most important
- **Efficiency matters** (20%): But differences in speed have limited impact on final score

**Example impact**:
- Perfect task (base=1.0) with poor efficiency (6 steps/15 max): 1.0 → 0.88 (12% reduction)
- Perfect task with good efficiency (6 steps/6 expected): 1.0 → 1.0 (0% reduction)
- Failed task (base=0.0): No matter efficiency: 0.0 → 0.0 (no credit)

### Leaderboard Metrics

The system tracks multiple metrics for agent rankings:

| Metric | Formula | Example |
|---|---|---|
| Success Rate | Tasks_successful / Total_tasks | 45/50 = 90% |
| Average Score | Sum_of_scores / Total_tasks | 38.5 / 50 = 0.77 |
| Average Steps | Sum_of_steps / Successful_tasks | 200 / 45 = 4.4 |
| Average Time | Sum_of_time_sec / Successful_tasks | 1200 / 45 = 26.7s |

---

## Part 5: Advanced Features

### Loop Detection & Recovery

When ActionTracker detects repeated actions (3+ consecutive):

1. **Warning phase** (repeat_count = threshold - 1):
   - Injects message: "You've tried the same {action} {repeat_count} times. If the screen hasn't changed, consider trying a different approach."

2. **Stuck phase** (repeat_count ≥ threshold):
   - Injects detailed feedback with coordinate suggestions from accessibility tree
   - Format: "STUCK LOOP DETECTED: Tried clicking at (x, y) {repeat_count} times. Consider: [alternative actions from a11y tree]"

### LLM Fallback Evaluation

When rule-based evaluation returns 0.0 but screenshots exist:

```python
# Use LLM (GPT-4V or Claude) to judge if task was semantically completed
llm_judgment = evaluate_with_llm(
    task_instruction=task["instruction"],
    screenshot_before=initial_screenshot,
    screenshot_after=final_screenshot,
    trajectory=action_sequence,
    confidence_threshold=0.85
)

if llm_judgment["success"] and confidence > threshold:
    score = llm_judgment["score"]  # May be intermediate value
else:
    score = 0.0  # Keep conservative approach
```

---

## Summary

**Key takeaways**:

1. **Multi-layer evaluation** captures both correctness and behavioral insights
2. **Efficiency scoring** distinguishes between fast and slow solutions (20% weight)
3. **Trajectory analysis** reveals agent struggles (loops, confusion) without penalizing
4. **Three score components**: base_score, efficiency, trajectory_analysis
5. **Final score** (0.0-1.0) combines correctness and efficiency
6. **Warnings** flag behavioral issues for manual investigation

**Example dashboard view**:
```
Task: Create a new document
Success: ✅ Yes
Final Score: 0.892

Base Score: 1.0 (task completed correctly)
Efficiency: 0.60 (took 10 steps, expected 6)
Adjusted Score: 0.892 = 0.8(1.0) + 0.2(0.60)(1.0)

Trajectory: 10 steps
- Actions: click(2), type(2), screenshot(3), scroll(1), done(1)
- Loops Detected: 1 (screenshot repeated 3x)
- Warnings: High screenshot ratio indicates confusion
- Recovery: Agent recovered after Green Agent feedback
```

