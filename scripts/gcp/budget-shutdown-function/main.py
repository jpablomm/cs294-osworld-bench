"""
Budget Alert Cloud Function - Auto-Shutdown OSWorld VMs

This Cloud Function is triggered by Pub/Sub when a budget alert fires.
It stops all running osworld-* VMs to prevent cost overruns.

Deployment:
    gcloud functions deploy budget-shutdown \
        --runtime python311 \
        --trigger-topic budget-alerts \
        --entry-point stop_osworld_vms \
        --set-env-vars GCP_PROJECT=your-project,GCP_ZONE=us-central1-a

Setup:
    1. Create Pub/Sub topic: budget-alerts
    2. Link topic to budget in Cloud Billing
    3. Deploy this function
"""

import base64
import json
import logging
import os
from google.cloud import compute_v1

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment
PROJECT_ID = os.environ.get("GCP_PROJECT")
ZONE = os.environ.get("GCP_ZONE", "us-central1-a")
VM_PREFIX = "osworld-"


def stop_osworld_vms(event, context):
    """
    Cloud Function entry point - stops all osworld-* VMs.

    Args:
        event: Pub/Sub event data
        context: Cloud Function context
    """
    # Parse the Pub/Sub message
    if "data" in event:
        message = base64.b64decode(event["data"]).decode("utf-8")
        logger.info(f"Received budget alert: {message}")

        try:
            alert_data = json.loads(message)
            budget_name = alert_data.get("budgetDisplayName", "Unknown")
            cost_amount = alert_data.get("costAmount", 0)
            budget_amount = alert_data.get("budgetAmount", 0)
            threshold = alert_data.get("alertThresholdExceeded", 0)

            logger.info(f"Budget: {budget_name}")
            logger.info(f"Cost: ${cost_amount} / ${budget_amount} ({threshold*100}% threshold)")
        except json.JSONDecodeError:
            logger.warning("Could not parse alert message as JSON")

    if not PROJECT_ID:
        logger.error("GCP_PROJECT environment variable not set")
        return "Error: GCP_PROJECT not set", 500

    # Initialize Compute Engine client
    instances_client = compute_v1.InstancesClient()

    # List all instances in the zone
    logger.info(f"Listing instances in {PROJECT_ID}/{ZONE}...")

    try:
        instances = instances_client.list(project=PROJECT_ID, zone=ZONE)
    except Exception as e:
        logger.error(f"Failed to list instances: {e}")
        return f"Error listing instances: {e}", 500

    stopped_count = 0
    error_count = 0

    for instance in instances:
        # Only stop osworld-* VMs
        if not instance.name.startswith(VM_PREFIX):
            continue

        # Only stop running instances
        if instance.status != "RUNNING":
            logger.info(f"Skipping {instance.name} (status: {instance.status})")
            continue

        logger.info(f"Stopping VM: {instance.name}")

        try:
            operation = instances_client.stop(
                project=PROJECT_ID,
                zone=ZONE,
                instance=instance.name
            )
            logger.info(f"Stop operation initiated: {operation.name}")
            stopped_count += 1
        except Exception as e:
            logger.error(f"Failed to stop {instance.name}: {e}")
            error_count += 1

    result = f"Stopped {stopped_count} VMs, {error_count} errors"
    logger.info(result)

    return result, 200


def delete_osworld_vms(event, context):
    """
    Alternative entry point - deletes all osworld-* VMs.
    Use this for more aggressive cost control.
    """
    if not PROJECT_ID:
        logger.error("GCP_PROJECT environment variable not set")
        return "Error: GCP_PROJECT not set", 500

    instances_client = compute_v1.InstancesClient()

    try:
        instances = instances_client.list(project=PROJECT_ID, zone=ZONE)
    except Exception as e:
        logger.error(f"Failed to list instances: {e}")
        return f"Error: {e}", 500

    deleted_count = 0

    for instance in instances:
        if not instance.name.startswith(VM_PREFIX):
            continue

        logger.info(f"Deleting VM: {instance.name}")

        try:
            instances_client.delete(
                project=PROJECT_ID,
                zone=ZONE,
                instance=instance.name
            )
            deleted_count += 1
        except Exception as e:
            logger.error(f"Failed to delete {instance.name}: {e}")

    return f"Deleted {deleted_count} VMs", 200
