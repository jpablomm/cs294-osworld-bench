# AgentBeats Compliance Checklist

Quick reference for tracking implementation progress against AgentBeats guidelines.

---

## Core Principles (From Guidelines)

### ✅ Agent Standardization
- [ ] Any A2A-compatible agent can participate without manual adaptation
- [ ] No benchmark-specific knowledge required in white agent
- [ ] Tool interface is abstracted and portable

### ✅ Benchmark Agentification
- [ ] Assessment managed by green agent
- [ ] Green agent can receive external instructions
- [ ] Green agent coordinates tests automatically
- [ ] Green agent assesses white agent performance

### ✅ Consistency with Original Benchmark
- [ ] Metric values comparable to original OSWorld
- [ ] Results are meaningful and trustworthy
- [ ] Evaluation uses ground truth checking

### ✅ One-Command Execution
- [ ] Entire pipeline simple to run
- [ ] Single command launches assessment
- [ ] No manual intervention required

---

## Implementation Checklist

### Green Agent

#### A2A Protocol ✅ (Mostly Done)
- [x] Implements `/agent-card` endpoint
- [x] Returns valid AgentCard with capabilities
- [x] Implements `/task` endpoint accepting A2ATask
- [x] Returns A2AMessage with results
- [ ] **TODO:** Convert to task-based pattern (not message-only)
- [ ] **TODO:** Add progress streaming/push notifications

#### Tool Handling ⚠️ (Needs Work)
- [x] Builds tool descriptions from OSWorld API
- [x] Sends tools in A2A message (Approach II)
- [ ] **TODO:** Remove infrastructure details (VM IPs, endpoints)
- [ ] **TODO:** Add tool call format specification
- [ ] **TODO:** Provide tool usage examples
- [ ] **TODO:** Consider implementing Approach III (MCP server)

#### Task Description ❌ (Major Issues)
- [x] Includes task instruction
- [x] Includes step guidance
- [x] Specifies max steps
- [ ] **TODO:** Make truly self-explanatory (no OSWorld knowledge needed)
- [ ] **TODO:** Add tool call format examples
- [ ] **TODO:** Add success criteria
- [ ] **TODO:** Add environment context
- [ ] **TODO:** Remove HTTP endpoint information

#### Evaluation ❌ (Critical Issue)
- [x] Loads OSWorld task with evaluator config
- [x] Calls evaluate_task() function
- [ ] **TODO:** Fix "simplified" evaluation fallback
- [ ] **TODO:** Remove trust of white agent self-assessment
- [ ] **TODO:** Verify OSWorld evaluators work correctly
- [ ] **TODO:** Add partial credit scoring (not just 0/1)
- [ ] **TODO:** Fail loudly on evaluation errors
- [ ] **TODO:** Add pass^k metric support

#### VM Orchestration ✅ (Working)
- [x] Creates VMs from golden images
- [x] Executes OSWorld task setup via SetupController
- [x] Manages VM lifecycle
- [x] Handles cleanup on success
- [x] Handles cleanup on failure

#### Security 🔴 (Critical Issues)
- [ ] **TODO:** Fix code injection in _execute_osworld_action()
- [ ] **TODO:** Add input validation for coordinates
- [ ] **TODO:** Add input validation for text strings
- [ ] **TODO:** Use safe code execution (not string concatenation)

#### Error Handling ⚠️ (Needs Improvement)
- [x] Catches exceptions in main workflow
- [ ] **TODO:** Distinguish error types (network, VM, white agent, green agent)
- [ ] **TODO:** Add retry logic for network errors
- [ ] **TODO:** Improve VM cleanup reliability
- [ ] **TODO:** Add timeout per step (not just total)

---

### White Agent

#### A2A Protocol ✅ (Done)
- [x] Implements `/agent-card` endpoint
- [x] Returns valid AgentCard
- [x] Implements `/task` endpoint
- [x] Manages conversation contexts
- [x] Tracks tool descriptions from green agent
- [x] Returns A2AMessage with actions

#### Functionality 🔴 (Critical Issue)
- [ ] **TODO:** Replace stub with real implementation
- [ ] **TODO:** Integrate vision-language model (GPT-4V, Claude, etc.)
- [ ] **TODO:** Parse screenshots from observations
- [ ] **TODO:** Reason about task and current state
- [ ] **TODO:** Select appropriate tools
- [ ] **TODO:** Format tool calls correctly
- [ ] **TODO:** Handle tool responses

#### Tool Usage ❌ (Not Implemented)
- [x] Receives tool descriptions in A2A message
- [x] Stores tools in conversation context
- [ ] **TODO:** Actually use tool descriptions to decide actions
- [ ] **TODO:** Parse tool schemas
- [ ] **TODO:** Validate tool calls against schemas
- [ ] **TODO:** Handle tool call errors

#### Backward Compatibility ✅ (Done)
- [x] Maintains `/decide` endpoint
- [x] Maintains `/reset` endpoint
- [x] Can work with legacy green agent

---

### Launcher

#### Basic Functionality ✅ (Done)
- [x] Checks agent health
- [x] Fetches agent cards
- [x] Sends A2A task to green agent
- [x] Displays results
- [x] Proper exit codes

#### Advanced Features ❌ (Missing)
- [ ] **TODO:** Support parallel assessments
- [ ] **TODO:** Add progress tracking
- [ ] **TODO:** Support streaming updates
- [ ] **TODO:** Add cancellation support
- [ ] **TODO:** Support multiple task runs (pass^k)
- [ ] **TODO:** Add statistical aggregation

---

### Configuration & Platform

#### Assessment Configuration ❌ (Skipped)
- [ ] **TODO:** Define AssessmentConfig schema
- [ ] **TODO:** Support predefined configs
- [ ] **TODO:** Config validation
- [ ] **TODO:** Config templates
- [ ] **TODO:** Config by alias/reference

#### Platform Integration ❌ (Skipped)
- [ ] **TODO:** Metrics reporting API
- [ ] **TODO:** Agent registry
- [ ] **TODO:** Dynamic agent deployment
- [ ] **TODO:** Leaderboard integration
- [ ] **TODO:** Multi-agent assessment support

---

## Priority Tasks (Do These First)

### 🔴 Critical (Week 1 - 20 hours)

1. **White Agent - VLM Integration** (8 hours)
   - [ ] Choose VLM (GPT-4V, Claude 3.5 Sonnet, Gemini, etc.)
   - [ ] Set up API credentials
   - [ ] Implement vision processing
   - [ ] Implement tool calling logic
   - [ ] Test with simple task

   **Files:**
   - `white_agent/server.py` or `white_agent/gpt4v_server.py`

   **Success Criteria:**
   - White agent can view screenshot
   - White agent can read task instruction
   - White agent can select appropriate tool
   - White agent can format tool call correctly

2. **Evaluation - Ground Truth Checking** (6 hours)
   - [ ] Review `green_agent/osworld_evaluator.py`
   - [ ] Verify evaluate_task() uses OSWorld evaluators
   - [ ] Remove "simplified" fallback in a2a_green_agent.py
   - [ ] Test with known pass/fail tasks
   - [ ] Validate scores match OSWorld

   **Files:**
   - `green_agent/osworld_evaluator.py`
   - `orchestrator/a2a_green_agent.py:388-419`

   **Success Criteria:**
   - Completed tasks return success=1
   - Incomplete tasks return success=0
   - Scores match OSWorld ground truth

3. **Security - Fix Code Injection** (2 hours)
   - [ ] Replace string-based Python code generation
   - [ ] Use JSON-based action API if available
   - [ ] Add input validation
   - [ ] Test with malicious inputs

   **Files:**
   - `orchestrator/a2a_green_agent.py:839-949`

   **Success Criteria:**
   - Cannot inject code via text input
   - All inputs validated before use

4. **Task Format - Add Specification** (4 hours)
   - [ ] Add tool call format examples
   - [ ] Specify JSON structure with `<json>` tags
   - [ ] Add success criteria to task message
   - [ ] Test white agent can follow format

   **Files:**
   - `orchestrator/a2a_green_agent.py:627-671`

   **Success Criteria:**
   - Task message includes format examples
   - White agent understands format
   - Tool calls are properly structured

---

### 🟡 High Priority (Week 2 - 17 hours)

5. **Task Abstraction - Self-Explanatory** (3 hours)
   - [ ] Remove VM IP addresses from tool descriptions
   - [ ] Remove HTTP endpoint details
   - [ ] Use abstract tool names only
   - [ ] Add environment context

6. **Evaluation - Validation** (4 hours)
   - [ ] Test against 10 OSWorld tasks
   - [ ] Compare scores with original benchmark
   - [ ] Document any discrepancies
   - [ ] Fix evaluation issues found

7. **Error Handling - Improvements** (4 hours)
   - [ ] Classify error types
   - [ ] Add retry logic
   - [ ] Improve cleanup reliability
   - [ ] Add per-step timeouts

8. **Testing - Comprehensive** (6 hours)
   - [ ] Write unit tests for green agent
   - [ ] Write unit tests for white agent
   - [ ] Write integration tests
   - [ ] Write evaluation validation tests

---

### 🟢 Medium Priority (Weeks 3-4)

9. **Green Agent - Task-Based Pattern** (8 hours)
10. **Green Agent - Progress Streaming** (4 hours)
11. **Green Agent - Approach III (MCP)** (12 hours)
12. **Metrics - pass^k Support** (6 hours)
13. **Configuration - Framework** (8 hours)
14. **Launcher - Parallel Support** (6 hours)

---

## Testing Checklist

### Unit Tests
- [ ] Green agent tool description generation
- [ ] Green agent task message formatting
- [ ] Green agent action execution
- [ ] White agent context management
- [ ] White agent observation parsing
- [ ] Evaluation scoring logic

### Integration Tests
- [ ] End-to-end assessment with working white agent
- [ ] Multiple task runs
- [ ] Evaluation consistency
- [ ] Error handling (network failures, VM failures, etc.)
- [ ] Cleanup on success and failure

### Validation Tests
- [ ] Compare OSWorld evaluator scores with ground truth
- [ ] Test 10 tasks from each domain
- [ ] Verify pass^k metrics
- [ ] Benchmark performance vs original OSWorld

---

## Documentation Checklist

### For White Agent Developers
- [ ] White agent development guide
- [ ] Expected action format specification
- [ ] Tool descriptions format
- [ ] Testing guide
- [ ] Example implementations

### For Green Agent Users
- [ ] A2A protocol guide
- [ ] Launcher usage guide
- [ ] Configuration options
- [ ] Troubleshooting guide

### For Evaluators
- [ ] Evaluation system documentation
- [ ] Success criteria per task type
- [ ] Debugging evaluation failures
- [ ] Metrics interpretation

---

## Progress Tracking

### Current Status (Baseline)
- A2A Protocol: 85% complete
- Tool Handling: 60% complete
- Task Description: 40% complete
- Evaluation: 30% complete
- White Agent: 10% complete
- Platform: 40% complete
- **Overall: 47% complete**

### Target Milestones

**Week 1 (End):**
- A2A Protocol: 85%
- Tool Handling: 70%
- Task Description: 60%
- Evaluation: 80%
- White Agent: 60%
- **Overall Target: 65%**

**Week 2 (End):**
- A2A Protocol: 90%
- Tool Handling: 80%
- Task Description: 90%
- Evaluation: 95%
- White Agent: 80%
- **Overall Target: 80%**

**Week 4 (End):**
- All categories: 95%+
- **Overall Target: 95%**

---

## Quick Reference: File Locations

### Green Agent
```
orchestrator/a2a_green_agent.py     - Main A2A implementation
orchestrator/vm_manager.py          - VM orchestration
orchestrator/task_executor.py       - Task execution
green_agent/osworld_evaluator.py    - Evaluation logic
green_agent/osworld_client.py       - OSWorld REST client
```

### White Agent
```
white_agent/a2a_adapter.py          - A2A wrapper
white_agent/server.py               - Stub implementation (REPLACE)
white_agent/gpt4v_server.py         - GPT-4V implementation (USE)
```

### Launcher & Tools
```
launcher_a2a.py                     - A2A assessment launcher
examples/a2a_demo.py                - Interactive demo
```

### Documentation
```
README.md                           - Main documentation
AGENTBEATS_PROGRESS.md              - Implementation log
AGENTBEATS_GAP_ANALYSIS.md          - This assessment (detailed)
ASSESSMENT_EXECUTIVE_SUMMARY.md     - This assessment (summary)
```

---

## Questions to Guide Your Work

Before starting each task, ask:

1. **Does this make tasks more self-explanatory?**
   - Remove OSWorld-specific details
   - Add clear examples
   - Include all context needed

2. **Does this maintain evaluation consistency?**
   - Use OSWorld ground truth
   - Validate against original benchmark
   - Don't trust self-assessment

3. **Does this improve A2A compliance?**
   - Follow protocol exactly
   - Use task-based for long operations
   - Implement streaming for progress

4. **Does this work for any white agent?**
   - No hardcoded assumptions
   - Clear interfaces
   - Good documentation

---

**Last Updated:** 2025-11-11
**Next Review:** After completing Week 1 priorities

---

Use this checklist to track your progress. Check off items as you complete them. Update the "Progress Tracking" section weekly to measure improvement against compliance goals.
