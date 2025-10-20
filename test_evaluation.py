#!/usr/bin/env python3
"""
Test OSWorld Evaluation Module

Tests the evaluation system by:
1. Loading the trash recovery task
2. Testing evaluation on a VM with/without the recovered file
"""

import sys
import logging
from pathlib import Path

# Add green_agent to path
sys.path.insert(0, str(Path(__file__).parent))

from green_agent.osworld_evaluator import evaluate_task
from orchestrator.task_executor import TaskExecutor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_trash_recovery_evaluation(vm_ip: str):
    """
    Test trash recovery task evaluation

    Task: 5ea617a3-0e86-4ba6-aab2-dac9aa2e8d57
    Evaluator: Checks if /home/user/Desktop/poster_party_night.webp exists
    """
    task_id = "5ea617a3-0e86-4ba6-aab2-dac9aa2e8d57"
    domain = "os"

    logger.info(f"Testing evaluation for task {task_id}")

    # Load full OSWorld task
    task_executor = TaskExecutor()
    try:
        osworld_task = task_executor.load_osworld_task(task_id, domain=domain)
        logger.info(f"Loaded OSWorld task: {osworld_task.get('instruction', 'No instruction')}")
    except FileNotFoundError:
        logger.error(f"Task {task_id} not found in domain {domain}")
        return False

    # Verify evaluator exists
    if "evaluator" not in osworld_task:
        logger.error("Task does not have evaluator config")
        return False

    logger.info(f"Evaluator config: {osworld_task['evaluator']}")

    # Test 1: Evaluate without recovered file (should fail)
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Evaluation WITHOUT recovered file (expect score=0.0)")
    logger.info("="*60)

    try:
        score = evaluate_task(
            vm_ip=vm_ip,
            evaluator_config=osworld_task["evaluator"],
            task_id=task_id,
            server_port=5000,
            cache_dir="cache"
        )
        logger.info(f"Score without file: {score}")

        if score == 0.0:
            logger.info("✓ Test 1 PASSED: Correctly evaluated as failure")
        else:
            logger.error(f"✗ Test 1 FAILED: Expected 0.0, got {score}")
            return False

    except Exception as e:
        logger.error(f"Test 1 error: {e}", exc_info=True)
        return False

    # Test 2: Create the file and evaluate again (should succeed)
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Evaluation WITH recovered file (expect score=1.0)")
    logger.info("="*60)

    # Create the file on VM
    import requests
    try:
        logger.info("Creating test file on VM...")
        response = requests.post(
            f"http://{vm_ip}:5000/execute",
            json={
                "command": "touch /home/user/Desktop/poster_party_night.webp",
                "shell": True
            },
            timeout=10
        )

        if response.status_code == 200:
            logger.info("✓ File created successfully")
        else:
            logger.error(f"Failed to create file: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Failed to create file: {e}")
        return False

    # Run evaluation again
    try:
        score = evaluate_task(
            vm_ip=vm_ip,
            evaluator_config=osworld_task["evaluator"],
            task_id=task_id,
            server_port=5000,
            cache_dir="cache"
        )
        logger.info(f"Score with file: {score}")

        if score == 1.0:
            logger.info("✓ Test 2 PASSED: Correctly evaluated as success")
        else:
            logger.error(f"✗ Test 2 FAILED: Expected 1.0, got {score}")
            return False

    except Exception as e:
        logger.error(f"Test 2 error: {e}", exc_info=True)
        return False

    # Cleanup: Remove test file
    try:
        logger.info("Cleaning up test file...")
        requests.post(
            f"http://{vm_ip}:5000/execute",
            json={
                "command": "rm -f /home/user/Desktop/poster_party_night.webp",
                "shell": True
            },
            timeout=10
        )
        logger.info("✓ Cleanup complete")
    except Exception as e:
        logger.warning(f"Cleanup failed: {e}")

    logger.info("\n" + "="*60)
    logger.info("ALL TESTS PASSED!")
    logger.info("="*60)
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test OSWorld evaluation module")
    parser.add_argument(
        "--vm-ip",
        required=True,
        help="IP address of OSWorld VM with server running on port 5000"
    )

    args = parser.parse_args()

    success = test_trash_recovery_evaluation(args.vm_ip)
    sys.exit(0 if success else 1)
