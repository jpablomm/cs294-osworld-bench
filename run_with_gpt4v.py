#!/usr/bin/env python3
"""
Run OSWorld benchmarks using GPT-4V PromptAgent with native VM

This integrates OSWorld's official PromptAgent (GPT-4V) with our native OSWorld setup.
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add vendor/OSWorld to path
sys.path.insert(0, str(Path(__file__).parent / "vendor" / "OSWorld"))

from mm_agents.agent import PromptAgent
from green_agent.osworld_client import OSWorldClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
                # Launch GUI apps in background using shell
                command_str = ' '.join(command) + ' &'
                logger.info(f"Launching in background: {command_str}")
                result = osworld_client.execute(command_str, shell=True, timeout=5)
                logger.debug(f"Result: {result}")
            elif config_type == "execute":
                command = params.get("command", [])
                # Execute commands normally
                logger.info(f"Executing: {' '.join(command)}")
                result = osworld_client.execute(command, shell=False, timeout=30)
                logger.debug(f"Result: {result}")
            elif config_type == "sleep":
                seconds = params.get("seconds", 1)
                logger.info(f"Sleeping for {seconds} seconds")
                time.sleep(seconds)
        except Exception as e:
            logger.warning(f"Setup command failed (continuing anyway): {e}")


def execute_pyautogui_action(osworld_client: OSWorldClient, action_str: str):
    """
    Parse and execute a pyautogui action string via REST API.
    Handles both single-line commands and multi-line code blocks.
    """
    import re

    action_str = action_str.strip()

    # If it's a multi-line code block, extract individual pyautogui commands
    if '\n' in action_str or 'import' in action_str:
        lines = action_str.split('\n')
        for line in lines:
            line = line.strip()
            # Skip empty lines, imports, and comments
            if not line or line.startswith('#') or line.startswith('import') or line.startswith('time.'):
                continue
            # Recursively execute individual pyautogui commands
            if line.startswith('pyautogui.'):
                execute_pyautogui_action(osworld_client, line)
        return

    # Parse moveTo (for compatibility, execute as mouse_move) - support both positional and named args
    if match := re.match(r'pyautogui\.moveTo\((?:x=)?(\d+),\s*(?:y=)?(\d+)', action_str):
        x, y = int(match.group(1)), int(match.group(2))
        osworld_client.mouse_move(x, y)

    # Parse click actions - support both positional and named args
    elif match := re.match(r'pyautogui\.click\((?:x=)?(\d+),\s*(?:y=)?(\d+)\)', action_str):
        x, y = int(match.group(1)), int(match.group(2))
        osworld_client.click_at(x, y)

    elif match := re.match(r'pyautogui\.click\(\)', action_str):
        # Click at current position
        osworld_client.click_at(None, None)

    elif match := re.match(r'pyautogui\.doubleClick\((?:x=)?(\d+),\s*(?:y=)?(\d+)\)', action_str):
        x, y = int(match.group(1)), int(match.group(2))
        osworld_client.double_click_at(x, y)

    elif match := re.match(r'pyautogui\.rightClick\((?:x=)?(\d+),\s*(?:y=)?(\d+)\)', action_str):
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
        keys_match = re.findall(r"'([^']+)'", action_str)
        if keys_match:
            # Convert OSWorld key names to pyautogui key names
            key_map = {
                'control_l': 'ctrl',
                'shift_l': 'shift',
                'alt_l': 'alt',
                'super_l': 'win',
            }
            keys = [key_map.get(k.lower(), k) for k in keys_match]
            osworld_client.hotkey(*keys)

    # Parse press actions
    elif match := re.match(r"pyautogui\.press\('([^']+)'\)", action_str):
        key = match.group(1)
        osworld_client.press_key(key)

    # Parse scroll actions
    elif match := re.match(r'pyautogui\.scroll\((-?\d+)', action_str):
        amount = int(match.group(1))
        # Note: OSWorld API may need scroll implementation
        logger.warning(f"Scroll not yet implemented: {action_str}")

    else:
        logger.warning(f"Unknown pyautogui action: {action_str}")


def run_single_task(
    task_id: str,
    domain: str,
    osworld_url: str,
    agent: PromptAgent,
    max_steps: int = 15,
    save_screenshots: bool = True
):
    """Run a single OSWorld benchmark task with GPT-4V agent"""

    logger.info(f"\n{'='*80}")
    logger.info(f"Running task: {domain}/{task_id}")
    logger.info(f"{'='*80}\n")

    # Load task configuration
    task_config = load_task_config(task_id, domain)
    instruction = task_config.get("instruction", "")
    logger.info(f"Instruction: {instruction}")

    # Initialize OSWorld client
    osworld_client = OSWorldClient(osworld_url)

    # Reset agent
    agent.reset()

    # Run task setup (config commands)
    # For Chrome tasks, skip the OSWorld config and launch Chrome directly with proper flags
    if "chrome" in domain.lower() or "chrome" in instruction.lower():
        logger.info("Launching Chrome for Chrome-based task...")
        try:
            # Kill any existing Chrome
            osworld_client.execute(["pkill", "-f", "chrome"], timeout=5)
            time.sleep(1)
        except:
            pass

        # Launch Chrome with proper flags for this environment
        chrome_cmd = f"google-chrome --no-sandbox --user-data-dir=/tmp/chrome-{task_id[:8]} https://www.google.com &"
        logger.info(f"Executing: {chrome_cmd}")
        try:
            osworld_client.execute(chrome_cmd, shell=True, timeout=10)
        except Exception as e:
            # Chrome launch may timeout but that's OK - it runs in background
            logger.debug(f"Chrome launch timed out (expected): {e}")
        time.sleep(5)  # Give Chrome time to fully start
    else:
        # Run standard task setup for non-Chrome tasks
        setup_config = task_config.get("config", [])
        if setup_config:
            logger.info("Running task setup...")
            run_task_setup(osworld_client, setup_config)
            time.sleep(2)  # Give setup time to complete

    # Create results directory
    if save_screenshots:
        results_dir = Path("results") / domain / task_id
        results_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Saving screenshots to: {results_dir}")

    # Run agent loop
    logger.info(f"Starting GPT-4V agent loop (max {max_steps} steps)...")

    task_success = False

    for step in range(1, max_steps + 1):
        logger.info(f"\n--- Step {step}/{max_steps} ---")

        # Get observation from OSWorld
        screenshot = osworld_client.screenshot()
        obs = {"screenshot": screenshot}

        # Save screenshot
        if save_screenshots:
            screenshot_path = results_dir / f"step_{step:03d}.png"
            with open(screenshot_path, 'wb') as f:
                f.write(screenshot)
            logger.debug(f"Saved screenshot to {screenshot_path}")

        # Get action from GPT-4V agent
        logger.info("Querying GPT-4V agent...")
        try:
            response, actions = agent.predict(instruction, obs)
            logger.info(f"GPT-4V response: {response[:200]}..." if len(response) > 200 else f"GPT-4V response: {response}")
            logger.info(f"Actions: {actions}")
        except Exception as e:
            logger.error(f"Agent prediction failed: {e}")
            break

        # Check if done or failed
        if "DONE" in actions:
            logger.info("✓ GPT-4V agent signaled DONE - task complete!")
            task_success = True
            break
        if "FAIL" in actions:
            logger.error("✗ GPT-4V agent signaled FAIL")
            break

        # Execute actions via REST API
        for action in actions:
            if action in ["DONE", "FAIL", "WAIT"]:
                continue

            logger.info(f"Executing: {action}")
            try:
                execute_pyautogui_action(osworld_client, action)
            except Exception as e:
                logger.error(f"Action execution failed: {e}")

        # Sleep after execution
        time.sleep(1)

    logger.info(f"\n{'='*80}")
    logger.info(f"Task completed after {step} steps")
    logger.info(f"Success: {task_success}")
    logger.info(f"{'='*80}\n")

    osworld_client.close()

    return {
        "task_id": task_id,
        "domain": domain,
        "instruction": instruction,
        "steps": step,
        "success": task_success,
        "screenshots_dir": str(results_dir) if save_screenshots else None
    }


def main():
    parser = argparse.ArgumentParser(description="Run OSWorld benchmarks with GPT-4V")
    parser.add_argument("--osworld-url", type=str, required=True,
                        help="OSWorld VM REST API URL")
    parser.add_argument("--openai-api-key", type=str,
                        default=os.environ.get("OPENAI_API_KEY"),
                        help="OpenAI API key (or set OPENAI_API_KEY env var)")
    parser.add_argument("--model", type=str, default="gpt-4o",
                        help="OpenAI model to use (gpt-4o, gpt-4o-mini, etc.)")
    parser.add_argument("--domain", type=str, default="chrome",
                        help="Domain to test")
    parser.add_argument("--task-id", type=str, required=True,
                        help="Specific task ID to run")
    parser.add_argument("--max-steps", type=int, default=15,
                        help="Maximum steps per task")
    parser.add_argument("--temperature", type=float, default=1.0,
                        help="Model temperature")
    parser.add_argument("--save-screenshots", action="store_true", default=True,
                        help="Save screenshots to results directory")

    args = parser.parse_args()

    if not args.openai_api_key:
        logger.error("OpenAI API key required. Set OPENAI_API_KEY env var or use --openai-api-key")
        return 1

    # Set OpenAI API key
    os.environ["OPENAI_API_KEY"] = args.openai_api_key

    # Initialize GPT-4V agent
    logger.info(f"Initializing GPT-4V agent (model: {args.model})...")
    agent = PromptAgent(
        model=args.model,
        observation_type="screenshot",
        action_space="pyautogui",
        max_tokens=1500,
        temperature=args.temperature,
        top_p=0.9
    )
    logger.info("✓ GPT-4V agent initialized")

    # Run task
    try:
        result = run_single_task(
            task_id=args.task_id,
            domain=args.domain,
            osworld_url=args.osworld_url,
            agent=agent,
            max_steps=args.max_steps,
            save_screenshots=args.save_screenshots
        )

        # Print summary
        logger.info("\n" + "="*80)
        logger.info("FINAL RESULTS")
        logger.info("="*80)
        logger.info(f"Task: {result['domain']}/{result['task_id']}")
        logger.info(f"Instruction: {result['instruction']}")
        logger.info(f"Steps: {result['steps']}")
        logger.info(f"Success: {'✓ YES' if result['success'] else '✗ NO'}")
        if result['screenshots_dir']:
            logger.info(f"Screenshots: {result['screenshots_dir']}")
        logger.info("="*80)

        return 0 if result['success'] else 1

    except Exception as e:
        logger.error(f"Error running task: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
