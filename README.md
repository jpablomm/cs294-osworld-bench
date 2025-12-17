# Green Agent - Autonomous Agent Evaluation System

An academic project for evaluating autonomous agents on desktop automation tasks. This system provides infrastructure for running agents against the [OSWorld benchmark](https://github.com/xlang-ai/OSWorld), with cloud deployment, multi-model support, and A2A protocol compliance for AgentBeats.

## What This Project Provides

**Our contributions (this repository):**
- **Green Agent**: Assessment orchestrator that manages task execution and evaluation
- **White Agent**: LLM-powered decision agent supporting multiple models (GPT-4o, Claude, Gemini, Qwen)
- **Web UI**: Next.js dashboard for launching assessments and viewing results
- **Cloud Infrastructure**: GCP deployment with golden VM images and VM pooling
- **A2A Protocol**: AgentBeats platform integration for standardized agent communication

**External dependency:**
- **OSWorld** (in `vendor/`): Desktop benchmark framework from [xlang-ai/OSWorld](https://github.com/xlang-ai/OSWorld) that provides task definitions, desktop environment server, and evaluation metrics

---

## Running Assessments

### Prerequisites

1. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys (OPENAI_API_KEY, etc.)
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up a Desktop VM** (for production mode):
   ```bash
   gcloud compute instances create desktop-vm-1 \
     --image=osworld-golden-v2-gnome \
     --machine-type=n1-standard-4 \
     --zone=us-central1-a

   VM_IP=$(gcloud compute instances describe desktop-vm-1 \
     --zone=us-central1-a \
     --format="get(networkInterfaces[0].accessConfigs[0].natIP)")
   ```

### Running White Agent + Green Agent

**Step 1: Start the White Agent (LLM decision agent)**

```bash
# Start white agent on port 9002
LOG_LEVEL=DEBUG uvicorn white_agent.a2a.server:app --host 0.0.0.0 --port 9002

# Or with specific model:
MODEL=gpt-4o LOG_LEVEL=DEBUG uvicorn white_agent.a2a.server:app --host 0.0.0.0 --port 9002
```

**Step 2: Start the Green Agent (assessment orchestrator)**

```bash
# Production mode (with GCP VM management):
OSWORLD_OBS_TYPE="screenshot" \
GOOGLE_CLOUD_PROJECT=your-gcp-project \
GREEN_AGENT_API_KEY="your-api-key" \
uvicorn green_agent.a2a.server_a2a:app --host 0.0.0.0 --port 8001

# For mock mode (no VM needed, for testing):
USE_FAKE_OSWORLD=1 \
GOOGLE_CLOUD_PROJECT=your-gcp-project \
GREEN_AGENT_API_KEY="dev-key-local-testing" \
uvicorn green_agent.a2a.server_a2a:app --host 0.0.0.0 --port 8001
```

**Step 3: Submit an assessment task**

```bash
# Submit a Chrome task for evaluation
curl -X POST http://localhost:8001/task \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "assessment-001",
    "message": "Run desktop automation assessment",
    "metadata": {
      "osworld_task_id": "030eeff7-b492-4218-b312-701ec99ee0cc",
      "domain": "chrome",
      "white_agent_url": "http://localhost:9002",
      "max_steps": 15
    }
  }'
```

**Available task domains and sample task IDs:**
- `chrome` (52 tasks): `030eeff7-b492-4218-b312-701ec99ee0cc`, `06fe7178-4491-4589-810f-2e2bc9502122`
- `os` (34 tasks): `13584542-872b-42d8-b299-866967b5c3ef`, `5ea617a3-0e86-4ba6-aab2-dac9aa2e8d57`
- `libreoffice_calc`, `libreoffice_writer`, `libreoffice_impress`, `gimp`, `vlc`, `vs_code`, `thunderbird`

Task definitions are in `green_agent/tasks_config/{domain}/`.

---

## Testing Green Agent Evaluation

### Test evaluation on a specific task

```bash
# Test the evaluation module with a real VM
python test_evaluation.py --vm-ip $VM_IP
```

This runs the trash recovery task (`5ea617a3-0e86-4ba6-aab2-dac9aa2e8d57`) and verifies:
1. Evaluation returns 0.0 when the task is NOT completed
2. Evaluation returns 1.0 when the task IS completed

### Run unit tests

```bash
# Run all tests
pytest tests/

# Run security tests
pytest tests/test_security.py -v
```

### Manual evaluation test

```bash
# 1. Start green agent (Terminal 1)
OSWORLD_OBS_TYPE="screenshot" \
GOOGLE_CLOUD_PROJECT=your-gcp-project \
GREEN_AGENT_API_KEY="your-api-key" \
uvicorn green_agent.a2a.server_a2a:app --host 0.0.0.0 --port 8001

# 2. Start white agent (Terminal 2)
LOG_LEVEL=DEBUG uvicorn white_agent.a2a.server:app --host 0.0.0.0 --port 9002

# 3. In another terminal, submit a task and check evaluation results
curl -X POST http://localhost:8001/task \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "eval-test-001",
    "message": "Test evaluation",
    "metadata": {
      "osworld_task_id": "5ea617a3-0e86-4ba6-aab2-dac9aa2e8d57",
      "domain": "os",
      "white_agent_url": "http://localhost:9002",
      "max_steps": 15
    }
  }'

# 4. Check assessment status
curl http://localhost:8001/assessments
```

---

## Reproducing OSWorld Benchmark Results

This system implements the [OSWorld benchmark](https://github.com/xlang-ai/OSWorld). To reproduce benchmark results:

### Run a single task

```bash
# 1. Start both agents (in separate terminals)
# Terminal 1 - White Agent:
LOG_LEVEL=DEBUG uvicorn white_agent.a2a.server:app --host 0.0.0.0 --port 9002

# Terminal 2 - Green Agent:
OSWORLD_OBS_TYPE="screenshot" \
GOOGLE_CLOUD_PROJECT=your-gcp-project \
GREEN_AGENT_API_KEY="your-api-key" \
uvicorn green_agent.a2a.server_a2a:app --host 0.0.0.0 --port 8001

# 2. Run a specific OSWorld task (Terminal 3)
curl -X POST http://localhost:8001/task \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "benchmark-chrome-001",
    "message": "OSWorld benchmark task",
    "metadata": {
      "osworld_task_id": "030eeff7-b492-4218-b312-701ec99ee0cc",
      "domain": "chrome",
      "white_agent_url": "http://localhost:9002",
      "max_steps": 15
    }
  }'
```

### Run batch assessments via Web UI

```bash
# 1. Start all services (in separate terminals)

# Terminal 1 - Green Agent:
OSWORLD_OBS_TYPE="screenshot" \
GOOGLE_CLOUD_PROJECT=your-gcp-project \
GREEN_AGENT_API_KEY="your-api-key" \
uvicorn green_agent.a2a.server_a2a:app --host 0.0.0.0 --port 8001

# Terminal 2 - White Agent:
LOG_LEVEL=DEBUG uvicorn white_agent.a2a.server:app --host 0.0.0.0 --port 9002

# Terminal 3 - Web UI:
cd webui-next && npm run dev

# 2. Open http://localhost:3000
# 3. Use the Launch page to run multiple tasks
# 4. View results on the Leaderboard page
```

### Compare models on OSWorld tasks

The system supports running the same task with different models:

```bash
# Run with GPT-4o (Terminal 1)
MODEL=gpt-4o LOG_LEVEL=DEBUG uvicorn white_agent.a2a.server:app --host 0.0.0.0 --port 9002

# Run with Claude (Terminal 2)
MODEL=claude-3-5-sonnet-20241022 LOG_LEVEL=DEBUG uvicorn white_agent.a2a.server:app --host 0.0.0.0 --port 9003

# Submit tasks to each agent and compare results via Web UI or curl
```

---

## Running on AgentBeats

This system is **AgentBeats-compatible** via the A2A protocol.

### A2A Discovery Endpoint

```bash
# Get agent card (AgentBeats discovery)
curl http://localhost:8001/.well-known/agent.json
```

### Deploy to Cloud Run for AgentBeats

```bash
# Deploy Green Agent
bash deploy/scripts/green-agent.sh

# Deploy White Agent
bash deploy/scripts/white-agent-agentbeats.sh

# After deployment, register with AgentBeats using the Cloud Run URLs
```

### AgentBeats Task Format

```json
{
  "task_id": "agentbeats-task-001",
  "message": "Complete the desktop automation task",
  "metadata": {
    "osworld_task_id": "030eeff7-b492-4218-b312-701ec99ee0cc",
    "domain": "chrome",
    "white_agent_url": "https://white-agent-xxxxx.run.app",
    "max_steps": 15,
    "callback_url": "https://agentbeats.example.com/callback"
  }
}
```

### A2A Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/agent.json` | GET | AgentBeats discovery |
| `/agent-card` | GET | Agent capabilities |
| `/task` | POST | Submit assessment task |
| `/health` | GET | Health check |
| `/assessments` | GET | List assessments |

---

## Project Structure

```
green_agent/                # Assessment orchestrator (our code)
  a2a/
    server_a2a.py           # A2A server (main entry point)
    server.py               # Legacy server
    executor.py             # Task execution logic
    vm_manager.py           # GCE VM lifecycle
    vm_pool.py              # Snapshot-based VM pooling
  config.py                 # Configuration
  osworld_evaluator.py      # Evaluation using OSWorld metrics
  action_tracker.py         # Loop detection
  tasks_config/             # Task definitions (OSWorld format)
    chrome/                 # 52 Chrome tasks
    os/                     # 34 OS tasks
    ...                     # Other domains

white_agent/                # LLM decision agent (our code)
  a2a/
    server.py               # A2A server (main entry point)
    controller.py           # AgentBeats controller
  prompt_agent.py           # Multi-model prompt handling
  prompts.py                # System prompts
  core.py                   # Action parsing

webui-next/                 # Web dashboard (our code)
deploy/                     # Deployment configs
vendor/OSWorld/             # External: OSWorld benchmark framework
tests/                      # Test suite
```

---

## Environment Variables

### Required

```bash
# LLM API key (at least one)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# GCP Project
GOOGLE_CLOUD_PROJECT=your-project-id

# Supabase (for Web UI)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
```

### Desktop VM Configuration

```bash
USE_NATIVE_OSWORLD=1              # Use real VM
USE_FAKE_OSWORLD=0                # Disable mock mode
OSWORLD_SERVER_URL=http://IP:5000 # VM address
OSWORLD_MAX_STEPS=15              # Max steps per task
```

### White Agent Configuration

```bash
MODEL=gpt-4o                      # LLM model
TEMPERATURE=1.0                   # Generation temperature
OSWORLD_OBS_TYPE=screenshot       # Observation type
```

---

## Troubleshooting

### Desktop VM Not Responding

```bash
gcloud compute ssh desktop-vm-1 --zone=us-central1-a
sudo systemctl status gdm osworld-server
sudo systemctl restart osworld-server
sudo journalctl -u osworld-server -n 50
```

### Common Issues

| Issue | Solution |
|-------|----------|
| VM not responding | Restart osworld-server service |
| White agent timeout | Check API keys and model availability |
| Evaluation returns 0 | Check task setup and evaluator config |

---

## Links

- **OSWorld Benchmark**: https://github.com/xlang-ai/OSWorld
- **AgentBeats**: A2A protocol for agent communication
- **GCP Console**: https://console.cloud.google.com/compute

---

## Acknowledgments

- **UC Berkeley** - CS294 Course Project
- **OSWorld Team** - Desktop benchmark framework
- **Google Cloud Platform** - Infrastructure

Built for autonomous agent evaluation research.
