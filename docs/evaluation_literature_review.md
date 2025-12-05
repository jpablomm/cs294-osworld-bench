# Evaluation Methods: Literature Review & Comparison

## 1. OSWorld's Current Approach

OSWorld uses **rule-based, outcome-focused evaluation**:

| Aspect | OSWorld Approach |
|--------|------------------|
| **When** | After task completion |
| **What** | Final state only |
| **How** | Programmatic checks (getters + metrics) |
| **Granularity** | Binary (pass/fail) or continuous score |

### Strengths
- Deterministic and reproducible
- No additional LLM costs
- Fast execution

### Weaknesses (from literature)
- **False negatives**: WebArena Verified found 11.3% false-negative rate in original evaluators
- **Brittleness**: Minor UI/state variations cause failures
- **No partial credit**: Agent that completes 90% of task scores same as 0%
- **Temporal instability**: Websites/apps change, breaking evaluators
- **Limited to final state**: Doesn't evaluate HOW the agent solved it

---

## 2. Alternative Evaluation Paradigms

### 2.1 LLM-as-Judge

**Used by**: WebVoyager, Mind2Web 2, various production systems

Instead of rule-based checks, use an LLM to evaluate:
```
Given:
- Task instruction: "Book a flight to NYC"
- Agent trajectory: [screenshot1, action1, screenshot2, action2, ...]
- Final state: [screenshot]

Did the agent successfully complete the task?
```

| Pros | Cons |
|------|------|
| Handles variations gracefully | Additional LLM cost per evaluation |
| Can evaluate subjective tasks | May have biases |
| No brittle selectors | Need to validate judge accuracy |
| 85.3% agreement with humans (WebVoyager) | Slower than rule-based |

**Key finding**: AgentRewardBench found that rule-based evaluations often *underreport* agent success rates.

---

### 2.2 Process Reward Models (PRMs)

**Research**: AgentPRM, InversePRM, Fin-PRM, GUI-PRA

Instead of only evaluating the final outcome, evaluate **each step**:

```
Step 1: Click on File menu     → Score: 0.9 (good progress)
Step 2: Click on random area   → Score: 0.1 (regression)
Step 3: Click on Save As       → Score: 0.95 (recovered)
```

| Pros | Cons |
|------|------|
| Credit assignment for partial success | Requires training a reward model |
| Can guide search/planning | More complex infrastructure |
| Identifies where agents fail | Needs trajectory data |
| Enables RL fine-tuning | |

**Key insight**: Actions should be evaluated on "proximity to goal" and "progress made", not just correctness.

---

### 2.3 Hierarchical Evaluation (MMBench-GUI)

Evaluate at multiple levels:

| Level | What's Evaluated |
|-------|------------------|
| L1: Content Understanding | Can agent understand what's on screen? |
| L2: Element Grounding | Can agent locate UI elements? |
| L3: Task Automation | Can agent complete single tasks? |
| L4: Task Collaboration | Can agent do multi-app workflows? |

Also introduces **EQA (Efficiency-Quality-Aware)** metric:
- Not just "did it succeed?" but "how efficiently?"
- Penalizes unnecessary actions

---

### 2.4 Multi-Dimensional Evaluation

**Research**: ST-WebAgentBench, SecureWebArena

Beyond task success, evaluate:
- **Safety**: Did the agent avoid harmful actions?
- **Trustworthiness**: Did it follow policies?
- **Side effects**: Did it cause unintended changes?
- **Repetitiveness**: Did it get stuck in loops?

---

## 3. Comparison Matrix

| Approach | OSWorld | LLM-as-Judge | PRMs | Hierarchical |
|----------|---------|--------------|------|--------------|
| Evaluates final state | ✅ | ✅ | ✅ | ✅ |
| Evaluates trajectory | ❌ | Partial | ✅ | ✅ |
| Handles variations | ❌ | ✅ | ✅ | ✅ |
| Partial credit | ❌ | Possible | ✅ | ✅ |
| No extra LLM cost | ✅ | ❌ | ❌* | ❌ |
| Deterministic | ✅ | ❌ | ✅* | Depends |
| Identifies failure point | ❌ | Partial | ✅ | ✅ |

*After training

---

## 4. Key Gaps in OSWorld Evaluation

Based on the literature, these are the main improvement opportunities:

### Gap 1: No Partial Credit
**Problem**: Agent completes 8/10 steps correctly, scores 0.0
**Solution**: Step-level scoring or trajectory analysis

### Gap 2: Brittleness
**Problem**: Evaluators break when UI changes slightly
**Solution**: LLM-based verification or fuzzy matching

### Gap 3: No Trajectory Analysis
**Problem**: Can't tell if agent used efficient path vs. lucky stumble
**Solution**: Process reward models or trajectory scoring

### Gap 4: Binary Success Only
**Problem**: No insight into agent capabilities
**Solution**: Hierarchical evaluation (grounding, understanding, execution)

### Gap 5: No Efficiency Metric
**Problem**: 50-step solution scores same as 5-step solution
**Solution**: EQA-style metrics

### Gap 6: No Safety Evaluation
**Problem**: Agent might succeed but cause side effects
**Solution**: Multi-dimensional evaluation

---

## 5. Recommended Improvements (Prioritized)

### Tier 1: Quick Wins
1. **Add step counting to score** - Penalize inefficient solutions
2. **Fuzzy matching for text comparisons** - Already have `fuzzy_match`, use more broadly
3. **Log trajectory for post-hoc analysis** - Already collecting, make accessible

### Tier 2: Medium Effort
4. **LLM-as-Judge fallback** - When rule-based eval fails, use LLM
5. **Partial credit scoring** - Track which sub-goals were achieved
6. **Hierarchical metrics** - Separate grounding vs. execution failures

### Tier 3: Research-Level
7. **Train a Process Reward Model** - Per-step scoring
8. **Multi-dimensional safety metrics** - Side effect detection
9. **Self-improving evaluation** - Use failures to improve evaluators

---

## Sources

- [WebArena Verified](https://openreview.net/forum?id=CSIo4D7xLx) - Reducing false negatives
- [AgentBench (ICLR'24)](https://github.com/THUDM/AgentBench) - Multi-environment evaluation
- [AgentRewardBench](https://arxiv.org/abs/2502.10325) - LLM judges for trajectories
- [MMBench-GUI](https://arxiv.org/html/2507.19478) - Hierarchical evaluation
- [AgentPRM](https://arxiv.org/abs/2511.08325) - Process reward models
- [GUI Agents Survey](https://arxiv.org/html/2412.13501v1) - Comprehensive overview
- [OSWorld Verified](https://xlang.ai/blog/osworld-verified) - Known limitations
- [ST-WebAgentBench](https://arxiv.org/html/2410.06703v5) - Safety evaluation
- [Epoch AI OSWorld Analysis](https://epoch.ai/blog/what-does-osworld-tell-us-about-ais-ability-to-use-computers) - Benchmark limitations
