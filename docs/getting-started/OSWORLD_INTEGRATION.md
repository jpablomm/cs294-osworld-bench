# OSWorld Integration Guide

This document explains how to install dependencies and test the White Agent integration with OSWorld.

---

## Prerequisites

- Python 3.11 (recommended for macOS ARM, required for some dependencies)
- Virtual environment activated
- OSWorld VM (for production) or Docker Desktop (for legacy Docker mode - deprecated)

> ⚠️ The bundled `white_agent/server.py` is a minimal stub that only issues `wait` actions and finishes after a handful of frames. Use it for smoke tests, but switch to `white_agent/gpt4v_server.py` (requires an OpenAI API key) or your own action-capable white agent when you need real desktop automation.

---

## Phase 5: Installing OSWorld Dependencies

### Option A: Using pip

```bash
# Navigate to OSWorld vendor directory
cd vendor/OSWorld

# Install dependencies
pip install -r requirements.txt
```

### Option B: Using uv (faster, recommended)

```bash
# Navigate to OSWorld vendor directory
cd vendor/OSWorld

# Install with uv
uv pip install -r requirements.txt
```

### macOS ARM (Apple Silicon) Specific Instructions

If you encounter errors on macOS ARM64:

1. **Use Python 3.11** (not 3.13):
```bash
# With uv
uv python install 3.11
uv venv -p 3.11 .venv
source .venv/bin/activate
```

2. **Apply constraints for torch**:
```bash
uv pip install -r vendor/OSWorld/requirements.txt -c constraints-macos-arm.txt
```

3. **Allow pre-releases if needed**:
```bash
uv pip install --prerelease=allow -r vendor/OSWorld/requirements.txt
```

4. **For borb wheel extraction errors**:
```bash
uv cache clean
uv pip install --no-binary borb borb==3.0.2
uv pip install --prerelease=allow -r vendor/OSWorld/requirements.txt --no-deps
```

### Expected Installation Time

- **First time**: 15-30 minutes (downloads ML models, compiles packages)
- **Subsequent installs**: 5-10 minutes (uses cache)

### Verifying Installation

```bash
# Test OSWorld imports
cd /path/to/green_agent
python3 -c "
import sys
sys.path.insert(0, 'vendor/OSWorld')
from desktop_env.desktop_env import DesktopEnv
import lib_run_single
from mm_agents.white_agent_bridge import WhiteAgentBridge
print('✅ All imports successful!')
"
```

---

## Phase 6: Testing the Integration

### Test 1: Fake Mode (Sanity Check)

Ensure fake mode still works after changes:

```bash
# Terminal 1: Start White Agent
python white_agent/server.py --port 8090

# Terminal 2: Start Green Agent (fake mode)
export USE_FAKE_OSWORLD=1
uvicorn green_agent.app:app --host 0.0.0.0 --port 8080

# Terminal 3: Trigger assessment
curl -X POST http://localhost:8080/assessments/start \
  -H 'Content-Type: application/json' \
  -d '{"task_id":"ubuntu_001","white_agent_url":"http://localhost:8090"}'

# Get result
curl http://localhost:8080/assessments/<assessment_id>/results
```

**Expected Output:**
- success: 1
- steps: 10
- time_sec: < 5 seconds
- 10 PNG frames in `runs/<assessment_id>/frames/`

### Test 2: Native OSWorld Mode (Production)

**Prerequisites:**
- OSWorld VM running (from golden image)
- Firewall rule allowing port 5000
- See [Native Mode Guide](NATIVE_MODE.md) for VM setup

```bash
# Terminal 1: Start White Agent
python white_agent/server.py --port 9000

# Terminal 2: Start Green Agent (native mode)
export USE_FAKE_OSWORLD=0
export USE_NATIVE_OSWORLD=1
export OSWORLD_SERVER_URL="http://YOUR_VM_IP:5000"
uvicorn green_agent.app:app --host 0.0.0.0 --port 8000

# Terminal 3: Trigger assessment
curl -X POST http://localhost:8000/assessments/start \
  -H 'Content-Type: application/json' \
  -d '{"task_id":"ubuntu_001","white_agent_url":"http://localhost:9000"}'

# Get result
curl http://localhost:8000/assessments/<assessment_id>/results
```

**What to expect with the stub white agent:**
1. Green Agent connects to the OSWorld VM via REST API.
2. Each step sends a screenshot to the white agent.
3. The stub responds with `{"op": "wait"}` until it reaches its internal step limit, then returns `{"op": "done"}`.
4. The Green Agent logs the `wait` actions, sleeps for `OSWORLD_SLEEP_AFTER_EXECUTION`, and eventually marks the run complete (usually `success=0`, `steps≈10` in native mode).
5. Screenshots are saved under `runs/<assessment_id>/frames/`, but there will be no UI changes.

To exercise real desktop automation, swap in an action-capable white agent before rerunning the assessment:

```bash
# Example: run the GPT-4V white agent (requires OPENAI_API_KEY)
export OPENAI_API_KEY=sk-...
uvicorn white_agent.gpt4v_server:app --host 0.0.0.0 --port 9000
```

With a production agent you should see `click`, `type`, `execute`, and other OS interactions in the logs, and the results payload will include meaningful metrics/evaluation scores.

**Native mode performance (typical with action-capable agent):**
- Screenshot latency: ~100 ms
- Command execution: 50–500 ms
- Full action cycle (observe → decide → act → settle): 2–5 s

### Test 3: Verify White Agent Communication

Check that White Agent is receiving correct observations:

```bash
# Add logging to white_agent/server.py
# In the decide() function, add:
import logging
logging.basicConfig(level=logging.INFO)

@app.post("/decide")
def decide(obs: Observation) -> Dict[str, Any]:
    logging.info(f"Received observation: frame_id={obs.frame_id}, hint={obs.ui_hint}")
    # ... rest of function

# Then run assessment and check logs
```

### Test 4: Legacy Action Bridge (Optional)

If you still use the legacy Docker/QEMU workflow, you can validate the `WhiteAgentBridge` conversion logic with a small script:

```python
# test_action_conversion.py
import sys
sys.path.insert(0, 'vendor/OSWorld')

from mm_agents.white_agent_bridge import WhiteAgentBridge

bridge = WhiteAgentBridge("http://localhost:8090")

test_cases = [
    ({"op": "click", "args": {"x": 100, "y": 200}}, "pyautogui.click(100, 200)"),
    ({"op": "hotkey", "args": {"keys": ["ctrl", "s"]}}, "pyautogui.hotkey('ctrl', 's')"),
    ({"op": "type", "args": {"text": "Hello"}}, 'pyautogui.typewrite("""Hello""", interval=0.01)'),
    ({"op": "done"}, "DONE"),
]

for action_in, expected_out in test_cases:
    result = bridge._convert_action(action_in)[0]
    assert expected_out in result, f"Failed: {action_in} -> {result}"
    print(f"✓ {action_in['op']} converts correctly")

print("✅ All action conversions passed!")
```

Run it only if you rely on the legacy path:

```bash
python test_action_conversion.py
```

---

## Troubleshooting

### Error: "OSWorld dependencies not installed"

**Cause:** OSWorld modules not in Python path

**Solution:**
```bash
cd vendor/OSWorld
pip install -r requirements.txt
```

### Error: "white_agent_url is required for real OSWorld mode"

**Cause:** Missing white_agent_url parameter

**Solution:** Ensure the POST request includes white_agent_url:
```json
{"task_id":"ubuntu_001","white_agent_url":"http://localhost:8090"}
```

### Error: "OSWorld server not responding"

**Cause:** OSWorld VM not running or unreachable

**Solutions:**
1. Check VM is running: `gcloud compute instances list`
2. Verify firewall allows port 5000
3. Test connectivity: `curl http://VM_IP:5000/platform`
4. SSH into VM and check service: `sudo systemctl status osworld-server`

### Error: "Connection refused to White Agent"

**Cause:** White Agent not running or wrong port

**Solutions:**
1. Start White Agent: `python white_agent/server.py --port 8090`
2. Verify it's running: `curl http://localhost:8090/card`
3. Check firewall isn't blocking port 8090

### Performance: Assessment takes too long

**Solutions:**
1. Reduce max_steps: `export OSWORLD_MAX_STEPS=5`
2. Use native mode (not Docker): `export USE_NATIVE_OSWORLD=1`
3. Ensure VM has enough resources (n1-standard-4 recommended)

### macOS Specific: "No module named 'wrapt_timeout_decorator'"

**Solution:**
```bash
pip install wrapt_timeout_decorator
```

### macOS Specific: "Torch wheels not found"

**Solution:**
```bash
uv pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1
uv pip install -r vendor/OSWorld/requirements.txt --no-deps
```

---

## Validation Checklist

Use this checklist to verify the integration is working:

- [ ] Fake mode assessment completes successfully
- [ ] Real OSWorld mode starts without errors
- [ ] White Agent receives observations (check logs)
- [ ] White Agent actions are converted correctly
- [ ] OSWorld executes actions in desktop
- [ ] Screenshots are captured and saved
- [ ] Metrics are recorded in database
- [ ] Artifacts directory contains logs and screenshots

---

## Performance Benchmarks

Expected performance on different systems:

| System | Fake Mode (10 steps) | Native Mode (10 steps) |
|--------|----------------------|------------------------|
| macOS M1 (8GB) | 2–3 s | 6–8 s |
| macOS M1 (16GB) | 2–3 s | 4–6 s |
| Linux x86 (16GB) | 2–3 s | 3–5 s |
| Linux x86 (32GB) | 2–3 s | 3–4 s |

*Numbers are typical once the VM is booted and an action-capable white agent is running. The first native run may include an extra few seconds while caches warm up.*

---

## Next Steps

Once the integration is validated:

1. **Expand White Agent Logic:** Improve decision-making beyond baseline
2. **Add More Tasks:** Create additional task definitions in `tasks/`
3. **Implement Real Evaluators:** Replace placeholder evaluator with actual checks
4. **Optimize Performance:** Parallel assessments, caching, etc.
5. **Add Monitoring:** Metrics, dashboards, alerts
6. **Scale Up:** Multiple providers (AWS, GCP, Azure)

---

## Support

If you encounter issues not covered here:

1. Check OSWorld logs: `runs/<assessment_id>/osworld/osworld.log`
2. Check Green Agent logs
3. Enable debug logging: `export LOG_LEVEL=DEBUG`
4. Review the audit report for known issues

---

## Architecture Overview

**Native Mode (Recommended):**
```
┌─────────────────────────────────────────────────────────┐
│ Green Agent (FastAPI)                                   │
│ ├─ POST /assessments/start                              │
│ └─ osworld_adapter.py                                   │
│    └─ Native Mode: REST API to OSWorld VM ──────────┐   │
└─────────────────────────────────────────────────────│───┘
                                                      │
                                                      │ HTTP REST
                                                      ▼
┌─────────────────────────────────────────────────────────┐
│ OSWorld VM (GCE)                                        │
│ ├─ OSWorld Server (Flask :5000)                        │
│ ├─ GNOME Desktop Environment                            │
│ └─ Applications (Chrome, Firefox, etc.)                │
└─────────────────────────────────────────────────────────┘
                          │
                          │ HTTP
                          ▼
┌─────────────────────────────────────────────────────────┐
│ White Agent (FastAPI)                                   │
│ ├─ POST /decide: Returns actions                         │
│ └─ Receives: screenshots, returns: click/type/etc.     │
└─────────────────────────────────────────────────────────┘
```

See [Native Mode Guide](NATIVE_MODE.md) for complete architecture details.

---

**Last Updated:** 2025-10-16
**Version:** 1.0.0
