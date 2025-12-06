#!/bin/bash
# Deploy GPT-4V White Agent to Cloud Run
# This agent uses OpenAI's GPT-4V API for vision-language reasoning

set -e

echo "========================================"
echo "  Deploying GPT-4V White Agent"
echo "========================================"

# Load environment variables from .env file if it exists
if [ -f .env ]; then
  echo "Loading environment variables from .env file..."
  set -a
  source .env
  set +a
else
  echo "No .env file found. Looking for environment variables..."
fi

# Configuration
PROJECT_ID="cs294-475401"
REGION="us-central1"
SERVICE_NAME="white-agent"
IMAGE_NAME="us-central1-docker.pkg.dev/${PROJECT_ID}/green-agent/white-agent:latest"

# Check for required credentials
if [ -z "$OPENAI_API_KEY" ]; then
  echo ""
  echo "❌ ERROR: OPENAI_API_KEY not set!"
  echo ""
  echo "The white agent requires an OpenAI API key for GPT-4V access."
  echo ""
  echo "Please create a .env file with:"
  echo "  OPENAI_API_KEY=sk-your-openai-api-key-here"
  echo ""
  echo "Or set the environment variable manually:"
  echo "  export OPENAI_API_KEY=\"sk-your-key\""
  echo ""
  echo "Get your API key from: https://platform.openai.com/api-keys"
  echo ""
  exit 1
fi

echo "Building Docker image..."
gcloud builds submit \
  --config deploy/cloudbuild/white-agent.yaml \
  --project $PROJECT_ID

echo ""
echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --set-env-vars "OPENAI_API_KEY=${OPENAI_API_KEY}" \
  --set-env-vars "GPT4V_MODEL=${GPT4V_MODEL:-gpt-4o}" \
  --set-env-vars "GPT4V_TEMPERATURE=${GPT4V_TEMPERATURE:-1.0}" \
  --set-env-vars "NODE_ENV=production" \
  --project $PROJECT_ID

echo ""
echo "========================================"
echo "  Deployment Complete!"
echo "========================================"

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)' --project $PROJECT_ID)
echo ""
echo "White Agent URL:   $SERVICE_URL"
echo "Health:            $SERVICE_URL/health"
echo "Agent Card:        $SERVICE_URL/agent-card"
echo "A2A Task Endpoint: $SERVICE_URL/task"
echo ""
echo "Test the agent:"
echo "  curl $SERVICE_URL/health"
echo "  curl $SERVICE_URL/agent-card"
echo ""
