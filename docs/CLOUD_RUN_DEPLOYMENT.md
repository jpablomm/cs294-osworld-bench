# Cloud Run Deployment - Implementation Guide

## Overview

This document explains how the Green Agent is deployed to Google Cloud Run as a production-ready, serverless A2A-compliant agent with AgentBeats platform compatibility.

**Production URL:** `https://green-agent-750082808015.us-central1.run.app`

## Table of Contents

1. [Architecture](#architecture)
2. [Key Design Decisions](#key-design-decisions)
3. [Dependency Optimization](#dependency-optimization)
4. [AgentBeats Integration](#agentbeats-integration)
5. [Deployment Process](#deployment-process)
6. [Configuration](#configuration)
7. [Troubleshooting](#troubleshooting)
8. [Maintenance](#maintenance)

---

## Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Cloud Run Service                        │
│  https://green-agent-750082808015.us-central1.run.app       │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Green Agent (FastAPI/Uvicorn)              │    │
│  │                                                     │    │
│  │  Endpoints:                                        │    │
│  │  • POST /task - A2A task handling                  │    │
│  │  • GET /health - Health check                      │    │
│  │  • GET /.well-known/agent-card.json - Discovery   │    │
│  │  • GET /agent-card - A2A protocol compliance       │    │
│  │                                                     │    │
│  │  Components:                                        │    │
│  │  • orchestrator/a2a_green_agent.py                 │    │
│  │  • green_agent/ - Assessment logic                 │    │
│  │  • vendor/OSWorld/ - Desktop env (minimal)         │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  Container: Python 3.12-slim                                │
│  Memory: 512MB-2GB (auto-scaling)                           │
│  Timeout: 5 minutes                                         │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│              Google Compute Engine (GCE)                     │
│  OSWorld VM Instances (created on-demand)                   │
│                                                              │
│  • osworld-gnome-v6 (GNOME desktop environment)             │
│  • Desktop automation tasks                                 │
│  • White agent execution                                    │
└─────────────────────────────────────────────────────────────┘
```

### Request Flow

1. **Client** sends POST request to `/task` with A2A-compliant payload
2. **Green Agent** validates request, checks API key (if enabled)
3. **Green Agent** creates GCE VM from golden image
4. **Green Agent** deploys white agent to VM
5. **White Agent** executes OSWorld task on VM desktop
6. **Green Agent** collects results and returns A2A response
7. **VM** is cleaned up after assessment

---

## Key Design Decisions

### 1. Direct Agent Execution (No Controller)

**Decision:** Run the agent directly with uvicorn instead of using the AgentBeats controller (earthshaker).

**Rationale:**
- **Simpler architecture:** One process instead of controller + subprocess
- **Better reliability:** No subprocess communication to fail
- **Cloud Run optimization:** Serverless environments handle lifecycle management
- **Easier debugging:** Direct logs without controller layer
- **Still AgentBeats-compatible:** Exposes standard `/.well-known/agent-card.json` endpoint

**What We Tried:**
```dockerfile
# This didn't work in Cloud Run (controller couldn't launch agent subprocess)
CMD ["sh", "-c", "export AGENT_PORT=${PORT:-8080} && exec agentbeats run_ctrl"]
```

**What Works:**
```dockerfile
# Direct execution - simple and reliable
CMD ["sh", "-c", "exec uvicorn orchestrator.a2a_green_agent:app --host ${HOST:-0.0.0.0} --port ${PORT:-8080}"]
```

### 2. Python 3.12 (Not 3.13)

**Decision:** Use Python 3.12-slim base image.

**Rationale:**
- **Better package compatibility:** OSWorld dependencies work reliably
- **Stable ecosystem:** More packages have pre-built wheels
- **No issues with earthshaker:** Since we removed it, Python 3.13 requirement is gone
- **Production-ready:** Python 3.12 is mature and well-tested

### 3. Minimal OSWorld Dependencies

**Decision:** Only include 11 essential packages instead of all 72 OSWorld dependencies.

**Rationale:**
- **Faster builds:** Less time downloading and compiling
- **Smaller images:** Reduced container size
- **No unnecessary deps:** Avoid heavyweight ML libraries (torch, transformers, opencv)
- **Cloud Run optimization:** Smaller images = faster cold starts

---

## Dependency Optimization

### The Problem

OSWorld's `desktop_env/evaluators/metrics/__init__.py` imported ALL evaluators:

```python
# Original file (vendor/OSWorld/desktop_env/evaluators/metrics/__init__.py)
from .chrome import *
from .docs import *
from .gimp import *
from .vlc import *
from .libreoffice import *
# ... 50+ more evaluators
```

This caused a cascade of dependencies:
- 72 total packages in `vendor/OSWorld/requirements.txt`
- Including: `torch` (~2GB), `transformers`, `opencv-python`, `easyocr`
- Build times: 5-10 minutes
- Docker image size: >2GB

### The Solution

**Root Cause Analysis:**
```
Green Agent → SetupController → evaluators/metrics/utils.compare_urls
                                          ↑
                            This is ALL we need!
```

The green agent only uses `SetupController`, which only needs `compare_urls` from the utils module. But the `__init__.py` was loading EVERYTHING.

**Fix:** Patched `vendor/OSWorld/desktop_env/evaluators/metrics/__init__.py`:

```python
# Minimal __init__.py to avoid loading ALL evaluators
# Original file imports ALL evaluators which have heavy dependencies
# We only need utils.compare_urls for SetupController
# This prevents loading: chrome, docs, gimp, libreoffice, vlc, etc.

# If you need the full evaluators, use direct imports:
# from desktop_env.evaluators.metrics.chrome import ...
```

**Result:**
- **Before:** 72 dependencies, ~2GB image, 5-10 min builds
- **After:** 11 dependencies, ~500MB image, 2-3 min builds

### Minimal Dependency List

```python
# requirements-cloudrun.txt (OSWorld section only)

# OSWorld SetupController dependencies (minimal)
playwright==1.49.1
fabric==3.2.2
requests==2.32.3
pydrive==1.3.1
requests-toolbelt==1.0.0
python-dotenv==1.0.1

# utils.py imports (needed by SetupController)
lxml==5.3.0
xmltodict==0.14.2
openpyxl==3.1.5
formulas==1.2.9
tldextract==5.1.3
```

**What We Excluded:**
- ML/AI libraries: `torch`, `transformers`, `sentence-transformers`
- Computer vision: `opencv-python`, `easyocr`, `pytesseract`
- Browser automation extras: `selenium`, `beautifulsoup4`
- GUI automation: `pyautogui`, `mss`, `pyscreeze`
- Database ORMs: `sqlalchemy`, `psycopg2-binary`

---

## AgentBeats Integration

### What is AgentBeats?

AgentBeats is a platform for discovering and managing A2A-compliant agents. It provides:
- Agent discovery via standard endpoints
- Lifecycle management (via controller)
- Platform registry for public agents

### Our Integration Approach

**Standard Compliance:**

1. **Discovery Endpoint:** `GET /.well-known/agent-card.json`
   ```json
   {
     "name": "OSWorld Assessment Agent",
     "description": "Green agent for desktop automation assessments...",
     "version": "0.1.0",
     "capabilities": [
       "osworld-benchmarks",
       "desktop-automation-assessment",
       "vm-orchestration"
     ],
     "protocols": ["a2a", "rest"]
   }
   ```

2. **A2A Protocol:** `POST /task` with standardized request/response
   ```json
   {
     "task_id": "unique-id",
     "message": "Run OSWorld task",
     "metadata": {
       "osworld_task_id": "osworld-ubuntu-001"
     }
   }
   ```

3. **Health Check:** `GET /health` for monitoring
   ```json
   {
     "status": "healthy",
     "agent_type": "green",
     "protocol": "a2a",
     "active_assessments": 0
   }
   ```

**Why We Skipped the Controller:**

The AgentBeats controller (`earthshaker` package) is optional. We chose direct execution because:

- **Cloud Run handles lifecycle:** Auto-scaling, health checks, restarts
- **Simpler deployment:** One process instead of two
- **Controller had issues:** Couldn't launch agent subprocess in containerized environment
- **Still compliant:** Discovery endpoint is what the platform needs

**When to Use the Controller:**

The controller is useful for:
- Local development (easy start/stop/restart)
- Multi-agent orchestration
- Environments without container orchestration
- Debug UI needs

For serverless Cloud Run, it's unnecessary.

---

## Deployment Process

### Prerequisites

1. **Google Cloud SDK** installed and authenticated
2. **Docker** (optional - Cloud Build handles building)
3. **GCP Project** with billing enabled
4. **Artifact Registry** repository created:
   ```bash
   gcloud artifacts repositories create green-agent \
     --repository-format=docker \
     --location=us-central1
   ```

### File Structure

```
green_agent/
├── Dockerfile.green-agent          # Production Dockerfile
├── cloudbuild-production.yaml      # Cloud Build config
├── requirements-cloudrun.txt       # Minimal dependencies
├── .gcloudignore                   # Build exclusions
├── orchestrator/
│   └── a2a_green_agent.py         # Main agent FastAPI app
├── green_agent/                    # Assessment logic
├── white_agent/                    # White agent code
├── vendor/OSWorld/                 # OSWorld (patched)
│   └── desktop_env/evaluators/metrics/__init__.py  # ⚠️ PATCHED
└── docs/
    └── CLOUD_RUN_DEPLOYMENT.md    # This file
```

### Build Configuration

**cloudbuild-production.yaml:**
```yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-f'
      - 'Dockerfile.green-agent'
      - '-t'
      - 'us-central1-docker.pkg.dev/cs294-475401/green-agent/green-agent'
      - '.'
images:
  - 'us-central1-docker.pkg.dev/cs294-475401/green-agent/green-agent'
```

**Why Cloud Build YAML?**
- The `gcloud builds submit` command doesn't support `--file` or `--dockerfile` flags
- Using `--config` with YAML is the standard approach
- Allows reproducible builds with version control

### Deployment Steps

**1. Build the Docker image:**
```bash
gcloud builds submit --config cloudbuild-production.yaml
```

**2. Deploy to Cloud Run:**
```bash
gcloud run deploy green-agent \
  --image us-central1-docker.pkg.dev/cs294-475401/green-agent/green-agent \
  --region us-central1 \
  --allow-unauthenticated \
  --timeout=5m \
  --memory=2Gi \
  --cpu=2 \
  --set-env-vars GCP_PROJECT=cs294-475401 \
  --set-env-vars USE_NATIVE_OSWORLD=1
```

**3. Verify deployment:**
```bash
# Test health endpoint
curl https://green-agent-750082808015.us-central1.run.app/health

# Test AgentBeats discovery
curl https://green-agent-750082808015.us-central1.run.app/.well-known/agent-card.json
```

### One-Step Deployment

Combine build and deploy:
```bash
gcloud builds submit --config cloudbuild-production.yaml && \
gcloud run deploy green-agent \
  --image us-central1-docker.pkg.dev/cs294-475401/green-agent/green-agent \
  --region us-central1 \
  --allow-unauthenticated \
  --timeout=5m
```

---

## Configuration

### Environment Variables

**Set via Cloud Run:**
```bash
gcloud run services update green-agent \
  --region us-central1 \
  --set-env-vars KEY=VALUE
```

**Available Variables:**

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `PORT` | HTTP server port | `8080` | No (Cloud Run sets this) |
| `HOST` | Bind address | `0.0.0.0` | No |
| `GCP_PROJECT` | Google Cloud project ID | - | Yes |
| `USE_NATIVE_OSWORLD` | Use native OSWorld mode | `0` | No |
| `OSWORLD_MAX_STEPS` | Max steps per assessment | `15` | No |
| `GREEN_AGENT_API_KEY` | API key for authentication | - | No (but recommended) |

### API Key Authentication

**Enable in production:**
```bash
# Generate strong API key
API_KEY=$(openssl rand -hex 32)

# Set on Cloud Run
gcloud run services update green-agent \
  --region us-central1 \
  --set-env-vars GREEN_AGENT_API_KEY=$API_KEY

# Share key securely with authorized clients
```

**Client usage:**
```bash
curl -X POST https://green-agent-750082808015.us-central1.run.app/task \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "task_id": "test-123",
    "message": "Run assessment"
  }'
```

**Why enable API key?**
- Prevents unauthorized VM creation → High GCE costs
- Protects against DoS attacks
- Audit trail of legitimate requests

### Resource Limits

**Current configuration:**
- **Memory:** 512MB minimum, 2GB maximum (auto-scaling)
- **CPU:** 1-2 vCPUs (auto-scaling)
- **Timeout:** 5 minutes (max request duration)
- **Concurrency:** 80 requests per instance

**Adjust if needed:**
```bash
gcloud run services update green-agent \
  --region us-central1 \
  --memory 4Gi \
  --cpu 4 \
  --timeout 10m \
  --concurrency 10
```

---

## Troubleshooting

### Issue: 404 on Endpoints

**Symptoms:**
```bash
curl https://green-agent-750082808015.us-central1.run.app/health
# Returns: {"detail":"Not Found"}
```

**Cause:** Old deployment with AgentBeats controller (controller running, agent subprocess not launched)

**Solution:**
```bash
# Redeploy with latest image (direct execution)
gcloud builds submit --config cloudbuild-production.yaml && \
gcloud run deploy green-agent \
  --image us-central1-docker.pkg.dev/cs294-475401/green-agent/green-agent \
  --region us-central1
```

### Issue: Container Fails to Start

**Symptoms:**
- Cloud Run shows "Container failed to start"
- Logs show "Port 8080 not listening"

**Debugging:**
```bash
# Check recent logs
gcloud run services logs read green-agent \
  --region us-central1 \
  --limit 100

# Look for Python errors or missing dependencies
```

**Common causes:**
1. Missing dependency in `requirements-cloudrun.txt`
2. Import error in `orchestrator/a2a_green_agent.py`
3. OSWorld `__init__.py` was restored (loading all evaluators)

**Solution:**
```bash
# Check the patched file wasn't overwritten
cat vendor/OSWorld/desktop_env/evaluators/metrics/__init__.py

# Should show minimal stub, not full imports
```

### Issue: Slow Build Times

**Symptoms:**
- Cloud Build takes >5 minutes
- Installing dependencies is slow

**Optimization:**
```bash
# Check if unnecessary dependencies crept back in
grep -E "torch|transformers|opencv" requirements-cloudrun.txt

# Should return nothing - these are excluded
```

### Issue: High Memory Usage

**Symptoms:**
- Cloud Run instances using 1.5GB+ memory
- OOM errors in logs

**Debugging:**
```bash
# Check active assessments
curl https://green-agent-750082808015.us-central1.run.app/health
# "active_assessments" should be low

# Check for memory leaks
gcloud run services logs read green-agent --limit 500 | grep -i memory
```

**Solution:**
```bash
# Increase memory limit
gcloud run services update green-agent \
  --region us-central1 \
  --memory 4Gi
```

---

## Maintenance

### Monitoring

**Health checks:**
```bash
# Automated monitoring
while true; do
  curl -s https://green-agent-750082808015.us-central1.run.app/health | jq
  sleep 60
done
```

**Cloud Run metrics:**
- Go to: https://console.cloud.google.com/run
- Select: `green-agent` service
- View: Request count, latency, errors, memory, CPU

**Billing alerts:**
```bash
# Set up budget alert
gcloud billing budgets create \
  --billing-account=YOUR-BILLING-ACCOUNT \
  --display-name="Green Agent Cloud Run Budget" \
  --budget-amount=100USD
```

### Updates

**Deploy new version:**
```bash
# 1. Make code changes
vim orchestrator/a2a_green_agent.py

# 2. Test locally (optional)
docker build -f Dockerfile.green-agent -t green-agent:test .
docker run -p 8080:8080 green-agent:test

# 3. Build and deploy
gcloud builds submit --config cloudbuild-production.yaml && \
gcloud run deploy green-agent \
  --image us-central1-docker.pkg.dev/cs294-475401/green-agent/green-agent \
  --region us-central1
```

**Rollback to previous version:**
```bash
# List revisions
gcloud run revisions list \
  --service green-agent \
  --region us-central1

# Rollback to specific revision
gcloud run services update-traffic green-agent \
  --region us-central1 \
  --to-revisions green-agent-00005-xyz=100
```

### Dependency Updates

**Update OSWorld:**
```bash
cd vendor/OSWorld
git pull origin main

# ⚠️ IMPORTANT: Re-apply patch
cat > desktop_env/evaluators/metrics/__init__.py <<'EOF'
# Minimal __init__.py to avoid loading ALL evaluators
# Original file imports ALL evaluators which have heavy dependencies
# We only need utils.compare_urls for SetupController
EOF

# Test locally before deploying
cd ../..
python -c "from vendor.OSWorld.desktop_env.controllers.setup import SetupController; print('OK')"
```

**Update Python packages:**
```bash
# Update requirements file
vim requirements-cloudrun.txt

# Test build
gcloud builds submit --config cloudbuild-production.yaml

# If successful, deploy
gcloud run deploy green-agent \
  --image us-central1-docker.pkg.dev/cs294-475401/green-agent/green-agent \
  --region us-central1
```

### Cost Optimization

**Current costs:**
- Cloud Run: Pay-per-use (requests × duration)
- Container Registry: Storage for images
- GCE VMs: Created during assessments (main cost)

**Reduce Cloud Run costs:**
```bash
# Lower minimum instances (cold starts OK)
gcloud run services update green-agent \
  --region us-central1 \
  --min-instances 0 \
  --max-instances 10

# Reduce memory if not needed
gcloud run services update green-agent \
  --region us-central1 \
  --memory 1Gi
```

**Monitor GCE costs:**
```bash
# Check running VMs
gcloud compute instances list

# Set up auto-cleanup (add to green agent logic)
# Delete VMs older than 2 hours
```

---

## Summary

### What We Built

✅ **Serverless green agent** on Cloud Run
✅ **AgentBeats-compatible** via standard discovery endpoint
✅ **Optimized dependencies** (11 packages vs. 72)
✅ **Fast builds** (2-3 minutes vs. 10+ minutes)
✅ **Small images** (~500MB vs. 2GB+)
✅ **Direct execution** (no controller complexity)

### Key Files

| File | Purpose | Critical? |
|------|---------|-----------|
| `Dockerfile.green-agent` | Production container | ✅ Yes |
| `cloudbuild-production.yaml` | Build config | ✅ Yes |
| `requirements-cloudrun.txt` | Dependencies | ✅ Yes |
| `vendor/OSWorld/.../__init__.py` | **PATCHED** | ⚠️ **CRITICAL** |
| `.gcloudignore` | Build exclusions | No |

### Production Checklist

Before deploying:
- [ ] Verify `vendor/OSWorld/desktop_env/evaluators/metrics/__init__.py` is patched
- [ ] Set `GREEN_AGENT_API_KEY` environment variable
- [ ] Set `GCP_PROJECT` environment variable
- [ ] Test health endpoint after deployment
- [ ] Test `.well-known/agent-card.json` endpoint
- [ ] Verify Cloud Run logs show no errors
- [ ] Set up billing alerts

### Support

**Documentation:**
- This file: `docs/CLOUD_RUN_DEPLOYMENT.md`
- AgentBeats integration: `AGENTBEATS_INTEGRATION.md`
- Main README: `README.md`

**Logs:**
```bash
gcloud run services logs read green-agent --region us-central1 --limit 100
```

**Deployment URL:**
https://green-agent-750082808015.us-central1.run.app
