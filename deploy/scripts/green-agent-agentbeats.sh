#!/bin/bash
#
# Deploy Green Agent with AgentBeats Controller to Google Cloud Run
# This is a SEPARATE deployment from the production green-agent instance
#
# Service Name: green-agent-agentbeats (keeps production untouched)
# Uses: AgentBeats controller (earthshaker) via Procfile
# Purpose: Testing and AgentBeats platform registration
#
# Usage:
#   bash deploy_green_agent_agentbeats.sh [--project PROJECT_ID]
#

set -e

echo "========================================="
echo "Green Agent AgentBeats Controller Deploy"
echo "========================================="
echo ""
echo "⚠️  This creates a SEPARATE Cloud Run service"
echo "   Production 'green-agent' remains untouched"
echo ""

# Configuration - hardcoded project
PROJECT_ID="cs294-475401"
REGION="us-central1"
SERVICE_NAME="green-agent-agentbeats"
IMAGE_TAG="$REGION-docker.pkg.dev/$PROJECT_ID/$SERVICE_NAME/$SERVICE_NAME"

echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Service Name: $SERVICE_NAME (AgentBeats test instance)"
echo ""

# Step 1: Create Artifact Registry repository if it doesn't exist
echo "Step 1: Checking Artifact Registry..."
if ! gcloud artifacts repositories describe $SERVICE_NAME --location=$REGION --project=$PROJECT_ID &>/dev/null; then
    echo "Creating Artifact Registry repository..."
    gcloud artifacts repositories create $SERVICE_NAME \
        --repository-format=docker \
        --location=$REGION \
        --project=$PROJECT_ID \
        --description="Green Agent with AgentBeats controller" 2>&1 | grep -v "ALREADY_EXISTS" || true
fi
echo "✓ Artifact Registry ready"
echo ""

# Step 2: Build container image using Docker
echo "Step 2: Building container image..."
echo "Building $IMAGE_TAG"

# Create a temporary cloudbuild.yaml
cat > /tmp/cloudbuild-green-agent-agentbeats.yaml << EOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '$IMAGE_TAG', '-f', 'deploy/docker/Dockerfile.green-agent-agentbeats', '.']

  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '$IMAGE_TAG']

images:
  - '$IMAGE_TAG'

options:
  machineType: 'E2_HIGHCPU_8'
  logging: CLOUD_LOGGING_ONLY

timeout: 1200s
EOF

echo "Submitting build (this may take 5-10 minutes)..."
gcloud builds submit \
    --config /tmp/cloudbuild-green-agent-agentbeats.yaml \
    --project=$PROJECT_ID \
    --timeout=20m

rm /tmp/cloudbuild-green-agent-agentbeats.yaml

echo "✓ Container image built successfully"
echo ""

# Step 3: Deploy to Cloud Run
echo "Step 3: Deploying to Cloud Run..."

# Get the service URL to set CLOUDRUN_HOST (predict it from service name)
# Cloud Run URLs follow pattern: SERVICE-HASH-REGION.a.run.app
# We'll update it after deployment, but set HTTPS_ENABLED now
PREDICTED_HOST="${SERVICE_NAME}-750082808015.${REGION}.run.app"

# Load all environment variables from .env file first
if [ -f ".env" ]; then
    echo "Loading configuration from .env..."
    export $(grep -v '^#' .env | xargs)
fi

# Build environment variables
ENV_VARS="GCP_PROJECT=$PROJECT_ID"
ENV_VARS="$ENV_VARS,USE_NATIVE_OSWORLD=1"
ENV_VARS="$ENV_VARS,USE_FAKE_OSWORLD=0"
ENV_VARS="$ENV_VARS,OSWORLD_MAX_STEPS=15"
ENV_VARS="$ENV_VARS,HTTPS_ENABLED=true"

# VM Pool configuration (for snapshot-based VM reuse)
# Values come from .env or use defaults
VM_POOL_ENABLED="${VM_POOL_ENABLED:-false}"
VM_POOL_SIZE="${VM_POOL_SIZE:-1}"
VM_POOL_SNAPSHOT_NAME="${VM_POOL_SNAPSHOT_NAME:-osworld-golden-snapshot}"

ENV_VARS="$ENV_VARS,VM_POOL_ENABLED=$VM_POOL_ENABLED"
ENV_VARS="$ENV_VARS,VM_POOL_SIZE=$VM_POOL_SIZE"
ENV_VARS="$ENV_VARS,VM_POOL_SNAPSHOT_NAME=$VM_POOL_SNAPSHOT_NAME"

echo "VM Pool: enabled=$VM_POOL_ENABLED, size=$VM_POOL_SIZE, snapshot=$VM_POOL_SNAPSHOT_NAME"

# Add Supabase credentials (required for screenshot storage)
if [ -n "$SUPABASE_URL" ]; then
    ENV_VARS="$ENV_VARS,SUPABASE_URL=$SUPABASE_URL"
fi
if [ -n "$SUPABASE_SERVICE_KEY" ]; then
    ENV_VARS="$ENV_VARS,SUPABASE_SERVICE_KEY=$SUPABASE_SERVICE_KEY"
fi

gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE_TAG" \
    --region "$REGION" \
    --project="$PROJECT_ID" \
    --platform managed \
    --timeout 30m \
    --memory 4Gi \
    --cpu 2 \
    --max-instances 5 \
    --min-instances 0 \
    --allow-unauthenticated \
    --set-env-vars "$ENV_VARS"

echo "✓ Deployed to Cloud Run"
echo ""

# Step 4: Get service URL and update CLOUDRUN_HOST
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" \
    --project="$PROJECT_ID" \
    --format "value(status.url)")

# Extract hostname from URL (remove https://)
CLOUDRUN_HOST=$(echo "$SERVICE_URL" | sed 's|https://||')

echo "Step 4: Updating CLOUDRUN_HOST environment variable..."
echo "CLOUDRUN_HOST: $CLOUDRUN_HOST"

# Update the service with the actual CLOUDRUN_HOST
gcloud run services update "$SERVICE_NAME" \
    --region "$REGION" \
    --project="$PROJECT_ID" \
    --update-env-vars "CLOUDRUN_HOST=$CLOUDRUN_HOST"

echo "✓ CLOUDRUN_HOST set"
echo ""

echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""
echo "Service URL: $SERVICE_URL"
echo ""

# Test commands
echo "Test AgentBeats Controller Endpoints:"
echo ""
echo "1. Controller Status:"
echo "   curl $SERVICE_URL/status"
echo ""
echo "2. List Agents:"
echo "   curl $SERVICE_URL/agents"
echo ""
echo "3. Controller Info Page:"
echo "   curl $SERVICE_URL/info"
echo ""
echo "4. Agent Discovery (via proxy):"
echo "   # Get agent ID from /agents, then:"
echo "   curl $SERVICE_URL/to_agent/{AGENT_ID}/.well-known/agent-card.json"
echo ""
echo "5. Direct Agent Discovery (if controller proxies root):"
echo "   curl $SERVICE_URL/.well-known/agent-card.json"
echo ""
echo "========================================="
echo "AgentBeats Platform Registration"
echo "========================================="
echo ""
echo "Use this Controller URL for registration:"
echo "  $SERVICE_URL"
echo ""
echo "The platform will verify:"
echo "  - GET $SERVICE_URL/status"
echo "  - GET $SERVICE_URL/agents"
echo "  - GET $SERVICE_URL/.well-known/agent-card.json (via proxy)"
echo ""
echo "========================================="
