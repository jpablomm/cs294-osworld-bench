#!/usr/bin/env python3
"""
Test Chrome Task Directly on VM

Tests a Chrome domain task on a VM to verify:
1. OSWorld server connectivity
2. Chrome setup (socat, CDP connection)
3. White agent task execution
"""

import sys
import time
import json
import logging
import argparse
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from green_agent.white_client import WhiteClient
from green_agent.osworld_adapter import run_osworld
from orchestrator.task_executor import TaskExecutor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_chrome_task(vm_ip: str, white_agent_url: str, task_id: str = None):
    """
    Test Chrome task on VM

    Args:
        vm_ip: VM external IP
        white_agent_url: White agent URL
        task_id: Optional specific Chrome task ID. If None, uses a simple one.
    """

    # Default to a simple Chrome task if not specified
    if task_id is None:
        task_id = "b070486d-e161-459b-aa2b-ef442d973b92"  # Simple Chrome navigation task

    logger.info(f"Testing Chrome task {task_id} on VM {vm_ip}")

    # Wait for OSWorld server
    import requests
    logger.info("Waiting for OSWorld server to be ready...")
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"http://{vm_ip}:5000/platform", timeout=5)
            if response.status_code == 200:
                logger.info(f"✓ OSWorld server ready: {response.json()}")
                break
        except Exception as e:
            logger.debug(f"Attempt {i+1}/{max_retries}: {e}")
            time.sleep(2)
    else:
        logger.error("OSWorld server did not become ready")
        return False

    # Load Chrome task
    task_executor = TaskExecutor()
    try:
        osworld_task = task_executor.load_osworld_task(task_id, domain="chrome")
        logger.info(f"Loaded task: {osworld_task.get('instruction', 'No instruction')}")
    except FileNotFoundError:
        logger.error(f"Chrome task {task_id} not found")
        return False

    # Check if task has setup config
    if "config" not in osworld_task or not osworld_task["config"]:
        logger.error("Task does not have config/setup steps")
        return False

    logger.info(f"Task has {len(osworld_task['config'])} setup steps")

    # Test setup steps manually
    logger.info("\n" + "="*60)
    logger.info("TESTING SETUP STEPS")
    logger.info("="*60)

    setup_results = []
    for i, step in enumerate(osworld_task["config"], 1):
        logger.info(f"\nStep {i}/{len(osworld_task['config'])}: {step}")

        # Execute setup via OSWorld server
        try:
            if step.get("type") == "execute":
                # Execute command
                response = requests.post(
                    f"http://{vm_ip}:5000/execute",
                    json={"command": step.get("parameters", {}).get("command", [])},
                    timeout=30
                )
                logger.info(f"Execute response: {response.status_code} - {response.text[:200]}")
                setup_results.append({
                    "step": i,
                    "type": step.get("type"),
                    "success": response.status_code == 200,
                    "response": response.text
                })
            elif step.get("type") in ["_launch_setup", "_chrome_open_tabs_setup", "_setup"]:
                # Use OSWorld's setup endpoint
                setup_type = step.get("type")
                response = requests.post(
                    f"http://{vm_ip}:5000/setup/{setup_type.replace('_', '')}",
                    json=step.get("parameters", {}),
                    timeout=30
                )
                logger.info(f"Setup response: {response.status_code} - {response.text[:200]}")
                setup_results.append({
                    "step": i,
                    "type": step.get("type"),
                    "success": response.status_code == 200,
                    "response": response.text
                })
            else:
                logger.warning(f"Unknown step type: {step.get('type')}")
                setup_results.append({
                    "step": i,
                    "type": step.get("type"),
                    "success": False,
                    "response": "Unknown type"
                })
        except Exception as e:
            logger.error(f"Step {i} failed: {e}")
            setup_results.append({
                "step": i,
                "type": step.get("type"),
                "success": False,
                "response": str(e)
            })

    # Report setup results
    logger.info("\n" + "="*60)
    logger.info("SETUP RESULTS")
    logger.info("="*60)

    for result in setup_results:
        status = "✓" if result["success"] else "✗"
        logger.info(f"{status} Step {result['step']} ({result['type']}): {result['response'][:100]}")

    setup_success = all(r["success"] for r in setup_results)

    if not setup_success:
        logger.error("Setup failed! Cannot proceed with task execution")

        # Specific check for socat
        socat_steps = [r for r in setup_results if "socat" in str(r.get("response", "")).lower()]
        if socat_steps:
            logger.error("\n⚠️  SOCAT ISSUE DETECTED:")
            for step in socat_steps:
                logger.error(f"   {step['response']}")
            logger.error("\n   Solution: Install socat on the VM:")
            logger.error(f"   gcloud compute ssh osworld-test-chrome --zone=us-central1-a --command='sudo apt-get update && sudo apt-get install -y socat'")

        return False

    logger.info("\n✓ All setup steps completed successfully!")

    # Now test Chrome CDP connection
    logger.info("\n" + "="*60)
    logger.info("TESTING CHROME CDP CONNECTION")
    logger.info("="*60)

    try:
        # Try to connect to Chrome via CDP on port 9222
        response = requests.get(f"http://{vm_ip}:9222/json/version", timeout=5)
        logger.info(f"✓ Chrome CDP accessible: {response.json()}")
    except Exception as e:
        logger.error(f"✗ Chrome CDP not accessible on port 9222: {e}")
        logger.error("   This could be a firewall issue. Port 9222 needs to be open.")
        logger.error("   Current firewall rules only allow ports 5000 and 5910")
        return False

    # If we got here, everything is working!
    logger.info("\n" + "="*60)
    logger.info("✓ ALL CHECKS PASSED! Chrome setup is working correctly.")
    logger.info("="*60)

    # Now try to run the actual task
    logger.info("\nRunning full task execution with white agent...")

    # Initialize white agent
    white = WhiteClient(white_agent_url)
    try:
        white.reset()
        logger.info("White agent reset")
    except Exception as e:
        logger.error(f"White agent error: {e}")
        return False

    # Create minimal task config
    task = {
        "instruction": osworld_task.get("instruction", "Navigate in Chrome"),
        "max_steps": 15
    }

    def white_decide(obs):
        return white.decide(obs)

    # Set environment
    import os
    os.environ["OSWORLD_SERVER_URL"] = f"http://{vm_ip}:5000"
    os.environ["USE_NATIVE_OSWORLD"] = "1"
    os.environ["USE_FAKE_OSWORLD"] = "0"

    # Run task
    try:
        result = run_osworld(
            task,
            white_decide,
            "/tmp/chrome_test_artifacts",
            white_agent_url=white_agent_url,
            osworld_task=osworld_task
        )

        logger.info(f"\n✓ Task completed: success={result.get('success')}, steps={result.get('steps')}")
        return True

    except Exception as e:
        logger.error(f"Task execution failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Chrome task on VM")
    parser.add_argument(
        "--vm-ip",
        required=True,
        help="VM external IP address"
    )
    parser.add_argument(
        "--white-agent-url",
        default="http://localhost:9002",
        help="White Agent URL (default: http://localhost:9002)"
    )
    parser.add_argument(
        "--task-id",
        help="Optional specific Chrome task ID"
    )

    args = parser.parse_args()

    success = test_chrome_task(args.vm_ip, args.white_agent_url, args.task_id)
    sys.exit(0 if success else 1)
