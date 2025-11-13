#!/usr/bin/env python3
"""
A2A Launcher - End-to-End OSWorld Assessment via AgentBeats Protocol

This script demonstrates how to use the A2A green agent to conduct
OSWorld assessments with Approach II (tools in messages).

Usage:
    python launcher_a2a.py --task-id <osworld-task-id> --white-agent-url <url>

Example:
    python launcher_a2a.py \\
        --task-id osworld-ubuntu-tiny \\
        --white-agent-url http://localhost:9001 \\
        --green-agent-url http://localhost:8001
"""

import argparse
import asyncio
import logging
import sys
import uuid
from typing import Dict, Any
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def check_agent_health(url: str, agent_type: str) -> bool:
    """Check if an agent is running and healthy"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/health")
            response.raise_for_status()
            health = response.json()
            logger.info(f"{agent_type} agent is healthy: {health}")
            return True
    except Exception as e:
        logger.error(f"{agent_type} agent not reachable at {url}: {e}")
        return False


async def get_agent_card(url: str, agent_type: str) -> Dict[str, Any]:
    """Fetch agent card to verify A2A compliance"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/agent-card")
            response.raise_for_status()
            card = response.json()
            logger.info(f"{agent_type} agent card:")
            logger.info(f"  Name: {card['name']}")
            logger.info(f"  Version: {card['version']}")
            logger.info(f"  Protocols: {card['protocols']}")
            logger.info(f"  Capabilities: {card['capabilities']}")
            return card
    except Exception as e:
        logger.error(f"Failed to get {agent_type} agent card: {e}")
        return {}


async def send_a2a_task(
    green_agent_url: str,
    task_id: str,
    white_agent_url: str,
    osworld_task_id: str,
    max_steps: int = 15,
    vm_image: str = "osworld-golden-v8-gnome",
    domain: str = None
) -> Dict[str, Any]:
    """
    Send A2A task to green agent and wait for results

    Args:
        green_agent_url: URL of A2A green agent
        task_id: Unique task identifier
        white_agent_url: URL of A2A white agent
        osworld_task_id: OSWorld task to execute
        max_steps: Maximum steps for assessment
        vm_image: Golden VM image name
        domain: OSWorld task domain (os, chrome, vlc, etc.)

    Returns:
        Assessment results as A2A Message
    """
    logger.info(f"Sending A2A task {task_id} to green agent...")

    # Build A2A task
    a2a_task = {
        "task_id": task_id,
        "context_id": task_id,
        "message": f"Run OSWorld assessment for task '{osworld_task_id}'",
        "metadata": {
            "osworld_task_id": osworld_task_id,
            "white_agent_url": white_agent_url,
            "max_steps": max_steps,
            "vm_image": vm_image,
            "metrics": ["success", "steps", "time_sec"]
        }
    }

    # Add domain if specified
    if domain:
        a2a_task["metadata"]["domain"] = domain

    try:
        async with httpx.AsyncClient(timeout=900.0) as client:  # 15 min timeout
            logger.info("POSTing task to green agent /task endpoint...")
            response = await client.post(
                f"{green_agent_url}/task",
                json=a2a_task
            )
            response.raise_for_status()

            message = response.json()
            logger.info("Received A2A message from green agent")

            return message

    except httpx.TimeoutException:
        logger.error("Assessment timed out after 15 minutes")
        raise
    except Exception as e:
        logger.error(f"Assessment failed: {e}")
        raise


def format_assessment_results(message: Dict[str, Any]) -> str:
    """Format A2A message results for display"""
    content = message.get("content", "")
    metadata = message.get("metadata", {})
    status = metadata.get("status", "unknown")

    output = f"""
{'=' * 60}
ASSESSMENT RESULTS
{'=' * 60}

Status: {status.upper()}

{content}

{'=' * 60}
DETAILED METRICS
{'=' * 60}
"""

    if "metrics" in metadata:
        metrics = metadata["metrics"]
        for key, value in metrics.items():
            output += f"\n{key}: {value}"

    output += f"\n\n{'=' * 60}\n"

    return output


async def main():
    parser = argparse.ArgumentParser(
        description="Launch OSWorld assessment via A2A protocol"
    )
    parser.add_argument(
        "--task-id",
        required=True,
        help="OSWorld task ID to execute (e.g., osworld-ubuntu-tiny)"
    )
    parser.add_argument(
        "--white-agent-url",
        required=True,
        help="URL of A2A white agent (e.g., http://localhost:9001)"
    )
    parser.add_argument(
        "--green-agent-url",
        default="http://localhost:8001",
        help="URL of A2A green agent (default: http://localhost:8001)"
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=15,
        help="Maximum steps for assessment (default: 15)"
    )
    parser.add_argument(
        "--vm-image",
        default="osworld-golden-v8-gnome",
        help="Golden VM image name (default: osworld-golden-v8-gnome)"
    )
    parser.add_argument(
        "--domain",
        help="OSWorld task domain (os, chrome, vlc, etc.)"
    )

    args = parser.parse_args()

    logger.info("Starting A2A Assessment Launcher")
    logger.info(f"OSWorld Task: {args.task_id}")
    logger.info(f"Green Agent: {args.green_agent_url}")
    logger.info(f"White Agent: {args.white_agent_url}")

    # Step 1: Check agent health
    logger.info("Step 1: Checking agent health...")
    green_healthy = await check_agent_health(args.green_agent_url, "Green")
    white_healthy = await check_agent_health(args.white_agent_url, "White")

    if not green_healthy or not white_healthy:
        logger.error("One or more agents are not healthy. Exiting.")
        sys.exit(1)

    # Step 2: Get agent cards
    logger.info("Step 2: Fetching agent cards...")
    await get_agent_card(args.green_agent_url, "Green")
    await get_agent_card(args.white_agent_url, "White")

    # Step 3: Send assessment task
    logger.info("Step 3: Sending assessment task...")
    assessment_id = f"assess-{uuid.uuid4().hex[:8]}"

    try:
        message = await send_a2a_task(
            green_agent_url=args.green_agent_url,
            task_id=assessment_id,
            white_agent_url=args.white_agent_url,
            osworld_task_id=args.task_id,
            max_steps=args.max_steps,
            vm_image=args.vm_image,
            domain=args.domain
        )

        # Step 4: Display results
        logger.info("Step 4: Displaying results...")
        print(format_assessment_results(message))

        # Exit with appropriate code
        metadata = message.get("metadata", {})
        if metadata.get("status") == "completed":
            metrics = metadata.get("metrics", {})
            if metrics.get("success"):
                logger.info("Assessment PASSED")
                sys.exit(0)
            else:
                logger.info("Assessment FAILED")
                sys.exit(1)
        else:
            logger.error("Assessment did not complete successfully")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Assessment failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
