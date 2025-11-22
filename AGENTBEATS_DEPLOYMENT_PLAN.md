# AgentBeats Controller Deployment Plan

**Date:** 2025-11-22
**Goal:** Deploy green agent with AgentBeats controller for platform registration
**Strategy:** Separate Cloud Run service (keeps production untouched)

---

## Overview

We're creating a **NEW Cloud Run service** specifically for AgentBeats:

| Service | Purpose | Status |
|---------|---------|--------|
| `green-agent` | **Production** - Your Web UI | ✅ Keep untouched |
| `green-agent-agentbeats` | **AgentBeats Testing** - Platform registration | 🆕 Deploy now |

**Why separate?**
- ✅ Zero risk to production
- ✅ Different configuration (controller vs direct)
- ✅ Easy to test and delete
- ✅ Both can run simultaneously

---

## What's Been Prepared

### 1. ✅ Dependencies Updated
**File:** `requirements-cloudrun.txt`

**Added:**
- `earthshaker==0.2.0` - AgentBeats controller
- `cssselect==1.2.0` - Required by lxml (we discovered this!)
- All OSWorld dependencies (pydrive, formulas, xmltodict, etc.)

### 2. ✅ Dockerfile Created
**File:** `Dockerfile.green-agent-agentbeats`

**Features:**
- Python 3.13 (earthshaker requirement)
- Uses `agentbeats run_ctrl` as entry point
- Includes all dependencies
- Health check on `/status` endpoint

### 3. ✅ Deployment Script Ready
**File:** `deploy_green_agent_agentbeats.sh`

**What it does:**
1. Creates Artifact Registry repository
2. Builds Docker image
3. Deploys to Cloud Run service `green-agent-agentbeats`
4. Outputs test commands and registration URL

---

## Deployment Steps

### Option A: Deploy Now (Recommended)

```bash
# 1. Deploy to Cloud Run (takes ~10 minutes)
bash deploy_green_agent_agentbeats.sh --project cs294-475401

# 2. Wait for deployment to complete
# Script will output the service URL

# 3. Test the endpoints
SERVICE_URL="https://green-agent-agentbeats-XXXXX.run.app"

curl $SERVICE_URL/status
curl $SERVICE_URL/agents
curl $SERVICE_URL/.well-known/agent-card.json
```

### Option B: Review First

If you want to review the configuration before deploying:

```bash
# Check the Dockerfile
cat Dockerfile.green-agent-agentbeats

# Check requirements
cat requirements-cloudrun.txt

# Check deployment script
cat deploy_green_agent_agentbeats.sh

# When ready, run:
bash deploy_green_agent_agentbeats.sh --project cs294-475401
```

---

## Expected Behavior

### During Deployment (10-15 minutes)

1. **Build Phase** (8-10 min)
   - Docker image built with Python 3.13
   - All dependencies installed (~70 packages)
   - Image pushed to Artifact Registry

2. **Deploy Phase** (2-3 min)
   - Cloud Run service created
   - Container starts
   - Controller launches
   - Agent starts on internal port

3. **Verification**
   - Health check passes
   - Service becomes available
   - URL provided

### After Deployment

**Service URL:** `https://green-agent-agentbeats-XXXXX.run.app`

**Available Endpoints:**
- `GET /status` - Controller status
- `GET /agents` - List managed agents
- `GET /docs` - FastAPI Swagger UI
- `GET /info` - Controller info page
- `GET /to_agent/{id}/*` - Proxy to agent
- `GET /.well-known/agent-card.json` - Discovery (via proxy or direct)

**Controller Behavior:**
1. Detects `run.sh` script
2. Assigns random internal port (e.g., 54073)
3. Launches green agent: `uvicorn orchestrator.a2a_green_agent:app --host 0.0.0.0 --port {PORT}`
4. Agent starts (takes ~30 seconds)
5. Controller state changes: `starting` → `running`
6. All requests proxied to agent

---

## Testing Checklist

After deployment, verify these endpoints:

```bash
# Get the service URL from deployment output
SERVICE_URL="https://green-agent-agentbeats-XXXXX.run.app"

# 1. Controller Status
curl $SERVICE_URL/status | jq
# Expected: {"maintained_agents": 1, "running_agents": 1, ...}

# 2. List Agents
curl $SERVICE_URL/agents | jq
# Expected: {"agent_id": {"url": "...", "internal_port": 12345, "state": "running"}}

# 3. Get agent ID
AGENT_ID=$(curl -s $SERVICE_URL/agents | jq -r 'keys[0]')
echo "Agent ID: $AGENT_ID"

# 4. Health via Proxy
curl $SERVICE_URL/to_agent/$AGENT_ID/health | jq
# Expected: {"status": "healthy", "agent_type": "green", ...}

# 5. Discovery via Proxy
curl $SERVICE_URL/to_agent/$AGENT_ID/.well-known/agent-card.json | jq
# Expected: {"name": "OSWorld Assessment Agent", ...}

# 6. Controller Management UI
open $SERVICE_URL/docs
```

---

## AgentBeats Platform Registration

Once deployed and tested, register on AgentBeats:

### Step 1: Visit Platform
Go to AgentBeats platform registration page (URL from course materials)

### Step 2: Fill Form

**Required Fields:**
- **Controller URL:** `https://green-agent-agentbeats-XXXXX.run.app`
- **Agent Name:** OSWorld Assessment Agent
- **Description:** Green agent for desktop automation assessments using native OSWorld

**Optional Fields:**
- **Capabilities:** osworld-benchmarks, desktop-automation-assessment, vm-orchestration
- **Assessment Types:** osworld-single-agent, osworld-chrome, osworld-os
- **Contact:** Your email

### Step 3: Verification
Platform will verify:
1. `GET {url}/status` - Controller responds
2. `GET {url}/agents` - Agent is registered
3. `GET {url}/.well-known/agent-card.json` - Discovery works

### Step 4: Confirmation
- Agent appears in AgentBeats registry
- You receive confirmation email
- Agent is now discoverable by others

---

## Troubleshooting

### Issue: Build Fails

**Error:** Dependency conflicts
**Solution:**
```bash
# Check requirements
cat requirements-cloudrun.txt

# Ensure earthshaker==0.2.0 is present
grep earthshaker requirements-cloudrun.txt
```

### Issue: Controller Not Starting

**Error:** Health check fails
**Solution:**
```bash
# Check Cloud Run logs
gcloud run services logs read green-agent-agentbeats \
    --region us-central1 \
    --limit 100

# Look for:
# - "INFO: Uvicorn running on..." (controller started)
# - "Starting Green Agent on..." (agent starting)
# - Import errors (missing dependencies)
```

### Issue: Agent State Stuck in "starting"

**Cause:** Missing dependencies (we've added them, but just in case)
**Solution:**
```bash
# SSH into Cloud Run (if needed)
gcloud run services logs read green-agent-agentbeats \
    --region us-central1 \
    --limit 200 | grep -i "error\|traceback"

# Check for ModuleNotFoundError
# If found, add missing package to requirements-cloudrun.txt and redeploy
```

### Issue: Discovery Endpoint 404

**Cause:** Might need to access via proxy
**Solution:**
```bash
# Try both:
curl $SERVICE_URL/.well-known/agent-card.json
curl $SERVICE_URL/to_agent/{AGENT_ID}/.well-known/agent-card.json

# Use whichever works for registration
```

---

## Cost Estimate

**New Service Cost:**
- **Memory:** 4 GiB
- **CPU:** 2 vCPU
- **Pricing:** ~$0.10/hour when active
- **Min instances:** 0 (scales to zero when idle)

**Estimated Monthly Cost:**
- **Testing (8 hours/month):** ~$0.80
- **Light use (50 hours/month):** ~$5
- **Always on (730 hours/month):** ~$73

**Note:** With `min-instances: 0`, service scales to zero when idle (no cost).

---

## Cleanup (If Needed)

If you want to delete the test service later:

```bash
# Delete Cloud Run service
gcloud run services delete green-agent-agentbeats \
    --region us-central1 \
    --project cs294-475401

# Delete Artifact Registry images (optional)
gcloud artifacts repositories delete green-agent-agentbeats \
    --location us-central1 \
    --project cs294-475401
```

**Note:** This does NOT affect your production `green-agent` service!

---

## Summary

**Ready to deploy?** Run:
```bash
bash deploy_green_agent_agentbeats.sh --project cs294-475401
```

**This will:**
1. ✅ Create separate Cloud Run service
2. ✅ Keep production untouched
3. ✅ Deploy with AgentBeats controller
4. ✅ Provide registration URL

**After deployment:**
1. Test all endpoints (use checklist above)
2. Screenshot the working endpoints
3. Register on AgentBeats platform
4. Include in project submission

---

## Questions?

Before deploying, confirm:
- [ ] You want to create a new separate service (recommended)
- [ ] Project ID is correct: `cs294-475401`
- [ ] You have billing enabled on the project
- [ ] You're ready to wait 10-15 minutes for build/deploy

**Ready when you are!** 🚀
