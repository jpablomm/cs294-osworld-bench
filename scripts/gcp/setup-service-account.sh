#!/bin/bash
#
# OSWorld Service Account Setup Script
#
# Creates a restricted service account for local development with:
# - Minimal IAM roles (VM management, storage upload)
# - Resource conditions (only osworld-* VMs)
# - JSON key file for authentication
#
# Usage:
#   ./setup-service-account.sh [PROJECT_ID] [SA_NAME]
#
# Example:
#   ./setup-service-account.sh my-gcp-project osworld-dev
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${1:-$(gcloud config get-value project 2>/dev/null)}"
SA_NAME="${2:-osworld-dev}"
SA_DISPLAY_NAME="OSWorld Development (Restricted)"
KEY_FILE="osworld-service-account-key.json"
ZONE="us-central1-a"
BUCKET_NAME="osworld-green-agent-artifacts"

# Validate inputs
if [[ -z "$PROJECT_ID" ]]; then
    echo -e "${RED}Error: No project ID provided and none set in gcloud config${NC}"
    echo "Usage: $0 <PROJECT_ID> [SA_NAME]"
    exit 1
fi

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  OSWorld Service Account Setup${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "Project ID:      ${GREEN}${PROJECT_ID}${NC}"
echo -e "Service Account: ${GREEN}${SA_NAME}${NC}"
echo -e "Email:           ${GREEN}${SA_EMAIL}${NC}"
echo -e "Key File:        ${GREEN}${KEY_FILE}${NC}"
echo ""

# Confirm
read -p "Continue with setup? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo -e "${YELLOW}Step 1: Creating service account...${NC}"

# Check if service account already exists
if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
    echo -e "  Service account already exists, skipping creation"
else
    gcloud iam service-accounts create "$SA_NAME" \
        --project="$PROJECT_ID" \
        --display-name="$SA_DISPLAY_NAME" \
        --description="Restricted service account for OSWorld local development"
    echo -e "  ${GREEN}Created service account${NC}"
fi

echo ""
echo -e "${YELLOW}Step 2: Granting IAM roles with conditions...${NC}"

# Role 1: Compute Instance Admin (with condition for osworld-* VMs only)
echo -e "  Granting compute.instanceAdmin.v1 (restricted to osworld-* VMs)..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/compute.instanceAdmin.v1" \
    --condition="expression=resource.name.startsWith('projects/${PROJECT_ID}/zones/${ZONE}/instances/osworld-'),title=OSWorld VMs only,description=Only allow management of VMs with osworld- prefix" \
    --quiet 2>/dev/null || echo -e "    ${YELLOW}(Role may already be bound)${NC}"

# Role 2: Compute Image User (to create VMs from golden images)
echo -e "  Granting compute.imageUser..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/compute.imageUser" \
    --quiet 2>/dev/null || echo -e "    ${YELLOW}(Role may already be bound)${NC}"

# Role 3: Service Account User (to attach service accounts to VMs)
echo -e "  Granting iam.serviceAccountUser..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/iam.serviceAccountUser" \
    --quiet 2>/dev/null || echo -e "    ${YELLOW}(Role may already be bound)${NC}"

# Role 4: Storage Object Creator (upload only - no delete)
echo -e "  Granting storage.objectCreator on bucket ${BUCKET_NAME}..."
# First check if bucket exists
if gsutil ls -b "gs://${BUCKET_NAME}" &>/dev/null; then
    gsutil iam ch "serviceAccount:${SA_EMAIL}:roles/storage.objectCreator" "gs://${BUCKET_NAME}" 2>/dev/null \
        || echo -e "    ${YELLOW}(Role may already be bound or bucket permissions issue)${NC}"
else
    echo -e "    ${YELLOW}Bucket ${BUCKET_NAME} not found, skipping storage role${NC}"
    echo -e "    ${YELLOW}Create bucket first or update BUCKET_NAME in this script${NC}"
fi

# Role 5: Viewer (for project info auto-detection)
echo -e "  Granting browser role (minimal read access)..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/browser" \
    --quiet 2>/dev/null || echo -e "    ${YELLOW}(Role may already be bound)${NC}"

echo -e "  ${GREEN}IAM roles configured${NC}"

echo ""
echo -e "${YELLOW}Step 3: Creating service account key...${NC}"

# Check if key file already exists
if [[ -f "$KEY_FILE" ]]; then
    echo -e "  ${YELLOW}Key file already exists: ${KEY_FILE}${NC}"
    read -p "  Overwrite existing key? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "  Keeping existing key"
    else
        rm "$KEY_FILE"
        gcloud iam service-accounts keys create "$KEY_FILE" \
            --iam-account="$SA_EMAIL" \
            --project="$PROJECT_ID"
        echo -e "  ${GREEN}Created new key file${NC}"
    fi
else
    gcloud iam service-accounts keys create "$KEY_FILE" \
        --iam-account="$SA_EMAIL" \
        --project="$PROJECT_ID"
    echo -e "  ${GREEN}Created key file: ${KEY_FILE}${NC}"
fi

# Secure the key file
chmod 600 "$KEY_FILE"

echo ""
echo -e "${YELLOW}Step 4: Verifying setup...${NC}"

# Verify service account
echo -e "  Checking service account..."
gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" --format="value(email)" &>/dev/null \
    && echo -e "    ${GREEN}Service account: OK${NC}" \
    || echo -e "    ${RED}Service account: FAILED${NC}"

# Verify key file
echo -e "  Checking key file..."
if [[ -f "$KEY_FILE" ]] && jq -e '.type == "service_account"' "$KEY_FILE" &>/dev/null; then
    echo -e "    ${GREEN}Key file: OK${NC}"
else
    echo -e "    ${RED}Key file: FAILED${NC}"
fi

echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "To use this service account, add to your ${GREEN}.env${NC} file:"
echo ""
echo -e "  ${YELLOW}GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/${KEY_FILE}${NC}"
echo -e "  ${YELLOW}GOOGLE_CLOUD_PROJECT=${PROJECT_ID}${NC}"
echo ""
echo -e "Or export in your shell:"
echo ""
echo -e "  ${YELLOW}export GOOGLE_APPLICATION_CREDENTIALS=\"$(pwd)/${KEY_FILE}\"${NC}"
echo -e "  ${YELLOW}export GOOGLE_CLOUD_PROJECT=\"${PROJECT_ID}\"${NC}"
echo ""
echo -e "${RED}IMPORTANT:${NC}"
echo -e "  - Keep ${KEY_FILE} secure and never commit to git"
echo -e "  - Add ${KEY_FILE} to .gitignore"
echo -e "  - Rotate keys periodically (recommended: 90 days)"
echo ""

# Add to .gitignore if not already there
GITIGNORE_FILE="$(git rev-parse --show-toplevel 2>/dev/null)/.gitignore"
if [[ -f "$GITIGNORE_FILE" ]]; then
    if ! grep -q "$KEY_FILE" "$GITIGNORE_FILE"; then
        echo "$KEY_FILE" >> "$GITIGNORE_FILE"
        echo -e "${GREEN}Added ${KEY_FILE} to .gitignore${NC}"
    fi
fi
