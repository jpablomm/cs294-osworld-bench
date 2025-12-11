#!/bin/bash
#
# Deploy Green Agent with AgentBeats Integration to Google Cloud Run
#
# This script deploys the A2A-compliant green agent with:
# - AgentBeats discovery endpoints
# - Environment variable support
# - Optional API key authentication
#
# Usage:
#   bash deploy_green_agent.sh [--project PROJECT_ID] [--with-api-key]
#

set -e

echo "========================================="
echo "Green Agent AgentBeats Deployment"
echo "========================================="
echo ""

# Configuration
PROJECT_ID="cs294-475401"
WITH_API_KEY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --with-api-key)
            WITH_API_KEY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: bash deploy_green_agent.sh [--with-api-key]"
            exit 1
            ;;
    esac
done

REGION="us-central1"
SERVICE_NAME="green-agent"
IMAGE_TAG="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Service Name: $SERVICE_NAME"
echo ""

# Use API key from .env or existing production key
API_KEY=""
if [[ "$WITH_API_KEY" == true ]]; then
    # Check if API key exists in .env first
    if [ -f ".env" ]; then
        source .env 2>/dev/null
    fi

    if [ -n "$GREEN_AGENT_API_KEY" ]; then
        echo "Using existing API key from .env"
        API_KEY="$GREEN_AGENT_API_KEY"
    else
        echo "Generating new secure API key..."
        API_KEY=$(openssl rand -hex 32)
        echo "New API Key: $API_KEY"
        echo "(Save this and update frontend config)"
    fi
    echo ""
fi

# Step 1: Create Artifact Registry repository if it doesn't exist
echo "Step 1: Checking Artifact Registry..."
if ! gcloud artifacts repositories describe $SERVICE_NAME --location=$REGION --project=$PROJECT_ID &>/dev/null; then
    echo "Creating Artifact Registry repository..."
    gcloud artifacts repositories create $SERVICE_NAME \
        --repository-format=docker \
        --location=$REGION \
        --project=$PROJECT_ID \
        --description="Green Agent with AgentBeats integration" 2>&1 | grep -v "ALREADY_EXISTS" || true
fi
echo "✓ Artifact Registry ready"
echo ""

# Update image tag to use Artifact Registry
IMAGE_TAG="$REGION-docker.pkg.dev/$PROJECT_ID/$SERVICE_NAME/$SERVICE_NAME"

# Step 2: Build container image using Docker
echo "Step 2: Building container image..."
echo "Building $IMAGE_TAG"

# Create a temporary cloudbuild.yaml
cat > /tmp/cloudbuild-green-agent.yaml << EOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '$IMAGE_TAG', '-f', 'deploy/docker/Dockerfile.green-agent', '.']

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
    --config /tmp/cloudbuild-green-agent.yaml \
    --project=$PROJECT_ID \
    --timeout=20m

rm /tmp/cloudbuild-green-agent.yaml

echo "✓ Container image built successfully"
echo ""

# Step 3: Deploy to Cloud Run
echo "Step 3: Deploying to Cloud Run..."

# Build environment variables
ENV_VARS="GCP_PROJECT=$PROJECT_ID"
ENV_VARS="$ENV_VARS,USE_NATIVE_OSWORLD=1"
ENV_VARS="$ENV_VARS,USE_FAKE_OSWORLD=0"
ENV_VARS="$ENV_VARS,OSWORLD_MAX_STEPS=15"

# Add API key if generated
if [ -n "$API_KEY" ]; then
    ENV_VARS="$ENV_VARS,GREEN_AGENT_API_KEY=$API_KEY"
fi

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
    --max-instances 10 \
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
echo "Test endpoints:"
echo ""
echo "1. Health check:"
echo "   curl $SERVICE_URL/health"
echo ""
echo "2. Agent card (A2A):"
echo "   curl $SERVICE_URL/agent-card"
echo ""
echo "3. AgentBeats discovery:"
echo "   curl $SERVICE_URL/.well-known/agent-card.json"
echo ""

if [ -n "$API_KEY" ]; then
    echo "4. Submit assessment (with API key):"
    echo "   curl -X POST $SERVICE_URL/task \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -H 'X-API-Key: $API_KEY' \\"
    echo "     -d '{"
    echo "       \"task_id\": \"test-123\","
    echo "       \"message\": \"Run OSWorld assessment\","
    echo "       \"metadata\": {"
    echo "         \"osworld_task_id\": \"osworld-ubuntu-tiny\","
    echo "         \"white_agent_url\": \"http://your-white-agent.run.app\","
    echo "         \"max_steps\": 5"
    echo "       }"
    echo "     }'"
    echo ""
    echo "⚠️  IMPORTANT: Save your API key!"
    echo "   API Key: $API_KEY"
    echo ""
else
    echo "4. Submit assessment (no API key):"
    echo "   curl -X POST $SERVICE_URL/task \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{"
    echo "       \"task_id\": \"test-123\","
    echo "       \"message\": \"Run OSWorld assessment\","
    echo "       \"metadata\": {"
    echo "         \"osworld_task_id\": \"osworld-ubuntu-tiny\","
    echo "         \"white_agent_url\": \"http://your-white-agent.run.app\","
    echo "         \"max_steps\": 5"
    echo "       }"
    echo "     }'"
    echo ""
    echo "⚠️  Note: No API key protection enabled."
    echo "   To enable security, redeploy with: bash deploy_green_agent.sh --project $PROJECT_ID --with-api-key"
fi

echo ""
echo "AgentBeats Platform Registration:"
echo "  Use this URL: $SERVICE_URL"
echo ""
echo "========================================="
