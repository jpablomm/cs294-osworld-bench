# Green Agent Architecture - Quick Reference Guide

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GREEN AGENT SYSTEM                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Task Definition  →  Green Agent  →  White Agent  →  OSWorld VM    │
│  (tasks/*.json)      (REST API)      (Decision)      (Execution)   │
│                                                                       │
│  Storage:                                                             │
│  - SQLite (runs.db, assessments.db)                                 │
│  - GCS (Google Cloud Storage)                                        │
│  - Local Filesystem (artifacts/)                                     │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Files & Their Roles

### Execution Layer
- **green_agent/app.py** - REST API entry point (POST /assessments/start)
- **green_agent/osworld_adapter.py** - Execution engine (3 modes: Fake, Native, Docker)
- **green_agent/osworld_client.py** - REST client for OSWorld VM
- **green_agent/white_client.py** - HTTP client for white agent communication

### Evaluation Layer
- **green_agent/osworld_evaluator.py** - Task success evaluation using OSWorld metrics
- **orchestrator/task_executor.py** - High-level task orchestration

### Storage Layer
- **green_agent/storage.py** - SQLite wrapper for run tracking
- **orchestrator/storage.py** - Results and artifacts management
- **orchestrator/database.py** - Assessment history and leaderboards

### API Layer
- **green_agent/app.py** - Direct API (simple mode)
- **orchestrator/a2a_green_agent.py** - A2A protocol compliance
- **orchestrator/webui_server.py** - Web UI dashboard

## Execution Modes

| Mode | Variable | Performance | Use Case |
|------|----------|-------------|----------|
| **Fake** | USE_FAKE_OSWORLD=1 | ~100ms | Testing, CI/CD |
| **Native** | USE_NATIVE_OSWORLD=1 | 0.1-0.5s/step | Production (REST API) |
| **Docker** | None set | ~10-20s | Legacy (broken) |

## Key Data Structures

### Task Definition (tasks/*.json)
```json
{
  "task_id": "ubuntu_001",
  "goal": "Open Writer and save PDF",
  "constraints": {"max_steps": 80, "max_time_sec": 480},
  "environment": "OSWorld:Ubuntu:22.04",
  "hints": ["Writer icon is in dock"]
}
```

### Observation (White Agent Input)
```json
{
  "frame_id": 1,
  "image_png_b64": "base64_png_data",
  "instruction": "Open Writer and save PDF",
  "done": false,
  "accessibility_tree": {},
  "cursor_position": [960, 540],
  "screen_size": {"width": 1920, "height": 1080}
}
```

### Action (White Agent Output)
```json
{
  "action_type": "click|type|execute|DONE|wait",
  "x": 960,
  "y": 540,
  "text": "Hello",
  "command": "ls -la"
}
```

### Assessment Result
```json
{
  "success": 1,
  "steps": 15,
  "time_sec": 45.3,
  "failure_reason": null,
  "evaluation_score": 0.95,
  "artifacts_dir": "temp_artifacts/assess-xxxxx"
}
```

## Execution Flow Summary

```
1. POST /assessments/start
   ↓
2. Create run record (SQLite)
   ↓
3. Load task JSON
   ↓
4. Loop (max_steps iterations):
   - Get screenshot from OSWorld VM
   - Create observation (with base64 PNG)
   - Call white agent: decide(observation)
   - Parse action response
   - Execute action on VM
   - Save screenshot to frames/step_NNNN.png
   - If action = "DONE" → break
   ↓
5. Evaluate task success (OSWorld evaluator)
   ↓
6. Update SQLite with results
   ↓
7. Upload artifacts to GCS (if configured)
   ↓
8. Return assessment_id
```

## Evaluation Process

```
Task has "evaluator" config?
├─ YES → Run OSWorld evaluator
│        ├─ Get result (file, command output, etc.)
│        ├─ Get expected (if needed)
│        ├─ Apply metric function
│        ├─ Success = score >= 1.0
│        └─ Return score
│
└─ NO → Simplified check
         └─ Success = (no failure AND steps > 0)
```

## Artifact Structure

```
temp_artifacts/assess-10b22689/
├── frames/
│   ├── step_0_initial.png       (initial screenshot)
│   ├── step_0.png               (after action 0)
│   ├── step_1.png               (after action 1)
│   └── ... (up to max_steps)
└── osworld/                     (Docker mode only)
    ├── trajectory.json
    └── evaluation_details.json
```

## Database Schema

### Table: runs
```sql
assessment_id (PK)
task_id
white_agent
status (running|completed)
success (0|1)
steps
time_sec
failure_reason
artifacts_dir
created_at
```

### Table: actions
```sql
assessment_id
step
op (operation type)
args (JSON)
ok (0|1)
ts (timestamp)
```

## API Endpoints

### Green Agent (green_agent/app.py)
```
POST   /assessments/start           Start assessment
GET    /assessments                 List assessments
GET    /assessments/{id}/status     Get status
GET    /assessments/{id}/results    Get final results
GET    /assessments/{id}/artifacts  List artifacts
```

### Orchestrator A2A (orchestrator/a2a_green_agent.py)
```
POST   /task                        A2A task endpoint
GET    /agent-card                  Agent capabilities
GET    /.well-known/agent-card.json Discovery endpoint
```

### WebUI (orchestrator/webui_server.py)
```
GET    /api/assessments             List with filters
POST   /api/assessments             Create assessment
GET    /api/assessments/{id}        Get assessment details
GET    /api/stats                   System statistics
GET    /api/leaderboard            Agent rankings
```

## Environment Variables

**Execution**
- USE_FAKE_OSWORLD=1|0
- USE_NATIVE_OSWORLD=1|0
- OSWORLD_SERVER_URL=http://IP:5000
- OSWORLD_MAX_STEPS=15

**Storage**
- USE_GCS=true|false
- GCS_BUCKET_NAME=bucket
- RUNS_DIR=runs
- RUNS_DB=runs.db

**GCP**
- GCP_PROJECT=project-id
- GOOGLE_CLOUD_PROJECT=project-id
- GOOGLE_APPLICATION_CREDENTIALS=/path/to/creds.json

## Critical Execution Paths

### Starting Assessment
```python
# green_agent/app.py:82-149
POST /assessments/start
  → create_run() [SQLite]
  → load task JSON
  → white.reset()
  → run_osworld(task, white_decide, artifacts_dir)
    → run_osworld_native() [if native mode]
      → screenshot() [REST]
      → create_observation()
      → white.decide()
      → execute_action()
      → evaluate_task() [if evaluator]
  → update_status()
  → return assessment_id
```

### Evaluating Task
```python
# green_agent/osworld_evaluator.py:168-343
evaluate_task(vm_ip, evaluator_config)
  → parse_evaluator_config()
  → run_postconfig() [if any]
  → for each metric:
    → get_result() [file, command, etc.]
    → get_expected() [if any]
    → apply_metric() [equality, regex, etc.]
  → combine scores [AND/OR]
  → return float (0.0-1.0)
```

## Performance Characteristics

| Metric | Fake Mode | Native Mode | Docker Mode |
|--------|-----------|-------------|------------|
| Boot Time | N/A | 60s (golden image) | 15-20m |
| Step Latency | ~10ms | 100-500ms | 5-10s |
| Screenshot | ~1ms | 100-200ms | 2-5s |
| Reliability | 100% | ~99% | ~20% |
| Cost/Task | N/A | $0.016 | $0.05-0.10 |

## Common Tasks

### Get Assessment Status
```bash
curl http://localhost:8000/assessments/{id}/status
```

### List All Assessments
```bash
curl http://localhost:8000/assessments?limit=50
```

### Download Artifacts
```bash
# Get artifact list
curl http://localhost:8000/assessments/{id}/artifacts

# Download screenshot
curl http://localhost:8000/assessments/{id}/artifacts/frames/step_0001.png \
  -o step_0001.png
```

### Query Database
```python
from orchestrator.database import AssessmentDB

db = AssessmentDB("assessments.db")
stats = db.get_stats()
leaderboard = db.get_task_leaderboard("ubuntu_001")
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "white_agent_error" | White agent not responding | Check white agent URL, health |
| "OSWorld server not responding" | VM not ready | Check OSWORLD_SERVER_URL, VM status |
| "evaluation_failed_score_0.0" | Evaluation returned 0 | Check task's evaluator config, VM state |
| No screenshots captured | Artifact dir not writable | Check RUNS_DIR permissions |
| Assessment hangs | Network issue | Check timeouts, restart white agent |

## Key Concepts

- **Green Agent**: Orchestrator that runs tasks (this system)
- **White Agent**: LLM or policy that makes decisions (external)
- **OSWorld VM**: Ubuntu desktop environment with REST API
- **Task**: JSON with goal, constraints, evaluation rules
- **Assessment**: One execution of a task
- **Evaluation**: Success check using OSWorld metrics
- **Artifact**: Screenshot, log, or trajectory from execution

