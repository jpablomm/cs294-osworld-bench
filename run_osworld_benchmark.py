#!/usr/bin/env python3
"""
Run OSWorld benchmarks using native VM + White Agent Bridge

This script:
1. Loads OSWorld benchmark tasks
2. Uses White Agent Bridge to connect to our White Agent
3. Runs tasks on our native OSWorld VM
4. Evaluates results using OSWorld's evaluation functions
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add vendor/OSWorld to path
sys.path.insert(0, str(Path(__file__).parent / "vendor" / "OSWorld"))

from mm_agents.white_agent_bridge import WhiteAgentBridge
from green_agent.osworld_client import OSWorldClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def execute_pyautogui_action(osworld_client: OSWorldClient, action_str: str):
    """
    Parse and execute a pyautogui action string via REST API.

    Examples:
        pyautogui.click(100, 200)
        pyautogui.doubleClick(100, 200)
        pyautogui.typewrite("hello", interval=0.01)
        pyautogui.hotkey('ctrl', 's')
        pyautogui.press('enter')
        pyautogui.sleep(1.0)
    """
    import re
    import time

    action_str = action_str.strip()

    # Parse click actions
    if match := re.match(r'pyautogui\.click\((\d+),\s*(\d+)\)', action_str):
        x, y = int(match.group(1)), int(match.group(2))
        osworld_client.click_at(x, y)

    elif match := re.match(r'pyautogui\.doubleClick\((\d+),\s*(\d+)\)', action_str):
        x, y = int(match.group(1)), int(match.group(2))
        osworld_client.double_click_at(x, y)

    elif match := re.match(r'pyautogui\.rightClick\((\d+),\s*(\d+)\)', action_str):
        x, y = int(match.group(1)), int(match.group(2))
        osworld_client.right_click_at(x, y)

    # Parse type/typewrite actions
    elif match := re.match(r'pyautogui\.typewrite\(["\'](.+?)["\']', action_str):
        text = match.group(1)
        osworld_client.type_text(text)

    elif match := re.match(r'pyautogui\.write\(["\'](.+?)["\']', action_str):
        text = match.group(1)
        osworld_client.type_text(text)

    # Parse hotkey actions
    elif 'pyautogui.hotkey' in action_str:
        # Extract keys from hotkey('ctrl', 's') format
        keys_match = re.findall(r"'([^']+)'", action_str)
        if keys_match:
            # Map common keys
            key_map = {
                'ctrl': 'Control_L',
                'shift': 'Shift_L',
                'alt': 'Alt_L',
                'super': 'Super_L'
            }
            keys = [key_map.get(k.lower(), k) for k in keys_match]
            osworld_client.hotkey(*keys)

    # Parse press actions
    elif match := re.match(r"pyautogui\.press\('([^']+)'\)", action_str):
        key = match.group(1)
        osworld_client.press_key(key)

    # Parse sleep/wait
    elif match := re.match(r'pyautogui\.sleep\(([\d.]+)\)', action_str):
        duration = float(match.group(1))
        time.sleep(duration)

    else:
        logger.warning(f"Unknown pyautogui action: {action_str}")


def load_benchmark_tasks(test_file: str) -> dict:
    """Load benchmark tasks from test file"""
    with open(test_file, 'r') as f:
        return json.load(f)


def load_task_config(task_id: str, domain: str) -> dict:
    """Load specific task configuration"""
    task_file = Path("vendor/OSWorld/evaluation_examples/examples") / domain / f"{task_id}.json"

    if not task_file.exists():
        raise FileNotFoundError(f"Task file not found: {task_file}")

    with open(task_file, 'r') as f:
        return json.load(f)


def run_task_setup(osworld_client: OSWorldClient, config_list: list):
    """Run task setup commands"""
    for config in config_list:
        config_type = config.get("type")
        params = config.get("parameters", {})

        try:
            if config_type == "launch":
                command = params.get("command", [])
                logger.info(f"Launching: {' '.join(command)}")
                result = osworld_client.execute(command)
                logger.debug(f"Result: {result}")
            elif config_type == "execute":
                command = params.get("command", [])
                logger.info(f"Executing: {' '.join(command)}")
                result = osworld_client.execute(command)
                logger.debug(f"Result: {result}")
            elif config_type == "sleep":
                import time
                seconds = params.get("seconds", 1)
                logger.info(f"Sleeping for {seconds} seconds")
                time.sleep(seconds)
        except Exception as e:
            logger.warning(f"Setup command failed (continuing anyway): {e}")
            # Continue with other setup commands


def run_single_task(
    task_id: str,
    domain: str,
    osworld_url: str,
    white_agent_url: str,
    max_steps: int = 15
):
    """Run a single OSWorld benchmark task"""

    logger.info(f"\n{'='*80}")
    logger.info(f"Running task: {domain}/{task_id}")
    logger.info(f"{'='*80}\n")

    # Load task configuration
    task_config = load_task_config(task_id, domain)
    instruction = task_config.get("instruction", "")
    logger.info(f"Instruction: {instruction}")

    # Initialize clients
    osworld_client = OSWorldClient(osworld_url)
    white_agent = WhiteAgentBridge(
        white_agent_url=white_agent_url,
        action_space="pyautogui",
        platform="ubuntu"
    )

    # Reset White Agent
    white_agent.reset()

    # Run task setup (config commands)
    setup_config = task_config.get("config", [])
    if setup_config:
        logger.info("Running task setup...")
        run_task_setup(osworld_client, setup_config)
        import time
        time.sleep(2)  # Give setup time to complete

    # Run agent loop
    logger.info(f"Starting agent loop (max {max_steps} steps)...")

    for step in range(1, max_steps + 1):
        logger.info(f"\n--- Step {step}/{max_steps} ---")

        # Get observation from OSWorld
        screenshot = osworld_client.screenshot()
        obs = {
            "screenshot": screenshot
        }

        # Get action from White Agent (via bridge)
        response_text, actions = white_agent.predict(instruction, obs)
        logger.info(f"White Agent: {response_text}")
        logger.info(f"Actions: {actions}")

        # Check if done or failed
        if "DONE" in actions:
            logger.info("White Agent signaled DONE")
            break
        if "FAIL" in actions:
            logger.error("White Agent signaled FAIL")
            break

        # Execute actions - convert pyautogui strings to REST API calls
        for action in actions:
            if action in ["DONE", "FAIL", "WAIT"]:
                continue

            logger.info(f"Executing action: {action}")
            execute_pyautogui_action(osworld_client, action)

        # Sleep after execution
        import time
        time.sleep(1)

    logger.info(f"\nTask completed after {step} steps")

    # Run evaluation
    # TODO: Implement OSWorld's evaluation functions
    logger.info("\nEvaluation not yet implemented")

    osworld_client.close()

    return {
        "task_id": task_id,
        "domain": domain,
        "steps": step,
        "instruction": instruction
    }


def main():
    parser = argparse.ArgumentParser(description="Run OSWorld benchmarks on native VM")
    parser.add_argument("--osworld-url", type=str, required=True,
                        help="OSWorld VM REST API URL (e.g., http://10.128.0.10:5000)")
    parser.add_argument("--white-agent-url", type=str, default="http://localhost:9000",
                        help="White Agent URL")
    parser.add_argument("--test-file", type=str,
                        default="vendor/OSWorld/evaluation_examples/test_small.json",
                        help="Test file with task IDs")
    parser.add_argument("--domain", type=str, default="chrome",
                        help="Domain to test (chrome, gimp, libreoffice_calc, etc.)")
    parser.add_argument("--task-id", type=str, default=None,
                        help="Specific task ID to run (if not set, runs all in domain)")
    parser.add_argument("--max-steps", type=int, default=15,
                        help="Maximum steps per task")

    args = parser.parse_args()

    # Load test file
    logger.info(f"Loading test file: {args.test_file}")
    test_tasks = load_benchmark_tasks(args.test_file)

    if args.domain not in test_tasks:
        logger.error(f"Domain '{args.domain}' not found in test file")
        logger.error(f"Available domains: {', '.join(test_tasks.keys())}")
        return 1

    # Get tasks to run
    if args.task_id:
        task_ids = [args.task_id]
    else:
        task_ids = test_tasks[args.domain]

    logger.info(f"Running {len(task_ids)} tasks from domain '{args.domain}'")
    logger.info(f"Task IDs: {task_ids[:3]}..." if len(task_ids) > 3 else f"Task IDs: {task_ids}")

    # Run tasks
    results = []
    for task_id in task_ids:
        try:
            result = run_single_task(
                task_id=task_id,
                domain=args.domain,
                osworld_url=args.osworld_url,
                white_agent_url=args.white_agent_url,
                max_steps=args.max_steps
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Error running task {task_id}: {e}", exc_info=True)
            results.append({
                "task_id": task_id,
                "domain": args.domain,
                "error": str(e)
            })

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info(f"SUMMARY: Completed {len(results)}/{len(task_ids)} tasks")
    logger.info(f"{'='*80}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
