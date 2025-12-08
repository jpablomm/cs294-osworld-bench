#!/bin/bash
#
# OSWorld Budget Alerts Setup Script
#
# Creates billing budget with alerts at 50%, 90%, and 100% thresholds.
# Optionally sets up email notifications.
#
# Prerequisites:
#   - Billing account linked to project
#   - Billing Admin or Budget Admin role
#
# Usage:
#   ./setup-budget-alerts.sh [PROJECT_ID] [MONTHLY_BUDGET_USD]
#
# Example:
#   ./setup-budget-alerts.sh my-project 100
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID="${1:-$(gcloud config get-value project 2>/dev/null)}"
MONTHLY_BUDGET="${2:-100}"  # Default $100/month
BUDGET_NAME="OSWorld Development Budget"

if [[ -z "$PROJECT_ID" ]]; then
    echo -e "${RED}Error: No project ID provided${NC}"
    echo "Usage: $0 <PROJECT_ID> [MONTHLY_BUDGET_USD]"
    exit 1
fi

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  OSWorld Budget Alerts Setup${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "Project:        ${GREEN}${PROJECT_ID}${NC}"
echo -e "Monthly Budget: ${GREEN}\$${MONTHLY_BUDGET} USD${NC}"
echo ""

# Get billing account
echo -e "${YELLOW}Step 1: Finding billing account...${NC}"
BILLING_ACCOUNT=$(gcloud billing projects describe "$PROJECT_ID" --format="value(billingAccountName)" 2>/dev/null | sed 's/billingAccounts\///')

if [[ -z "$BILLING_ACCOUNT" ]]; then
    echo -e "${RED}Error: No billing account found for project ${PROJECT_ID}${NC}"
    echo ""
    echo "To link a billing account:"
    echo "  gcloud billing projects link $PROJECT_ID --billing-account=ACCOUNT_ID"
    echo ""
    echo "To list available billing accounts:"
    echo "  gcloud billing accounts list"
    exit 1
fi

echo -e "  Billing Account: ${GREEN}${BILLING_ACCOUNT}${NC}"

# Check if gcloud beta is available (needed for budgets)
echo ""
echo -e "${YELLOW}Step 2: Checking gcloud beta components...${NC}"
if ! gcloud beta --help &>/dev/null; then
    echo -e "${YELLOW}Installing gcloud beta components...${NC}"
    gcloud components install beta --quiet
fi
echo -e "  ${GREEN}gcloud beta: OK${NC}"

# Create budget
echo ""
echo -e "${YELLOW}Step 3: Creating budget with alerts...${NC}"

# Check if budget already exists
EXISTING_BUDGET=$(gcloud beta billing budgets list \
    --billing-account="$BILLING_ACCOUNT" \
    --filter="displayName='${BUDGET_NAME}'" \
    --format="value(name)" 2>/dev/null || true)

if [[ -n "$EXISTING_BUDGET" ]]; then
    echo -e "  ${YELLOW}Budget already exists: ${EXISTING_BUDGET}${NC}"
    read -p "  Delete and recreate? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        gcloud beta billing budgets delete "$EXISTING_BUDGET" --quiet
        echo -e "  Deleted existing budget"
    else
        echo -e "  Keeping existing budget"
        SKIP_CREATE=true
    fi
fi

if [[ -z "$SKIP_CREATE" ]]; then
    # Create the budget with threshold alerts
    gcloud beta billing budgets create \
        --billing-account="$BILLING_ACCOUNT" \
        --display-name="$BUDGET_NAME" \
        --budget-amount="${MONTHLY_BUDGET}USD" \
        --threshold-rule=percent=0.5,basis=current-spend \
        --threshold-rule=percent=0.9,basis=current-spend \
        --threshold-rule=percent=1.0,basis=current-spend \
        --filter-projects="projects/$PROJECT_ID" \
        --all-updates-rule \
        --quiet

    echo -e "  ${GREEN}Budget created successfully${NC}"
fi

echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}  Budget Alerts Configured!${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "Alerts will trigger at:"
echo -e "  - ${YELLOW}50%${NC}  (\$$(echo "$MONTHLY_BUDGET * 0.5" | bc) spent)"
echo -e "  - ${YELLOW}90%${NC}  (\$$(echo "$MONTHLY_BUDGET * 0.9" | bc) spent)"
echo -e "  - ${YELLOW}100%${NC} (\$${MONTHLY_BUDGET} spent)"
echo ""

echo -e "${BLUE}================================================${NC}"
echo -e "${YELLOW}Optional: Set Up Email Notifications${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "To receive email alerts, configure notification channels:"
echo ""
echo -e "1. Go to GCP Console Budgets:"
echo -e "   ${GREEN}https://console.cloud.google.com/billing/budgets?project=${PROJECT_ID}${NC}"
echo ""
echo -e "2. Click on '${BUDGET_NAME}'"
echo ""
echo -e "3. Under 'Manage notifications', add:"
echo -e "   - Email recipients"
echo -e "   - Pub/Sub topic (for programmatic alerts)"
echo -e "   - Cloud Monitoring notification channels"
echo ""

echo -e "${BLUE}================================================${NC}"
echo -e "${YELLOW}Optional: Auto-Shutdown on Budget Exceeded${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "To automatically stop VMs when budget is exceeded:"
echo ""
echo -e "1. Create a Pub/Sub topic for budget alerts"
echo -e "2. Create a Cloud Function triggered by the topic"
echo -e "3. Function stops all osworld-* VMs"
echo ""
echo -e "Example Cloud Function code is in:"
echo -e "  ${GREEN}scripts/gcp/budget-shutdown-function/${NC}"
echo ""
