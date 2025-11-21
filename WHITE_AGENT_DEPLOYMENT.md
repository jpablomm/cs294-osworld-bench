# White Agent Cloud Run Deployment Guide

## Audit Summary

### Architecture
- **Agent Type**: GPT-4V White Agent (PromptAgent from OSWorld)
- **Protocol**: A2A (AgentBeats) compliant
- **Main Entry Point**: `white_agent/gpt4v_server.py:app`
- **Runtime**: FastAPI + Uvicorn on Python 3.12
- **Deployment Target**: Google Cloud Run

### Key Characteristics
- **Stateless**: Conversation contexts stored in memory (ephemeral, Cloud Run compatible)
- **No Database**: No persistent storage required
- **External API**: Uses OpenAI GPT-4V API (requires OPENAI_API_KEY)
- **Lightweight**: Optimized to ~500MB (vs 2GB+ with full OSWorld dependencies)

## Files Created

### 1. `requirements-white-agent.txt`
Optimized dependencies that exclude:
- ❌ torch (~2GB) - not needed, uses OpenAI API
- ❌ transformers - not needed, uses OpenAI API
- ❌ pyautogui, mss, pynput - GUI automation not needed on server
- ❌ opencv, matplotlib - visualization not needed

Only includes:
- ✅ FastAPI/Uvicorn (web server)
- ✅ OpenAI client (for GPT-4V)
- ✅ Pillow (image handling)
- ✅ A2A protocol libraries

### 2. `Dockerfile.white-agent`
Multi-stage Docker build:
- Base: Python 3.12-slim
- Copies only required OSWorld modules: `mm_agents/` and `utils.py`
- Minimal system dependencies (curl, gcc)
- Health check endpoint
- Runs on port 8080 (Cloud Run standard)

### 3. `cloudbuild-white-agent.yaml`
Google Cloud Build configuration:
- Builds Docker image
- Pushes to Artifact Registry: `us-central1-docker.pkg.dev/cs294-475401/green-agent/white-agent:latest`

### 4. `deploy-white-agent.sh`
Automated deployment script:
- Validates OPENAI_API_KEY is set
- Builds image via Cloud Build
- Deploys to Cloud Run with proper configuration
- Outputs service URLs

## Required Environment Variables

### Production (Cloud Run)
```bash
OPENAI_API_KEY=sk-...          # REQUIRED - Your OpenAI API key
GPT4V_MODEL=gpt-4o              # Optional (default: gpt-4o)
GPT4V_TEMPERATURE=1.0           # Optional (default: 1.0)
PORT=8080                       # Provided by Cloud Run
```

### Local Development
```bash
export OPENAI_API_KEY="sk-your-key-here"
export GPT4V_MODEL="gpt-4o"
export GPT4V_TEMPERATURE="1.0"

# Run locally
.venv/bin/uvicorn white_agent.gpt4v_server:app --host 0.0.0.0 --port 9002
```

## Deployment Instructions

### Prerequisites
1. OpenAI API key from https://platform.openai.com/api-keys
2. GCP project with Cloud Run API enabled
3. Authenticated gcloud CLI

### Steps

1. **Set up environment:**
   ```bash
   # Add to .env file
   OPENAI_API_KEY=sk-your-openai-api-key-here
   GPT4V_MODEL=gpt-4o
   GPT4V_TEMPERATURE=1.0
   ```

2. **Deploy to Cloud Run:**
   ```bash
   ./deploy-white-agent.sh
   ```

3. **Verify deployment:**
   ```bash
   # Get service URL
   SERVICE_URL=$(gcloud run services describe white-agent --region us-central1 --format 'value(status.url)' --project cs294-475401)

   # Test health
   curl $SERVICE_URL/health

   # Get agent card
   curl $SERVICE_URL/agent-card
   ```

## API Endpoints

### A2A Protocol Endpoints

#### `GET /agent-card`
Returns agent capabilities and metadata (AgentBeats discovery).

**Response:**
```json
{
  "name": "GPT-4V OSWorld Task Executor",
  "version": "1.0.0",
  "description": "Vision-language model for desktop automation using OSWorld",
  "protocols": ["a2a", "rest"],
  "capabilities": [
    "desktop-automation",
    "vision-language-reasoning",
    "screen-observation",
    "mouse-control",
    "keyboard-control",
    "task-execution",
    "gpt-4v-powered"
  ],
  "metadata": {
    "model": "gpt-4o",
    "action_space": "pyautogui",
    "observation_type": "screenshot"
  }
}
```

#### `POST /task`
Process an A2A task (screenshot + instruction → action).

**Request:**
```json
{
  "task_id": "unique-task-id",
  "context_id": "conversation-context-id",
  "message": "Open Firefox browser",
  "metadata": {
    "observation": {
      "frame_id": 0,
      "image_png_b64": "iVBORw0KGgoAAAANS...",
      "instruction": "Open Firefox browser",
      "done": false
    }
  }
}
```

**Response:**
```json
{
  "message_id": "generated-uuid",
  "task_id": "unique-task-id",
  "context_id": "conversation-context-id",
  "role": "agent",
  "content": "Step 0: Click on the Firefox icon...",
  "metadata": {
    "action": {
      "op": "click",
      "args": {"x": 150, "y": 200}
    },
    "step": 0,
    "done": false,
    "gpt4v_response": "I'll click on the Firefox icon...",
    "raw_actions": "pyautogui.click(150, 200)"
  }
}
```

#### `POST /reset`
Reset agent state and clear conversation contexts.

#### `GET /health`
Health check endpoint.

## Integration Points

### 1. Green Agent Integration
The green agent can call the white agent for task execution:

```python
# Green agent sends observation to white agent
response = requests.post(
    "https://white-agent-XXXXX.run.app/task",
    json={
        "task_id": assessment_id,
        "context_id": assessment_id,
        "message": instruction,
        "metadata": {
            "observation": {
                "frame_id": step,
                "image_png_b64": base64_screenshot,
                "instruction": instruction,
                "done": False
            }
        }
    }
)

# Extract action from response
action = response.json()["metadata"]["action"]
```

### 2. Direct AgentBeats Integration
The white agent exposes `/agent-card` for AgentBeats platform discovery.

### 3. Standalone API
Can be called directly via REST API for any vision-language task.

## Cost Optimization

### Cloud Run Costs
- **Memory**: 2Gi (recommended for GPT-4V processing)
- **CPU**: 2 (handles image processing efficiently)
- **Scaling**: 0 to 10 instances (pay per request)
- **Estimated cost**: ~$0.10 per hour of active use

### OpenAI API Costs
- **GPT-4o**: ~$0.005 per image + ~$0.015 per 1K output tokens
- **Typical task**: ~$0.02-0.05 per multi-step assessment

### Optimization Tips
1. Use context caching for repeated screenshots
2. Set `max_tokens=1500` to limit costs
3. Consider gpt-4o-mini for simpler tasks (10x cheaper)

## Monitoring & Debugging

### View Logs
```bash
# Stream logs
gcloud run services logs tail white-agent --region us-central1 --project cs294-475401

# View errors
gcloud run services logs read white-agent --region us-central1 --limit 50 --filter="severity>=ERROR"
```

### Debug Endpoints
```bash
# View active conversation contexts
curl $SERVICE_URL/debug/contexts
```

### Common Issues

#### 1. "Agent not initialized"
**Cause**: OPENAI_API_KEY not set or invalid.
**Fix**: Update Cloud Run env vars:
```bash
gcloud run services update white-agent \
  --set-env-vars "OPENAI_API_KEY=sk-your-new-key" \
  --region us-central1
```

#### 2. Timeout errors
**Cause**: GPT-4V API is slow.
**Fix**: Increase Cloud Run timeout:
```bash
gcloud run services update white-agent \
  --timeout 600 \
  --region us-central1
```

#### 3. Out of memory
**Cause**: Large images or many concurrent requests.
**Fix**: Increase memory:
```bash
gcloud run services update white-agent \
  --memory 4Gi \
  --region us-central1
```

## Architecture Diagram

```
┌─────────────────┐
│  Green Agent    │
│  (Orchestrator) │
└────────┬────────┘
         │ A2A Protocol
         │ POST /task
         │ {screenshot, instruction}
         ▼
┌─────────────────┐      ┌──────────────┐
│  White Agent    │─────▶│  OpenAI API  │
│  (Cloud Run)    │      │  (GPT-4V)    │
│                 │◀─────│              │
│ • gpt4v_server  │      └──────────────┘
│ • PromptAgent   │
│ • A2A Protocol  │
└─────────────────┘
         │
         │ Returns: {action, reasoning}
         ▼
┌─────────────────┐
│  OSWorld VM     │
│  (Desktop Env)  │
└─────────────────┘
```

## Next Steps

1. **Deploy White Agent:**
   ```bash
   ./deploy-white-agent.sh
   ```

2. **Update Green Agent** to use deployed white agent:
   ```python
   WHITE_AGENT_URL = "https://white-agent-XXXXX.run.app"
   ```

3. **Update WebUI** with white agent URL for monitoring

4. **Test end-to-end** assessment workflow

## Security Considerations

- ✅ Agent runs unauthenticated (stateless, no sensitive data)
- ✅ OpenAI API key stored as Cloud Run env var (encrypted at rest)
- ⚠️ Consider adding authentication if exposing to public internet
- ⚠️ Rate limit at Cloud Run level to prevent API abuse

## Performance Characteristics

- **Cold start**: ~5-10 seconds (downloading image, Python startup)
- **Warm latency**: ~2-5 seconds per action (GPT-4V API call)
- **Throughput**: ~10-20 concurrent requests with 2Gi memory
- **Image size limit**: ~10MB per screenshot (Cloud Run limit: 32MB request)

---

**Deployment Ready!** 🚀

Run `./deploy-white-agent.sh` to deploy the white agent to Cloud Run.
