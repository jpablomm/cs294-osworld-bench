# Google Cloud Platform Setup Guide

This guide covers setting up GCP for local development of the OSWorld Green Agent project.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Service Account Setup](#service-account-setup)
5. [Quota Configuration](#quota-configuration)
6. [Budget Alerts](#budget-alerts)
7. [Local Development Without GCP](#local-development-without-gcp)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The project uses Google Cloud for:

| Service | Purpose | Required? |
|---------|---------|-----------|
| Compute Engine | OSWorld VM instances | Yes (for full testing) |
| Cloud Storage | Screenshot/artifact storage | Optional |
| Cloud Billing | Budget alerts | Recommended |

### Authentication Options

| Method | Best For | Setup Complexity |
|--------|----------|------------------|
| `gcloud auth` | Personal development | Easy |
| Service Account Key | Team sharing, CI/CD | Medium |
| Workload Identity | GKE, Cloud Run | Advanced |

---

## Prerequisites

1. **Google Cloud SDK** installed:
   ```bash
   # macOS
   brew install google-cloud-sdk

   # Or download from https://cloud.google.com/sdk/docs/install
   ```

2. **GCP Project** with billing enabled

3. **APIs enabled**:
   ```bash
   gcloud services enable compute.googleapis.com
   gcloud services enable storage.googleapis.com
   ```

---

## Quick Start

### Option 1: Personal Development (gcloud auth)

```bash
# Authenticate with your Google account
gcloud auth login
gcloud auth application-default login

# Set default project
gcloud config set project YOUR_PROJECT_ID

# Verify
gcloud auth list
gcloud config list project
```

### Option 2: Service Account (Recommended for Teams)

```bash
# Run the setup script
./scripts/gcp/setup-service-account.sh YOUR_PROJECT_ID

# Add to .env
echo "GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/osworld-service-account-key.json" >> .env
echo "GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID" >> .env
```

---

## Service Account Setup

### Automated Setup

```bash
./scripts/gcp/setup-service-account.sh PROJECT_ID [SERVICE_ACCOUNT_NAME]
```

This script:
1. Creates a service account with minimal permissions
2. Grants IAM roles with resource conditions
3. Generates a JSON key file
4. Adds the key file to `.gitignore`

### Manual Setup

#### 1. Create Service Account

```bash
PROJECT_ID="your-project"
SA_NAME="osworld-dev"

gcloud iam service-accounts create $SA_NAME \
    --display-name="OSWorld Development (Restricted)"
```

#### 2. Grant Minimal Roles

```bash
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# VM management (restricted to osworld-* VMs)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/compute.instanceAdmin.v1" \
    --condition='expression=resource.name.startsWith("projects/'$PROJECT_ID'/zones/us-central1-a/instances/osworld-"),title=OSWorld VMs only'

# Use golden images
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/compute.imageUser"

# Attach service accounts to VMs
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/iam.serviceAccountUser"

# Storage upload only (no delete)
gsutil iam ch "serviceAccount:${SA_EMAIL}:roles/storage.objectCreator" \
    gs://osworld-green-agent-artifacts

# Basic project info access
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/browser"
```

#### 3. Create Key File

```bash
gcloud iam service-accounts keys create osworld-service-account-key.json \
    --iam-account="${SA_EMAIL}"

# Secure the file
chmod 600 osworld-service-account-key.json
```

#### 4. Configure Environment

```bash
# Add to .env
GOOGLE_APPLICATION_CREDENTIALS=/path/to/osworld-service-account-key.json
GOOGLE_CLOUD_PROJECT=your-project-id
```

### IAM Roles Reference

| Role | Purpose | Scope |
|------|---------|-------|
| `compute.instanceAdmin.v1` | Create/delete VMs | osworld-* VMs only |
| `compute.imageUser` | Use golden images | All project images |
| `iam.serviceAccountUser` | Attach SA to VMs | Required for VM creation |
| `storage.objectCreator` | Upload artifacts | Specific bucket only |
| `browser` | View project info | Read-only |

---

## Quota Configuration

### View Current Quotas

```bash
./scripts/gcp/setup-quotas.sh PROJECT_ID
```

### Recommended Limits

| Resource | Recommended | Why |
|----------|-------------|-----|
| CPUs | 16-32 | 4 CPUs × 4-8 VMs |
| VM Instances | 4-8 | Concurrent assessments |
| Persistent Disk | 200-400 GB | 50 GB per VM |
| External IPs | 4-8 | One per VM |

### Setting Quotas

1. Go to [GCP Console Quotas](https://console.cloud.google.com/iam-admin/quotas)
2. Filter by: Service = "Compute Engine API", Region = "us-central1"
3. Select quotas to modify
4. Click "Edit Quotas"
5. Submit request

**Note**: Quota decreases require manual approval. Increases are usually auto-approved.

---

## Budget Alerts

### Automated Setup

```bash
./scripts/gcp/setup-budget-alerts.sh PROJECT_ID MONTHLY_BUDGET_USD

# Example: $100/month budget
./scripts/gcp/setup-budget-alerts.sh my-project 100
```

### Alert Thresholds

| Threshold | Action |
|-----------|--------|
| 50% | Email notification |
| 90% | Email notification |
| 100% | Email notification + optional auto-shutdown |

### Auto-Shutdown on Budget Exceeded

Deploy the Cloud Function to automatically stop VMs:

```bash
# Create Pub/Sub topic
gcloud pubsub topics create budget-alerts

# Deploy function
cd scripts/gcp/budget-shutdown-function
gcloud functions deploy budget-shutdown \
    --runtime python311 \
    --trigger-topic budget-alerts \
    --entry-point stop_osworld_vms \
    --set-env-vars GCP_PROJECT=your-project,GCP_ZONE=us-central1-a

# Link topic to budget (via Console)
# Billing > Budgets > Select budget > Manage notifications > Connect Pub/Sub topic
```

---

## Local Development Without GCP

For testing without GCP access, use local mode:

### Option 1: Use Existing VM

If you have a running OSWorld VM:

```bash
# Point to existing VM
export OSWORLD_SERVER_URL=http://VM_IP:5000
export USE_NATIVE_OSWORLD=1

# Run white agent only (no VM management)
python -m white_agent.rest.server
```

### Option 2: Local OSWorld Server

Run OSWorld locally (requires Linux with GUI):

```bash
# Start local OSWorld server
cd vendor/OSWorld
python -m desktop_env.server.main --port 5000

# In another terminal
export OSWORLD_SERVER_URL=http://localhost:5000
python -m white_agent.rest.server
```

### Option 3: Mock Mode

For testing agent logic without real VMs:

```bash
export USE_FAKE_OSWORLD=1
python -m white_agent.rest.server
```

---

## Troubleshooting

### Authentication Errors

```
google.auth.exceptions.DefaultCredentialsError: Could not automatically determine credentials.
```

**Solution**:
```bash
# Option 1: Login with gcloud
gcloud auth application-default login

# Option 2: Set credentials file
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

### Permission Denied

```
googleapiclient.errors.HttpError: 403 Required 'compute.instances.create' permission
```

**Solution**:
- Verify service account has correct roles
- Check IAM conditions aren't blocking the request
- Ensure VM name starts with `osworld-`

### Quota Exceeded

```
Quota 'CPUS' exceeded. Limit: 8.0 in region us-central1.
```

**Solution**:
- Request quota increase in GCP Console
- Or stop unused VMs: `gcloud compute instances list --filter="name~osworld-" | xargs -I {} gcloud compute instances delete {}`

### Budget Alert Not Firing

**Checklist**:
1. Budget is linked to correct project
2. Pub/Sub topic exists and is connected
3. Cloud Function is deployed and has correct permissions
4. Check Cloud Function logs: `gcloud functions logs read budget-shutdown`

---

## Security Best Practices

1. **Never commit key files** - Add to `.gitignore`
2. **Rotate keys every 90 days**:
   ```bash
   gcloud iam service-accounts keys list --iam-account=SA_EMAIL
   gcloud iam service-accounts keys delete KEY_ID --iam-account=SA_EMAIL
   gcloud iam service-accounts keys create new-key.json --iam-account=SA_EMAIL
   ```
3. **Use IAM conditions** to restrict resource access
4. **Set budget alerts** to catch runaway costs
5. **Audit access** periodically:
   ```bash
   gcloud projects get-iam-policy PROJECT_ID
   ```

---

## Quick Reference

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account key | Yes (if using SA) |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | Yes |
| `GCP_ZONE` | Compute zone | No (default: us-central1-a) |
| `OSWORLD_SERVER_URL` | OSWorld server URL | No (auto from VM) |

### Useful Commands

```bash
# List all osworld VMs
gcloud compute instances list --filter="name~osworld-"

# Stop all osworld VMs
gcloud compute instances list --filter="name~osworld- AND status=RUNNING" \
    --format="value(name,zone)" | while read name zone; do
    gcloud compute instances stop $name --zone=$zone
done

# Delete all osworld VMs
gcloud compute instances list --filter="name~osworld-" \
    --format="value(name,zone)" | while read name zone; do
    gcloud compute instances delete $name --zone=$zone --quiet
done

# Check current spending
gcloud billing projects describe PROJECT_ID

# View service account permissions
gcloud projects get-iam-policy PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:SA_EMAIL"
```
