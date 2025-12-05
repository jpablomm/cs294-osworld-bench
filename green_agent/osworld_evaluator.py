"""
OSWorld Evaluation Module

Integrates OSWorld's complete evaluation system (getters + metrics)
to properly validate task success/failure according to benchmark criteria.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Union, Callable, Optional

logger = logging.getLogger(__name__)

# Add vendor/OSWorld to path for imports
vendor_path = Path(__file__).parent.parent / "vendor" / "OSWorld"
if str(vendor_path) not in sys.path:
    sys.path.insert(0, str(vendor_path))

try:
    from desktop_env.evaluators import metrics, getters
    from desktop_env.controllers.setup import SetupController
    from desktop_env.controllers.python import PythonController
except ImportError as e:
    logger.error(f"Failed to import OSWorld evaluators: {e}")
    logger.error("Make sure vendor/OSWorld is properly set up")
    raise


class MinimalEnv:
    """
    Minimal environment object that provides what OSWorld getters need.

    OSWorld getters already use REST API and only need vm_ip and ports.
    This is a lightweight alternative to creating a full DesktopEnv instance.
    """

    def __init__(
        self,
        vm_ip: str,
        server_port: int = 5000,
        chromium_port: int = 9222,
        vlc_port: int = 8080,
        vnc_port: int = 8006,
        cache_dir: str = "cache",
        task_id: str = "unknown"
    ):
        self.vm_ip = vm_ip
        self.server_port = server_port
        self.chromium_port = chromium_port
        self.vlc_port = vlc_port
        self.vnc_port = vnc_port

        # Cache directory for task-specific files
        self.cache_dir_base = cache_dir
        self.task_id = task_id
        self.cache_dir = os.path.join(cache_dir, task_id)
        os.makedirs(self.cache_dir, exist_ok=True)

        # Setup controller for postconfig
        self.setup_controller = SetupController(
            vm_ip=vm_ip,
            server_port=server_port,
            chromium_port=chromium_port,
            vlc_port=vlc_port,
            cache_dir=cache_dir,
            client_password="password"  # Default for GCP VMs
        )

        # Python controller for getters that need env.controller
        # (e.g., get_accessibility_tree, get_terminal_output, get_file, etc.)
        self._controller = PythonController(
            vm_ip=vm_ip,
            server_port=server_port
        )

    @property
    def controller(self):
        """Controller for OSWorld getters (get_accessibility_tree, get_file, etc.)"""
        return self._controller

    @property
    def vm_platform(self):
        """Get VM platform (Linux, Windows, Darwin) from controller"""
        return self._controller.get_vm_platform()

    @property
    def vm_screen_size(self):
        """Get VM screen size from controller"""
        return self._controller.get_vm_screen_size()


def parse_evaluator_config(evaluator: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse evaluator configuration and resolve function names to actual functions.

    Args:
        evaluator: Evaluator dict from OSWorld task JSON

    Returns:
        Dict with resolved functions:
        {
            "metrics": List[Callable] or Callable,
            "result_getters": List[Callable] or Callable,
            "expected_getters": List[Callable] or Callable or None,
            "metric_options": List[Dict] or Dict,
            "conjunction": str ("and" or "or"),
            "postconfig": List[Dict]  # Optional post-execution setup
        }
    """
    # Parse metric functions
    func_names = evaluator["func"]
    is_list = isinstance(func_names, list)

    try:
        if is_list:
            metric_funcs = [getattr(metrics, func_name) for func_name in func_names]
        else:
            metric_funcs = getattr(metrics, func_names)
    except AttributeError as e:
        logger.error(f"Unknown metric function: {e}")
        raise ValueError(f"Metric function not found in desktop_env.evaluators.metrics: {e}")

    # Parse result getters
    result_configs = evaluator.get("result", [])
    if result_configs:
        try:
            if isinstance(result_configs, list):
                result_getters = [
                    getattr(getters, f"get_{res['type']}")
                    for res in result_configs
                ]
            else:
                result_getters = getattr(getters, f"get_{result_configs['type']}")
        except (AttributeError, KeyError) as e:
            logger.error(f"Unknown result getter: {e}")
            raise ValueError(f"Result getter not found: {e}")
    else:
        result_getters = [None] * len(metric_funcs) if is_list else None

    # Parse expected getters (optional)
    expected_configs = evaluator.get("expected", [])
    if expected_configs:
        try:
            if isinstance(expected_configs, list):
                expected_getters = [
                    getattr(getters, f"get_{exp['type']}") if exp else None
                    for exp in expected_configs
                ]
            else:
                expected_getters = getattr(getters, f"get_{expected_configs['type']}")
        except (AttributeError, KeyError) as e:
            logger.error(f"Unknown expected getter: {e}")
            raise ValueError(f"Expected getter not found: {e}")
    else:
        expected_getters = [None] * len(metric_funcs) if is_list else None

    # Parse metric options (optional)
    options = evaluator.get("options", {})
    if isinstance(options, list):
        metric_options = [opt if opt else {} for opt in options]
    elif options:
        metric_options = options
    else:
        metric_options = [{}] * len(metric_funcs) if is_list else {}

    # Get conjunction (and/or) for multiple metrics
    conjunction = evaluator.get("conj", "and")

    # Get postconfig (optional setup to run BEFORE evaluation)
    postconfig = evaluator.get("postconfig", [])

    return {
        "metrics": metric_funcs,
        "result_getters": result_getters,
        "expected_getters": expected_getters,
        "metric_options": metric_options,
        "conjunction": conjunction,
        "postconfig": postconfig,
        "is_list": is_list
    }


def evaluate_task(
    vm_ip: str,
    evaluator_config: Dict[str, Any],
    task_id: str = "unknown",
    server_port: int = 5000,
    cache_dir: str = "cache",
    last_action: Optional[str] = None
) -> float:
    """
    Evaluate OSWorld task using configured getters and metrics.

    Args:
        vm_ip: VM IP address
        evaluator_config: Evaluator dict from OSWorld task JSON
        task_id: Task identifier (for cache directory)
        server_port: OSWorld server port (default 5000)
        cache_dir: Base cache directory
        last_action: The agent's final action - "FAIL", "DONE", or None.
                     Used for infeasible task evaluation.

    Returns:
        Score from 0.0 (failure) to 1.0 (success)

    Raises:
        ValueError: If evaluator config is invalid
        Exception: If evaluation fails
    """
    logger.info(f"Starting OSWorld evaluation for task {task_id}")
    logger.info(f"VM IP: {vm_ip}, Port: {server_port}")

    # Create minimal env object
    # Note: Use port 9222 because tasks use socat to forward 9222->1337
    env = MinimalEnv(
        vm_ip=vm_ip,
        server_port=server_port,
        chromium_port=9222,
        cache_dir=cache_dir,
        task_id=task_id
    )

    # Parse evaluator configuration
    try:
        parsed = parse_evaluator_config(evaluator_config)
    except Exception as e:
        logger.error(f"Failed to parse evaluator config: {e}")
        raise

    # Run postconfig (setup steps that run BEFORE evaluation)
    if parsed["postconfig"]:
        logger.info(f"Running postconfig with {len(parsed['postconfig'])} steps...")
        try:
            success = env.setup_controller.setup(parsed["postconfig"], use_proxy=False)
            if not success:
                logger.warning("Postconfig setup failed, continuing with evaluation anyway")
        except Exception as e:
            logger.error(f"Postconfig execution error: {e}")
            logger.warning("Continuing with evaluation despite postconfig failure")

    # Handle special case: infeasible tasks
    # These are tasks that should be marked as FAIL by the agent
    if evaluator_config.get("func") == "infeasible":
        logger.info(f"Task is marked as infeasible - checking for FAIL signal (last_action={last_action})")
        if last_action == "FAIL":
            logger.info("Agent correctly identified task as infeasible - returning 1.0")
            return 1.0
        else:
            logger.info("Agent did not identify task as infeasible - returning 0.0")
            return 0.0

    # Handle normal tasks where agent incorrectly gave up
    if last_action == "FAIL":
        logger.info("Agent returned FAIL on a feasible task - returning 0.0")
        return 0.0

    # Execute evaluation
    if parsed["is_list"]:
        # Multiple metrics
        logger.info(f"Evaluating with {len(parsed['metrics'])} metrics (conjunction: {parsed['conjunction']})")
        results = []

        for idx, metric_func in enumerate(parsed["metrics"]):
            result_getter = parsed["result_getters"][idx]
            expected_getter = parsed["expected_getters"][idx] if parsed["expected_getters"] else None
            metric_options = parsed["metric_options"][idx] if isinstance(parsed["metric_options"], list) else {}

            try:
                # Get actual result
                result_config = evaluator_config["result"][idx]
                logger.info(f"Metric {idx+1}: Getting result using {result_getter.__name__ if result_getter else 'None'}")
                logger.info(f"  Result config: {result_config}")

                if result_getter:
                    result_state = result_getter(env, result_config)
                    logger.info(f"  Result: {result_state}")
                else:
                    logger.warning(f"  No result getter for metric {idx+1}")
                    result_state = None

                # Get expected result (if needed)
                if expected_getter and "expected" in evaluator_config:
                    expected_config = evaluator_config["expected"][idx]
                    logger.info(f"  Getting expected using {expected_getter.__name__}")
                    logger.info(f"  Expected config: {expected_config}")
                    expected_state = expected_getter(env, expected_config)
                    logger.info(f"  Expected: {expected_state}")

                    # Apply metric with both actual and expected
                    score = metric_func(result_state, expected_state, **metric_options)
                else:
                    # Apply metric with just actual (expected is in options/rules)
                    score = metric_func(result_state, **metric_options)

                logger.info(f"  Metric {idx+1} score: {score}")

                # Early termination for conjunction
                if parsed["conjunction"] == "and" and float(score) == 0.0:
                    logger.info("AND conjunction: metric failed, returning 0.0")
                    return 0.0
                elif parsed["conjunction"] == "or" and float(score) == 1.0:
                    logger.info("OR conjunction: metric passed, returning 1.0")
                    return 1.0

                results.append(float(score))

            except FileNotFoundError as e:
                logger.error(f"Metric {idx+1}: File not found - {e}")
                if parsed["conjunction"] == "and":
                    return 0.0
                results.append(0.0)
            except Exception as e:
                logger.error(f"Metric {idx+1} evaluation error: {e}", exc_info=True)
                if parsed["conjunction"] == "and":
                    return 0.0
                results.append(0.0)

        # Compute final score based on conjunction
        if parsed["conjunction"] == "and":
            final_score = sum(results) / len(results) if results else 0.0
        else:  # "or"
            final_score = max(results) if results else 0.0

        logger.info(f"Final evaluation score: {final_score}")
        return final_score

    else:
        # Single metric
        logger.info(f"Evaluating with single metric: {parsed['metrics'].__name__}")

        try:
            # Get actual result
            result_config = evaluator_config.get("result", {})
            result_getter = parsed["result_getters"]

            logger.info(f"Getting result using {result_getter.__name__ if result_getter else 'None'}")
            logger.info(f"Result config: {result_config}")

            if result_getter:
                result_state = result_getter(env, result_config)
                logger.info(f"Result: {result_state}")
            else:
                logger.warning("No result getter configured")
                result_state = None

            # Get expected result (if needed)
            expected_getter = parsed["expected_getters"]
            if expected_getter and "expected" in evaluator_config:
                expected_config = evaluator_config["expected"]
                logger.info(f"Getting expected using {expected_getter.__name__}")
                logger.info(f"Expected config: {expected_config}")
                expected_state = expected_getter(env, expected_config)
                logger.info(f"Expected: {expected_state}")

                # Apply metric with both actual and expected
                score = parsed["metrics"](result_state, expected_state, **parsed["metric_options"])
            else:
                # Apply metric with just actual (expected is in options/rules)
                score = parsed["metrics"](result_state, **parsed["metric_options"])

            final_score = float(score)
            logger.info(f"Final evaluation score: {final_score}")
            return final_score

        except FileNotFoundError as e:
            logger.error(f"File not found during evaluation: {e}")
            return 0.0
        except Exception as e:
            logger.error(f"Evaluation error: {e}", exc_info=True)
            return 0.0
