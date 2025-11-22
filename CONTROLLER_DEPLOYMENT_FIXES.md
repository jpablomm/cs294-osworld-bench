# Fixing AgentBeats Controller Deployment

**Problem:** Controller starts successfully but agent subprocess fails to launch
**Symptom:** Agent stuck in "starting" state indefinitely
**Root Cause:** Multiple possible issues with subprocess environment

---

## Current Status

| Component | Status | Evidence |
|-----------|--------|----------|
| Controller | ✅ Running | `/status` endpoint works |
| Agent Detection | ✅ Working | Controller reads `run.sh` |
| Agent Launch | ❌ Failing | Stuck in "starting" state |
| Proxy | ❌ 500 Error | Can't connect to agent |

---

## Possible Root Causes

### 1. PYTHONPATH Not Set (Most Likely)

**Issue:** Controller subprocess doesn't inherit PYTHONPATH for `vendor/OSWorld` imports

**Evidence:**
```python
# This import fails in subprocess
from desktop_env.controllers.setup import SetupController
# ModuleNotFoundError: No module named 'desktop_env'
```

**Why it fails:**
- Controller spawns subprocess in `/app` directory
- Subprocess doesn't have `/app/vendor/OSWorld` in PYTHONPATH
- Python can't find `desktop_env` module

**Solution:** Add PYTHONPATH to `run.sh`

### 2. Working Directory Issue

**Issue:** Controller might execute `run.sh` from wrong directory

**Evidence:** Controller might run from `/` instead of `/app`

**Why it fails:**
- Relative imports break
- Can't find `orchestrator/a2a_green_agent.py`

**Solution:** Use absolute paths in `run.sh`

### 3. Missing Dependencies (Less Likely)

**Issue:** Some dependency not installed despite being in requirements

**Evidence:** We added all deps locally, but maybe missed one

**Solution:** Test imports before starting uvicorn

---

## Fix Approaches (Choose One)

### Approach A: Enhanced run.sh (Recommended)

**File:** `run.sh`

```bash
#!/bin/bash
set -e

# Set environment
HOST=${HOST:-0.0.0.0}
AGENT_PORT=${AGENT_PORT:-8001}

# FIX: Add PYTHONPATH for OSWorld vendor code
export PYTHONPATH=/app:/app/vendor/OSWorld:${PYTHONPATH:-}

# FIX: Ensure we're in the right directory
cd /app 2>/dev/null || true

echo "Starting Green Agent on $HOST:$AGENT_PORT (PYTHONPATH configured)"

# Start the agent
exec uvicorn orchestrator.a2a_green_agent:app --host $HOST --port $AGENT_PORT
```

**Pros:**
- ✅ Simple fix
- ✅ Addresses most common issue
- ✅ No Dockerfile changes

**Cons:**
- ⚠️ Assumes `/app` is working directory

---

### Approach B: Debug-First run.sh

**File:** `run-debug.sh` (already created)

Use the enhanced debugging version to:
1. See actual working directory
2. Check file existence
3. Test imports before uvicorn
4. Get detailed error messages in Cloud Run logs

**Implementation:**
```bash
# In Dockerfile.green-agent-agentbeats, change:
COPY run.sh run.sh
# To:
COPY run-debug.sh run.sh
```

**Pros:**
- ✅ Shows exactly what's failing
- ✅ Can diagnose in Cloud Run logs
- ✅ Validates environment before starting

**Cons:**
- ⚠️ More verbose logs
- ⚠️ Slightly slower startup

---

### Approach C: Set PYTHONPATH in Dockerfile

**File:** `Dockerfile.green-agent-agentbeats`

```dockerfile
# Add after ENV declarations (line ~42)
ENV PYTHONPATH=/app:/app/vendor/OSWorld

# This ensures subprocess inherits it
```

**Pros:**
- ✅ Guaranteed to be set
- ✅ No run.sh changes needed
- ✅ Cleaner separation of concerns

**Cons:**
- ⚠️ Requires rebuild/redeploy

---

### Approach D: Python Module Execution

**File:** `run.sh`

Instead of using `uvicorn` command, use Python module execution:

```bash
#!/bin/bash
set -e

HOST=${HOST:-0.0.0.0}
AGENT_PORT=${AGENT_PORT:-8001}

# Change to app directory
cd /app

# Use python -m to ensure proper path
exec python3 -m uvicorn orchestrator.a2a_green_agent:app \
    --host $HOST \
    --port $AGENT_PORT
```

**Pros:**
- ✅ Python handles PYTHONPATH internally
- ✅ More reliable module resolution

**Cons:**
- ⚠️ Slightly different invocation

---

### Approach E: Direct Agent Import (No Controller)

**Alternative:** Skip controller complexity for Cloud Run

**File:** `Dockerfile.green-agent-agentbeats`

```dockerfile
# Change CMD from:
CMD ["sh", "-c", "agentbeats run_ctrl"]

# To:
CMD ["sh", "-c", "export PYTHONPATH=/app:/app/vendor/OSWorld && exec uvicorn orchestrator.a2a_green_agent:app --host ${HOST:-0.0.0.0} --port ${PORT:-8080}"]
```

**Pros:**
- ✅ Guaranteed to work (same as production)
- ✅ No subprocess complexity
- ✅ Still has AgentBeats endpoints

**Cons:**
- ❌ No controller features (management UI, lifecycle API)
- ❌ Not true AgentBeats controller deployment

---

## Recommended Fix Strategy

### Step 1: Quick Test (5 minutes)

Try **Approach C** (PYTHONPATH in Dockerfile):

```dockerfile
# Edit Dockerfile.green-agent-agentbeats, add after line 42:
ENV PYTHONPATH=/app:/app/vendor/OSWorld
```

Then redeploy:
```bash
bash deploy_green_agent_agentbeats.sh --project cs294-475401
```

### Step 2: If Still Failing (10 minutes)

Try **Approach B** (Debug run.sh):

```bash
# Replace run.sh with run-debug.sh
mv run.sh run.sh.bak
cp run-debug.sh run.sh
chmod +x run.sh

# Redeploy
bash deploy_green_agent_agentbeats.sh --project cs294-475401

# Check logs for detailed error
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=green-agent-agentbeats" --limit=50 --project=cs294-475401
```

### Step 3: Nuclear Option (5 minutes)

Use **Approach E** (Direct mode with .well-known endpoints):

This is essentially what your production deployment does, and we KNOW it works.

---

## Testing the Fix

After deploying any fix, verify:

```bash
SERVICE_URL="https://green-agent-agentbeats-XXXXX.run.app"

# 1. Wait 30 seconds for agent to start
sleep 30

# 2. Check agent status
curl -s $SERVICE_URL/agents | jq

# Should show: "state": "running" (not "starting")

# 3. Get agent ID
AGENT_ID=$(curl -s $SERVICE_URL/agents | jq -r 'keys[0]')

# 4. Test proxy
curl -s $SERVICE_URL/to_agent/$AGENT_ID/health | jq

# Should return: {"status": "healthy", ...}

# 5. Test discovery
curl -s $SERVICE_URL/to_agent/$AGENT_ID/.well-known/agent-card.json | jq

# Should return: {"name": "OSWorld Assessment Agent", ...}
```

If all tests pass: ✅ Controller is working!

---

## Debugging Cloud Run Logs

If agent still fails to start:

```bash
# Get detailed logs
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=green-agent-agentbeats" \
  --limit=100 \
  --project=cs294-475401 \
  --format="table(timestamp,textPayload)"

# Look for:
# - "Starting Green Agent on..." (agent trying to start)
# - "ModuleNotFoundError" (import errors)
# - "Traceback" (Python errors)
# - "Error" (general errors)
```

**Common error patterns:**

| Error | Meaning | Fix |
|-------|---------|-----|
| `ModuleNotFoundError: desktop_env` | PYTHONPATH issue | Approach A or C |
| `FileNotFoundError: orchestrator` | Working directory issue | Add `cd /app` to run.sh |
| `ImportError: cannot import name` | Dependency missing | Check requirements-cloudrun.txt |
| `Permission denied` | run.sh not executable | Add `chmod +x run.sh` in Dockerfile |

---

## Why Production Works

Your production deployment (`green-agent`) works because:

1. **No controller** - Runs uvicorn directly, no subprocess
2. **PYTHONPATH set** - Dockerfile has correct environment
3. **Simple CMD** - Direct execution, no shell wrapper
4. **Tested dependencies** - All deps installed and verified

```dockerfile
# Production Dockerfile.green-agent
ENV PYTHONPATH=/app:/app/vendor/OSWorld  # <- This is set!
CMD ["sh", "-c", "exec uvicorn ..."]      # <- Direct execution
```

The controller version adds complexity:
1. Controller starts
2. Controller spawns subprocess (run.sh)
3. Subprocess might not inherit environment
4. Agent fails to import modules

---

## My Recommendation

For your university project:

**Option 1: Fix Controller (Learning Experience)**
- Shows persistence and debugging skills
- Demonstrates understanding of subprocess environments
- Try Approach C (PYTHONPATH in Dockerfile) first

**Option 2: Use Production (Pragmatic)**
- Already works perfectly
- 100% AgentBeats compliant
- Focus on platform registration and results

**Option 3: Document Both (Best for Grade)**
- Controller testing documented in `AGENTBEATS_CONTROLLER_TESTING.md` ✅
- Production deployment works ✅
- Explain trade-offs in write-up
- Shows engineering judgment

Honestly, **Option 3 is strongest** because it shows:
- ✅ You tested the controller (we did!)
- ✅ You debugged issues (we documented!)
- ✅ You chose pragmatic solution (production works!)
- ✅ You understand the tradeoffs

---

## Quick Reference

**If you want to fix controller:**
```bash
# Edit Dockerfile.green-agent-agentbeats, add line 43:
ENV PYTHONPATH=/app:/app/vendor/OSWorld

# Redeploy:
bash deploy_green_agent_agentbeats.sh --project cs294-475401

# Test after 1-2 minutes:
curl https://green-agent-agentbeats-XXX.run.app/agents
```

**If you want to use production:**
```bash
# Just register this URL on AgentBeats:
https://green-agent-b6s4fydcmq-uc.a.run.app

# It already works! All endpoints verified ✅
```

**For project submission, include:**
- ✅ `AGENTBEATS_CONTROLLER_TESTING.md` - Local controller testing
- ✅ `CONTROLLER_DEPLOYMENT_FIXES.md` - This document
- ✅ Production deployment (working)
- ✅ Screenshots of both
- ✅ Explanation of trade-offs

This shows **both technical depth AND pragmatism** - exactly what professors want to see! 🎓
