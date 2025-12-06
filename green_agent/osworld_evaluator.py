"""
OSWorld Evaluation Module

Integrates OSWorld's complete evaluation system (getters + metrics)
to properly validate task success/failure according to benchmark criteria.

Enhanced with:
- Efficiency-adjusted scoring (penalizes inefficient solutions)
- Tolerant matching (reduces false negatives from minor variations)
- Trajectory analysis (extracts insights from agent behavior)
"""

import logging
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Any, List, Union, Callable, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Quick Win 1: Efficiency-Adjusted Scoring
# =============================================================================

def calculate_efficiency_score(
    base_score: float,
    steps_taken: int,
    expected_steps: Optional[int] = None,
    max_steps: int = 15,
    efficiency_weight: float = 0.2
) -> Dict[str, Any]:
    """
    Calculate efficiency-adjusted score that penalizes inefficient solutions.

    Args:
        base_score: Original evaluation score (0.0 to 1.0)
        steps_taken: How many steps the agent used
        expected_steps: Baseline expected steps (if known from task metadata)
        max_steps: Maximum allowed steps (used if expected_steps not provided)
        efficiency_weight: How much efficiency affects final score (0.0 to 1.0)

    Returns:
        Dict with:
            - adjusted_score: Final score incorporating efficiency
            - base_score: Original correctness score
            - efficiency_ratio: How efficient the agent was (1.0 = optimal)
            - steps_taken: Number of steps used
            - expected_steps: Baseline steps used for comparison
    """
    if base_score == 0.0:
        return {
            "adjusted_score": 0.0,
            "base_score": 0.0,
            "efficiency_ratio": 0.0,
            "steps_taken": steps_taken,
            "expected_steps": expected_steps or max_steps
        }

    # Use expected_steps if provided, otherwise use a heuristic
    # Heuristic: expect task to be done in ~40% of max_steps for simple tasks
    baseline = expected_steps if expected_steps else max(1, int(max_steps * 0.4))

    # Efficiency ratio: 1.0 if at or under baseline, decreases as steps increase
    if steps_taken <= baseline:
        efficiency_ratio = 1.0
    else:
        # Gradual decay: at 2x baseline steps, efficiency is 0.5
        efficiency_ratio = baseline / steps_taken

    # Weighted combination
    correctness_weight = 1.0 - efficiency_weight
    adjusted_score = (correctness_weight * base_score) + (efficiency_weight * efficiency_ratio * base_score)

    logger.info(f"Efficiency scoring: base={base_score:.2f}, steps={steps_taken}, "
                f"baseline={baseline}, efficiency={efficiency_ratio:.2f}, adjusted={adjusted_score:.2f}")

    return {
        "adjusted_score": round(adjusted_score, 4),
        "base_score": base_score,
        "efficiency_ratio": round(efficiency_ratio, 4),
        "steps_taken": steps_taken,
        "expected_steps": baseline
    }


# =============================================================================
# Quick Win 2: Tolerant Matching
# =============================================================================

def tolerant_match(
    result: Any,
    expected: Any,
    threshold: float = 0.85,
    ignore_case: bool = True,
    ignore_whitespace: bool = True
) -> Dict[str, Any]:
    """
    Flexible string matching that handles minor variations.

    Tries exact match first (after normalization), then falls back to fuzzy matching.

    Args:
        result: Actual result from VM
        expected: Expected value
        threshold: Minimum similarity for fuzzy match (0.0 to 1.0)
        ignore_case: Whether to ignore case differences
        ignore_whitespace: Whether to normalize whitespace

    Returns:
        Dict with:
            - score: Match score (0.0 to 1.0)
            - match_type: "exact", "normalized", "fuzzy", or "no_match"
            - similarity: Raw similarity score
            - details: Additional match information
    """
    # Handle None/empty cases
    if result is None:
        return {
            "score": 0.0,
            "match_type": "no_match",
            "similarity": 0.0,
            "details": "Result is None"
        }

    # Convert to strings
    result_str = str(result)
    expected_str = str(expected)

    # Check exact match first
    if result_str == expected_str:
        return {
            "score": 1.0,
            "match_type": "exact",
            "similarity": 1.0,
            "details": "Exact match"
        }

    # Normalize strings
    def normalize(s: str) -> str:
        normalized = s
        if ignore_whitespace:
            normalized = " ".join(normalized.split())
        if ignore_case:
            normalized = normalized.lower()
        return normalized.strip()

    result_norm = normalize(result_str)
    expected_norm = normalize(expected_str)

    # Check normalized match
    if result_norm == expected_norm:
        return {
            "score": 1.0,
            "match_type": "normalized",
            "similarity": 1.0,
            "details": f"Match after normalization (case={'ignored' if ignore_case else 'preserved'}, whitespace={'normalized' if ignore_whitespace else 'preserved'})"
        }

    # Fuzzy match using rapidfuzz (already available in OSWorld deps)
    try:
        from rapidfuzz import fuzz
        similarity = fuzz.ratio(result_norm, expected_norm) / 100.0

        if similarity >= threshold:
            return {
                "score": similarity,
                "match_type": "fuzzy",
                "similarity": similarity,
                "details": f"Fuzzy match with {similarity:.1%} similarity (threshold: {threshold:.1%})"
            }
        else:
            return {
                "score": 0.0,
                "match_type": "no_match",
                "similarity": similarity,
                "details": f"Similarity {similarity:.1%} below threshold {threshold:.1%}"
            }
    except ImportError:
        logger.warning("rapidfuzz not available, falling back to exact match only")
        return {
            "score": 0.0,
            "match_type": "no_match",
            "similarity": 0.0,
            "details": "Fuzzy matching unavailable"
        }


# =============================================================================
# Quick Win 3: Trajectory Analysis
# =============================================================================

def analyze_trajectory(trajectory: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract insights from agent trajectory for debugging and analysis.

    Args:
        trajectory: List of trajectory entries from orchestrator, each containing:
            - step: Step number
            - action: Action dict with "op" and "args"
            - content: Agent's reasoning/response
            - message_data: Full message metadata
            - tool_data: Tool execution details

    Returns:
        Dict with analysis results:
            - total_steps: Number of steps taken
            - action_counts: Counter of action types
            - action_sequence: List of action ops in order
            - unique_actions: Number of distinct action types used
            - has_loops: Whether agent got stuck in repetitive patterns
            - loop_details: Information about detected loops
            - final_action: The last action taken
            - screenshot_ratio: Proportion of screenshot actions (may indicate confusion)
            - error_count: Number of failed tool executions
            - avg_action_duration_ms: Average time per action (if available)
    """
    if not trajectory:
        return {
            "total_steps": 0,
            "action_counts": {},
            "action_sequence": [],
            "unique_actions": 0,
            "has_loops": False,
            "loop_details": None,
            "final_action": None,
            "screenshot_ratio": 0.0,
            "error_count": 0,
            "avg_action_duration_ms": None,
            "analysis_status": "empty_trajectory"
        }

    # Extract action sequence
    actions = []
    error_count = 0
    durations = []

    for entry in trajectory:
        action = entry.get("action", {})
        op = action.get("op", "unknown")
        actions.append(op)

        # Count errors
        tool_data = entry.get("tool_data", {})
        if tool_data and tool_data.get("status") == "failed":
            error_count += 1

        # Collect durations
        if tool_data and "duration_ms" in tool_data:
            durations.append(tool_data["duration_ms"])

    action_counts = dict(Counter(actions))

    # Detect loops (same action repeated 3+ times consecutively)
    loops = _detect_action_loops(actions)

    # Calculate screenshot ratio
    screenshot_count = action_counts.get("screenshot", 0)
    screenshot_ratio = screenshot_count / len(actions) if actions else 0.0

    # Average duration
    avg_duration = sum(durations) / len(durations) if durations else None

    analysis = {
        "total_steps": len(trajectory),
        "action_counts": action_counts,
        "action_sequence": actions,
        "unique_actions": len(set(actions)),
        "has_loops": len(loops) > 0,
        "loop_details": loops if loops else None,
        "final_action": actions[-1] if actions else None,
        "screenshot_ratio": round(screenshot_ratio, 3),
        "error_count": error_count,
        "avg_action_duration_ms": round(avg_duration, 1) if avg_duration else None,
        "analysis_status": "complete"
    }

    # Add warnings for potential issues
    warnings = []
    if screenshot_ratio > 0.5:
        warnings.append("High screenshot ratio may indicate agent confusion")
    if len(loops) > 0:
        warnings.append(f"Detected {len(loops)} action loop(s)")
    if error_count > len(trajectory) * 0.3:
        warnings.append("High error rate in tool executions")

    if warnings:
        analysis["warnings"] = warnings

    return analysis


def _detect_action_loops(actions: List[str], min_loop_length: int = 3) -> List[Dict[str, Any]]:
    """
    Detect repetitive action patterns that may indicate the agent is stuck.

    Args:
        actions: List of action operation names
        min_loop_length: Minimum consecutive repetitions to count as a loop

    Returns:
        List of detected loops with position and action info
    """
    loops = []
    i = 0

    while i < len(actions):
        # Check for consecutive identical actions
        j = i
        while j < len(actions) and actions[j] == actions[i]:
            j += 1

        repeat_count = j - i
        if repeat_count >= min_loop_length:
            loops.append({
                "action": actions[i],
                "start_index": i,
                "repeat_count": repeat_count,
                "type": "consecutive_repeat"
            })

        i = j if j > i else i + 1

    # Also detect short repeating patterns (e.g., click-screenshot-click-screenshot)
    for pattern_len in [2, 3]:
        for i in range(len(actions) - pattern_len * min_loop_length + 1):
            pattern = tuple(actions[i:i + pattern_len])
            repeat_count = 1

            for j in range(i + pattern_len, len(actions) - pattern_len + 1, pattern_len):
                if tuple(actions[j:j + pattern_len]) == pattern:
                    repeat_count += 1
                else:
                    break

            if repeat_count >= min_loop_length:
                # Check if we already recorded this loop
                already_recorded = any(
                    loop["start_index"] == i and loop["type"] == "pattern_repeat"
                    for loop in loops
                )
                if not already_recorded:
                    loops.append({
                        "pattern": list(pattern),
                        "start_index": i,
                        "repeat_count": repeat_count,
                        "type": "pattern_repeat"
                    })

    return loops

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
    last_action: Optional[str] = None,
    steps_taken: Optional[int] = None,
    trajectory: Optional[List[Dict[str, Any]]] = None,
    max_steps: int = 15,
    expected_steps: Optional[int] = None
) -> Union[float, Dict[str, Any]]:
    """
    Evaluate OSWorld task using configured getters and metrics.

    Enhanced with efficiency scoring and trajectory analysis when additional
    parameters are provided.

    Args:
        vm_ip: VM IP address
        evaluator_config: Evaluator dict from OSWorld task JSON
        task_id: Task identifier (for cache directory)
        server_port: OSWorld server port (default 5000)
        cache_dir: Base cache directory
        last_action: The agent's final action - "FAIL", "DONE", or None.
                     Used for infeasible task evaluation.
        steps_taken: Number of steps the agent took (for efficiency scoring)
        trajectory: Full trajectory from orchestrator (for analysis)
        max_steps: Maximum allowed steps (for efficiency baseline)
        expected_steps: Expected steps for this task (overrides heuristic)

    Returns:
        If steps_taken or trajectory provided: Dict with detailed results
            - score: Final score (0.0 to 1.0)
            - base_score: Raw evaluation score before efficiency adjustment
            - efficiency: Efficiency scoring details
            - trajectory_analysis: Trajectory analysis (if trajectory provided)
        Otherwise: float score (0.0 to 1.0) for backward compatibility

    Raises:
        ValueError: If evaluator config is invalid
        Exception: If evaluation fails
    """
    logger.info(f"Starting OSWorld evaluation for task {task_id}")
    logger.info(f"VM IP: {vm_ip}, Port: {server_port}")

    # Determine if we should return enhanced results
    return_enhanced = steps_taken is not None or trajectory is not None

    # Helper to build result (handles both simple and enhanced returns)
    # Defined early so it can be used for infeasible tasks before MinimalEnv is created
    def build_result(base_score: float) -> Union[float, Dict[str, Any]]:
        if not return_enhanced:
            return base_score

        # Calculate efficiency score
        actual_steps = steps_taken if steps_taken is not None else (
            len(trajectory) if trajectory else 0
        )
        efficiency_data = calculate_efficiency_score(
            base_score=base_score,
            steps_taken=actual_steps,
            expected_steps=expected_steps,
            max_steps=max_steps
        )

        # Analyze trajectory if provided
        trajectory_data = None
        if trajectory:
            trajectory_data = analyze_trajectory(trajectory)

        return {
            "score": efficiency_data["adjusted_score"],
            "base_score": base_score,
            "efficiency": efficiency_data,
            "trajectory_analysis": trajectory_data,
            "task_id": task_id
        }

    # Handle special case: infeasible tasks BEFORE parsing evaluator config
    # These are tasks that should be marked as FAIL by the agent
    # Must check this first because "infeasible" is not a real metric function
    if evaluator_config.get("func") == "infeasible":
        logger.info(f"Task is marked as infeasible - checking for FAIL signal (last_action={last_action})")
        if last_action == "FAIL":
            logger.info("Agent correctly identified task as infeasible - returning 1.0")
            return build_result(1.0)
        else:
            logger.info("Agent did not identify task as infeasible - returning 0.0")
            return build_result(0.0)

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

    # Handle normal tasks where agent incorrectly gave up
    if last_action == "FAIL":
        logger.info("Agent returned FAIL on a feasible task - returning 0.0")
        return build_result(0.0)

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
                    return build_result(0.0)
                elif parsed["conjunction"] == "or" and float(score) == 1.0:
                    logger.info("OR conjunction: metric passed, returning 1.0")
                    return build_result(1.0)

                results.append(float(score))

            except FileNotFoundError as e:
                logger.error(f"Metric {idx+1}: File not found - {e}")
                if parsed["conjunction"] == "and":
                    return build_result(0.0)
                results.append(0.0)
            except Exception as e:
                logger.error(f"Metric {idx+1} evaluation error: {e}", exc_info=True)
                if parsed["conjunction"] == "and":
                    return build_result(0.0)
                results.append(0.0)

        # Compute final score based on conjunction
        if parsed["conjunction"] == "and":
            final_score = sum(results) / len(results) if results else 0.0
        else:  # "or"
            final_score = max(results) if results else 0.0

        logger.info(f"Final evaluation score: {final_score}")
        return build_result(final_score)

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
            return build_result(final_score)

        except FileNotFoundError as e:
            logger.error(f"File not found during evaluation: {e}")
            return build_result(0.0)
        except Exception as e:
            logger.error(f"Evaluation error: {e}", exc_info=True)
            return build_result(0.0)


async def evaluate_task_with_llm_fallback(
    vm_ip: str,
    evaluator_config: Dict[str, Any],
    task_id: str = "unknown",
    task_instruction: str = "",
    server_port: int = 5000,
    cache_dir: str = "cache",
    last_action: Optional[str] = None,
    steps_taken: Optional[int] = None,
    trajectory: Optional[List[Dict[str, Any]]] = None,
    max_steps: int = 15,
    expected_steps: Optional[int] = None,
    # LLM fallback options
    enable_llm_fallback: bool = False,
    llm_provider: str = "openai",
    llm_model: Optional[str] = None,
    llm_confidence_threshold: float = 0.7,
    screenshot_before: Optional[bytes] = None,
    screenshot_after: Optional[bytes] = None
) -> Dict[str, Any]:
    """
    Evaluate OSWorld task with optional LLM-as-Judge fallback.

    This async function wraps evaluate_task() and adds LLM fallback
    when rule-based evaluation returns 0.0.

    Args:
        vm_ip: VM IP address
        evaluator_config: Evaluator dict from OSWorld task JSON
        task_id: Task identifier
        task_instruction: Human-readable task description (for LLM judge)
        server_port: OSWorld server port
        cache_dir: Base cache directory
        last_action: Agent's final action ("FAIL", "DONE", or None)
        steps_taken: Number of steps taken
        trajectory: Full trajectory from orchestrator
        max_steps: Maximum allowed steps
        expected_steps: Expected steps for this task

        enable_llm_fallback: Whether to use LLM when rule-based fails
        llm_provider: LLM provider ("openai" or "anthropic")
        llm_model: Model name (defaults to provider's best)
        llm_confidence_threshold: Minimum confidence to trust LLM
        screenshot_before: Initial screenshot PNG bytes
        screenshot_after: Final screenshot PNG bytes

    Returns:
        Dict with evaluation results including:
            - score: Final score
            - base_score: Rule-based score
            - evaluation_method: "rule_based", "llm_judge_fallback", etc.
            - llm_judgment: LLM result (if fallback was used)
    """
    import asyncio

    # Run rule-based evaluation in thread pool (it's synchronous)
    rule_based_result = await asyncio.to_thread(
        evaluate_task,
        vm_ip=vm_ip,
        evaluator_config=evaluator_config,
        task_id=task_id,
        server_port=server_port,
        cache_dir=cache_dir,
        last_action=last_action,
        steps_taken=steps_taken,
        trajectory=trajectory,
        max_steps=max_steps,
        expected_steps=expected_steps
    )

    # Normalize result to dict
    if isinstance(rule_based_result, (int, float)):
        result = {
            "score": float(rule_based_result),
            "base_score": float(rule_based_result),
            "evaluation_method": "rule_based",
            "task_id": task_id
        }
    else:
        result = rule_based_result
        result["evaluation_method"] = "rule_based"

    rule_based_score = result.get("base_score", result.get("score", 0.0))

    # Check if we should invoke LLM fallback
    should_use_llm = (
        enable_llm_fallback and
        rule_based_score == 0.0 and
        (screenshot_before is not None or screenshot_after is not None)
    )

    if not should_use_llm:
        return result

    # Invoke LLM-as-Judge fallback
    logger.info("Rule-based evaluation returned 0.0, invoking LLM-as-Judge fallback")

    try:
        from green_agent.llm_judge import EvaluationEvidence, llm_judge_evaluation

        # Extract action sequence from trajectory
        action_sequence = []
        agent_reasoning = None
        if trajectory:
            for entry in trajectory:
                action = entry.get("action", {})
                op = action.get("op", "unknown")
                args = action.get("args", {})

                # Format action nicely
                if op == "click" and "x" in args and "y" in args:
                    action_sequence.append(f"click({args['x']}, {args['y']})")
                elif op == "type" and "text" in args:
                    action_sequence.append(f"type('{args['text'][:50]}...')" if len(args.get('text', '')) > 50 else f"type('{args.get('text', '')}')")
                elif op == "hotkey" and "keys" in args:
                    action_sequence.append(f"hotkey({', '.join(args['keys'])})")
                elif op == "scroll" and "amount" in args:
                    action_sequence.append(f"scroll({args['amount']})")
                else:
                    action_sequence.append(op)

            # Get last agent reasoning
            if trajectory:
                last_entry = trajectory[-1]
                agent_reasoning = last_entry.get("content", "")

        # Build evidence
        evidence = EvaluationEvidence(
            task_instruction=task_instruction,
            screenshot_before=screenshot_before,
            screenshot_after=screenshot_after,
            action_sequence=action_sequence,
            agent_reasoning=agent_reasoning,
            rule_based_score=rule_based_score,
            rule_based_error=result.get("failure_reason")
        )

        # Call LLM judge
        llm_result = await llm_judge_evaluation(
            evidence=evidence,
            provider=llm_provider,
            model=llm_model,
            confidence_threshold=llm_confidence_threshold
        )

        logger.info(f"LLM judge result: success={llm_result.get('success')}, "
                   f"confidence={llm_result.get('confidence'):.2f}")

        # Store LLM judgment in result
        result["llm_judgment"] = llm_result

        # Check if we should override the rule-based result
        if llm_result.get("meets_threshold", False):
            if llm_result.get("success", False):
                logger.info("LLM judge overrides: marking as SUCCESS")
                result["score"] = 1.0
                result["evaluation_method"] = "llm_judge_override"
            else:
                logger.info("LLM judge confirms: keeping as FAILURE")
                result["evaluation_method"] = "rule_based_confirmed_by_llm"
        else:
            logger.info(f"LLM confidence ({llm_result.get('confidence'):.2f}) below threshold "
                       f"({llm_confidence_threshold}), keeping rule-based result")
            result["evaluation_method"] = "rule_based_llm_uncertain"

    except Exception as e:
        logger.error(f"LLM fallback failed: {e}", exc_info=True)
        result["llm_fallback_error"] = str(e)
        result["evaluation_method"] = "rule_based_llm_failed"

    return result
