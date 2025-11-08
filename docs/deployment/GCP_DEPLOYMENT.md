# Green Agent - GCP Deployment Guide

This guide explains how to deploy Green Agent to Google Cloud Platform for production use.

## Why GCP?

- **Clean Linux environment**: No macOS-specific issues
- **Better Docker performance**: Native Linux containers
- **Multi-user access**: Remote API accessible to team
- **Scalable**: Can run multiple assessments in parallel
- **Production-ready**: Reliable, monitored infrastructure

---

## Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI installed locally ([install guide](https://cloud.google.com/sdk/docs/install))
- Project with Compute Engine API enabled

---

## Quick Start (10 minutes)

### Step 1: Create a GCP VM

```bash
# Set your GCP project
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Create a VM with Docker pre-installed
gcloud compute instances create green-agent-vm \
  --zone=us-central1-a \
  --machine-type=n1-standard-4 \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=50GB \
  --boot-disk-type=pd-standard \
  --tags=http-server,https-server \
  --metadata=startup-script='#!/bin/bash
    # Install Docker
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    usermod -aG docker $USER

    # Install Python 3.11
    apt-get update
    apt-get install -y python3.11 python3.11-venv python3-pip git

    # Install uv
    curl -LsSf https://astral.sh/uv/install.sh | sh
  '

# Create firewall rule for Green Agent API
gcloud compute firewall-rules create allow-green-agent \
  --allow=tcp:8080 \
  --target-tags=http-server \
  --description="Allow access to Green Agent API"
```

**VM Specs**:
- **Machine**: n1-standard-4 (4 vCPUs, 15GB RAM)
- **Cost**: ~$120/month (can use preemptible for ~$30/month)
- **Disk**: 50GB SSD

### Step 2: SSH into the VM

```bash
gcloud compute ssh green-agent-vm --zone=us-central1-a
```

### Step 3: Clone and Setup Green Agent

```bash
# Clone repository
git clone <your-repo-url> green_agent
cd green_agent

# Initialize git submodules
git submodule update --init --recursive

# Create virtual environment with Python 3.11
python3.11 -m venv .venv
source .venv/bin/activate

# Install uv (if not from startup script)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Install project dependencies
uv pip install -r requirements.txt

# Install OSWorld dependencies
cd vendor/OSWorld
uv pip install -r requirements.txt
cd ../..

# The SQLite schema is created automatically the first time the API starts
```

### Step 4: Start Green Agent

```bash
# Set environment variables
export USE_FAKE_OSWORLD=0
export OSWORLD_PROVIDER=docker
export OSWORLD_HEADLESS=1
export OSWORLD_MAX_STEPS=15

# Start Green Agent (production mode)
uv run uvicorn green_agent.app:app --host 0.0.0.0 --port 8080 &

# Check it's running
curl http://localhost:8080/card
```

### Step 5: Test from Local Machine

```bash
# Get VM external IP
export VM_IP=$(gcloud compute instances describe green-agent-vm \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

# Test Green Agent
curl http://$VM_IP:8080/card

# Start assessment (with local White Agent)
curl -X POST http://$VM_IP:8080/assessments/start \
  -H 'Content-Type: application/json' \
  -d '{"task_id":"ubuntu_001","white_agent_url":"http://YOUR_LOCAL_IP:8090"}'
```

---

## Production Deployment (with systemd)

### Create systemd service

```bash
sudo tee /etc/systemd/system/green-agent.service > /dev/null <<EOF
[Unit]
Description=Green Agent OSWorld Service
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/green_agent
Environment="PATH=/home/$USER/green_agent/.venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="USE_FAKE_OSWORLD=0"
Environment="OSWORLD_PROVIDER=docker"
Environment="OSWORLD_HEADLESS=1"
Environment="OSWORLD_MAX_STEPS=15"
ExecStart=/home/$USER/green_agent/.venv/bin/uvicorn green_agent.app:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable green-agent
sudo systemctl start green-agent

# Check status
sudo systemctl status green-agent

# View logs
sudo journalctl -u green-agent -f
```

---

## White Agent Deployment Options

### Option A: Keep White Agent Local
**Pros**: Simple, good for development
**Cons**: Need public IP or tunnel (ngrok)

```bash
# Local machine
ngrok http 8090

# Use ngrok URL in assessment request
curl -X POST http://$VM_IP:8080/assessments/start \
  -d '{"task_id":"ubuntu_001","white_agent_url":"https://abc123.ngrok.io"}'
```

### Option B: Deploy White Agent to GCP
**Pros**: Production-ready, low latency
**Cons**: More infrastructure to manage

```bash
# On same VM or separate VM
uv run python3 white_agent/server.py --port 8090 &

# Use internal/external IP
curl -X POST http://localhost:8080/assessments/start \
  -d '{"task_id":"ubuntu_001","white_agent_url":"http://localhost:8090"}'
```

---

## Cost Optimization

### Use Preemptible VM (70% cheaper)

```bash
gcloud compute instances create green-agent-vm-preempt \
  --zone=us-central1-a \
  --machine-type=n1-standard-4 \
  --preemptible \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=50GB
```

**Trade-off**: VM can be shut down with 30s notice (Google reclaims it)
**Solution**: Save state, auto-restart with startup script

### Auto-shutdown when idle

```bash
# Add to crontab
crontab -e

# Stop the VM at 2 AM every day (adjust schedule to your needs)
0 2 * * * gcloud compute instances stop green-agent-vm --zone=us-central1-a --quiet
```

Make sure the user running the cron job has application-default credentials or a service account key that allows `compute.instances.stop`.

### Use Spot VMs (even cheaper)

```bash
gcloud compute instances create green-agent-spot \
  --provisioning-model=SPOT \
  --instance-termination-action=STOP \
  --machine-type=n1-standard-4 \
  --zone=us-central1-a
```

---

## Monitoring

### Check VM metrics

```bash
# CPU, memory, disk
gcloud compute instances get-serial-port-output green-agent-vm --zone=us-central1-a
```

### Application logs

```bash
# On VM
sudo journalctl -u green-agent -f

# Or write to file
uv run uvicorn green_agent.app:app --host 0.0.0.0 --port 8080 \
  --log-config logging.json >> /var/log/green-agent.log 2>&1 &
```

### Docker container monitoring

```bash
# Check OSWorld containers
docker ps -a

# Container logs
docker logs <container-id>

# Clean up old containers
docker container prune -f
```

---

## Security

### Firewall rules

```bash
# Restrict to specific IPs
gcloud compute firewall-rules update allow-green-agent \
  --source-ranges="YOUR_IP/32,TEAM_IP/32"

# Or use Identity-Aware Proxy
gcloud compute instances add-iam-policy-binding green-agent-vm \
  --zone=us-central1-a \
  --member=user:teammate@example.com \
  --role=roles/iap.tunnelResourceAccessor
```

### API authentication (future enhancement)

Add API key authentication to Green Agent endpoints.

---

## Troubleshooting

### Green Agent not responding

```bash
# Check service status
sudo systemctl status green-agent

# Restart service
sudo systemctl restart green-agent

# Check logs
sudo journalctl -u green-agent -n 100
```

### Docker permission issues

```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker ps
```

### OSWorld container fails to start

```bash
# Check Docker daemon
sudo systemctl status docker

# Pull image manually
docker pull happysixd/osworld-docker

# Check logs
docker logs <container-id>
```

---

## Next Steps

1. ✅ Deploy Green Agent to GCP
2. ⏭️ Set up monitoring and alerting
3. ⏭️ Add WebUI for visualization
4. ⏭️ Implement parallel assessment execution
5. ⏭️ Set up CI/CD pipeline

---

## Estimated Costs

| Component | Monthly Cost |
|-----------|--------------|
| n1-standard-4 VM (on-demand) | ~$120 |
| 50GB disk | ~$8 |
| Network egress (100GB) | ~$12 |
| **Total (on-demand)** | **~$140** |
| **Total (preemptible)** | **~$40** |

*Prices as of 2025, subject to change*

---

## Support

For issues or questions:
1. Check logs: `sudo journalctl -u green-agent -f`
2. Review OSWorld logs: `runs/<assessment_id>/osworld/osworld.log`
3. Check Docker: `docker ps -a && docker logs <container>`

---

**Last Updated**: October 16, 2025
**Version**: 1.0.0
