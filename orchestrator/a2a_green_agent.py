"""
A2A-Compliant Green Agent for OSWorld Assessment

This module wraps the existing OSWorld orchestrator to make it AgentBeats-compliant.
It implements the A2A protocol while preserving all existing orchestrator functionality.
"""

import json
import logging
import asyncio
import httpx
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel

# Add OSWorld to path for SetupController
sys.path.insert(0, str(Path(__file__).parent.parent / "vendor" / "OSWorld"))

# Import existing orchestrator components
from .vm_manager import VMManager
from .storage import StorageManager
from .task_executor import TaskExecutor

# Import OSWorld SetupController
from desktop_env.controllers.setup import SetupController

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# A2A Protocol Models (simplified implementation based on AgentBeats spec)
class AgentCard(BaseModel):
    """Agent self-description following A2A protocol"""
    name: str
    description: str
    version: str
    capabilities: list[str]
    protocols: list[str]
    assessment_types: list[str]


class A2ATask(BaseModel):
    """A2A Task format"""
    task_id: str
    context_id: Optional[str] = None
    message: str  # Natural language or structured description
    metadata: Optional[Dict[str, Any]] = None


class A2AMessage(BaseModel):
    """A2A Message response"""
    message_id: str
    task_id: str
    context_id: Optional[str] = None
    role: str  # "agent"
    content: str
    metadata: Optional[Dict[str, Any]] = None


# Create FastAPI app for A2A green agent
app = FastAPI(
    title="OSWorld Green Agent (A2A)",
    description="AgentBeats-compliant assessment agent for OSWorld benchmarks",
    version="0.1.0"
)

# Initialize managers (reuse existing orchestrator components)
vm_manager = VMManager()
storage_manager = StorageManager(use_gcs=False)  # Local storage for demo
task_executor = TaskExecutor()

# Track active assessments
active_assessments: Dict[str, Dict[str, Any]] = {}


@app.get("/agent-card")
def get_agent_card() -> AgentCard:
    """
    Return agent card - A2A protocol requirement

    This describes the green agent's capabilities for AgentBeats platform
    """
    return AgentCard(
        name="OSWorld Assessment Agent",
        description=(
            "Green agent for conducting OSWorld desktop automation assessments. "
            "Creates VMs from golden images, orchestrates task execution with white agents, "
            "and reports standardized metrics (success rate, steps, execution time)."
        ),
        version="0.1.0",
        capabilities=[
            "osworld-benchmarks",
            "desktop-automation-assessment",
            "vm-orchestration",
            "chrome-tasks",
            "os-tasks",
            "gnome-tasks"
        ],
        protocols=["a2a", "rest"],
        assessment_types=[
            "osworld-single-agent",  # One white agent performs desktop tasks
            "osworld-chrome",        # Chrome-specific tasks
            "osworld-os",           # OS-level tasks
            "osworld-custom"        # Custom task definitions
        ]
    )


@app.post("/task")
async def handle_a2a_task(task: A2ATask) -> A2AMessage:
    """
    Handle A2A task - main entry point for assessments

    Accepts:
    - Natural language task description
    - Structured JSON config in metadata

    Returns:
    - A2A Message with assessment results
    """
    logger.info(f"Received A2A task: {task.task_id}")

    # Parse task configuration
    try:
        config = _parse_task_config(task)
        logger.info(f"Parsed config: {config}")
    except Exception as e:
        error_msg = f"Failed to parse task config: {e}"
        logger.error(error_msg)
        return A2AMessage(
            message_id=f"msg-{task.task_id}",
            task_id=task.task_id,
            context_id=task.context_id,
            role="agent",
            content=error_msg,
            metadata={"status": "failed", "error": str(e)}
        )

    # Execute assessment
    try:
        result = await _execute_assessment(task.task_id, config)

        # Format results as A2A message
        return A2AMessage(
            message_id=f"msg-{task.task_id}",
            task_id=task.task_id,
            context_id=task.context_id,
            role="agent",
            content=_format_results_message(result),
            metadata={
                "status": "completed",
                "metrics": result
            }
        )

    except Exception as e:
        error_msg = f"Assessment failed: {e}"
        logger.error(error_msg, exc_info=True)
        return A2AMessage(
            message_id=f"msg-{task.task_id}",
            task_id=task.task_id,
            context_id=task.context_id,
            role="agent",
            content=error_msg,
            metadata={"status": "failed", "error": str(e)}
        )


def _parse_task_config(task: A2ATask) -> Dict[str, Any]:
    """
    Parse task configuration from A2A task

    Supports:
    1. Structured config in metadata
    2. JSON in natural language message
    3. Natural language description (future: LLM parsing)
    """
    # Option 1: Check metadata for structured config
    if task.metadata and "config" in task.metadata:
        return task.metadata["config"]

    # Option 2: Try parsing message as JSON
    try:
        config = json.loads(task.message)
        if isinstance(config, dict):
            return config
    except json.JSONDecodeError:
        pass

    # Option 3: Extract from natural language (simple keyword extraction)
    # For demo, we look for key fields in the message
    config = {}
    message_lower = task.message.lower()

    # Extract white_agent_url
    if "white_agent_url" in task.metadata:
        config["white_agent_url"] = task.metadata["white_agent_url"]
    elif "white agent" in message_lower:
        # Would parse URL from message in real implementation
        raise ValueError("white_agent_url must be provided in metadata")

    # Extract osworld_task_id
    if "osworld_task_id" in task.metadata:
        config["osworld_task_id"] = task.metadata["osworld_task_id"]
    elif "task_id" in task.metadata:
        config["osworld_task_id"] = task.metadata["task_id"]
    else:
        raise ValueError("osworld_task_id must be provided in metadata")

    # Extract optional parameters
    config["max_steps"] = task.metadata.get("max_steps", 15)
    config["vm_image"] = task.metadata.get("vm_image", "osworld-golden-v3-gnome")
    config["metrics"] = task.metadata.get("metrics", ["success", "steps", "time_sec"])
    config["domain"] = task.metadata.get("domain")  # OSWorld task domain (os, chrome, vlc, etc.)

    return config


def _execute_osworld_setup(vm_ip: str, task_config: list) -> bool:
    """
    Execute OSWorld task setup using SetupController

    Args:
        vm_ip: VM IP address
        task_config: List of setup config dicts from OSWorld task JSON

    Returns:
        True if setup succeeded, False otherwise

    Raises:
        Exception if setup fails
    """
    if not task_config:
        logger.info("No setup configuration - skipping setup phase")
        return True

    logger.info(f"Executing OSWorld task setup with {len(task_config)} steps...")

    try:
        # Create cache directory for SetupController
        cache_dir = Path("cache")
        cache_dir.mkdir(exist_ok=True)
        logger.info(f"Created cache directory: {cache_dir.absolute()}")

        # Create SetupController
        setup_controller = SetupController(
            vm_ip=vm_ip,
            server_port=5000
        )

        # Execute setup
        success = setup_controller.setup(task_config)

        if success:
            logger.info("✓ OSWorld task setup completed successfully")
        else:
            logger.error("✗ OSWorld task setup failed")

        return success

    except Exception as e:
        logger.error(f"Setup execution failed: {e}", exc_info=True)
        raise


async def _execute_assessment(
    assessment_id: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute OSWorld assessment using existing orchestrator logic

    This is the core integration point that reuses all existing code.

    NEW: Implements Approach II - sends tool descriptions to white agent
    via A2A messages instead of MCP.
    """
    import time
    from pathlib import Path
    import httpx

    logger.info(f"Starting assessment {assessment_id}")
    start_time = time.time()

    # Track assessment
    active_assessments[assessment_id] = {
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
        "config": config
    }

    vm_info = None

    try:
        # Step 1: Create VM (reuse existing VMManager)
        logger.info("Creating VM...")
        vm_info = await asyncio.to_thread(
            vm_manager.create_vm,
            assessment_id
        )
        logger.info(f"VM created: {vm_info['vm_name']} at {vm_info['vm_ip']}")

        # Step 2: Wait for VM ready
        logger.info("Waiting for VM to be ready...")
        vm_ready = await asyncio.to_thread(
            vm_manager.wait_for_vm_ready,
            vm_info["vm_ip"],
            timeout=300  # Increased from 120 to 300 seconds (5 minutes)
        )

        if not vm_ready:
            raise Exception("VM did not become ready in time")

        # Step 2.5: Execute OSWorld task setup
        # Load full OSWorld task with config
        osworld_task = None
        try:
            logger.info("Loading full OSWorld task configuration...")
            osworld_task = task_executor.load_osworld_task(
                config["osworld_task_id"],
                domain=config.get("domain")
            )

            # Execute setup if config exists
            if "config" in osworld_task and osworld_task["config"]:
                setup_success = await asyncio.to_thread(
                    _execute_osworld_setup,
                    vm_info["vm_ip"],
                    osworld_task["config"]
                )

                if not setup_success:
                    raise Exception("Task setup failed")
            else:
                logger.info("No setup config in task - skipping setup phase")

        except FileNotFoundError:
            logger.warning(
                f"Full OSWorld task not found for {config['osworld_task_id']} - "
                "skipping setup phase"
            )
        except Exception as e:
            logger.error(f"Setup phase failed: {e}")
            raise

        # Step 3: Send task to white agent with tool descriptions (Approach II)
        logger.info("Sending task to white agent with tool descriptions...")

        # Build tool descriptions for OSWorld API
        tools = _build_osworld_tool_descriptions(vm_info["vm_ip"])

        # Get task description - prefer osworld_task if available
        if osworld_task:
            task = {"instruction": osworld_task.get("instruction", "Complete the task")}
        else:
            # Fallback to loading from tasks directory
            task = task_executor.load_task(config["osworld_task_id"])

        # Create A2A task message with tools
        white_agent_task = {
            "task_id": assessment_id,
            "context_id": assessment_id,
            "message": _format_task_message_with_tools(task, tools),
            "metadata": {
                "osworld_server": f"http://{vm_info['vm_ip']}:5000",
                "tools": tools,
                "max_steps": config.get("max_steps", 15)
            }
        }

        # Send to white agent and execute workflow
        logger.info("Running assessment with white agent...")
        artifacts_dir = f"./temp_artifacts/{assessment_id}"
        Path(artifacts_dir).mkdir(parents=True, exist_ok=True)

        result = await _execute_with_white_agent(
            white_agent_task,
            config["white_agent_url"],
            vm_info["vm_ip"],
            artifacts_dir,
            config.get("max_steps", 15)
        )

        # Step 4: Evaluate task success using OSWorld evaluation system
        if osworld_task and "evaluator" in osworld_task:
            logger.info("Running OSWorld evaluation...")
            try:
                from green_agent.osworld_evaluator import evaluate_task

                # Run OSWorld evaluation
                evaluation_score = await asyncio.to_thread(
                    evaluate_task,
                    vm_ip=vm_info["vm_ip"],
                    evaluator_config=osworld_task["evaluator"],
                    task_id=osworld_task.get("id", config["osworld_task_id"]),
                    server_port=5000,
                    cache_dir="cache"
                )

                logger.info(f"OSWorld evaluation score: {evaluation_score}")

                # Update success based on evaluation (score >= 1.0 = success)
                result["success"] = 1 if evaluation_score >= 1.0 else 0
                result["evaluation_score"] = evaluation_score
                result["evaluation_method"] = "osworld_benchmark"

                if result["success"] == 0 and "failure_reason" not in result:
                    result["failure_reason"] = f"evaluation_failed_score_{evaluation_score}"

            except Exception as e:
                logger.error(f"Evaluation error: {e}", exc_info=True)
                logger.warning("Evaluation failed - using white agent result as-is")
                result["evaluation_error"] = str(e)
        else:
            logger.info("No evaluator config found, using simplified success check from white agent")
            result["evaluation_method"] = "simplified"

        # Step 5: Add metadata
        result["vm_cost"] = vm_manager.get_vm_cost(time.time() - start_time)
        result["vm_info"] = vm_info
        result["assessment_id"] = assessment_id
        result["total_time_sec"] = time.time() - start_time

        logger.info(f"Assessment completed: success={result.get('success')}")

        # Step 5: Cleanup VM
        logger.info("Cleaning up VM...")
        await asyncio.to_thread(
            vm_manager.delete_vm,
            assessment_id
        )

        active_assessments[assessment_id]["status"] = "completed"
        return result

    except Exception as e:
        logger.error(f"Assessment failed: {e}", exc_info=True)

        # Cleanup VM on failure
        if vm_info:
            try:
                await asyncio.to_thread(
                    vm_manager.delete_vm,
                    assessment_id
                )
            except Exception as cleanup_error:
                logger.error(f"Cleanup failed: {cleanup_error}")

        active_assessments[assessment_id]["status"] = "failed"
        active_assessments[assessment_id]["error"] = str(e)

        raise


def _format_results_message(result: Dict[str, Any]) -> str:
    """Format assessment results as human-readable message"""
    success = "✅ Success" if result.get("success") else "❌ Failed"
    steps = result.get("steps", 0)
    time_sec = result.get("time_sec", 0)
    vm_cost = result.get("vm_cost", 0)

    message = f"""
Assessment Complete

Status: {success}
Steps taken: {steps}
Execution time: {time_sec:.2f}s
VM cost: ${vm_cost:.4f}

""".strip()

    if result.get("failure_reason"):
        message += f"\nFailure reason: {result['failure_reason']}"

    return message


def _build_osworld_tool_descriptions(vm_ip: str) -> list[Dict[str, Any]]:
    """
    Build tool descriptions for OSWorld REST API

    This follows the AgentBeats Approach II pattern:
    Tools are described in the A2A message, not via MCP.

    Returns list of tool specifications compatible with LLM function calling.
    """
    osworld_base_url = f"http://{vm_ip}:5000"

    return [
        {
            "name": "screenshot",
            "description": "Capture a screenshot of the current desktop state",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            },
            "endpoint": f"{osworld_base_url}/screenshot",
            "method": "GET",
            "returns": "PNG image (binary)"
        },
        {
            "name": "execute_python",
            "description": "Execute Python code in the desktop environment. Use for complex automation tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute"
                    }
                },
                "required": ["code"]
            },
            "endpoint": f"{osworld_base_url}/execute",
            "method": "POST",
            "returns": "Execution result with stdout/stderr"
        },
        {
            "name": "execute_command",
            "description": "Execute a shell command or launch an application",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute"
                    },
                    "shell": {
                        "type": "boolean",
                        "description": "Whether to run command through shell",
                        "default": True
                    }
                },
                "required": ["command"]
            },
            "endpoint": f"{osworld_base_url}/execute",
            "method": "POST",
            "returns": "Command execution result"
        },
        {
            "name": "click",
            "description": "Perform a mouse click at specific screen coordinates",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "integer",
                        "description": "X coordinate on screen"
                    },
                    "y": {
                        "type": "integer",
                        "description": "Y coordinate on screen"
                    },
                    "button": {
                        "type": "string",
                        "description": "Mouse button to click",
                        "enum": ["left", "right", "middle"],
                        "default": "left"
                    }
                },
                "required": ["x", "y"]
            },
            "endpoint": f"{osworld_base_url}/action",
            "method": "POST",
            "returns": "Action execution status"
        },
        {
            "name": "type_text",
            "description": "Type text using keyboard input",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to type"
                    }
                },
                "required": ["text"]
            },
            "endpoint": f"{osworld_base_url}/action",
            "method": "POST",
            "returns": "Action execution status"
        },
        {
            "name": "hotkey",
            "description": "Press keyboard hotkey combination (e.g., Ctrl+C, Alt+Tab)",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of keys to press together (e.g., ['ctrl', 'c'])"
                    }
                },
                "required": ["keys"]
            },
            "endpoint": f"{osworld_base_url}/action",
            "method": "POST",
            "returns": "Action execution status"
        },
        {
            "name": "wait",
            "description": "Wait for a specified duration (useful between actions)",
            "parameters": {
                "type": "object",
                "properties": {
                    "duration": {
                        "type": "number",
                        "description": "Duration to wait in seconds",
                        "default": 1.0
                    }
                },
                "required": []
            },
            "endpoint": None,
            "method": "LOCAL",
            "returns": "None (client-side wait)"
        }
    ]


def _format_task_message_with_tools(task: Dict[str, Any], tools: list[Dict[str, Any]]) -> str:
    """
    Format task message with embedded tool descriptions

    This follows the Tau-Bench/AgentBeats pattern where tools are described
    in natural language within the task message.
    """
    task_instruction = task.get("instruction", "Complete the task")

    # Build tool documentation string
    tools_doc = "# Available Tools\n\n"
    tools_doc += "You have access to the following tools for desktop automation:\n\n"

    for tool in tools:
        tools_doc += f"## {tool['name']}\n"
        tools_doc += f"{tool['description']}\n\n"

        if tool['parameters']['properties']:
            tools_doc += "Parameters:\n"
            for param_name, param_spec in tool['parameters']['properties'].items():
                required = " (required)" if param_name in tool['parameters'].get('required', []) else ""
                tools_doc += f"- `{param_name}` ({param_spec['type']}){required}: {param_spec.get('description', '')}\n"
        else:
            tools_doc += "No parameters required.\n"

        tools_doc += "\n"

    # Combine task instruction with tools
    message = f"""
{tools_doc}

# Task

{task_instruction}

Please complete this task using the available tools. For each step:
1. Take a screenshot to observe the current state
2. Decide on the appropriate action
3. Execute the action using the tools above
4. Verify the result with another screenshot

You have a maximum of 15 steps to complete the task.
""".strip()

    return message


async def _execute_with_white_agent(
    task_dict: Dict[str, Any],
    white_agent_url: str,
    vm_ip: str,
    artifacts_dir: str,
    max_steps: int
) -> Dict[str, Any]:
    """
    Execute assessment workflow with white agent via A2A protocol

    This implements the full assessment loop:
    1. Send initial task to white agent
    2. For each step:
       - Get action from white agent
       - Execute action on OSWorld VM
       - Capture observation
       - Send observation back to white agent
    3. Continue until task complete or max steps reached

    Args:
        task_dict: A2A task message with tools
        white_agent_url: URL of white agent endpoint
        vm_ip: IP address of OSWorld VM
        artifacts_dir: Directory to save screenshots/logs
        max_steps: Maximum number of steps allowed

    Returns:
        Assessment results with success, steps, time, etc.
    """
    import httpx
    import time
    import base64
    from pathlib import Path

    osworld_base_url = f"http://{vm_ip}:5000"
    start_time = time.time()

    # Track assessment state
    step = 0
    success = False
    failure_reason = None
    trajectory = []

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            # Step 1: Send initial task to white agent
            logger.info(f"Sending task to white agent at {white_agent_url}")

            # Initial observation - take screenshot
            screenshot_resp = await client.get(f"{osworld_base_url}/screenshot")
            screenshot_b64 = base64.b64encode(screenshot_resp.content).decode()

            # Save initial screenshot
            Path(f"{artifacts_dir}/step_0_initial.png").write_bytes(screenshot_resp.content)

            # Build initial A2A task with observation
            current_task = {
                "task_id": task_dict["task_id"],
                "context_id": task_dict["context_id"],
                "message": task_dict["message"],
                "metadata": {
                    **task_dict["metadata"],
                    "observation": {
                        "frame_id": 0,
                        "image_png_b64": screenshot_b64,
                        "instruction": task_dict["message"],
                        "done": False
                    }
                }
            }

            # Assessment loop
            while step < max_steps:
                logger.info(f"Step {step}/{max_steps}")

                # Get action from white agent
                response = await client.post(
                    f"{white_agent_url}/task",
                    json=current_task,
                    timeout=120.0
                )
                response.raise_for_status()

                message = response.json()

                # Check for error responses
                if "action" not in message.get("metadata", {}):
                    error_msg = message.get("metadata", {}).get("error", "Unknown error")
                    logger.error(f"White agent returned error: {error_msg}")
                    logger.error(f"Full response: {message}")
                    raise RuntimeError(f"White agent error: {error_msg}")

                action = message["metadata"]["action"]
                is_done = message["metadata"].get("done", False)

                logger.info(f"White agent action: {action['op']}")
                trajectory.append({
                    "step": step,
                    "action": action,
                    "content": message["content"]
                })

                # Check if task is done
                if is_done or action["op"] == "done":
                    success = True
                    logger.info(f"Task completed successfully at step {step}")
                    break

                # Execute action on OSWorld VM
                try:
                    await _execute_osworld_action(client, osworld_base_url, action)
                except Exception as e:
                    logger.error(f"Action execution failed: {e}")
                    failure_reason = f"Action execution failed: {str(e)}"
                    break

                # Wait a moment for action to complete
                await asyncio.sleep(0.5)

                # Capture new observation
                screenshot_resp = await client.get(f"{osworld_base_url}/screenshot")
                screenshot_b64 = base64.b64encode(screenshot_resp.content).decode()

                # Save screenshot
                Path(f"{artifacts_dir}/step_{step + 1}.png").write_bytes(screenshot_resp.content)

                # Update task for next iteration
                step += 1
                current_task = {
                    "task_id": task_dict["task_id"],
                    "context_id": task_dict["context_id"],
                    "message": f"Step {step}: Previous action completed. Current state shown in screenshot.",
                    "metadata": {
                        **task_dict["metadata"],
                        "observation": {
                            "frame_id": step,
                            "image_png_b64": screenshot_b64,
                            "instruction": task_dict["message"],
                            "done": False
                        }
                    }
                }

            if not success and step >= max_steps:
                failure_reason = f"Maximum steps ({max_steps}) reached"

        except Exception as e:
            logger.error(f"Assessment workflow failed: {e}", exc_info=True)
            failure_reason = str(e)

    # Build result
    result = {
        "success": success,
        "steps": step,
        "time_sec": time.time() - start_time,
        "trajectory": trajectory,
        "artifacts_dir": artifacts_dir
    }

    if failure_reason:
        result["failure_reason"] = failure_reason

    return result


async def _execute_osworld_action(
    client: httpx.AsyncClient,
    base_url: str,
    action: Dict[str, Any]
):
    """
    Execute a single action on the OSWorld VM

    Translates action dict to Python code and executes via /run_python endpoint
    """
    op = action.get("op")
    args = action.get("args", {})

    # Generate Python code based on action type
    python_code = None

    if op == "click":
        # Click action
        x = args.get("x")
        y = args.get("y")
        button = args.get("button", "left")

        if x is not None and y is not None:
            if button == "left":
                python_code = f"import pyautogui\npyautogui.click({x}, {y})"
            elif button == "right":
                python_code = f"import pyautogui\npyautogui.rightClick({x}, {y})"
        else:
            python_code = "import pyautogui\npyautogui.click()"

    elif op == "double_click":
        # Double click action
        x = args.get("x")
        y = args.get("y")
        if x is not None and y is not None:
            python_code = f"import pyautogui\npyautogui.doubleClick({x}, {y})"

    elif op == "right_click":
        # Right click action
        x = args.get("x")
        y = args.get("y")
        if x is not None and y is not None:
            python_code = f"import pyautogui\npyautogui.rightClick({x}, {y})"

    elif op == "type":
        # Type text action
        text = args.get("text", "")
        # Escape quotes in text
        escaped_text = text.replace("\\", "\\\\").replace('"', '\\"')
        python_code = f'import pyautogui\npyautogui.typewrite("{escaped_text}")'

    elif op == "hotkey":
        # Hotkey action
        keys = args.get("keys", [])
        if len(keys) == 1:
            python_code = f'import pyautogui\npyautogui.press("{keys[0]}")'
        elif len(keys) > 1:
            keys_str = ", ".join([f'"{k}"' for k in keys])
            python_code = f'import pyautogui\npyautogui.hotkey({keys_str})'

    elif op == "scroll":
        # Scroll action
        amount = args.get("amount", 0)
        python_code = f"import pyautogui\npyautogui.scroll({amount})"

    elif op == "execute_python":
        # Execute Python code directly
        python_code = args.get("code")

    elif op == "execute_command":
        # Execute shell command via /execute endpoint
        await client.post(
            f"{base_url}/execute",
            json={
                "command": args["command"],
                "shell": args.get("shell", True)
            }
        )
        return

    elif op == "wait":
        # Local wait
        await asyncio.sleep(args.get("duration", 1.0))
        return

    elif op == "done":
        # Task complete - no action needed
        return

    else:
        logger.warning(f"Unknown action op: {op}")
        return

    # Execute the Python code if we generated any
    if python_code:
        logger.info(f"Executing Python code: {python_code}")
        response = await client.post(
            f"{base_url}/run_python",
            json={"code": python_code},
            timeout=30.0
        )

        if response.status_code != 200:
            logger.error(f"Failed to execute action: {response.status_code} {response.text}")
            raise RuntimeError(f"Action execution failed: {response.text}")

        result = response.json()
        if result.get("status") == "error":
            logger.error(f"Python execution error: {result.get('message')}")
            raise RuntimeError(f"Python execution error: {result.get('message')}")


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent_type": "green",
        "protocol": "a2a",
        "assessment_types": ["osworld"],
        "active_assessments": len([a for a in active_assessments.values()
                                   if a["status"] == "running"])
    }


@app.get("/assessments")
def list_assessments():
    """List all assessments (for debugging)"""
    return {
        "assessments": active_assessments
    }
