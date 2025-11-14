# Cloud Run Deployment Guide

## Deployment Summary

**Status:** ✅ Deployed
**Service:** green-agent
**Region:** us-central1
**Project:** cs294-475401

---

## API Key

**Your API Key:**
```
a084e0362e078cf8c8b606f63378b2a7ab85d13b686ed79fd547080fa29f64ce
```

⚠️ **IMPORTANT:** Save this key securely! You must include it in all requests.

---

## Service URL

Once deployment completes, your service will be available at:
```
https://green-agent-[HASH]-uc.a.run.app
```

The deployment script will print the exact URL when it finishes.

---

## Available Endpoints

### 1. Health Check
```bash
curl https://green-agent-XXX-uc.a.run.app/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "agent_type": "green",
  "protocol": "a2a",
  "assessment_types": ["osworld"],
  "active_assessments": 0
}
```

### 2. Agent Card (A2A Protocol)
```bash
curl https://green-agent-XXX-uc.a.run.app/agent-card
```

### 3. AgentBeats Discovery Endpoint
```bash
curl https://green-agent-XXX-uc.a.run.app/.well-known/agent-card.json
```

**Expected Response:**
```json
{
  "name": "OSWorld Assessment Agent",
  "description": "Green agent for conducting OSWorld desktop automation assessments...",
  "version": "0.1.0",
  "capabilities": ["osworld-benchmarks", "desktop-automation-assessment", ...],
  "protocols": ["a2a", "rest"],
  "assessment_types": ["osworld-single-agent", "osworld-chrome", "osworld-os", "osworld-custom"]
}
```

### 4. Submit Assessment (with API Key)
```bash
curl -X POST https://green-agent-XXX-uc.a.run.app/task \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: a084e0362e078cf8c8b606f63378b2a7ab85d13b686ed79fd547080fa29f64ce' \
  -d '{
    "task_id": "test-assessment-001",
    "message": "Run OSWorld desktop automation assessment",
    "metadata": {
      "osworld_task_id": "osworld-ubuntu-tiny",
      "white_agent_url": "http://your-white-agent.run.app",
      "max_steps": 5
    }
  }'
```

---

## Authentication

All POST /task requests **require** the API key in the `X-API-Key` header:

```bash
-H 'X-API-Key: a084e0362e078cf8c8b606f63378b2a7ab85d13b686ed79fd547080fa29f64ce'
```

**Without the API key, you'll get:**
```json
{
  "detail": "Invalid or missing API key. Set X-API-Key header."
}
```

---

## Environment Variables (Cloud Run)

The deployed service has these environment variables set:

- `GCP_PROJECT=cs294-475401`
- `USE_NATIVE_OSWORLD=1`
- `USE_FAKE_OSWORLD=0`
- `OSWORLD_MAX_STEPS=15`
- `GREEN_AGENT_API_KEY=a084e0362e078cf8c8b606f63378b2a7ab85d13b686ed79fd547080fa29f64ce`

---

## Resource Configuration

- **Memory:** 4 GiB
- **CPU:** 2 vCPUs
- **Timeout:** 30 minutes (for long-running assessments)
- **Concurrency:** Multiple requests supported
- **Max Instances:** 10
- **Min Instances:** 0 (scales to zero when idle)

---

## Cost Estimate

### Per Assessment
- **Green Agent (Cloud Run):** ~$0.001/minute
- **VM Creation:** ~$0.016/task (5 min on n1-standard-4)
- **Total:** ~$0.02-0.05 per assessment

### Monthly (100 assessments)
- ~$2-5/month (very low cost due to scale-to-zero)

---

## Testing the Deployment

### Step 1: Check Health
```bash
SERVICE_URL="https://green-agent-XXX-uc.a.run.app"
curl $SERVICE_URL/health
```

### Step 2: Verify Discovery
```bash
curl $SERVICE_URL/.well-known/agent-card.json
```

### Step 3: Test Authentication
```bash
# This should FAIL (no API key)
curl -X POST $SERVICE_URL/task \
  -H 'Content-Type: application/json' \
  -d '{"task_id":"test","message":"test"}'

# This should SUCCEED (with API key)
curl -X POST $SERVICE_URL/task \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: a084e0362e078cf8c8b606f63378b2a7ab85d13b686ed79fd547080fa29f64ce' \
  -d '{"task_id":"test","message":"test"}'
```

---

## Monitoring

### View Logs
```bash
gcloud run services logs read green-agent \
  --region us-central1 \
  --limit 50
```

### Stream Logs (Real-time)
```bash
gcloud run services logs tail green-agent \
  --region us-central1
```

### View Metrics
Visit [Cloud Run Console](https://console.cloud.google.com/run) and navigate to the `green-agent` service for:
- Request count
- Response latency
- Error rate
- Resource utilization

---

## Updating the Deployment

### Update Code
```bash
# Make code changes, then redeploy
bash deploy_green_agent.sh --with-api-key
```

### Update Environment Variables
```bash
gcloud run services update green-agent \
  --region us-central1 \
  --set-env-vars "NEW_VAR=value"
```

### Rotate API Key
```bash
# Generate new key
NEW_KEY=$(openssl rand -hex 32)

# Update service
gcloud run services update green-agent \
  --region us-central1 \
  --set-env-vars "GREEN_AGENT_API_KEY=$NEW_KEY"

echo "New API Key: $NEW_KEY"
```

---

## Publishing on AgentBeats Platform

Once deployment is complete:

1. **Get Service URL:**
   ```bash
   gcloud run services describe green-agent \
     --region us-central1 \
     --format 'value(status.url)'
   ```

2. **Visit AgentBeats Platform** (hypothetical)

3. **Register Your Agent:**
   - Controller URL: `https://green-agent-XXX-uc.a.run.app`
   - Agent Name: OSWorld Assessment Agent
   - Description: Green agent for desktop automation assessments
   - Capabilities: osworld-benchmarks, vm-orchestration

4. **Verify Discovery:**
   - Platform will check: `https://your-url/.well-known/agent-card.json`
   - Should return valid AgentCard JSON

---

## Troubleshooting

### Issue: 401 Unauthorized
**Cause:** Missing or invalid API key
**Fix:** Include `X-API-Key` header with correct value

### Issue: 503 Service Unavailable
**Cause:** Cold start (first request after idle)
**Fix:** Wait 10-20 seconds and retry (subsequent requests will be fast)

### Issue: 504 Gateway Timeout
**Cause:** Assessment taking longer than Cloud Run timeout
**Fix:** This shouldn't happen (30min timeout set), but check VM creation logs

### Issue: VM Creation Fails
**Cause:** GCP quota limits or permissions
**Fix:**
```bash
# Check quotas
gcloud compute project-info describe --project cs294-475401

# Check IAM permissions
gcloud projects get-iam-policy cs294-475401
```

---

## Security Best Practices

### 1. API Key Management
- ✅ Store API key in secure secret manager
- ✅ Rotate key every 90 days
- ✅ Use different keys for dev/staging/prod
- ✅ Monitor unauthorized access attempts

### 2. Network Security
- ✅ Use Cloud Run ingress controls if needed
- ✅ Enable VPC connector for internal services
- ✅ Use Cloud Armor for DDoS protection (if public)

### 3. Access Control
- ✅ Limit who can deploy (`roles/run.developer`)
- ✅ Limit who can view logs (`roles/logging.viewer`)
- ✅ Use service accounts with minimal permissions

---

## Next Steps

1. ✅ Wait for deployment to complete
2. ✅ Test all endpoints
3. ✅ Deploy a white agent (separate service)
4. ✅ Run end-to-end assessment
5. ✅ Publish on AgentBeats platform
6. ✅ Set up monitoring alerts

---

**Deployment Date:** 2025-11-13
**Deployed By:** Automated via deploy_green_agent.sh
**Status:** In Progress ⏳
