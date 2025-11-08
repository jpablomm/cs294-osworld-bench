# Native OSWorld Mode Configuration

This guide explains how to configure and use **Native OSWorld mode** (REST API to GCE VMs). For complete system setup including White Agent, see [Complete System Guide](RUN_COMPLETE_SYSTEM.md).

---

## Overview

Native mode connects Green Agent directly to OSWorld VMs via REST API, providing **20x faster performance** than Docker/QEMU.

| Mode | Description | Use Case | Speed |
|------|-------------|----------|-------|
| **Fake** | Simulated screenshots | Testing, development | Instant |
| **Native** | REST API to real VMs | Production (recommended) | Fast (~100ms/action) |
| **Docker** | Docker/QEMU | Legacy (deprecated) | Slow (~2-5s/action) |

---

## Quick Setup

### 1. Create OSWorld VM

```bash
# Create VM from golden image
gcloud compute instances create my-osworld-1 \
  --image=osworld-golden-v2-gnome \
  --machine-type=n1-standard-4 \
  --zone=us-central1-a

# Get VM IP
VM_IP=$(gcloud compute instances describe my-osworld-1 \
  --zone=us-central1-a \
  --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

echo "OSWorld VM IP: $VM_IP"
```

### 2. Configure Environment Variables

```bash
# Required for native mode
export USE_FAKE_OSWORLD=0
export USE_NATIVE_OSWORLD=1
export OSWORLD_SERVER_URL="http://${VM_IP}:5000"

# Optional configuration
export OSWORLD_MAX_STEPS=20
export OSWORLD_SLEEP_AFTER_EXECUTION=3
export OSWORLD_OBS_TYPE=screenshot
```

### 3. Start Green Agent

```bash
cd green_agent
source .venv/bin/activate
uvicorn green_agent.app:app --host 0.0.0.0 --port 8000
```

### 4. Verify Configuration

```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "service": "green-agent",
  "version": "0.2.0",
  "osworld_mode": "native",
  "osworld_server_url": "http://10.128.0.3:5000",
  "max_steps": 20
}
```

---

## Environment Variables Reference

### Required

```bash
USE_FAKE_OSWORLD=0          # Disable fake mode
USE_NATIVE_OSWORLD=1        # Enable native mode
OSWORLD_SERVER_URL=http://VM_IP:5000  # OSWorld REST API URL
```

### Optional

```bash
OSWORLD_MAX_STEPS=15        # Max steps per task (default: 15)
OSWORLD_SLEEP_AFTER_EXECUTION=3  # Seconds after each action (default: 3)
OSWORLD_OBS_TYPE=screenshot # Observation type: screenshot, a11y_tree, screenshot_a11y_tree
DESKTOP_W=1920              # Desktop width (default: 1920)
DESKTOP_H=1080              # Desktop height (default: 1080)
```

---

## Architecture

```
┌──────────────┐
│ Green Agent  │
│   (port 8000)│
└──────┬───────┘
       │
       │ HTTP REST API
       ▼
┌──────────────────────┐
│ OSWorld VM (GCE)     │
│                      │
│  ┌────────────────┐  │
│  │ GNOME Desktop  │  │ Display :0
│  └────────────────┘  │
│  ┌────────────────┐  │
│  │ OSWorld Server │  │ REST API (port 5000)
│  │  /screenshot   │  │
│  │  /execute      │  │
│  │  /accessibility│  │
│  └────────────────┘  │
│  ┌────────────────┐  │
│  │ Chrome, etc.    │  │ Applications
│  └────────────────┘  │
└──────────────────────┘
```

---

## Performance

| Operation | Docker/QEMU | Native Mode | Improvement |
|-----------|-------------|-------------|-------------|
| Screenshot | 2-5 seconds | 0.1 seconds | **20-50x faster** |
| Execute command | 1-2 seconds | 0.05 seconds | **20-40x faster** |
| Full action cycle | 3-7 seconds | 0.2 seconds | **15-35x faster** |

**Cost:** ~$0.016 per 5-minute task (vs $0.05-0.10 with Docker)

---

## Multiple VMs

For parallel execution:

```bash
# Create multiple VMs
for i in {1..5}; do
  gcloud compute instances create osworld-vm-$i \
    --image=osworld-golden-v2-gnome \
    --machine-type=n1-standard-4 \
    --zone=us-central1-a \
    --async
done

# Get all IPs
gcloud compute instances list \
  --filter="name:osworld-vm-*" \
  --format="csv[no-heading](name,INTERNAL_IP)"
```

Then start multiple Green Agent instances, each pointing to a different VM.

---

## Troubleshooting

### OSWorld Server Not Responding

```bash
# Check VM is running
gcloud compute instances list --filter="name:osworld-vm-1"

# SSH into VM
gcloud compute ssh osworld-vm-1 --zone=us-central1-a

# Check services
sudo systemctl status gdm osworld-server

# Test API
curl http://localhost:5000/platform
```

### Green Agent Can't Connect

```bash
# Test connectivity
ping $VM_IP
curl http://$VM_IP:5000/platform

# Check firewall
gcloud compute firewall-rules list --filter="name:allow-osworld"
```

### Wrong Image Version

Ensure you're using `osworld-golden-v2-gnome` (not v1):
```bash
gcloud compute images describe osworld-golden-v2-gnome
```

---

## API Reference

See [OSWorld API Documentation](../api/OSWORLD_API.md) for complete REST API reference.

---

## Next Steps

- **Complete Setup:** See [Complete System Guide](RUN_COMPLETE_SYSTEM.md) for White Agent setup
- **Deployment:** See [GCP Deployment Guide](../deployment/GCP_DEPLOYMENT.md) for production deployment
- **Troubleshooting:** See [Debug Guide](../troubleshooting/DEBUG_OSWORLD.md) for common issues
