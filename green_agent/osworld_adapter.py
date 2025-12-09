import os, time, base64, io, logging
from typing import Dict, Any
from PIL import Image

logger = logging.getLogger(__name__)

# OSWorld configuration
OSWORLD_SERVER_URL = os.environ.get("OSWORLD_SERVER_URL", "http://localhost:5000")
OSWORLD_OBS_TYPE = os.environ.get("OSWORLD_OBS_TYPE", "screenshot_a11y_tree")
OSWORLD_MAX_STEPS = int(os.environ.get("OSWORLD_MAX_STEPS", os.environ.get("MAX_STEPS", 15)))
OSWORLD_SLEEP_AFTER_EXEC = int(os.environ.get("OSWORLD_SLEEP_AFTER_EXECUTION", 3))


def _png_b64(img: Image.Image) -> str:
    """Convert PIL Image to base64-encoded PNG string."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def run_osworld_native(
    task: Dict[str, Any],
    white_decide,
    artifacts_dir: str | None = None,
    white_agent_url: str | None = None,
    osworld_task: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Run OSWorld assessment using native REST API (port 5000).

    Args:
        task: Task dictionary with 'instruction' and 'id'
        white_decide: Callback function(obs) -> action
        artifacts_dir: Directory to save screenshots
        white_agent_url: URL of White Agent (unused, kept for compatibility)
        osworld_task: Full OSWorld task config with evaluator (optional)

    Returns:
        Dictionary with success, steps, time_sec, etc.
    """
    from .osworld_client import OSWorldClient, create_observation

    logger.info(f"Starting native OSWorld for task: {task.get('id', 'unknown')}")
    logger.info(f"OSWorld server: {OSWORLD_SERVER_URL}")

    # Connect to OSWorld server
    client = OSWorldClient(base_url=OSWORLD_SERVER_URL)

    # Health check
    if not client.health_check():
        return {
            "success": 0,
            "steps": 0,
            "time_sec": 0.0,
            "failure_reason": f"OSWorld server at {OSWORLD_SERVER_URL} is not responding",
            "artifacts": {}
        }

    logger.info("OSWorld server health check passed")

    # Create artifacts directory
    if artifacts_dir:
        frames_dir = os.path.join(artifacts_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
    else:
        frames_dir = None

    t0 = time.time()
    steps = 0
    failure = None
    max_steps = OSWORLD_MAX_STEPS

    try:
        # Initial screenshot to verify display is working
        initial_screenshot = client.screenshot()
        logger.info(f"Initial screenshot: {len(initial_screenshot)} bytes")

        # Main interaction loop
        for step in range(1, max_steps + 1):
            logger.info(f"Step {step}/{max_steps}")

            # Get observation from OSWorld
            include_a11y = OSWORLD_OBS_TYPE in ["a11y_tree", "screenshot_a11y_tree"]
            obs_obj = create_observation(client, include_a11y=include_a11y)

            # Save screenshot artifact
            if frames_dir:
                try:
                    screenshot_bytes = base64.b64decode(obs_obj.screenshot_b64)
                    screenshot_path = os.path.join(frames_dir, f"step_{step:04d}.png")
                    with open(screenshot_path, "wb") as f:
                        f.write(screenshot_bytes)
                    logger.debug(f"Saved screenshot: {screenshot_path}")
                except Exception as e:
                    logger.warning(f"Failed to save screenshot: {e}")

            # Prepare observation for white agent
            obs_for_white = {
                "frame_id": step,
                "image_png_b64": obs_obj.screenshot_b64,
                "instruction": task.get("instruction", ""),
                "done": False,
            }
            # Include accessibility tree if available (for screenshot_a11y_tree mode)
            if obs_obj.accessibility_tree:
                obs_for_white["accessibility_tree"] = obs_obj.accessibility_tree

            # Get action from white agent
            try:
                action = white_decide(obs_for_white)
                logger.info(f"White agent action: {action.get('action_type', 'unknown')}")
            except Exception as e:
                failure = f"white_agent_error: {e}"
                logger.error(f"White agent error: {e}")
                break

            # Execute action in OSWorld
            action_type = action.get("action_type", "")

            if action_type == "DONE":
                logger.info("White agent signaled DONE")
                break
            elif action_type == "execute":
                # Execute shell command
                command = action.get("command", "")
                if command:
                    try:
                        result = client.execute(command, shell=True)
                        logger.info(f"Executed: {command}, result: {result.get('status')}")
                    except Exception as e:
                        logger.warning(f"Execute failed: {e}")
            elif action_type == "click":
                # Click at coordinates
                x = action.get("x", 0)
                y = action.get("y", 0)
                try:
                    client.click_at(x, y)
                    logger.info(f"Clicked at ({x}, {y})")
                except Exception as e:
                    logger.warning(f"Click failed: {e}")
            elif action_type == "type":
                # Type text
                text = action.get("text", "")
                if text:
                    try:
                        client.type_text(text)
                        logger.info(f"Typed: {text[:50]}")
                    except Exception as e:
                        logger.warning(f"Type failed: {e}")

            steps += 1

            # Sleep after execution (give UI time to update)
            if OSWORLD_SLEEP_AFTER_EXEC > 0:
                time.sleep(OSWORLD_SLEEP_AFTER_EXEC)

        # Evaluate task success using OSWorld evaluation system
        # Check task first, fall back to osworld_task for backward compatibility
        eval_source = task if "evaluator" in task else osworld_task
        if eval_source and "evaluator" in eval_source:
            logger.info("Running OSWorld evaluation...")
            try:
                from .osworld_evaluator import evaluate_task

                # Extract VM IP from OSWORLD_SERVER_URL (format: http://IP:PORT)
                vm_ip = OSWORLD_SERVER_URL.split("//")[1].split(":")[0]

                # Run OSWorld evaluation
                evaluation_score = evaluate_task(
                    vm_ip=vm_ip,
                    evaluator_config=eval_source["evaluator"],
                    task_id=eval_source.get("id", task.get("id", "unknown")),
                    server_port=5000,
                    cache_dir="cache"
                )

                logger.info(f"OSWorld evaluation score: {evaluation_score}")

                # Success if score >= 1.0
                success = 1 if evaluation_score >= 1.0 else 0

                # Store evaluation score in failure reason if failed
                if success == 0 and failure is None:
                    failure = f"evaluation_failed_score_{evaluation_score}"

            except Exception as e:
                logger.error(f"Evaluation error: {e}", exc_info=True)
                # Fall back to simplified check if evaluation fails
                logger.warning("Falling back to simplified success check")
                success = 1 if failure is None and steps > 0 else 0
                if success == 1:
                    failure = f"evaluation_error: {e}"
        else:
            # Fall back to simplified check if no evaluator config
            logger.info("No evaluator config found, using simplified success check")
            success = 1 if failure is None and steps > 0 else 0

    except Exception as e:
        logger.error(f"Native OSWorld error: {e}", exc_info=True)
        failure = f"native_osworld_error: {e}"
        success = 0
    finally:
        client.close()

    dt = time.time() - t0

    logger.info(f"Native OSWorld completed: success={success}, steps={steps}, time={dt:.2f}s")

    return {
        "success": success,
        "steps": steps,
        "time_sec": round(dt, 3),
        "failure_reason": failure,
        "artifacts": {"frames_dir": frames_dir} if frames_dir else {}
    }


def run_osworld(
    task: Dict[str, Any],
    white_decide,
    artifacts_dir: str | None = None,
    white_agent_url: str | None = None,
    osworld_task: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Run OSWorld assessment with White Agent.

    Args:
        task: Task dictionary (Green Agent format)
        white_decide: Callback function (unused, kept for compatibility)
        artifacts_dir: Directory to save artifacts
        white_agent_url: URL of White Agent HTTP API
        osworld_task: Full OSWorld task config with evaluator (optional)

    Returns:
        Dictionary with assessment results
    """
    return run_osworld_native(task, white_decide, artifacts_dir, white_agent_url, osworld_task)
