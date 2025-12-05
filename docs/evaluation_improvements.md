# OSWorld Evaluation Improvements

This document describes enhancements made to the OSWorld evaluation system to address limitations identified through literature review.

## Background

The original OSWorld evaluation is binary and outcome-focused: it checks if the final state matches expectations, returning 1.0 (success) or 0.0 (failure). While deterministic and fast, this approach has limitations:

- Two agents completing the same task in 5 vs 50 steps get identical scores
- Minor text variations (case, whitespace) cause false negatives
- No visibility into agent behavior patterns or failure modes

We implemented four improvements to address these gaps.

---

## 1. Efficiency-Adjusted Scoring

### Problem
An agent that stumbles through 47 steps with loops and mistakes scores the same as one that efficiently completes the task in 5 steps.

### Solution
We calculate an efficiency ratio based on steps taken vs expected baseline:

```
efficiency_ratio = min(1.0, expected_steps / steps_taken)
adjusted_score = (0.8 × base_score) + (0.2 × efficiency_ratio × base_score)
```

### Examples

| Steps Taken | Expected | Efficiency | Base Score | Adjusted Score |
|-------------|----------|------------|------------|----------------|
| 5           | 6        | 1.0        | 1.0        | 1.0            |
| 10          | 6        | 0.6        | 1.0        | 0.92           |
| 15          | 6        | 0.4        | 1.0        | 0.88           |
| 5           | 6        | 1.0        | 0.0        | 0.0            |

### Configuration

```python
calculate_efficiency_score(
    base_score=1.0,
    steps_taken=10,
    expected_steps=6,      # From task metadata or heuristic
    max_steps=15,          # Fallback for baseline calculation
    efficiency_weight=0.2  # How much efficiency affects score
)
```

### Baseline Heuristic
When `expected_steps` is not provided, we use `max_steps × 0.4` as a reasonable baseline (e.g., 6 steps for a 15-step limit).

---

## 2. Tolerant Matching

### Problem
Exact string matching fails on minor variations:
- `"Hello World"` vs `"hello world"` (case)
- `"file.txt"` vs `"file.txt "` (trailing space)
- `"Projects"` vs `"Projecs"` (typo in expected value)

### Solution
A three-tier matching strategy:

1. **Exact match**: Direct string comparison
2. **Normalized match**: After lowercasing and whitespace normalization
3. **Fuzzy match**: Using rapidfuzz similarity with configurable threshold

### Examples

```python
tolerant_match("Hello World", "hello world")
# → {"score": 1.0, "match_type": "normalized"}

tolerant_match("file.txt  ", "file.txt")
# → {"score": 1.0, "match_type": "normalized"}

tolerant_match("Helo World", "Hello World")
# → {"score": 0.95, "match_type": "fuzzy"}

tolerant_match("completely different", "Hello World")
# → {"score": 0.0, "match_type": "no_match", "similarity": 0.12}
```

### Configuration

```python
tolerant_match(
    result="actual value",
    expected="expected value",
    threshold=0.85,        # Minimum similarity for fuzzy match
    ignore_case=True,      # Normalize case
    ignore_whitespace=True # Normalize whitespace
)
```

### Usage Note
This function is available for custom evaluation logic. It's not automatically applied to all metrics (to preserve backward compatibility), but can be used when writing new evaluators or as a fallback.

---

## 3. Trajectory Analysis

### Problem
When evaluation fails, there's no insight into why:
- Did the agent get stuck in a loop?
- Which actions failed?
- Was the agent confused (excessive screenshots)?

### Solution
Analyze the full action trajectory to extract behavioral insights:

```python
analyze_trajectory(trajectory)
```

### Output

```python
{
    "total_steps": 12,
    "action_counts": {"click": 5, "type": 3, "screenshot": 2, "done": 1, "scroll": 1},
    "action_sequence": ["click", "type", "click", ...],
    "unique_actions": 5,
    "has_loops": True,
    "loop_details": [
        {"action": "click", "start_index": 3, "repeat_count": 4, "type": "consecutive_repeat"}
    ],
    "final_action": "done",
    "screenshot_ratio": 0.167,
    "error_count": 1,
    "avg_action_duration_ms": 245.3,
    "warnings": ["Detected 1 action loop(s)"]
}
```

### Loop Detection

Two types of loops are detected:

1. **Consecutive repeats**: Same action 3+ times in a row
   - Example: `click, click, click, click`

2. **Pattern repeats**: Short patterns repeated 3+ times
   - Example: `click, screenshot, click, screenshot, click, screenshot`

### Warnings

Automatic warnings are generated for:
- High screenshot ratio (>50%) - may indicate confusion
- Action loops detected - agent may be stuck
- High error rate (>30%) - tool execution issues

---

## 4. LLM-as-Judge Fallback

### Problem
Rule-based evaluation can produce false negatives: the agent successfully completes a task, but the programmatic check fails due to:
- Timing issues (state not yet settled)
- UI variations (element positions shifted)
- Overly strict matching criteria
- Edge cases not covered by the evaluator

Research (AgentRewardBench) shows that rule-based evaluations often **underreport** agent success rates.

### Solution
When rule-based evaluation returns 0.0, invoke a vision LLM to analyze screenshots and determine if the task was actually completed:

```
Rule-based eval = 0.0
        ↓
Collect evidence (screenshots, actions, task instruction)
        ↓
Send to GPT-4o / Claude with structured prompt
        ↓
LLM returns: {success, confidence, reasoning}
        ↓
If confidence ≥ threshold → Override score
```

### Architecture

```
┌─────────────────────────────────────────────────┐
│              evaluate_task_with_llm_fallback()   │
├─────────────────────────────────────────────────┤
│  1. Run rule-based evaluation                    │
│         ↓                                        │
│     score > 0.0? → Return score                  │
│         ↓                                        │
│  2. Collect evidence                             │
│     - Screenshot before (initial state)          │
│     - Screenshot after (final state)             │
│     - Action sequence                            │
│     - Agent's reasoning                          │
│         ↓                                        │
│  3. Call vision LLM with evaluation prompt       │
│         ↓                                        │
│  4. Parse response, check confidence threshold   │
│         ↓                                        │
│  5. Override or confirm rule-based result        │
└─────────────────────────────────────────────────┘
```

### Configuration

```python
# Enable via assessment config
config = {
    "enable_llm_fallback": True,
    "llm_judge_provider": "openai",      # or "anthropic"
    "llm_judge_model": "gpt-4o",         # optional, uses provider default
    "llm_judge_confidence": 0.7,         # minimum confidence to trust LLM
}
```

### LLM Response Format

The LLM returns a structured JSON response:

```json
{
  "success": true,
  "confidence": 0.85,
  "reasoning": "The final screenshot shows a 'Projects' folder on the desktop. The agent clicked on the desktop, right-clicked to open context menu, selected 'New Folder', and typed the name. Despite the rule-based check failing (possibly due to icon position), the task goal was achieved.",
  "evidence_used": ["screenshot_after", "action_sequence"]
}
```

### Evaluation Methods

The `evaluation_method` field in results indicates how the score was determined:

| Method | Description |
|--------|-------------|
| `rule_based` | Standard programmatic evaluation |
| `llm_judge_override` | LLM overrode rule-based failure (false negative caught) |
| `rule_based_confirmed_by_llm` | LLM confirmed rule-based failure |
| `rule_based_llm_uncertain` | LLM confidence below threshold |
| `rule_based_llm_failed` | LLM call failed, kept rule-based result |

### Cost Analysis

| Component | Tokens | Cost (GPT-4o) |
|-----------|--------|---------------|
| Prompt + task | ~500 | $0.00125 |
| 2 screenshots (low-res) | ~1700 | $0.00425 |
| Response | ~200 | $0.002 |
| **Total per LLM eval** | ~2400 | **~$0.008** |

Assuming 30% of evaluations trigger fallback: **~$0.24 per 100 assessments**

### Example: False Negative Caught

```python
# Rule-based evaluation failed (icon position different than expected)
rule_based_score = 0.0

# LLM analyzes screenshots
llm_judgment = {
    "success": True,
    "confidence": 0.89,
    "reasoning": "The 'Projects' folder is visible on the desktop in the final screenshot..."
}

# Final result
{
    "score": 1.0,  # Overridden!
    "base_score": 0.0,
    "evaluation_method": "llm_judge_override",
    "evaluation_details": {
        "llm_judgment": {
            "success": True,
            "confidence": 0.89,
            "reasoning": "...",
            "provider": "openai",
            "model": "gpt-4o"
        }
    }
}
```

### Supported Providers

| Provider | Models | Notes |
|----------|--------|-------|
| OpenAI | gpt-4o, gpt-4o-mini | Best vision capabilities |
| Anthropic | claude-sonnet-4-20250514 | Strong reasoning |

---

## Integration

### Evaluation Result Structure

When `steps_taken` or `trajectory` is provided to `evaluate_task()`, the result includes enhanced data:

```python
{
    "score": 0.92,                    # Final adjusted score
    "base_score": 1.0,                # Raw correctness score
    "efficiency": {
        "adjusted_score": 0.92,
        "base_score": 1.0,
        "efficiency_ratio": 0.6,
        "steps_taken": 10,
        "expected_steps": 6
    },
    "trajectory_analysis": {
        "total_steps": 10,
        "action_counts": {...},
        "has_loops": False,
        "warnings": []
    },
    "task_id": "abc-123"
}
```

### Backward Compatibility

When called without the new parameters, `evaluate_task()` returns a simple float score as before:

```python
# Old behavior (still works)
score = evaluate_task(vm_ip, evaluator_config, task_id)
# → 1.0

# New behavior (with enhanced params)
result = evaluate_task(vm_ip, evaluator_config, task_id,
                       steps_taken=10, trajectory=trajectory)
# → {"score": 0.92, "base_score": 1.0, ...}
```

---

## Future Improvements

These quick wins lay groundwork for more advanced improvements:

1. **LLM-as-Judge fallback**: When rule-based evaluation fails, use an LLM to assess success
2. **Process Reward Model**: Train a model to score each step, not just final outcome
3. **Partial credit**: Track sub-goal completion for complex tasks
4. **Safety metrics**: Detect unintended side effects

See `docs/evaluation_literature_review.md` for detailed comparison with approaches from WebArena, AgentBench, and recent research.
