# Cloud-First OSWorld Architecture

## Executive Summary

Replace the brittle Docker→QEMU→Ubuntu stack with native GCE VMs running Ubuntu Desktop directly. This eliminates 5 layers of indirection, fixes all boot issues, and provides production-grade infrastructure.

> **Status:** Proposed future architecture. The Terraform, Cloud Run, and startup script snippets below are design examples and are not yet implemented in this repository.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     GREEN AGENT SYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐         ┌─────────────────┐                 │
│  │ Green Agent  │ ──────> │  Cloud Run      │                 │
│  │ (FastAPI)    │  HTTPS  │  Orchestrator   │                 │
│  └──────────────┘         └────────┬────────┘                 │
│                                     │                          │
│                                     ↓                          │
│                            ┌────────────────┐                  │
│                            │   Pub/Sub      │                  │
│                            │   (tasks)      │                  │
│                            └───────┬────────┘                  │
│                                    │                           │
│                                    ↓                           │
│              ┌─────────────────────────────────────┐           │
│              │  Managed Instance Group (MIG)       │           │
│              │  ┌───────────┐  ┌───────────┐      │           │
│              │  │ GCE VM 1  │  │ GCE VM 2  │ ...  │           │
│              │  │ Ubuntu +  │  │ Ubuntu +  │      │           │
│              │  │ OSWorld   │  │ OSWorld   │      │           │
│              │  └─────┬─────┘  └─────┬─────┘      │           │
│              └────────┼──────────────┼────────────┘           │
│                       │              │                         │
│                       ↓              ↓                         │
│              ┌──────────────────────────────┐                  │
│              │  Cloud Storage (Artifacts)   │                  │
│              │  - Screenshots               │                  │
│              │  - Videos                    │                  │
│              │  - Logs                      │                  │
│              │  - Run manifests             │                  │
│              └──────────────────────────────┘                  │
│                                                                 │
│                       ↓                                         │
│              ┌──────────────────────────────┐                  │
│              │  BigQuery (Results)          │                  │
│              │  - run_results               │                  │
│              │  - step_metrics              │                  │
│              │  - evaluations               │                  │
│              └──────────────────────────────┘                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Golden Image (GCE Image Family: `osworld-desktop`)

**Contents:**
```dockerfile
# Built via Cloud Build + Packer
FROM ubuntu:22.04

# Base desktop environment
- Ubuntu Desktop (minimal)
- Xvfb (virtual display at :99)
- Openbox (lightweight window manager)
- x11vnc (optional remote viewing)

# Applications (OSWorld requirements)
- Google Chrome (stable)
- Firefox ESR
- LibreOffice
- GIMP
- VS Code

# OSWorld runtime
- Python 3.10+
- OSWorld server (vendor/OSWorld/desktop_env/server/main.py)
- Collector agents (screenshots, a11y tree, window graph)

# Monitoring
- Cloud Ops Agent (logging, metrics)
- Systemd services for all components
```

**Build process:**
```bash
# Cloud Build pipeline
gcloud builds submit \
  --config=cloudbuild.yaml \
  --substitutions=_IMAGE_FAMILY=osworld-desktop,_VERSION=2025-10-18
```

**Image versioning:**
- Family: `osworld-desktop` (stable)
- Versioned: `osworld-desktop-2025-10-18-001`
- SBOM generated per build
- SHA256 hash tracked

### 2. Instance Template

**Specs:**
```hcl
resource "google_compute_instance_template" "osworld_worker" {
  name_prefix  = "osworld-worker-"
  machine_type = "n2-standard-4"  # 4 vCPU, 16GB RAM

  # Boot from golden image
  disk {
    source_image = "projects/${var.project}/global/images/family/osworld-desktop"
    auto_delete  = true
    boot         = true
    disk_size_gb = 50
  }

  # Network config
  network_interface {
    subnetwork = google_compute_subnetwork.osworld.id
    # No external IP - use IAP
  }

  # Service account with minimal permissions
  service_account {
    email  = google_service_account.osworld_worker.email
    scopes = [
      "https://www.googleapis.com/auth/devstorage.read_write",  # GCS
      "https://www.googleapis.com/auth/logging.write",           # Logging
      "https://www.googleapis.com/auth/monitoring.write",        # Metrics
      "https://www.googleapis.com/auth/pubsub",                  # Pub/Sub
    ]
  }

  # Startup script
  metadata = {
    startup-script = file("${path.module}/scripts/startup.sh")
    enable-oslogin = "TRUE"
  }

  # Security hardening
  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  labels = {
    component = "osworld-worker"
    purpose   = "benchmark"
  }
}
```

### 3. Managed Instance Group (MIG)

**Configuration:**
```hcl
resource "google_compute_region_instance_group_manager" "osworld_workers" {
  name               = "osworld-workers"
  base_instance_name = "osworld"
  region             = var.region

  version {
    instance_template = google_compute_instance_template.osworld_worker.id
  }

  # Auto-scaling configuration
  target_size = 0  # Scale to zero when idle

  auto_healing_policies {
    health_check      = google_compute_health_check.osworld.id
    initial_delay_sec = 300
  }

  update_policy {
    type                  = "PROACTIVE"
    minimal_action        = "REPLACE"
    max_surge_fixed       = 3
    max_unavailable_fixed = 0
  }
}

resource "google_compute_region_autoscaler" "osworld_workers" {
  name   = "osworld-workers-autoscaler"
  region = var.region
  target = google_compute_region_instance_group_manager.osworld_workers.id

  autoscaling_policy {
    min_replicas    = 0
    max_replicas    = 20
    cooldown_period = 60

    # Scale based on Pub/Sub queue depth
    metric {
      name   = "pubsub.googleapis.com/subscription/num_undelivered_messages"
      target = 1  # 1 message per VM
      type   = "GAUGE"
      filter = "resource.label.subscription_id=\"osworld-tasks-sub\""
    }
  }
}
```

### 4. VM Startup Script

**`scripts/startup.sh`:**
```bash
#!/bin/bash
set -euo pipefail

# Logging
exec 1> >(logger -s -t osworld-startup) 2>&1

echo "Starting OSWorld worker initialization..."

# Get task config from metadata
TASK_ID=$(curl -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/attributes/task-id")
TASK_CONFIG=$(curl -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/attributes/task-config")

# Set up environment
export DISPLAY=:99
export TASK_ID="$TASK_ID"
export ARTIFACTS_BUCKET="gs://green-agent-artifacts"
export RUN_ID="run-$(date +%s)-${TASK_ID}"

# Start virtual display
Xvfb :99 -screen 0 1920x1080x24 &
XVFB_PID=$!
sleep 2

# Start window manager
openbox &
sleep 1

# Start OSWorld server
cd /opt/osworld
python3 -m desktop_env.server.main \
  --port 5000 \
  --artifacts-dir "/tmp/artifacts/${RUN_ID}" &
SERVER_PID=$!

# Wait for server to be ready
for i in {1..30}; do
  if curl -s http://localhost:5000/health > /dev/null; then
    echo "OSWorld server ready"
    break
  fi
  echo "Waiting for OSWorld server... ($i/30)"
  sleep 2
done

# Execute task (pulled from Pub/Sub via Cloud Run orchestrator)
echo "Executing task: $TASK_ID"
python3 /opt/osworld/run_task.py \
  --task-id "$TASK_ID" \
  --task-config "$TASK_CONFIG" \
  --output-dir "/tmp/artifacts/${RUN_ID}"

# Upload artifacts to GCS
echo "Uploading artifacts to ${ARTIFACTS_BUCKET}/${RUN_ID}/"
gsutil -m rsync -r "/tmp/artifacts/${RUN_ID}" "${ARTIFACTS_BUCKET}/${RUN_ID}/"

# Report completion to orchestrator
ORCHESTRATOR_URL=$(curl -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/attributes/orchestrator-url")
curl -X POST "${ORCHESTRATOR_URL}/complete" \
  -H "Content-Type: application/json" \
  -d "{\"run_id\": \"${RUN_ID}\", \"task_id\": \"${TASK_ID}\", \"status\": \"success\"}"

# Clean shutdown
kill $SERVER_PID $XVFB_PID
echo "Task complete. Shutting down."
sleep 5
shutdown -h now
```

### 5. Cloud Run Orchestrator

**Purpose:** Stateless control plane for task lifecycle management.

**Endpoints:**

```python
# orchestrator/main.py
from fastapi import FastAPI, HTTPException
from google.cloud import pubsub_v1, compute_v1, bigquery
import uuid

app = FastAPI()

# POST /tasks - Submit new task
@app.post("/tasks")
async def submit_task(task: TaskRequest):
    """
    1. Validate task
    2. Generate run_id
    3. Publish to Pub/Sub
    4. Scale MIG if needed
    5. Return run_id
    """
    run_id = f"run-{uuid.uuid4()}"

    # Publish to Pub/Sub
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, "osworld-tasks")

    message_data = {
        "run_id": run_id,
        "task_id": task.task_id,
        "config": task.config,
        "timeout": task.timeout or 900,
    }

    future = publisher.publish(topic_path, json.dumps(message_data).encode())
    future.result()  # Wait for publish

    # Scale MIG (will auto-scale based on queue depth)
    # Just ensure it's not paused

    return {"run_id": run_id, "status": "queued"}

# POST /complete - VM reports completion
@app.post("/complete")
async def complete_task(completion: TaskCompletion):
    """
    1. Validate completion
    2. Write to BigQuery
    3. Update run status
    4. Trigger any webhooks
    """
    bq_client = bigquery.Client()

    row = {
        "run_id": completion.run_id,
        "task_id": completion.task_id,
        "status": completion.status,
        "completed_at": datetime.utcnow().isoformat(),
        "artifacts_path": f"gs://green-agent-artifacts/{completion.run_id}/",
    }

    table_id = f"{PROJECT_ID}.osworld.run_results"
    errors = bq_client.insert_rows_json(table_id, [row])

    if errors:
        raise HTTPException(status_code=500, detail=str(errors))

    return {"status": "recorded"}

# GET /runs/{run_id} - Get run status
@app.get("/runs/{run_id}")
async def get_run_status(run_id: str):
    """
    Query BigQuery for run status and return results
    """
    bq_client = bigquery.Client()
    query = f"""
        SELECT * FROM `{PROJECT_ID}.osworld.run_results`
        WHERE run_id = @run_id
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("run_id", "STRING", run_id)
        ]
    )

    results = bq_client.query(query, job_config=job_config).result()

    for row in results:
        return dict(row)

    raise HTTPException(status_code=404, detail="Run not found")
```

### 6. Integration with Green Agent

**Update `osworld_adapter.py`:**

```python
# green_agent/osworld_adapter.py
import httpx
from typing import Dict, Any

class CloudOSWorldAdapter:
    """Adapter for cloud-first OSWorld infrastructure."""

    def __init__(self, orchestrator_url: str):
        self.orchestrator_url = orchestrator_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def run_task(
        self,
        task_id: str,
        task_config: Dict[str, Any],
        timeout: int = 900
    ) -> Dict[str, Any]:
        """
        Submit task to Cloud Run orchestrator.

        Returns:
            {
                "run_id": "run-uuid",
                "status": "queued"
            }
        """
        response = await self.client.post(
            f"{self.orchestrator_url}/tasks",
            json={
                "task_id": task_id,
                "config": task_config,
                "timeout": timeout,
            }
        )
        response.raise_for_status()
        return response.json()

    async def get_run_status(self, run_id: str) -> Dict[str, Any]:
        """
        Get status of a run.

        Returns:
            {
                "run_id": "run-uuid",
                "task_id": "task-123",
                "status": "success|failed|running",
                "completed_at": "2025-10-18T...",
                "artifacts_path": "gs://..."
            }
        """
        response = await self.client.get(
            f"{self.orchestrator_url}/runs/{run_id}"
        )
        response.raise_for_status()
        return response.json()

    async def wait_for_completion(
        self,
        run_id: str,
        poll_interval: int = 5,
        max_wait: int = 1800
    ) -> Dict[str, Any]:
        """
        Poll until run completes or times out.
        """
        import asyncio

        elapsed = 0
        while elapsed < max_wait:
            status = await self.get_run_status(run_id)

            if status["status"] in ["success", "failed", "timeout"]:
                return status

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"Run {run_id} did not complete in {max_wait}s")


# Update the main run_osworld function
async def run_osworld(
    task: Dict[str, Any],
    white_decide: Any,
    artifacts_dir: str,
    white_agent_url: str
) -> Dict[str, Any]:
    """Run OSWorld benchmark using cloud infrastructure."""

    orchestrator_url = os.getenv(
        "OSWORLD_ORCHESTRATOR_URL",
        "https://osworld-orchestrator-xxxxx.run.app"
    )

    adapter = CloudOSWorldAdapter(orchestrator_url)

    # Submit task
    submission = await adapter.run_task(
        task_id=task["task_id"],
        task_config={
            "goal": task["goal"],
            "white_agent_url": white_agent_url,
        }
    )

    # Wait for completion
    result = await adapter.wait_for_completion(submission["run_id"])

    return {
        "success": result["status"] == "success",
        "run_id": result["run_id"],
        "artifacts_path": result["artifacts_path"],
    }
```

## Benefits Over Current Setup

| Aspect | Current (Docker/QEMU) | Proposed (Cloud-First) |
|--------|----------------------|------------------------|
| **Layers** | 5 (GCE→Docker→QEMU→Ubuntu→OSWorld) | 2 (GCE→OSWorld) |
| **Boot time** | 5-15 min (often fails) | 30-60 sec (reliable) |
| **Debugging** | No console, VNC broken | Serial console, IAP, stackdriver |
| **Networking** | Port forwarding × 3 layers | Standard GCP networking |
| **Scaling** | Manual VM management | Auto-scaling MIG |
| **Cost (idle)** | $120/month (always on) | $0 (scales to zero) |
| **Cost (active)** | $120/month + wasted time | $0.20/hour per worker |
| **Observability** | Docker logs only | Cloud Logging + Monitoring + BigQuery |
| **Reproducibility** | Docker image drift | Immutable GCE images |
| **Security** | Public IPs, open ports | Private network, IAP only |
| **UEFI bugs** | Yes (happysixd image) | No (native boot) |

## Migration Path

### Phase 1: Prototype (1-2 days)
1. Create minimal golden image (Ubuntu + Xvfb + Chrome + OSWorld server)
2. Test manual VM boot and OSWorld functionality
3. Verify artifacts can be collected

### Phase 2: Infrastructure (2-3 days)
1. Set up Terraform for VPC, subnets, Cloud NAT
2. Create instance template and MIG
3. Set up Cloud Storage buckets
4. Create BigQuery tables

### Phase 3: Orchestration (2-3 days)
1. Build Cloud Run orchestrator (FastAPI)
2. Set up Pub/Sub topics
3. Implement task submission and completion flow
4. Add basic error handling

### Phase 4: Integration (1-2 days)
1. Update Green Agent to use new adapter
2. Test end-to-end with simple tasks
3. Add monitoring and alerting

### Phase 5: Production (ongoing)
1. Add image build automation (Cloud Build)
2. Implement advanced features (video recording, a11y tree)
3. Build dashboards and leaderboards
4. Optimize costs and performance

## Estimated Costs

**Development/Testing:**
- Instance Templates: Free
- Cloud Run (orchestrator): ~$5/month
- Cloud Storage: ~$5/month for 100GB
- BigQuery: ~$10/month for 1TB queries
- VMs (testing): ~$20/month (50 hours × $0.40/hour)
- **Total: ~$40/month**

**Production (100 runs/day):**
- VMs: ~$200/month (500 hours × $0.40/hour)
- Cloud Run: ~$10/month
- Cloud Storage: ~$20/month for 500GB
- BigQuery: ~$50/month for 5TB queries
- **Total: ~$280/month**

**Compared to current:** $120/month for 1 VM that doesn't work

## Next Steps

1. **Create prototype golden image** - Manual VM setup to prove concept
2. **Write startup script** - Get OSWorld server running headless
3. **Test task execution** - Verify Chrome works, screenshots captured
4. **Build Cloud Run orchestrator** - Basic task submission
5. **Update Green Agent** - Use new cloud adapter

Want me to start implementing the golden image build process?
