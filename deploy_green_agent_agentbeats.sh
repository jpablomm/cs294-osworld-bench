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

# Parse arguments
PROJECT_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --project)
            PROJECT_ID="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: bash deploy_green_agent_agentbeats.sh [--project PROJECT_ID]"
            exit 1
            ;;
    esac
done

# If no project specified, use gcloud config
if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID=$(gcloud config get-value project)
fi

# Configuration
REGION="us-central1"
SERVICE_NAME="green-agent-agentbeats"  # Different from production!
IMAGE_TAG="$REGION-docker.pkg.dev/$PROJECT_ID/$SERVICE_NAME/$SERVICE_NAME"

# Check if project is set
if [ -z "$PROJECT_ID" ]; then
    echo "Error: GCP project not set. Specify with --project or run: gcloud config set project PROJECT_ID"
    exit 1
fi

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
    args: ['build', '-t', '$IMAGE_TAG', '-f', 'Dockerfile.green-agent-agentbeats', '.']

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

# Build environment variables
ENV_VARS="GCP_PROJECT=$PROJECT_ID"
ENV_VARS="$ENV_VARS,USE_NATIVE_OSWORLD=1"
ENV_VARS="$ENV_VARS,USE_FAKE_OSWORLD=0"
ENV_VARS="$ENV_VARS,OSWORLD_MAX_STEPS=15"

# Load Supabase credentials from .env file if available
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

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

# Step 4: Get service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" \
    --project="$PROJECT_ID" \
    --format "value(status.url)")

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
