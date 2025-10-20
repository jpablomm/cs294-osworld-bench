#!/bin/bash
#
# Deploy OSWorld VM Orchestrator to Google Cloud Run
#
# Usage:
#   bash deploy_orchestrator.sh
#

set -e

echo "========================================="
echo "OSWorld VM Orchestrator Deployment"
echo "========================================="
echo ""

# Configuration
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
SERVICE_NAME="osworld-orchestrator"
ARTIFACT_REGISTRY_LOCATION="us-central1"
ARTIFACT_REGISTRY_REPO="osworld-orchestrator"
IMAGE_NAME="$ARTIFACT_REGISTRY_LOCATION-docker.pkg.dev/$PROJECT_ID/$ARTIFACT_REGISTRY_REPO/$SERVICE_NAME"

# Check if project is set
if [ -z "$PROJECT_ID" ]; then
    echo "Error: GCP project not set. Run: gcloud config set project PROJECT_ID"
    exit 1
fi

echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Service Name: $SERVICE_NAME"
echo ""

# Step 1: Build container image
echo "Step 1: Building container image..."
echo "Building $IMAGE_NAME"

# Create temporary cloudbuild.yaml for custom Dockerfile
cat > /tmp/cloudbuild.yaml << EOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '$IMAGE_NAME', '-f', 'Dockerfile.orchestrator', '.']
images: ['$IMAGE_NAME']
EOF

gcloud builds submit \
    --config /tmp/cloudbuild.yaml \
    --timeout=20m

rm /tmp/cloudbuild.yaml

echo "✓ Container image built successfully"
echo ""

# Step 2: Deploy to Cloud Run
echo "Step 2: Deploying to Cloud Run..."

gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE_NAME" \
    --region "$REGION" \
    --platform managed \
    --timeout 15m \
    --memory 2Gi \
    --cpu 2 \
    --max-instances 10 \
    --min-instances 0 \
    --allow-unauthenticated \
    --set-env-vars "USE_GCS=false"

echo "✓ Deployed to Cloud Run"
echo ""

# Step 3: Get service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" \
    --format "value(status.url)")

echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""
echo "Service URL: $SERVICE_URL"
echo ""
echo "Test the service:"
echo "  curl $SERVICE_URL/health"
echo ""
echo "Submit a task:"
echo "  curl -X POST $SERVICE_URL/tasks \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"task_id\":\"osworld-ubuntu-tiny\", \"white_agent_url\":\"http://your-white-agent.run.app\"}'"
echo ""
echo "========================================="
