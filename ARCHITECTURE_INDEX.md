# Green Agent Architecture Documentation Index

This folder contains comprehensive documentation of the Green Agent architecture, task execution flow, and evaluation mechanisms.

## Documentation Files

### 1. GREEN_AGENT_ARCHITECTURE.md (25 KB, 747 lines)
**Complete architectural reference for developers**

Contains:
- Executive summary of the system architecture
- Detailed task definition formats and conversion
- Complete execution flow diagrams for all 3 modes
- White agent communication protocol specification
- Assessment/evaluation logic (3-tier evaluation system)
- Data/artifacts capture mechanisms
- Complete file documentation with line numbers
- Task completion handlers and status tracking
- Scoring and evaluation logic
- Quick reference table of key files
- Environment variables documentation
- End-to-end flow example with data structures
- Data flow diagrams and integration points

**Use this for**: Understanding the complete system, implementation details, debugging, and extending functionality.

### 2. ARCHITECTURE_QUICK_REFERENCE.md (9 KB)
**Quick lookup guide for common questions**

Contains:
- System overview diagram
- Core files organized by layer (Execution, Evaluation, Storage, API)
- Execution modes comparison table
- Key data structures (Task, Observation, Action, Result)
- Execution flow summary
- Evaluation process diagram
- Artifact structure
- Database schema
- API endpoints summary
- Environment variables
- Critical execution paths (code snippets)
- Performance characteristics
- Common tasks and curl examples
- Troubleshooting guide
- Key concepts glossary

**Use this for**: Quick lookups, debugging specific issues, common operations.

### 3. ARCHITECTURE_INDEX.md (this file)
**Navigation guide for the documentation**

---

## Quick Navigation

### For Different Use Cases

**I want to understand...**

| Question | Location |
|----------|----------|
| How tasks are defined | GREEN_AGENT_ARCHITECTURE.md § 1 |
| How execution works | GREEN_AGENT_ARCHITECTURE.md § 2 |
| Where task completion is handled | GREEN_AGENT_ARCHITECTURE.md § 6 |
| How evaluation works | GREEN_AGENT_ARCHITECTURE.md § 3 & 7 |
| What artifacts are captured | GREEN_AGENT_ARCHITECTURE.md § 4 |
| Main entry points | GREEN_AGENT_ARCHITECTURE.md § 1.2 |
| Key orchestrator files | GREEN_AGENT_ARCHITECTURE.md § 5 |
| The three execution modes | GREEN_AGENT_ARCHITECTURE.md § 2.2 |
| White agent communication | GREEN_AGENT_ARCHITECTURE.md § 2.3 |
| Database schemas | GREEN_AGENT_ARCHITECTURE.md § 4.2 |
| Environment variables | GREEN_AGENT_ARCHITECTURE.md § 9 |
| Leaderboard computation | GREEN_AGENT_ARCHITECTURE.md § 8 |

**I need a quick reference for...**

| Need | Location |
|------|----------|
| API endpoints | ARCHITECTURE_QUICK_REFERENCE.md § API Endpoints |
| System architecture diagram | ARCHITECTURE_QUICK_REFERENCE.md § System Overview |
| Execution flow | ARCHITECTURE_QUICK_REFERENCE.md § Execution Flow Summary |
| Artifact structure | ARCHITECTURE_QUICK_REFERENCE.md § Artifact Structure |
| Database schema | ARCHITECTURE_QUICK_REFERENCE.md § Database Schema |
| Environment variables | ARCHITECTURE_QUICK_REFERENCE.md § Environment Variables |
| Common curl commands | ARCHITECTURE_QUICK_REFERENCE.md § Common Tasks |
| Troubleshooting | ARCHITECTURE_QUICK_REFERENCE.md § Troubleshooting |
| Key concepts | ARCHITECTURE_QUICK_REFERENCE.md § Key Concepts |

---

## Architecture Overview

### System Components

1. **Green Agent** (green_agent/ module)
   - REST API for direct access
   - Three execution modes (Fake, Native, Docker)
   - White agent communication
   - OSWorld integration
   - SQLite storage

2. **Orchestrator** (orchestrator/ module)
   - A2A protocol compliance
   - Task execution orchestration
   - GCE VM management
   - Database and leaderboards
   - Web UI server

3. **OSWorld VM**
   - Desktop environment
   - REST API server
   - Task execution

4. **White Agent** (external)
   - Makes decisions (LLM-based typically)
   - Receives observations
   - Returns actions

### Main Entry Points

**Direct API Mode**:
```
POST /assessments/start → green_agent/app.py:82-149
```

**Orchestrator Mode**:
```
POST /task → orchestrator/a2a_green_agent.py:180-237
```

**Web UI Mode**:
```
GET /api/assessments → orchestrator/webui_server.py
```

### Key Execution Paths

**Execution**:
- green_agent/app.py → green_agent/osworld_adapter.py → green_agent/osworld_client.py → OSWorld VM

**Evaluation**:
- green_agent/osworld_evaluator.py → OSWorld metrics and getters

**Storage**:
- green_agent/storage.py (SQLite) OR orchestrator/storage.py (GCS/Filesystem)

---

## File Organization

### Green Agent Module (green_agent/)
- **app.py** - REST API entry point
- **osworld_adapter.py** - Execution engine (3 modes)
- **osworld_evaluator.py** - Task evaluation
- **osworld_client.py** - OSWorld REST client
- **white_client.py** - White agent client
- **storage.py** - SQLite wrapper
- **task_converter.py** - Format conversion
- **models.py** - Pydantic models

### Orchestrator Module (orchestrator/)
- **a2a_green_agent.py** - A2A protocol
- **task_executor.py** - Task orchestration
- **database.py** - Assessment history & leaderboards
- **webui_server.py** - Web UI server
- **vm_manager.py** - GCE VM management
- **storage.py** - Results/artifacts management
- **gcs_storage.py** - GCS integration

### Task Files (tasks/)
- **ubuntu_001.json** - Example Ubuntu task
- **osworld-ubuntu-tiny.json** - Minimal test task

---

## Key Concepts

| Concept | Definition | Location |
|---------|-----------|----------|
| Task | JSON file with goal, constraints, evaluation rules | GREEN_AGENT_ARCHITECTURE.md § 1.1 |
| Assessment | One execution of a task | GREEN_AGENT_ARCHITECTURE.md § 1.2 |
| Observation | Screenshot + metadata sent to white agent | GREEN_AGENT_ARCHITECTURE.md § 2.3 |
| Action | Decision from white agent (click, type, etc.) | GREEN_AGENT_ARCHITECTURE.md § 2.3 |
| Evaluator | OSWorld config for checking task success | GREEN_AGENT_ARCHITECTURE.md § 3.2 |
| Artifact | Screenshot or trajectory from execution | GREEN_AGENT_ARCHITECTURE.md § 4.1 |
| Green Agent | This system (orchestrator) | ARCHITECTURE_QUICK_REFERENCE.md § Key Concepts |
| White Agent | External decision-making system (LLM) | ARCHITECTURE_QUICK_REFERENCE.md § Key Concepts |
| OSWorld VM | Desktop environment where tasks run | ARCHITECTURE_QUICK_REFERENCE.md § Key Concepts |

---

## Critical Code Locations

### Starting an Assessment
```python
# GREEN_AGENT_ARCHITECTURE.md § 2.1
File: green_agent/app.py
Function: start_assessment()
Lines: 82-149
```

### Native Mode Execution
```python
# GREEN_AGENT_ARCHITECTURE.md § 2.2
File: green_agent/osworld_adapter.py
Function: run_osworld_native()
Lines: 97-323
```

### Task Evaluation
```python
# GREEN_AGENT_ARCHITECTURE.md § 3.2
File: green_agent/osworld_evaluator.py
Function: evaluate_task()
Lines: 168-343
```

### Storage & Database
```python
# GREEN_AGENT_ARCHITECTURE.md § 4.2
File: green_agent/storage.py
Lines: 46-103
```

### Task Completion
```python
# GREEN_AGENT_ARCHITECTURE.md § 6.1-6.3
File: green_agent/osworld_adapter.py
Lines: 229-231 (completion detection)
Lines: 266-303 (post-completion)
```

---

## Execution Modes Comparison

| Aspect | Fake | Native | Docker |
|--------|------|--------|--------|
| Configuration | USE_FAKE_OSWORLD=1 | USE_NATIVE_OSWORLD=1 | None |
| Performance | ~100ms | 0.1-0.5s/step | 10-20s/step |
| Use Case | Testing, CI/CD | Production | Legacy |
| Status | Working | Production Ready | Broken |
| File | osworld_adapter.py:51-93 | osworld_adapter.py:97-323 | osworld_adapter.py:388+ |

---

## Database Tables

### runs (green_agent/storage.py)
- assessment_id (PK)
- task_id, white_agent, status, success, steps
- time_sec, failure_reason, artifacts_dir, created_at

### actions (green_agent/storage.py)
- assessment_id, step, op, args (JSON), ok, ts

### assessments (orchestrator/database.py)
- id (PK), task_id, domain, status
- started_at, completed_at, steps, success
- evaluation_score, evaluation_method, failure_reason
- time_sec, vm_cost, config, result, trajectory
- run_number, batch_id

---

## API Endpoints

### Green Agent REST API
- POST /assessments/start - Start assessment
- GET /assessments - List assessments
- GET /assessments/{id}/status - Get status
- GET /assessments/{id}/results - Get results
- GET /assessments/{id}/artifacts - List artifacts

### Orchestrator A2A API
- POST /task - A2A task endpoint
- GET /agent-card - Agent capabilities
- GET /.well-known/agent-card.json - Discovery

### Web UI API
- GET /api/assessments - List with filters
- POST /api/assessments - Create assessment
- GET /api/assessments/{id} - Get details
- GET /api/stats - System statistics
- GET /api/leaderboard - Agent rankings

---

## Related Documentation

- **README.md** - Project overview and quick start
- **CONTRIBUTING.md** - Development guidelines
- **docs/** - Additional documentation

---

## Recommended Reading Order

**For New Developers**:
1. ARCHITECTURE_QUICK_REFERENCE.md - Get oriented
2. GREEN_AGENT_ARCHITECTURE.md § 1 & 2 - Understand execution
3. GREEN_AGENT_ARCHITECTURE.md § 3 & 4 - Learn evaluation & storage
4. Review actual code files

**For Debugging**:
1. ARCHITECTURE_QUICK_REFERENCE.md § Troubleshooting
2. GREEN_AGENT_ARCHITECTURE.md relevant section
3. Check database and artifact files

**For Integration**:
1. ARCHITECTURE_QUICK_REFERENCE.md § API Endpoints
2. GREEN_AGENT_ARCHITECTURE.md § 2.3 - White agent protocol
3. GREEN_AGENT_ARCHITECTURE.md § 4 - Storage integration

---

## Document Maintenance

**Last Updated**: November 13, 2024
**Coverage**: Complete analysis of Green Agent codebase
**Scope**: All task execution, evaluation, and storage mechanisms

If you find gaps or need clarifications, please refer to the source files with the provided line numbers.

