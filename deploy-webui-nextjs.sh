#!/bin/bash
# Deploy consolidated Next.js WebUI to Cloud Run with Supabase
# All backend logic is in Next.js API routes

set -e

echo "========================================"
echo "  Deploying Next.js WebUI to Cloud Run"
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
SERVICE_NAME="webui-nextjs"
IMAGE_NAME="us-central1-docker.pkg.dev/${PROJECT_ID}/green-agent/webui-nextjs:latest"

# Green Agent configuration (can be overridden in .env)
GREEN_AGENT_URL="${GREEN_AGENT_URL:-https://green-agent-750082808015.us-central1.run.app}"
GREEN_AGENT_API_KEY="${GREEN_AGENT_API_KEY:-c9d29a1d3b879cd6495d9eb6909cc6d72716b3c97b9bc345ccc0131ce41e18ce}"

# Use NEXT_PUBLIC_ prefixed variables if they exist (from webui-next/.env.local)
SUPABASE_URL="${SUPABASE_URL:-${NEXT_PUBLIC_SUPABASE_URL}}"
SUPABASE_ANON_KEY="${SUPABASE_ANON_KEY:-${NEXT_PUBLIC_SUPABASE_ANON_KEY}}"

# Supabase credentials check (REQUIRED)
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_KEY" ]; then
  echo ""
  echo "❌ ERROR: Supabase credentials not set!"
  echo ""
  echo "Please create a .env file with your Supabase credentials:"
  echo ""
  echo "  cp .env.example .env"
  echo "  # Then edit .env and fill in your credentials"
  echo ""
  echo "Or set environment variables manually:"
  echo "  export SUPABASE_URL=\"https://your-project.supabase.co\""
  echo "  export SUPABASE_SERVICE_KEY=\"your-service-key\""
  echo "  export SUPABASE_ANON_KEY=\"your-anon-key\""
  echo ""
  echo "You can get these from your Supabase project dashboard:"
  echo "  1. Go to https://supabase.com/dashboard"
  echo "  2. Select your project"
  echo "  3. Go to Settings > API"
  echo ""
  exit 1
fi

echo "Building Docker image..."
gcloud builds submit \
  --config cloudbuild-webui-nextjs.yaml \
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
  --set-env-vars "GREEN_AGENT_URL=${GREEN_AGENT_URL}" \
  --set-env-vars "GREEN_AGENT_API_KEY=${GREEN_AGENT_API_KEY}" \
  --set-env-vars "SUPABASE_URL=${SUPABASE_URL}" \
  --set-env-vars "SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}" \
  --set-env-vars "SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}" \
  --set-env-vars "NODE_ENV=production" \
  --set-env-vars "GCS_BUCKET_NAME=osworld-green-agent-artifacts" \
  --project $PROJECT_ID

echo ""
echo "========================================"
echo "  Deployment Complete!"
echo "========================================"

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)' --project $PROJECT_ID)
echo ""
echo "WebUI URL: $SERVICE_URL"
echo "Health:    $SERVICE_URL/api/health"
echo "Stats:     $SERVICE_URL/api/stats"
echo ""
