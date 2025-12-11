#!/bin/bash
#
# Deploy White Agent with AgentBeats Controller to Google Cloud Run
# This is a SEPARATE deployment from the production white-agent instance
#
# Service Name: white-agent-agentbeats (keeps production untouched)
# Uses: AgentBeats controller (earthshaker) via Procfile
# Purpose: Testing and AgentBeats platform registration
#
# Usage:
#   bash deploy_white_agent_agentbeats.sh [--project PROJECT_ID]
#

set -e

echo "========================================="
echo "White Agent AgentBeats Controller Deploy"
echo "========================================="
echo ""
echo "  This creates a SEPARATE Cloud Run service"
echo "   Production 'white-agent' remains untouched"
echo ""

# Configuration - hardcoded project
PROJECT_ID="cs294-475401"
REGION="us-central1"
SERVICE_NAME="white-agent-agentbeats"
IMAGE_TAG="$REGION-docker.pkg.dev/$PROJECT_ID/$SERVICE_NAME/$SERVICE_NAME"

# Load environment variables from .env file if available
if [ -f ".env" ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Check for required OpenAI API key
if [ -z "$OPENAI_API_KEY" ]; then
    echo ""
    echo "ERROR: OPENAI_API_KEY not set!"
    echo ""
    echo "The white agent requires an OpenAI API key for GPT models."
    echo ""
    echo "Please create a .env file with:"
    echo "  OPENAI_API_KEY=sk-your-openai-api-key-here"
    echo ""
    exit 1
fi

# Optional: Anthropic API key for Claude models
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  WARNING: ANTHROPIC_API_KEY not set. Claude models will not work."
fi

# Optional: Tavily API key for web search
if [ -z "$TAVILY_API_KEY" ]; then
    echo "⚠️  WARNING: TAVILY_API_KEY not set. Web search will be disabled."
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
        --description="White Agent with AgentBeats controller" 2>&1 | grep -v "ALREADY_EXISTS" || true
fi
echo "Artifact Registry ready"
echo ""

# Step 2: Build container image using Docker
echo "Step 2: Building container image..."
echo "Building $IMAGE_TAG"

# Create a temporary cloudbuild.yaml
cat > /tmp/cloudbuild-white-agent-agentbeats.yaml << EOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '$IMAGE_TAG', '-f', 'deploy/docker/Dockerfile.white-agent-agentbeats', '.']

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
    --config /tmp/cloudbuild-white-agent-agentbeats.yaml \
    --project=$PROJECT_ID \
    --timeout=20m

rm /tmp/cloudbuild-white-agent-agentbeats.yaml

echo "Container image built successfully"
echo ""

# Step 3: Deploy to Cloud Run
echo "Step 3: Deploying to Cloud Run..."

# Build environment variables
ENV_VARS="OPENAI_API_KEY=$OPENAI_API_KEY"
ENV_VARS="$ENV_VARS,GPT4V_MODEL=${GPT4V_MODEL:-gpt-5.1}"
ENV_VARS="$ENV_VARS,GPT4V_TEMPERATURE=${GPT4V_TEMPERATURE:-1.0}"
ENV_VARS="$ENV_VARS,HTTPS_ENABLED=true"

# Add optional API keys if set
if [ -n "$ANTHROPIC_API_KEY" ]; then
    ENV_VARS="$ENV_VARS,ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"
fi

if [ -n "$TAVILY_API_KEY" ]; then
    ENV_VARS="$ENV_VARS,TAVILY_API_KEY=$TAVILY_API_KEY"
fi

gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE_TAG" \
    --region "$REGION" \
    --project="$PROJECT_ID" \
    --platform managed \
    --timeout 10m \
    --memory 2Gi \
    --cpu 2 \
    --max-instances 10 \
    --min-instances 0 \
    --allow-unauthenticated \
    --set-env-vars "$ENV_VARS"

echo "Deployed to Cloud Run"
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

echo "CLOUDRUN_HOST set"
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
echo "========================================="
echo "AgentBeats Platform Registration"
echo "========================================="
echo ""
echo "Use this Controller URL for registration:"
echo "  $SERVICE_URL"
echo ""
echo "========================================="
