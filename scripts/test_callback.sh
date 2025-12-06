#!/bin/bash

# Test script to verify event callbacks are working

WEBUI_URL="${1:-http://localhost:3000}"
ASSESSMENT_ID="${2:-test_assessment_123}"

echo "Testing event callback to WebUI..."
echo "WebUI URL: $WEBUI_URL"
echo "Assessment ID: $ASSESSMENT_ID"
echo ""

# Test 1: Send a simple event
echo "Test 1: Sending vm_created event..."
curl -X POST "$WEBUI_URL/api/internal/events/$ASSESSMENT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "vm_created",
    "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'",
    "vm_name": "test-vm",
    "vm_ip": "10.0.0.1"
  }' \
  -w "\nHTTP Status: %{http_code}\n\n"

# Test 2: Check if event was saved
echo "Test 2: Checking agent-state..."
curl -X GET "$WEBUI_URL/api/assessments/$ASSESSMENT_ID/agent-state" \
  -H "Content-Type: application/json" \
  -w "\nHTTP Status: %{http_code}\n\n" | jq '.'

echo "Done!"
