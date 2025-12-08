#!/bin/bash
#
# OSWorld Quota Configuration Script
#
# Displays current quotas and provides instructions for setting limits.
# Note: Quota changes require manual approval via GCP Console for decreases.
#
# Usage:
#   ./setup-quotas.sh [PROJECT_ID]
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID="${1:-$(gcloud config get-value project 2>/dev/null)}"
REGION="us-central1"
ZONE="${REGION}-a"

if [[ -z "$PROJECT_ID" ]]; then
    echo -e "${RED}Error: No project ID provided${NC}"
    exit 1
fi

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  OSWorld Quota Configuration${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "Project: ${GREEN}${PROJECT_ID}${NC}"
echo -e "Region:  ${GREEN}${REGION}${NC}"
echo ""

echo -e "${YELLOW}Current Compute Engine Quotas:${NC}"
echo ""

# Get current quotas
echo -e "${BLUE}CPUs (${REGION}):${NC}"
gcloud compute regions describe "$REGION" --project="$PROJECT_ID" \
    --format="table(quotas.filter(metric='CPUS'):format='table(metric,limit,usage)')" 2>/dev/null \
    || echo "  Unable to fetch CPU quota"

echo ""
echo -e "${BLUE}Instances (${REGION}):${NC}"
gcloud compute regions describe "$REGION" --project="$PROJECT_ID" \
    --format="table(quotas.filter(metric='INSTANCES'):format='table(metric,limit,usage)')" 2>/dev/null \
    || echo "  Unable to fetch instance quota"

echo ""
echo -e "${BLUE}Persistent Disk (${REGION}):${NC}"
gcloud compute regions describe "$REGION" --project="$PROJECT_ID" \
    --format="table(quotas.filter(metric='DISKS_TOTAL_GB'):format='table(metric,limit,usage)')" 2>/dev/null \
    || echo "  Unable to fetch disk quota"

echo ""
echo -e "${BLUE}External IP Addresses (${REGION}):${NC}"
gcloud compute regions describe "$REGION" --project="$PROJECT_ID" \
    --format="table(quotas.filter(metric='IN_USE_ADDRESSES'):format='table(metric,limit,usage)')" 2>/dev/null \
    || echo "  Unable to fetch IP quota"

echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${YELLOW}Recommended Quota Limits for OSWorld Dev:${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "  ${GREEN}CPUs:${NC}              16-32 (4 CPUs per VM × 4-8 VMs)"
echo -e "  ${GREEN}VM Instances:${NC}      4-8 concurrent"
echo -e "  ${GREEN}Persistent Disk:${NC}   200-400 GB (50 GB per VM)"
echo -e "  ${GREEN}External IPs:${NC}      4-8"
echo -e "  ${GREEN}SSD Disk:${NC}          200-400 GB (optional, for faster VMs)"
echo ""

echo -e "${BLUE}================================================${NC}"
echo -e "${YELLOW}To Request Quota Changes:${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "1. Go to GCP Console:"
echo -e "   ${GREEN}https://console.cloud.google.com/iam-admin/quotas?project=${PROJECT_ID}${NC}"
echo ""
echo -e "2. Filter by:"
echo -e "   - Service: ${GREEN}Compute Engine API${NC}"
echo -e "   - Region: ${GREEN}${REGION}${NC}"
echo ""
echo -e "3. Select quotas to modify and click ${GREEN}'Edit Quotas'${NC}"
echo ""
echo -e "4. For ${YELLOW}decreasing${NC} quotas (cost control):"
echo -e "   - Submit a quota decrease request"
echo -e "   - May require justification"
echo ""
echo -e "5. For ${YELLOW}increasing${NC} quotas:"
echo -e "   - Submit a quota increase request"
echo -e "   - Usually approved within 24-48 hours"
echo ""

echo -e "${BLUE}================================================${NC}"
echo -e "${YELLOW}Alternative: Use gcloud to request increases${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "# Request CPU quota increase to 32"
echo -e "${GREEN}gcloud compute regions describe ${REGION} --project=${PROJECT_ID}${NC}"
echo ""
echo -e "Note: Quota decreases must be done via Console."
echo ""
