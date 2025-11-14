# Green Agent Architecture & Task Execution Flow - Comprehensive Overview

## Executive Summary

The Green Agent is a production-ready autonomous agent evaluation system for OSWorld benchmarks. It orchestrates desktop automation task execution, captures comprehensive execution artifacts, and provides sophisticated evaluation mechanisms through OSWorld's evaluation system.

**Key Architecture Components:**
- Multi-layered orchestration (Green Agent + White Agent + OSWorld VM)
- Three execution modes: Fake (testing), Native (production via REST API), Docker (legacy)
- Database-backed assessment tracking with leaderboard capabilities
- Real-time artifact capture (screenshots, trajectories, logs)
- OSWorld integration for task-specific evaluation

---

## 1. Task Definition & Execution Flow

### 1.1 Task Definition Format

**Green Agent Task Format** (stored in `tasks/*.json`):
```json
{
  "task_id": "ubuntu_001",
  "environment": "OSWorld:Ubuntu:22.04",
  "goal": "Open Writer, type 'Hello OSWorld', and save a PDF to Desktop.",
  "constraints": { "max_steps": 80, "max_time_sec": 480 },
  "hints": ["The Writer icon is in the dock.", "Use Ctrl+S to save."]
}
```

**Conversion to OSWorld Format** via `task_converter.py`:
```python
convert_to_osworld_format(green_task) -> Dict
# Converts Green Agent format to OSWorld's required format with:
# - id, instruction, config (setup), evaluator config
```

### 1.2 Main Entry Points

#### A. Green Agent REST API (`green_agent/app.py` - Lines 82-149)
- **POST /assessments/start** - Start an assessment
  - Request: `StartAssessmentRequest` with `task_id`, `white_agent_url`
  - Response: `assessment_id` (UUID), status "running"
  - Creates run record in SQLite, starts OSWorld execution
  - Synchronously executes task (blocks until complete)

- **GET /assessments** - List assessments
- **GET /assessments/{assessment_id}/status** - Check status
- **GET /assessments/{assessment_id}/results** - Get final metrics
- **GET /assessments/{assessment_id}/artifacts** - List captured artifacts

#### B. Orchestrator A2A Interface (`orchestrator/a2a_green_agent.py`)
- **POST /task** - AgentBeats-compliant task endpoint
  - Accepts A2A Task format with metadata
  - Parses config from structured JSON, natural language, or metadata
  - Executes via `_execute_assessment()` (async)
  - Returns A2A Message with results

- **GET /.well-known/agent-card.json** - A2A discovery endpoint
- **GET /agent-card** - Agent capabilities descriptor

#### C. Web UI Server (`orchestrator/webui_server.py`)
- REST API for dashboard operations
- Real-time event streaming for assessment progress
- Task launching, results browsing, leaderboard queries
- Database queries for statistics and batch analysis

---

## 2. Task Execution Architecture

### 2.1 Execution Flow Diagram

```
START: POST /assessments/start
    |
    +---> green_agent/app.py::start_assessment()
    |         |
    |         +---> storage.create_run() [SQLite: status="running"]
    |         |
    |         +---> Load task JSON (tasks/<task_id>.json)
    |         |
    |         +---> WhiteClient.reset() [HTTP to white agent]
    |         |
    |         +---> run_osworld(task, white_decide, artifacts_dir)
    |                 |
    |                 +---> MODE SELECTION:
    |                       |
    |                       +---> USE_FAKE_OSWORLD=1 [Fake mode - instant]
    |                       |     |
    |                       |     +---> run_osworld_like()
    |                       |           Generate synthetic frames, call white agent
    |                       |           Return {success, steps, time_sec}
    |                       |
    |                       +---> USE_NATIVE_OSWORLD=1 [Production - REST API]
    |                       |     |
    |                       |     +---> run_osworld_native()
    |                       |           |
    |                       |           +---> OSWorldClient.screenshot() [REST]
    |                       |           |
    |                       |           +---> create_observation()
    |                       |           |     {screenshot_b64, a11y_tree, cursor}
    |                       |           |
    |                       |           +---> white_decide(observation)
    |                       |           |     [HTTP to white agent]
    |                       |           |
    |                       |           +---> Execute action:
    |                       |           |     - click_at(x, y)
    |                       |           |     - type_text(text)
    |                       |           |     - execute(command)
    |                       |           |     - press_key(key)
    |                       |           |
    |                       |           +---> evaluate_task() [OSWorld evaluator]
    |                       |           |     Score result against task rules
    |                       |           |
    |                       |           +---> Return {success, steps, time_sec, score}
    |                       |
    |                       +---> Docker/QEMU mode [Legacy]
    |                             Use vendor/OSWorld library directly
    |
    +---> storage.update_status()
    |     [SQLite: status="completed", success, steps, time_sec, failure_reason]
    |
    RETURN: {assessment_id, status="running"|"completed"}
```

### 2.2 Execution Modes

#### Mode 1: Fake Mode (Development)
- **Environment Variable**: `USE_FAKE_OSWORLD=1`
- **Implementation**: `run_osworld_like()` (Lines 51-93 in osworld_adapter.py)
- **Behavior**: 
  - Generates synthetic frames (10 frames, configurable)
  - Calls white agent for each frame
  - Returns success=1 if no errors
  - No actual desktop interaction
- **Use Case**: Testing, CI/CD pipelines, rapid iteration
- **Performance**: ~100ms per assessment

#### Mode 2: Native Mode (Production - REST API)
- **Environment Variables**: `USE_NATIVE_OSWORLD=1`, `OSWORLD_SERVER_URL=http://IP:5000`
- **Implementation**: `run_osworld_native()` (Lines 97-323 in osworld_adapter.py)
- **Architecture**:
  - Communicates via REST API with OSWorld server on VM
  - Server provides endpoints: `/screenshot`, `/execute`, `/accessibility`, etc.
  - Client: `OSWorldClient` class in `osworld_client.py`
- **Execution Loop**:
  1. Get screenshot (REST: GET /screenshot)
  2. Build observation (with optional a11y tree)
  3. Call white agent: `white.decide(observation)`
  4. Parse action from white agent response
  5. Execute action via REST (click, type, execute, etc.)
  6. Sleep (configurable: OSWORLD_SLEEP_AFTER_EXECUTION)
  7. Loop until max_steps or white agent returns "DONE"
- **Evaluation**: 
  - Integrates OSWorld's `evaluate_task()` if evaluator config present
  - Extracts evaluation score from task's "evaluator" section
  - Success = 1 if evaluation_score >= 1.0
- **Performance**: ~0.1-0.5 seconds per step
- **Artifacts**: Saves screenshot PNG for each step in `artifacts_dir/frames/step_NNNN.png`

#### Mode 3: Docker/QEMU (Legacy)
- **Use**: When neither fake nor native enabled
- **Implementation**: Uses vendor/OSWorld library directly
- **Status**: Currently broken (see error handling)

### 2.3 White Agent Communication

**WhiteClient** (`green_agent/white_client.py`):
```python
class WhiteClient:
    def reset(self) -> None:
        POST {base_url}/reset
    
    def decide(observation: Dict) -> Dict:
        POST {base_url}/decide with JSON body
        Expected response: {"action_type": str, "x": int, "y": int, ...}
```

**Observation Format**:
```python
{
    "frame_id": int,
    "image_png_b64": str,  # Base64-encoded PNG screenshot
    "instruction": str,     # Task goal
    "done": bool,          # Whether task is complete
    "accessibility_tree": Dict (optional),
    "cursor_position": (int, int) (optional),
    "screen_size": {"width": int, "height": int} (optional)
}
```

**Action Format** (white agent response):
```python
{
    "action_type": "click" | "type" | "execute" | "DONE" | "wait",
    "x": int,              # For click actions
    "y": int,              # For click actions
    "text": str,           # For type actions
    "command": str,        # For execute actions
}
```

---

## 3. Assessment/Evaluation Logic

### 3.1 Success Determination

**Three-Tier Evaluation** (Lines 266-303 in osworld_adapter.py):

1. **OSWorld Evaluator** (if available)
   - Module: `green_agent/osworld_evaluator.py`
   - Checks if task has "evaluator" config section
   - Uses OSWorld's getters (file checks, command outputs, etc.)
   - Uses OSWorld's metrics (equality, regex, comparison, etc.)
   - Returns float score from 0.0 to 1.0
   - Success = 1 if score >= 1.0

2. **Simplified Check** (fallback)
   - Success = 1 if no failure_reason AND steps > 0
   - Used when: no evaluator config OR evaluation errors

3. **Failure Tracking**
   - Captures: white_agent errors, OSWorld errors, evaluation failures
   - Stores in `failure_reason` field (e.g., "evaluation_failed_score_0.5")

### 3.2 OSWorld Evaluator Deep Dive

**Module**: `green_agent/osworld_evaluator.py` (Lines 168-343)

**Evaluation Process**:
```python
def evaluate_task(
    vm_ip: str,
    evaluator_config: Dict,  # From task JSON ["evaluator"] section
    task_id: str,
    server_port: int = 5000,
    cache_dir: str = "cache"
) -> float:
```

**Evaluator Config Structure**:
```json
{
  "func": "metric_function_name" | ["func1", "func2"],
  "result": {"type": "getter_type", ...} | [{"type": "..."}, ...],
  "expected": {"type": "getter_type", ...} | [{"type": "..."}, ...],
  "options": {...},  // Options passed to metric functions
  "conj": "and" | "or",  // Conjunction for multiple metrics
  "postconfig": [...]  // Setup steps before evaluation
}
```

**Evaluation Steps**:
1. Create MinimalEnv (lightweight OSWorld environment)
2. Run postconfig (setup steps via SetupController)
3. For each metric:
   - Get result via result getter (e.g., get_file content)
   - Get expected via expected getter (optional)
   - Apply metric function (e.g., file_exist, str_eq_regex, etc.)
   - Return float score
4. Combine scores using conjunction (AND = average, OR = max)

**Getters** (from OSWorld):
- `get_file(env, config)` - Read file content
- `get_command_output(env, config)` - Execute command, get output
- `get_chrome_content(env, config)` - Get page content from Chrome
- `get_current_url(env, config)` - Get current Chrome URL
- etc.

**Metrics** (from OSWorld):
- `str_eq_regex(actual, expected)` - Regex match
- `file_exist(actual)` - File exists check
- `dir_exist(actual)` - Directory exists check
- `str_eq(actual, expected)` - Exact string match
- etc.

**Example Evaluation Config** (ubuntu task):
```json
{
  "func": "str_eq_regex",
  "result": {
    "type": "file",
    "path": "/root/Desktop/output.pdf"
  },
  "options": {
    "rule": ".*"  // File exists
  }
}
```

---

## 4. Data/Artifacts Captured

### 4.1 Artifact Storage Structure

**Base Directory**: `temp_artifacts/{assessment_id}/` or `orchestrator_results/{task_id}/`

**Directory Structure**:
```
assess-10b22689/
├── frames/
│   ├── step_0_initial.png      [Initial screenshot]
│   ├── step_0_before.png       [Before action 0]
│   ├── step_0.png              [After action 0]
│   ├── step_1_before.png       [Before action 1]
│   ├── step_1.png              [After action 1]
│   ├── step_2.png
│   ├── ...
│   └── step_15.png             [Final screenshot]
├── osworld/                     [Docker/QEMU mode only]
│   ├── trajectory.json
│   └── evaluation_details.json
└── [action logs, if tracked]
```

**Screenshot Details**:
- **Format**: PNG (base64 encoded during transmission, saved as binary)
- **Size**: ~200-225 KB per screenshot
- **Frequency**: One per step (after action execution)
- **Total Captured**: max_steps count
- **Storage**: Local filesystem or GCS (via GCS storage manager)

### 4.2 Database Records

**SQLite Schema** (`green_agent/storage.py` - Lines 8-31):

**Table: runs**
```sql
CREATE TABLE runs (
    assessment_id TEXT PRIMARY KEY,
    task_id TEXT,
    white_agent TEXT,
    status TEXT,              -- "running" | "completed"
    success INTEGER,          -- 0 | 1
    steps INTEGER,
    time_sec REAL,
    failure_reason TEXT,      -- Error message or null
    artifacts_dir TEXT,       -- Path to artifacts
    created_at REAL           -- Unix timestamp
)
```

**Table: actions**
```sql
CREATE TABLE actions (
    assessment_id TEXT,
    step INTEGER,
    op TEXT,                  -- Action operation type
    args TEXT,                -- JSON serialized action args
    ok INTEGER,               -- 0 | 1 (success)
    ts REAL                   -- Unix timestamp
)
```

**Metadata Stored**:
- Run ID, Task ID, White Agent URL
- Status (running/completed), Success flag
- Step count, Execution time
- Failure reason (if any)
- Artifact directory path
- Timestamp

### 4.3 Results JSON

**Location**: `orchestrator_results/tasks/{task_id}/results.json` (when using StorageManager)

**Structure**:
```json
{
    "success": 0 | 1,
    "steps": 15,
    "time_sec": 45.3,
    "failure_reason": null | "error message",
    "evaluation_score": 0.75,
    "vm_info": {
        "vm_name": "osworld-assess-xxxx",
        "vm_ip": "34.10.199.148",
        "created_at": "2024-11-13T10:00:00Z"
    },
    "vm_cost": 0.016,
    "orchestrator_task_id": "uuid",
    "osworld_task_id": "ubuntu_001",
    "artifacts": [
        {"filename": "frames/step_0001.png", "url": "...", "size_bytes": 225000},
        ...
    ]
}
```

### 4.4 GCS Storage (Production)

**GCS Structure** (if `USE_GCS=true`):
```
gs://bucket-name/
├── tasks/{task_id}/
│   ├── results.json          [Results metadata]
│   ├── artifacts/
│   │   ├── frames/
│   │   │   ├── step_0001.png
│   │   │   ├── step_0002.png
│   │   │   └── ...
│   │   └── logs/
│   │       └── osworld.log
│   └── screenshots/          [If direct upload to GCS]
│       ├── {assessment_id}/{step_number}.png
│       └── ...
```

**Upload Mechanism** (Lines 194-205 in osworld_adapter.py):
- During native mode execution
- Per-step screenshot upload to GCS
- Filename pattern: `gs://bucket/{assessment_id}/screenshots/{step_number}.png`
- Non-blocking (warnings logged if upload fails)

---

## 5. Main Orchestrator Files

### 5.1 Green Agent Module (`green_agent/`)

**green_agent/app.py** (Lines 1-215)
- REST API server for direct green agent access
- Entry point: `POST /assessments/start`
- Synchronous assessment execution
- Storage: SQLite in `runs/` directory

**green_agent/osworld_adapter.py** (Lines 1-523)
- Execution engine for all three modes
- Main dispatcher: `run_osworld()`
- Mode-specific implementations: `run_osworld_like()`, `run_osworld_native()`
- Artifact capture and GCS upload

**green_agent/osworld_evaluator.py** (Lines 1-343)
- OSWorld evaluation integration
- Parses evaluator config
- Executes getters and metrics
- Returns success score

**green_agent/osworld_client.py** (Lines 1-369)
- REST client for OSWorld server
- Methods: screenshot(), execute(), click_at(), type_text(), etc.
- Observation builder: `create_observation()`

**green_agent/white_client.py** (Lines 1-25)
- HTTP client for white agent communication
- Methods: reset(), decide()

**green_agent/storage.py** (Lines 1-103)
- SQLite database wrapper
- Functions: create_run(), update_status(), record_action(), fetch_run(), list_runs()

**green_agent/task_converter.py** (Lines 1-96)
- Format conversion: Green Agent → OSWorld
- Functions: convert_to_osworld_format(), extract_max_steps()

**green_agent/models.py** (Lines 1-48)
- Pydantic models for API requests/responses
- Classes: StartAssessmentRequest, Observation, Action, AssessmentStatus, RunMetrics

### 5.2 Orchestrator Module (`orchestrator/`)

**orchestrator/a2a_green_agent.py**
- AgentBeats-compliant A2A interface
- Entry point: `POST /task`
- Wraps existing orchestrator with A2A protocol
- Task execution via `_execute_assessment()`

**orchestrator/task_executor.py** (Lines 1-220)
- High-level task execution
- Methods: run_assessment()
- Loads task configs, calls run_osworld(), tracks steps

**orchestrator/vm_manager.py** (Lines 1-100+)
- GCE VM lifecycle management
- Methods: create_vm(), wait_for_vm_ready(), delete_vm()
- Auto-detects project ID from environment

**orchestrator/storage.py** (Lines 1-245)
- Task results and artifacts storage
- Supports: GCS and local filesystem
- Methods: save_task_results(), upload_artifacts(), list_artifacts()

**orchestrator/database.py** (Lines 1-440)
- SQLite database for assessment history
- Methods: save_assessment(), get_assessment(), list_assessments()
- Leaderboard queries: get_task_leaderboard(), get_global_leaderboard()
- Stats: get_stats(), get_task_statistics()
- Config hashing for agent comparison

**orchestrator/webui_server.py** (Lines 1-80+)
- FastAPI web server for dashboard
- REST API for assessment queries
- Real-time event streaming via Server-Sent Events
- Static file serving for web UI

**orchestrator/gcs_storage.py**
- GCS integration for production deployments
- Handles authentication, bucket operations, file uploads

---

## 6. Task Completion Handlers

### 6.1 Completion Detection

**Method**: Explicit "DONE" action from white agent OR max_steps reached

**Code** (osworld_adapter.py, Lines 229-231):
```python
action_type = action.get("action_type", "")
if action_type == "DONE":
    logger.info("White agent signaled DONE")
    break
# Loop continues until max_steps or DONE
```

### 6.2 Post-Completion Processing

**Flow**:
1. Evaluation (via `evaluate_task()`)
2. Success determination (score-based or simplified)
3. Result aggregation (success, steps, time_sec)
4. Storage update (SQLite or PostgreSQL)
5. Artifact upload (to GCS if configured)
6. Response to caller

**Stored Results**:
```python
{
    "success": int,           # 0 or 1
    "steps": int,             # Steps taken
    "time_sec": float,        # Total execution time
    "failure_reason": str | None,  # Error details if failed
    "artifacts": {...},       # Artifact info
    "evaluation_score": float  # If available
}
```

### 6.3 Status Tracking

**POST /assessments/start** Updates (Lines 134-141):
```python
storage.update_status(
    assess_id,
    status="completed",
    success=int(result.get("success", 0)),
    steps=int(result.get("steps", 0)),
    time_sec=float(result.get("time_sec", 0.0)),
    failure_reason=result.get("failure_reason")
)
```

**Status Values**: "running" → "completed" or "failed"

---

## 7. Scoring & Evaluation Logic

### 7.1 Multi-Level Evaluation

**Level 1: OSWorld Evaluator** (if configured)
- Reads task JSON's "evaluator" section
- Executes getters (file checks, command outputs, etc.)
- Runs metrics (equality, regex, comparisons)
- Returns float score (0.0 to 1.0)
- Conjunction: AND (average) or OR (max)

**Level 2: Simplified Evaluation** (fallback)
- Success = 1 if (no failure AND steps > 0)
- Used when: no evaluator config or evaluation fails

**Level 3: Failure Tracking**
- Captures white agent errors
- Captures OSWorld connection errors
- Captures evaluation errors
- Stores error message in failure_reason

### 7.2 Evaluation Entry Point

**Function**: `evaluate_task()` (osworld_evaluator.py, Lines 168-343)

**Called From**: Lines 268-299 (osworld_adapter.py)

**Preconditions**:
- OSWorld task has "evaluator" config
- MinimalEnv created with VM IP and server port

**Output**:
- Float score (0.0 to 1.0)
- Returns 0.0 on any error (file not found, getter error, etc.)

### 7.3 Leaderboard Computation

**Database**: `orchestrator/database.py`

**Methods**:
- `get_task_leaderboard(task_id, metric, limit)` - Rankings by task
- `get_global_leaderboard(metric, limit, domain)` - Cross-task rankings
- `get_task_statistics(task_id)` - Rolling averages for a task

**Metrics**:
- success_rate (% successful runs)
- avg_steps (average steps taken)
- avg_time_sec (average execution time)
- avg_evaluation_score (average eval score)

**Grouping**: By agent configuration (hashed for comparison)

---

## 8. Key Files Quick Reference

| File | Purpose | Lines |
|------|---------|-------|
| green_agent/app.py | REST API, assessment start | 82-149 |
| green_agent/osworld_adapter.py | Execution engine, all modes | 51-323 |
| green_agent/osworld_evaluator.py | OSWorld evaluation | 168-343 |
| green_agent/osworld_client.py | OSWorld REST client | 15-286 |
| green_agent/storage.py | SQLite database | 46-103 |
| orchestrator/a2a_green_agent.py | A2A protocol interface | 180-237 |
| orchestrator/task_executor.py | High-level executor | 103-220 |
| orchestrator/database.py | Assessment history DB | 94-340 |
| orchestrator/webui_server.py | Web dashboard | API endpoints |
| orchestrator/vm_manager.py | GCE VM lifecycle | 68+ |

---

## 9. Environment Variables

**Execution Mode Control**:
- `USE_FAKE_OSWORLD=1|0` - Enable fake mode (default: 1)
- `USE_NATIVE_OSWORLD=1|0` - Enable native mode (default: 0)
- `OSWORLD_SERVER_URL` - OSWorld REST API URL (e.g., http://10.0.0.5:5000)
- `OSWORLD_MAX_STEPS` - Maximum steps per task (default: 15)
- `MAX_STEPS` - Legacy max steps variable (default: 120)
- `OSWORLD_SLEEP_AFTER_EXECUTION` - Sleep between steps (default: 3 seconds)

**Storage Control**:
- `USE_GCS=true|false` - Use Google Cloud Storage (default: true)
- `GCS_BUCKET_NAME` - GCS bucket for artifacts
- `RUNS_DIR` - Directory for local run artifacts (default: runs/)
- `RUNS_DB` - SQLite database path (default: runs.db)

**Server Control**:
- `HOST` - Server bind address (for A2A)
- `AGENT_PORT` - Server port (for A2A)
- `GREEN_AGENT_API_KEY` - Optional API key auth
- `WEBUI_SERVER_URL` - WebUI server for event pushing

**GCP Control**:
- `GCP_PROJECT` or `GOOGLE_CLOUD_PROJECT` - GCP project ID
- `GOOGLE_APPLICATION_CREDENTIALS` - Service account JSON path

---

## 10. Flow Summary: End-to-End Example

1. **Task Definition**: Create `tasks/my_task.json` with goal, hints, constraints
2. **Green Agent Start**: POST to `/assessments/start` with task_id and white_agent_url
3. **Artifact Creation**: Create `runs/{assessment_id}/` directory
4. **OSWorld Connection**: Connect to OSWorld REST API on VM
5. **Execution Loop**:
   - Get screenshot from VM
   - Send to white agent for decision
   - Execute action (click, type, etc.)
   - Save screenshot to `frames/step_NNNN.png`
   - Repeat until max_steps or DONE
6. **Evaluation**: Run OSWorld evaluator if config present
7. **Results**: Store in SQLite, upload artifacts to GCS
8. **Query**: Check status via `/assessments/{id}/status` or `/results`
9. **Download**: List artifacts via `/assessments/{id}/artifacts`

---

## 11. Data Flow Diagram

```
┌─────────────┐
│  Task JSON  │  tasks/{task_id}.json
└─────┬───────┘
      │
      v
┌──────────────────────┐
│  Green Agent API     │  POST /assessments/start
│  (green_agent/app.py)│
└──────┬───────────────┘
       │
       v
┌──────────────────────┐
│  White Agent Client  │  HTTP POST /decide
│  (white_client.py)   │
└──────────────────────┘
       ^
       │
       v
┌──────────────────────┐
│  OSWorld Runner      │  run_osworld_native()
│  (osworld_adapter.py)│
└──────┬───────────────┘
       │
       v
┌──────────────────────┐
│  OSWorld REST Client │  GET /screenshot, POST /execute
│  (osworld_client.py) │
└──────┬───────────────┘
       │
       v
┌──────────────────────┐
│  OSWorld VM Server   │  Serves REST API on :5000
│  (on GCE Instance)   │
└──────────────────────┘

┌──────────────────────┐
│  OSWorld Evaluator   │  evaluate_task()
│  (osworld_evaluator) │
└──────┬───────────────┘
       │
       v
┌──────────────────────┐
│  Storage Manager     │  save_task_results()
│  (storage.py)        │  upload_artifacts()
└──────┬───────────────┘
       │
       +──-> SQLite (runs.db)
       |     ├── assessments table
       |     └── actions table
       │
       └──-> GCS or Filesystem
             ├── results.json
             └── artifacts/frames/*.png
```

---

## 12. Key Integration Points

1. **Task Format**: Green Agent ← → OSWorld (via task_converter.py)
2. **Observation Format**: OSWorld ← → White Agent (via observation dict)
3. **Action Format**: White Agent ← → OSWorld Client (via action dict)
4. **Evaluation**: OSWorld Evaluator ← → Task Config (via evaluator section)
5. **Storage**: Results ← → SQLite/GCS (via StorageManager)
6. **API**: Green Agent ← → Web UI (via REST endpoints)
7. **Protocol**: A2A ← → Green Agent (via a2a_green_agent.py)

