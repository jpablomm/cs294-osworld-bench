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
import os
import time
import uuid
import base64
import signal
import atexit
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException, Depends, BackgroundTasks, Request
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add OSWorld to path for SetupController
# Path: green_agent/a2a/server.py -> ../../vendor/OSWorld
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "vendor" / "OSWorld"))

# All orchestrator imports are done lazily to avoid blocking subprocess startup
# GCP and Supabase clients can hang during import in Cloud Run subprocesses
# VMManager, TaskExecutor, upload_screenshot are imported in getter functions

# SetupController is imported lazily in _execute_osworld_setup to speed up startup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import configuration
from green_agent.config import (
    ACTION_REPEAT_THRESHOLD,
    ACTION_COORD_TOLERANCE,
    WEBUI_SERVER_URL,
    GREEN_AGENT_API_KEY,
    GCP_PROJECT,
    SETUP_STABILIZATION_WAIT,
    EVAL_STABILIZATION_WAIT,
    CLOUDRUN_HOST,
    HTTPS_ENABLED,
    GREEN_AGENT_HOST,
    GREEN_AGENT_PORT,
    get_agent_url,
)

# Import VM pool configuration
from green_agent.a2a.pool_config import VM_POOL_ENABLED, get_pool_config

# Import ActionTracker for loop detection
try:
    from green_agent.action_tracker import ActionTracker
    LOOP_DETECTION_ENABLED = True
    logger.info("[LoopDetection] ActionTracker imported successfully")
except ImportError:
    ActionTracker = None
    LOOP_DETECTION_ENABLED = False
    logger.warning("[LoopDetection] ActionTracker not available - loop detection disabled")


# A2A Protocol Models (following A2A SDK: a2a.types)
# These models must match the a2a SDK's AgentCard schema exactly for validation to pass
class AgentSkill(BaseModel):
    """A2A Skill definition - matches a2a.types.AgentSkill"""
    id: str
    name: str
    description: str
    tags: list[str]  # Required field, not optional
    inputModes: Optional[list[str]] = None
    outputModes: Optional[list[str]] = None


class AgentProvider(BaseModel):
    """A2A Provider definition - matches a2a.types.AgentProvider"""
    organization: str
    url: str


class AgentCapabilities(BaseModel):
    """A2A Capability flags - matches a2a.types.AgentCapabilities"""
    streaming: Optional[bool] = None
    pushNotifications: Optional[bool] = None
    stateTransitionHistory: Optional[bool] = None
    extensions: Optional[list] = None


class AgentCard(BaseModel):
    """Agent self-description following A2A SDK schema (a2a.types.AgentCard)"""
    # Required fields
    name: str
    description: str
    url: str
    version: str
    capabilities: AgentCapabilities
    defaultInputModes: list[str]
    defaultOutputModes: list[str]
    skills: list[AgentSkill]
    # Optional fields
    documentationUrl: Optional[str] = None
    provider: Optional[AgentProvider] = None
    protocolVersion: Optional[str] = "0.3.0"
    preferredTransport: Optional[str] = "JSONRPC"


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

# Lazy initialization of managers to avoid blocking subprocess startup
# GCP API calls and Supabase clients can hang during import in Cloud Run subprocesses
_vm_manager = None
_vm_pool = None  # VM pool for snapshot-based reuse
_task_executor = None

def get_vm_manager():
    """Lazily initialize VMManager on first use"""
    global _vm_manager
    if _vm_manager is None:
        from .vm_manager import VMManager
        logger.info(f"Initializing VMManager with project_id from config: {GCP_PROJECT}")
        _vm_manager = VMManager(project_id=GCP_PROJECT)
        logger.info(f"VMManager initialized with project_id: {_vm_manager.project_id}")
    return _vm_manager

async def get_vm_pool():
    """Lazily initialize VMPoolManager on first use (async)"""
    global _vm_pool
    if _vm_pool is None:
        from .vm_pool import VMPoolManager
        config = get_pool_config()
        logger.info(f"Initializing VMPoolManager with config: {config}")
        _vm_pool = VMPoolManager(
            project_id=GCP_PROJECT,
            zone=config["zone"],
            pool_size=config["pool_size"],
            snapshot_name=config["snapshot_name"],
            machine_type=config["machine_type"],
            max_tasks_per_vm=config["max_tasks_per_vm"],
            max_consecutive_failures=config["max_consecutive_failures"],
            restore_timeout=config["restore_timeout"],
            ready_timeout=config["ready_timeout"],
            fallback_to_fresh=config["fallback_to_fresh"],
        )
        await _vm_pool.initialize()
    return _vm_pool

def get_task_executor():
    """Lazily initialize TaskExecutor on first use"""
    global _task_executor
    if _task_executor is None:
        from .task_executor import TaskExecutor
        _task_executor = TaskExecutor()
    return _task_executor

def get_upload_screenshot():
    """Lazily import upload_screenshot function"""
    from .supabase_storage import upload_screenshot
    return upload_screenshot

# Track active assessments
active_assessments: Dict[str, Dict[str, Any]] = {}

# Flag to prevent duplicate cleanup during shutdown
_is_shutting_down = False


def _cleanup_all_vms():
    """
    Cleanup all running VMs on shutdown.

    This prevents orphaned VMs which waste cloud resources.
    Called by signal handlers and atexit.
    """
    global _is_shutting_down, _vm_pool

    if _is_shutting_down:
        return  # Already cleaning up
    _is_shutting_down = True

    # If pool is enabled and initialized, shut it down
    if VM_POOL_ENABLED and _vm_pool is not None:
        logger.info("Shutting down VM pool...")
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_vm_pool.shutdown())
            else:
                loop.run_until_complete(_vm_pool.shutdown())
            logger.info("VM pool shutdown complete")
        except Exception as e:
            logger.error(f"Failed to shutdown VM pool: {e}")
        return  # Pool handles its own VMs

    # Original cleanup for non-pool VMs
    running_assessments = [
        (aid, data) for aid, data in active_assessments.items()
        if data.get("status") == "running"
    ]

    if not running_assessments:
        logger.info("No running assessments to cleanup")
        return

    logger.warning(f"Cleaning up {len(running_assessments)} running assessment(s)...")

    for assessment_id, data in running_assessments:
        try:
            logger.info(f"Deleting VM for assessment {assessment_id}...")
            get_vm_manager().delete_vm(assessment_id)
            logger.info(f"VM for assessment {assessment_id} deleted successfully")
        except Exception as e:
            logger.error(f"Failed to cleanup VM for {assessment_id}: {e}")


def _signal_handler(signum, frame):
    """
    Handle SIGINT (Ctrl+C) and SIGTERM signals gracefully.

    Ensures VMs are cleaned up before exit to prevent orphaned resources.
    """
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logger.warning(f"Received {sig_name} signal - initiating graceful shutdown...")

    _cleanup_all_vms()

    logger.info("Graceful shutdown complete. Exiting.")
    sys.exit(0)


# Register signal handlers for graceful shutdown
# Note: These may not work in all environments (e.g., some WSGI servers)
# but will work when running directly with uvicorn
try:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    logger.info("Registered signal handlers for graceful shutdown")
except Exception as e:
    logger.warning(f"Could not register signal handlers: {e}")

# Register atexit handler as fallback
atexit.register(_cleanup_all_vms)


# WebUI server configuration and API key authentication are imported from green_agent.config

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """
    Verify API key for protected endpoints.

    This protects against DoS attacks and unauthorized VM creation,
    as recommended in AgentBeats documentation.

    To enable: Set GREEN_AGENT_API_KEY environment variable.
    To use: Include 'X-API-Key' header in requests.
    """
    # If no API key is configured, allow all requests
    if GREEN_AGENT_API_KEY is None:
        return True

    # If API key is configured, require it in requests
    if x_api_key != GREEN_AGENT_API_KEY:
        logger.warning("Unauthorized access attempt - invalid or missing API key")
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Set X-API-Key header."
        )

    return True

async def _push_event_to_webui(callback_url: Optional[str], event_data: Dict[str, Any]):
    """
    Push real-time event to WebUI server for SSE broadcasting

    This allows the live view to display assessment progress in real-time

    Args:
        callback_url: URL to send events to (from task config)
        event_data: Event payload to send
    """
    if not callback_url:
        logger.debug("No callback_url configured - skipping event push")
        return

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                callback_url,
                json=event_data
            )
            logger.debug(f"Pushed event to {callback_url}: {event_data.get('type')}")
    except Exception as e:
        # Don't fail assessment if webui event push fails
        logger.debug(f"Failed to push event to WebUI: {e}")


def _build_agent_card(request_url: str = None) -> AgentCard:
    """Build agent card with dynamic URL based on request or environment"""
    # Try to determine the agent URL
    # Priority: CLOUDRUN_HOST > request URL > HOST:PORT
    if CLOUDRUN_HOST:
        # Use explicit Cloud Run host (e.g., for cloudflared forwarding)
        protocol = "https" if HTTPS_ENABLED else "http"
        agent_url = f"{protocol}://{CLOUDRUN_HOST}"
    elif request_url:
        agent_url = request_url.split("/.well-known")[0].split("/agent-card")[0]
    else:
        # Fallback to config defaults
        agent_url = get_agent_url()

    return AgentCard(
        name="OSWorld Assessment Agent",
        description=(
            "Green agent for conducting OSWorld desktop automation assessments. "
            "Creates VMs from golden images, orchestrates task execution with white agents, "
            "and reports standardized metrics (success rate, steps, execution time)."
        ),
        url=agent_url,
        version="0.1.0",
        provider=AgentProvider(
            organization="Berkeley CS294",
            url="https://github.com/agentbeats/green-agent"
        ),
        documentationUrl="https://github.com/agentbeats/green-agent",
        defaultInputModes=["application/json"],
        defaultOutputModes=["application/json"],
        skills=[
            AgentSkill(
                id="osworld-assessment",
                name="OSWorld Assessment",
                description="Run OSWorld desktop automation benchmark assessments",
                tags=["benchmark", "desktop", "automation", "assessment"],
            ),
            AgentSkill(
                id="chrome-task",
                name="Chrome Browser Tasks",
                description="Execute Chrome browser automation tasks",
                tags=["chrome", "browser", "web"],
            ),
            AgentSkill(
                id="os-task",
                name="OS-Level Tasks",
                description="Execute operating system level tasks (file management, settings)",
                tags=["os", "files", "settings", "gnome"],
            ),
        ],
        capabilities=AgentCapabilities(
            streaming=False,
            pushNotifications=True,
            stateTransitionHistory=True
        )
    )


@app.get("/agent-card")
def get_agent_card(request: Request) -> AgentCard:
    """
    Return agent card - A2A protocol requirement
    """
    return _build_agent_card(str(request.url))


@app.get("/.well-known/agent.json")
async def get_well_known_agent_json(request: Request) -> AgentCard:
    """
    A2A Protocol standard discovery endpoint.

    Per A2A spec: https://agent2agent.info/docs/concepts/agentcard/
    Agent cards should be hosted at: /.well-known/agent.json
    """
    return _build_agent_card(str(request.url))


# Keep old endpoint for backwards compatibility
@app.get("/.well-known/agent-card.json")
async def get_well_known_agent_card_legacy(request: Request) -> AgentCard:
    """Legacy endpoint - redirects to standard A2A endpoint"""
    return _build_agent_card(str(request.url))


@app.post("/task", dependencies=[Depends(verify_api_key)])
async def handle_a2a_task(task: A2ATask, background_tasks: BackgroundTasks) -> A2AMessage:
    """
    Handle A2A task - main entry point for assessments

    Accepts:
    - Natural language task description
    - Structured JSON config in metadata

    Returns:
    - A2A Message with "accepted" status immediately
    - Assessment runs in background, updates sent via callbacks
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

    # Launch assessment in background (fire-and-forget)
    background_tasks.add_task(_execute_assessment, task.task_id, config)
    logger.info(f"Assessment {task.task_id} launched in background")

    # Return immediately with "accepted" status
    return A2AMessage(
        message_id=f"msg-{task.task_id}",
        task_id=task.task_id,
        context_id=task.context_id,
        role="agent",
        content=f"Assessment {task.task_id} accepted and running in background",
        metadata={
            "status": "accepted",
            "assessment_id": task.task_id,
            "message": "Assessment is running in background. Updates will be sent via callback URL."
        }
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
    config["vm_image"] = task.metadata.get("vm_image", "osworld-golden-v12-gnome")
    config["metrics"] = task.metadata.get("metrics", ["success", "steps", "time_sec"])
    config["domain"] = task.metadata.get("domain")  # OSWorld task domain (os, chrome, vlc, etc.)

    # Extract model from agent_config (passed from webui)
    agent_config = task.metadata.get("agent_config", {})
    if isinstance(agent_config, dict) and "model" in agent_config:
        config["model"] = agent_config["model"]
        logger.info(f"Model from agent_config: {config['model']}")

    # Extract full OSWorld task if provided (from Supabase)
    if "osworld_task" in task.metadata:
        config["osworld_task"] = task.metadata["osworld_task"]
        logger.info(f"OSWorld task loaded from metadata (Supabase)")

    # Extract callback_url for real-time updates
    if "callback_url" in task.metadata:
        config["callback_url"] = task.metadata["callback_url"]
        logger.info(f"Callback URL configured: {config['callback_url']}")

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
    # Lazy import to speed up module startup (heavy dependencies in OSWorld)
    from desktop_env.controllers.setup import SetupController

    logger.info(f"Executing OSWorld task setup...")

    try:
        # Create cache directory for SetupController
        cache_dir = Path("cache")
        cache_dir.mkdir(exist_ok=True)
        logger.info(f"Created cache directory: {cache_dir.absolute()}")

        # Create SetupController
        # Note: Use port 9222 because tasks use socat to forward 9222->1337
        # Chrome binds to localhost:1337, socat binds to 0.0.0.0:9222
        setup_controller = SetupController(
            vm_ip=vm_ip,
            server_port=5000,
            chromium_port=9222
        )

        # Kill GNOME keyring daemon to prevent password prompts blocking tasks
        # This runs before any task setup to ensure keyring doesn't interfere
        keyring_kill_config = [
            {
                "type": "execute",
                "parameters": {
                    "command": ["pkill", "-f", "gnome-keyring-daemon"],
                    "shell": False
                }
            }
        ]
        logger.info("Killing GNOME keyring daemon to prevent password prompts...")
        setup_controller.setup(keyring_kill_config)

        if not task_config:
            logger.info("No additional setup configuration - skipping setup phase")
            return True

        logger.info(f"Executing {len(task_config)} setup steps...")

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
    pooled_vm = None  # Track pooled VM for release
    callback_url = config.get("callback_url")

    try:
        # Step 1: Get VM (from pool or create fresh)
        if VM_POOL_ENABLED:
            # Use VM pool with snapshot-based reset
            logger.info("Acquiring VM from pool...")
            await _push_event_to_webui(callback_url, {
                "type": "vm_pool_acquiring",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Acquiring VM from pool..."
            })

            pool = await get_vm_pool()
            pooled_vm = await pool.acquire_vm(assessment_id)

            vm_info = {
                "vm_name": pooled_vm.vm_name,
                "vm_ip": pooled_vm.vm_ip,
                "pool_vm_id": pooled_vm.vm_id,
                "from_pool": True,
                "tasks_completed": pooled_vm.tasks_completed,
            }
            logger.info(f"Acquired VM from pool: {vm_info['vm_name']} at {vm_info['vm_ip']}")

            await _push_event_to_webui(callback_url, {
                "type": "vm_acquired_from_pool",
                "timestamp": datetime.utcnow().isoformat(),
                "vm_name": vm_info['vm_name'],
                "vm_ip": vm_info['vm_ip'],
                "tasks_completed": pooled_vm.tasks_completed,
            })

            # Pool VM is already ready
            await _push_event_to_webui(callback_url, {
                "type": "vm_ready",
                "timestamp": datetime.utcnow().isoformat(),
                "vm_ip": vm_info["vm_ip"],
                "from_pool": True,
                "message": "VM acquired from pool and ready"
            })
        else:
            # Original behavior: create fresh VM
            logger.info("Creating VM...")

            await _push_event_to_webui(callback_url, {
                "type": "vm_creation_started",
                "timestamp": datetime.utcnow().isoformat(),
                "vm_image": config.get("vm_image", "osworld-golden-v12-gnome")
            })

            vm_info = await asyncio.to_thread(
                get_vm_manager().create_vm,
                assessment_id
            )
            vm_info["from_pool"] = False
            logger.info(f"VM created: {vm_info['vm_name']} at {vm_info['vm_ip']}")

            await _push_event_to_webui(callback_url, {
                "type": "vm_created",
                "timestamp": datetime.utcnow().isoformat(),
                "vm_name": vm_info['vm_name'],
                "vm_ip": vm_info['vm_ip']
            })

            # Step 2: Wait for VM ready (only for fresh VMs)
            logger.info("Waiting for VM to be ready (timeout: 600s)...")

            await _push_event_to_webui(callback_url, {
                "type": "vm_waiting",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Waiting for VM to boot and OSWorld server to start (up to 10 minutes)"
            })

            vm_ready = await asyncio.to_thread(
                get_vm_manager().wait_for_vm_ready,
                vm_info["vm_ip"],
                timeout=600
            )

            if not vm_ready:
                logger.error(f"VM {vm_info['vm_ip']} did not become ready within 600 seconds")
                logger.info(f"Will cleanup VM {assessment_id} due to timeout")
                raise TimeoutError(f"VM {vm_info['vm_ip']} failed to become ready within 600 seconds (timeout)")

            await _push_event_to_webui(callback_url, {
            "type": "vm_ready",
            "timestamp": datetime.utcnow().isoformat(),
            "vm_ip": vm_info["vm_ip"],
            "message": "VM is ready and OSWorld server is responding"
        })

        # Step 2.5: Execute OSWorld task setup
        # Use OSWorld task from metadata (Supabase) if available, otherwise try to load from files
        osworld_task = config.get("osworld_task")
        if not osworld_task:
            try:
                logger.info("Loading full OSWorld task configuration from files...")
                osworld_task = get_task_executor().load_task(
                    config["osworld_task_id"],
                    domain=config.get("domain")
                )
            except FileNotFoundError:
                logger.warning(
                    f"Full OSWorld task not found in files for {config['osworld_task_id']} - "
                    "skipping setup phase"
                )
        else:
            logger.info("Using OSWorld task from Supabase metadata")

        # Execute setup if task has config
        if osworld_task and "config" in osworld_task and osworld_task["config"]:
            try:
                # Educational event: Setup started
                await _push_event_to_webui(callback_url, {
                    "type": "setup_started",
                    "timestamp": datetime.utcnow().isoformat(),
                    "num_steps": len(osworld_task["config"]),
                    "message": f"Running OSWorld task setup ({len(osworld_task['config'])} steps)"
                })

                setup_success = await asyncio.to_thread(
                    _execute_osworld_setup,
                    vm_info["vm_ip"],
                    osworld_task["config"]
                )

                if not setup_success:
                    raise Exception("Task setup failed")

                # Educational event: Setup completed
                await _push_event_to_webui(callback_url, {
                    "type": "setup_completed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": "OSWorld task setup completed successfully"
                })

                # Wait for environment to stabilize after setup
                # OSWorld runners use 60s, but we use 30s as a balance
                if SETUP_STABILIZATION_WAIT > 0:
                    logger.info(f"Waiting {SETUP_STABILIZATION_WAIT}s for environment to stabilize after setup...")
                    await _push_event_to_webui(callback_url, {
                        "type": "stabilization_wait",
                        "timestamp": datetime.utcnow().isoformat(),
                        "duration_sec": SETUP_STABILIZATION_WAIT,
                        "message": f"Waiting {SETUP_STABILIZATION_WAIT}s for environment to stabilize"
                    })
                    await asyncio.sleep(SETUP_STABILIZATION_WAIT)
                    logger.info("Stabilization wait complete")

            except Exception as e:
                logger.error(f"Setup phase failed: {e}")
                raise
        else:
            logger.info("No setup config in task - skipping setup phase")

        # Step 3: Send task to white agent with tool descriptions (Approach II)
        logger.info("Sending task to white agent with tool descriptions...")

        # Build tool descriptions for OSWorld API
        tools = _build_osworld_tool_descriptions(vm_info["vm_ip"])

        # Get task description from osworld_task (loaded from Supabase or files)
        if osworld_task and "instruction" in osworld_task:
            task = {"instruction": osworld_task["instruction"]}
        else:
            # Fallback if no instruction available
            task = {"instruction": "Complete the task"}

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

        # Educational event: White agent execution started
        await _push_event_to_webui(callback_url, {
            "type": "white_agent_started",
            "timestamp": datetime.utcnow().isoformat(),
            "white_agent_url": config["white_agent_url"],
            "task_instruction": task.get("instruction", "")[:200],  # First 200 chars
            "max_steps": config.get("max_steps", 15),
            "message": "Sending task to white agent for execution"
        })

        result = await _execute_with_white_agent(
            white_agent_task,
            config["white_agent_url"],
            vm_info["vm_ip"],
            artifacts_dir,
            config.get("max_steps", 15),
            callback_url,  # Pass callback_url for event pushing
            config.get("model")  # Pass model for white agent
        )

        # Educational event: White agent execution completed
        await _push_event_to_webui(callback_url, {
            "type": "white_agent_completed",
            "timestamp": datetime.utcnow().isoformat(),
            "steps_taken": result.get("steps", 0),
            "time_sec": result.get("time_sec", 0),
            "message": f"White agent completed execution in {result.get('steps', 0)} steps"
        })

        # Step 4: Evaluate task success using OSWorld evaluation system
        if osworld_task and "evaluator" in osworld_task:
            # Wait for environment to settle before evaluation
            # OSWorld runners use 20s to let UI animations complete
            if EVAL_STABILIZATION_WAIT > 0:
                logger.info(f"Waiting {EVAL_STABILIZATION_WAIT}s for environment to settle before evaluation...")
                await asyncio.sleep(EVAL_STABILIZATION_WAIT)

            logger.info("Running OSWorld evaluation...")

            # Educational event: Evaluation started
            await _push_event_to_webui(callback_url, {
                "type": "evaluation_started",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Running OSWorld benchmark evaluation to verify task completion"
            })

            try:
                from green_agent.osworld_evaluator import evaluate_task_with_llm_fallback

                # Extract last action from trajectory for infeasible task evaluation
                last_action = None
                if result.get("trajectory"):
                    last_entry = result["trajectory"][-1]
                    raw_actions = (
                        last_entry
                        .get("message_data", {})
                        .get("payload", {})
                        .get("metadata", {})
                        .get("raw_actions", "")
                    )
                    raw_actions_str = str(raw_actions).upper()
                    if "FAIL" in raw_actions_str:
                        last_action = "FAIL"
                    elif "DONE" in raw_actions_str:
                        last_action = "DONE"
                    logger.info(f"Extracted last_action from trajectory: {last_action}")

                # Run OSWorld evaluation with enhanced metrics and LLM fallback
                steps_taken = result.get("steps", 0)
                trajectory = result.get("trajectory", [])
                max_steps = config.get("max_steps", 15)

                # Extract screenshots for LLM fallback
                screenshot_before = result.get("screenshot_before")
                screenshot_after = result.get("screenshot_after")

                # LLM fallback configuration
                enable_llm_fallback = config.get("enable_llm_fallback", True)
                llm_provider = config.get("llm_judge_provider", "openai")
                llm_model = config.get("llm_judge_model")  # None = use default
                llm_confidence_threshold = config.get("llm_judge_confidence", 0.7)

                if enable_llm_fallback:
                    logger.info(f"LLM fallback enabled: provider={llm_provider}, "
                               f"model={llm_model or 'default'}, threshold={llm_confidence_threshold}")

                evaluation_result = await evaluate_task_with_llm_fallback(
                    vm_ip=vm_info["vm_ip"],
                    evaluator_config=osworld_task["evaluator"],
                    task_id=osworld_task.get("id", config["osworld_task_id"]),
                    task_instruction=osworld_task.get("instruction", ""),
                    server_port=5000,
                    cache_dir="cache",
                    last_action=last_action,
                    steps_taken=steps_taken,
                    trajectory=trajectory,
                    max_steps=max_steps,
                    # LLM fallback options
                    enable_llm_fallback=enable_llm_fallback,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                    llm_confidence_threshold=llm_confidence_threshold,
                    screenshot_before=screenshot_before,
                    screenshot_after=screenshot_after
                )

                # evaluation_result is always a dict from evaluate_task_with_llm_fallback
                evaluation_score = evaluation_result.get("score", 0.0)
                base_score = evaluation_result.get("base_score", evaluation_score)
                efficiency_data = evaluation_result.get("efficiency", {})
                trajectory_analysis = evaluation_result.get("trajectory_analysis", {})
                eval_method = evaluation_result.get("evaluation_method", "rule_based")
                llm_judgment = evaluation_result.get("llm_judgment")

                logger.info(f"OSWorld evaluation: base_score={base_score:.2f}, "
                           f"final_score={evaluation_score:.2f}, "
                           f"method={eval_method}, steps={steps_taken}")

                # Store enhanced evaluation data
                result["evaluation_details"] = {
                    "base_score": base_score,
                    "adjusted_score": evaluation_score,
                    "efficiency": efficiency_data,
                    "trajectory_analysis": trajectory_analysis,
                    "evaluation_method": eval_method
                }

                # Include LLM judgment if available
                if llm_judgment:
                    result["evaluation_details"]["llm_judgment"] = llm_judgment
                    logger.info(f"LLM judgment: success={llm_judgment.get('success')}, "
                               f"confidence={llm_judgment.get('confidence', 0):.2f}, "
                               f"reasoning={llm_judgment.get('reasoning', '')[:100]}...")

                # Update success based on evaluation (score >= 1.0 = success)
                result["success"] = 1 if evaluation_score >= 1.0 else 0
                result["evaluation_score"] = evaluation_score
                result["evaluation_method"] = eval_method

                if result["success"] == 0 and "failure_reason" not in result:
                    result["failure_reason"] = f"evaluation_failed_score_{evaluation_score}"

                # Educational event: Evaluation completed
                await _push_event_to_webui(callback_url, {
                    "type": "evaluation_completed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": result["success"] == 1,
                    "evaluation_score": evaluation_score,
                    "base_score": base_score,
                    "efficiency_ratio": efficiency_data.get("efficiency_ratio") if efficiency_data else None,
                    "evaluation_method": eval_method,
                    "llm_override": eval_method == "llm_judge_override",
                    "message": f"Evaluation {'passed' if result['success'] == 1 else 'failed'} (score: {evaluation_score:.2f}, method: {eval_method})"
                })

            except Exception as e:
                logger.error(f"Evaluation error: {e}", exc_info=True)
                # Mark as failure if evaluation fails - don't trust white agent
                result["success"] = 0
                result["evaluation_error"] = str(e)
                result["failure_reason"] = f"evaluation_exception: {str(e)}"
                result["evaluation_method"] = "osworld_benchmark_failed"
                logger.error("Evaluation failed - marking assessment as failed")

                # Educational event: Evaluation error
                await _push_event_to_webui(callback_url, {
                    "type": "evaluation_error",
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e),
                    "message": f"Evaluation failed: {str(e)}"
                })
        else:
            logger.error("No evaluator config found - cannot validate task completion!")
            result["success"] = 0
            result["evaluation_method"] = "no_evaluator"
            result["failure_reason"] = "missing_evaluator_config"
            logger.error("Task marked as failed due to missing evaluator")

            # Educational event: No evaluator
            await _push_event_to_webui(callback_url, {
                "type": "evaluation_error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": "missing_evaluator_config",
                "message": "No evaluator configuration found for this task"
            })

        # Step 5: Add metadata
        result["vm_cost"] = get_vm_manager().get_vm_cost(time.time() - start_time)
        result["vm_info"] = vm_info
        result["assessment_id"] = assessment_id
        result["total_time_sec"] = time.time() - start_time

        logger.info(f"Assessment completed: success={result.get('success')}")

        # Educational event: Assessment summary
        await _push_event_to_webui(callback_url, {
            "type": "assessment_summary",
            "timestamp": datetime.utcnow().isoformat(),
            "success": result.get("success") == 1,
            "steps": result.get("steps", 0),
            "time_sec": result["total_time_sec"],
            "vm_cost": result["vm_cost"],
            "evaluation_score": result.get("evaluation_score"),
            "message": f"Assessment {'completed successfully' if result.get('success') == 1 else 'failed'}"
        })

        # Step 5: Cleanup VM (release to pool or delete)
        logger.info("Cleaning up VM...")

        if VM_POOL_ENABLED and pooled_vm:
            # Release VM back to pool for snapshot restore
            await _push_event_to_webui(callback_url, {
                "type": "vm_releasing_to_pool",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Releasing VM back to pool for restore"
            })

            pool = await get_vm_pool()
            await pool.release_vm(pooled_vm.vm_id, success=True)

            await _push_event_to_webui(callback_url, {
                "type": "vm_released_to_pool",
                "timestamp": datetime.utcnow().isoformat(),
                "vm_id": pooled_vm.vm_id,
            })
        else:
            # Delete VM (original behavior)
            await _push_event_to_webui(callback_url, {
                "type": "vm_cleanup_started",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Deleting VM and cleaning up resources"
            })

            await asyncio.to_thread(
                get_vm_manager().delete_vm,
                assessment_id
            )

        # Educational event: Assessment completed
        await _push_event_to_webui(callback_url, {
            "type": "assessment_completed",
            "timestamp": datetime.utcnow().isoformat(),
            "success": result.get("success") == 1,
            "message": "Assessment workflow completed"
        })

        active_assessments[assessment_id]["status"] = "completed"
        return result

    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"Assessment failed ({error_type}): {e}", exc_info=True)

        # Cleanup VM on failure (release to pool or delete)
        if VM_POOL_ENABLED and pooled_vm:
            try:
                logger.info(f"Releasing VM {pooled_vm.vm_id} to pool due to failure...")
                pool = await get_vm_pool()
                await pool.release_vm(pooled_vm.vm_id, success=False)
                logger.info(f"VM {pooled_vm.vm_id} released to pool")
            except Exception as cleanup_error:
                logger.error(f"Pool release failed for {pooled_vm.vm_id}: {cleanup_error}", exc_info=True)
        elif vm_info:
            try:
                logger.info(f"Cleaning up VM {vm_info['vm_name']} ({assessment_id}) due to failure...")
                await asyncio.to_thread(
                    get_vm_manager().delete_vm,
                    assessment_id
                )
                logger.info(f"VM {vm_info['vm_name']} successfully cleaned up")
            except Exception as cleanup_error:
                logger.error(f"VM cleanup failed for {assessment_id}: {cleanup_error}", exc_info=True)

        active_assessments[assessment_id]["status"] = "failed"
        active_assessments[assessment_id]["error"] = str(e)
        active_assessments[assessment_id]["error_type"] = error_type

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

    NOTE: This function still accepts vm_ip for internal routing but does NOT
    expose infrastructure details in the tool descriptions returned to agents.

    Returns list of tool specifications compatible with LLM function calling.
    """
    # Internal endpoint mapping (not exposed to agents)
    osworld_base_url = f"http://{vm_ip}:5000"
    _internal_endpoints = {
        "screenshot": (f"{osworld_base_url}/screenshot", "GET"),
        "execute_python": (f"{osworld_base_url}/execute", "POST"),
        "execute_command": (f"{osworld_base_url}/execute", "POST"),
        "click": (f"{osworld_base_url}/action", "POST"),
        "double_click": (f"{osworld_base_url}/action", "POST"),
        "right_click": (f"{osworld_base_url}/action", "POST"),
        "type_text": (f"{osworld_base_url}/action", "POST"),
        "hotkey": (f"{osworld_base_url}/action", "POST"),
        "scroll": (f"{osworld_base_url}/action", "POST"),
        "move": (f"{osworld_base_url}/action", "POST"),
        "wait": (None, "LOCAL")
    }

    return [
        {
            "name": "screenshot",
            "description": "Capture a screenshot of the current desktop state. Use this to observe what's visible on the screen before deciding on actions.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            },
            "returns": {
                "content_type": "image/png",
                "schema": {"type": "string", "format": "binary"},
                "description": "PNG image of the desktop (base64-encoded in JSON responses)"
            },
            "examples": [
                {
                    "description": "Capture current screen state",
                    "input": {},
                    "output": "PNG image data"
                }
            ],
            "validation": {
                "parameter_rules": {}
            },
            "metadata": {
                "category": "observation",
                "tags": ["screen", "vision", "observation"],
                "complexity": "simple",
                "safety_level": "safe"
            }
        },
        {
            "name": "execute_python",
            "description": "Execute Python code in the desktop environment. Use for complex automation tasks that require logic, loops, or API calls. The code runs with desktop automation libraries available (pyautogui, subprocess, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute. Must be valid Python 3 syntax.",
                        "minLength": 1,
                        "maxLength": 50000
                    }
                },
                "required": ["code"]
            },
            "returns": {
                "content_type": "application/json",
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["success", "error"]},
                        "stdout": {"type": "string"},
                        "stderr": {"type": "string"},
                        "exit_code": {"type": "integer"}
                    }
                },
                "description": "Execution result with stdout, stderr, and exit code"
            },
            "examples": [
                {
                    "description": "Print hello world",
                    "input": {"code": "print('Hello, World!')"},
                    "output": {"status": "success", "stdout": "Hello, World!\n", "stderr": "", "exit_code": 0}
                }
            ],
            "validation": {
                "parameter_rules": {
                    "code": {
                        "validator": "text",
                        "bounds": {"min": 1, "max": 50000}
                    }
                }
            },
            "metadata": {
                "category": "action",
                "tags": ["python", "automation", "advanced"],
                "complexity": "complex",
                "safety_level": "requires_validation"
            }
        },
        {
            "name": "execute_command",
            "description": "Execute a shell command or launch an application. Use this to start programs, run system commands, or perform file operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute (e.g., 'google-chrome', 'ls -la')",
                        "minLength": 1,
                        "maxLength": 10000
                    },
                    "shell": {
                        "type": "boolean",
                        "description": "Whether to run command through shell interpreter",
                        "default": True
                    }
                },
                "required": ["command"]
            },
            "returns": {
                "content_type": "application/json",
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["success", "error"]},
                        "stdout": {"type": "string"},
                        "stderr": {"type": "string"},
                        "exit_code": {"type": "integer"}
                    }
                },
                "description": "Command execution result with output streams"
            },
            "examples": [
                {
                    "description": "Launch Chrome browser",
                    "input": {"command": "google-chrome"},
                    "output": {"status": "success", "exit_code": 0}
                }
            ],
            "validation": {
                "parameter_rules": {
                    "command": {
                        "validator": "text",
                        "bounds": {"min": 1, "max": 10000}
                    }
                }
            },
            "metadata": {
                "category": "action",
                "tags": ["command", "shell", "application"],
                "complexity": "moderate",
                "safety_level": "requires_validation"
            }
        },
        {
            "name": "click",
            "description": "Perform a mouse click at specific screen coordinates. Typical screen resolution is 1920x1080 pixels, with (0,0) at the top-left corner.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "integer",
                        "description": "Horizontal position in pixels from left edge (0-1920)",
                        "minimum": 0,
                        "maximum": 1920
                    },
                    "y": {
                        "type": "integer",
                        "description": "Vertical position in pixels from top edge (0-1080)",
                        "minimum": 0,
                        "maximum": 1080
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
            "returns": {
                "content_type": "application/json",
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["success", "error"]},
                        "message": {"type": "string"}
                    }
                },
                "description": "Confirmation of click execution"
            },
            "examples": [
                {
                    "description": "Click center of screen",
                    "input": {"x": 960, "y": 540},
                    "output": {"status": "success", "message": "Clicked at (960, 540)"}
                }
            ],
            "validation": {
                "parameter_rules": {
                    "x": {
                        "validator": "coordinate",
                        "bounds": {"min": 0, "max": 1920}
                    },
                    "y": {
                        "validator": "coordinate",
                        "bounds": {"min": 0, "max": 1080}
                    }
                }
            },
            "metadata": {
                "category": "action",
                "tags": ["mouse", "click", "interaction"],
                "complexity": "simple",
                "safety_level": "safe"
            }
        },
        {
            "name": "double_click",
            "description": "Perform a double mouse click at specific screen coordinates. Useful for opening files, selecting words, or activating UI elements that require double-clicking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "integer",
                        "description": "Horizontal position in pixels from left edge (0-1920)",
                        "minimum": 0,
                        "maximum": 1920
                    },
                    "y": {
                        "type": "integer",
                        "description": "Vertical position in pixels from top edge (0-1080)",
                        "minimum": 0,
                        "maximum": 1080
                    }
                },
                "required": ["x", "y"]
            },
            "returns": {
                "content_type": "application/json",
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["success", "error"]},
                        "message": {"type": "string"}
                    }
                },
                "description": "Confirmation of double-click execution"
            },
            "examples": [
                {
                    "description": "Double-click to open a file",
                    "input": {"x": 500, "y": 300},
                    "output": {"status": "success", "message": "Double-clicked at (500, 300)"}
                }
            ],
            "validation": {
                "parameter_rules": {
                    "x": {
                        "validator": "coordinate",
                        "bounds": {"min": 0, "max": 1920}
                    },
                    "y": {
                        "validator": "coordinate",
                        "bounds": {"min": 0, "max": 1080}
                    }
                }
            },
            "metadata": {
                "category": "action",
                "tags": ["mouse", "double-click", "interaction"],
                "complexity": "simple",
                "safety_level": "safe"
            }
        },
        {
            "name": "right_click",
            "description": "Perform a right mouse click at specific screen coordinates. Opens context menus and shows additional options for UI elements.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "integer",
                        "description": "Horizontal position in pixels from left edge (0-1920)",
                        "minimum": 0,
                        "maximum": 1920
                    },
                    "y": {
                        "type": "integer",
                        "description": "Vertical position in pixels from top edge (0-1080)",
                        "minimum": 0,
                        "maximum": 1080
                    }
                },
                "required": ["x", "y"]
            },
            "returns": {
                "content_type": "application/json",
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["success", "error"]},
                        "message": {"type": "string"}
                    }
                },
                "description": "Confirmation of right-click execution"
            },
            "examples": [
                {
                    "description": "Right-click to open context menu",
                    "input": {"x": 600, "y": 400},
                    "output": {"status": "success", "message": "Right-clicked at (600, 400)"}
                }
            ],
            "validation": {
                "parameter_rules": {
                    "x": {
                        "validator": "coordinate",
                        "bounds": {"min": 0, "max": 1920}
                    },
                    "y": {
                        "validator": "coordinate",
                        "bounds": {"min": 0, "max": 1080}
                    }
                }
            },
            "metadata": {
                "category": "action",
                "tags": ["mouse", "right-click", "context-menu"],
                "complexity": "simple",
                "safety_level": "safe"
            }
        },
        {
            "name": "scroll",
            "description": "Scroll the mouse wheel up or down. Positive values scroll up, negative values scroll down. Use this for scrolling through web pages, documents, or lists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "integer",
                        "description": "Scroll amount in 'clicks'. Positive scrolls up, negative scrolls down. Typical values: 3 for small scroll, 10 for page scroll.",
                        "minimum": -100,
                        "maximum": 100
                    },
                    "x": {
                        "type": "integer",
                        "description": "Optional X coordinate to scroll at (defaults to current position)",
                        "minimum": 0,
                        "maximum": 1920
                    },
                    "y": {
                        "type": "integer",
                        "description": "Optional Y coordinate to scroll at (defaults to current position)",
                        "minimum": 0,
                        "maximum": 1080
                    }
                },
                "required": ["amount"]
            },
            "returns": {
                "content_type": "application/json",
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["success", "error"]},
                        "message": {"type": "string"}
                    }
                },
                "description": "Confirmation of scroll execution"
            },
            "examples": [
                {
                    "description": "Scroll down a page",
                    "input": {"amount": -5},
                    "output": {"status": "success", "message": "Scrolled -5 clicks"}
                },
                {
                    "description": "Scroll up",
                    "input": {"amount": 3},
                    "output": {"status": "success", "message": "Scrolled 3 clicks"}
                }
            ],
            "validation": {
                "parameter_rules": {
                    "amount": {
                        "validator": "integer",
                        "bounds": {"min": -100, "max": 100}
                    }
                }
            },
            "metadata": {
                "category": "action",
                "tags": ["mouse", "scroll", "navigation"],
                "complexity": "simple",
                "safety_level": "safe"
            }
        },
        {
            "name": "type_text",
            "description": "Type text using keyboard input. The text will be entered at the current cursor position. Use this for filling forms, entering search queries, or writing text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to type (supports alphanumeric, spaces, and common punctuation)",
                        "minLength": 1,
                        "maxLength": 10000
                    }
                },
                "required": ["text"]
            },
            "returns": {
                "content_type": "application/json",
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["success", "error"]},
                        "characters_typed": {"type": "integer"},
                        "message": {"type": "string"}
                    }
                },
                "description": "Confirmation of text entry"
            },
            "examples": [
                {
                    "description": "Type a search query",
                    "input": {"text": "machine learning papers"},
                    "output": {"status": "success", "characters_typed": 24}
                }
            ],
            "validation": {
                "parameter_rules": {
                    "text": {
                        "validator": "text",
                        "bounds": {"min": 1, "max": 10000}
                    }
                }
            },
            "metadata": {
                "category": "action",
                "tags": ["keyboard", "text", "input"],
                "complexity": "simple",
                "safety_level": "safe"
            }
        },
        {
            "name": "hotkey",
            "description": "Press a keyboard hotkey combination (e.g., Ctrl+C for copy, Alt+Tab to switch windows). Common modifiers: ctrl, alt, shift, cmd/win.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of keys to press together. First keys are modifiers (ctrl, alt, shift), last key is the action key (c, v, tab, etc.)",
                        "minItems": 1,
                        "maxItems": 4
                    }
                },
                "required": ["keys"]
            },
            "returns": {
                "content_type": "application/json",
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["success", "error"]},
                        "keys_pressed": {"type": "array", "items": {"type": "string"}},
                        "message": {"type": "string"}
                    }
                },
                "description": "Confirmation of hotkey execution"
            },
            "examples": [
                {
                    "description": "Copy text (Ctrl+C)",
                    "input": {"keys": ["ctrl", "c"]},
                    "output": {"status": "success", "keys_pressed": ["ctrl", "c"]}
                },
                {
                    "description": "Switch window (Alt+Tab)",
                    "input": {"keys": ["alt", "tab"]},
                    "output": {"status": "success", "keys_pressed": ["alt", "tab"]}
                }
            ],
            "validation": {
                "parameter_rules": {
                    "keys": {
                        "validator": "keys",
                        "allowed_values": [
                            "ctrl", "alt", "shift", "cmd", "win",
                            "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
                            "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
                            "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
                            "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
                            "enter", "tab", "space", "backspace", "delete", "escape",
                            "up", "down", "left", "right",
                            "home", "end", "pageup", "pagedown"
                        ]
                    }
                }
            },
            "metadata": {
                "category": "action",
                "tags": ["keyboard", "hotkey", "shortcut"],
                "complexity": "moderate",
                "safety_level": "safe"
            }
        },
        {
            "name": "move",
            "description": "Move the mouse cursor to a specific position. Useful for waking up screens from sleep or positioning before other actions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "integer",
                        "description": "X coordinate (pixels from left edge)",
                        "minimum": 0
                    },
                    "y": {
                        "type": "integer",
                        "description": "Y coordinate (pixels from top edge)",
                        "minimum": 0
                    }
                },
                "required": ["x", "y"]
            },
            "returns": {
                "content_type": "application/json",
                "schema": {"type": "object"},
                "description": "Empty success response"
            },
            "examples": [
                {
                    "description": "Move mouse to center of screen",
                    "input": {"x": 960, "y": 540},
                    "output": {}
                }
            ],
            "validation": {
                "parameter_rules": {
                    "x": {"validator": "integer", "bounds": {"min": 0, "max": 7680}},
                    "y": {"validator": "integer", "bounds": {"min": 0, "max": 4320}}
                }
            },
            "metadata": {
                "category": "action",
                "tags": ["mouse", "cursor", "positioning"],
                "complexity": "simple",
                "safety_level": "safe"
            }
        },
        {
            "name": "wait",
            "description": "Wait for a specified duration. Useful for allowing UI to update between actions or waiting for applications to load.",
            "parameters": {
                "type": "object",
                "properties": {
                    "duration": {
                        "type": "number",
                        "description": "Duration to wait in seconds (0.1 to 30.0)",
                        "minimum": 0.1,
                        "maximum": 30.0,
                        "default": 1.0
                    }
                },
                "required": []
            },
            "returns": {
                "content_type": "application/json",
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["success"]},
                        "duration": {"type": "number"}
                    }
                },
                "description": "Confirmation of wait completion"
            },
            "examples": [
                {
                    "description": "Wait 2 seconds",
                    "input": {"duration": 2.0},
                    "output": {"status": "success", "duration": 2.0}
                }
            ],
            "validation": {
                "parameter_rules": {
                    "duration": {
                        "validator": "number",
                        "bounds": {"min": 0.1, "max": 30.0}
                    }
                }
            },
            "metadata": {
                "category": "utility",
                "tags": ["timing", "delay", "wait"],
                "complexity": "simple",
                "safety_level": "safe"
            }
        }
    ]


def _format_task_message_with_tools(task: Dict[str, Any], tools: list[Dict[str, Any]]) -> str:
    """
    Format task message with embedded tool descriptions

    This follows the Tau-Bench/AgentBeats pattern where tools are described
    in natural language within the task message, with JSON examples showing
    the expected format.
    """
    task_instruction = task.get("instruction", "Complete the task")

    # Build tool documentation string
    tools_doc = "# Available Tools\n\n"
    tools_doc += "You have access to the following tools for desktop automation:\n\n"

    for tool in tools:
        tools_doc += f"## {tool['name']}\n\n"
        tools_doc += f"{tool['description']}\n\n"

        # Parameters
        if tool['parameters']['properties']:
            tools_doc += "**Parameters:**\n"
            for param_name, param_spec in tool['parameters']['properties'].items():
                required_marker = " (required)" if param_name in tool['parameters'].get('required', []) else " (optional)"
                param_type = param_spec['type']

                # Add bounds/constraints info
                constraints = []
                if 'minimum' in param_spec:
                    constraints.append(f"min: {param_spec['minimum']}")
                if 'maximum' in param_spec:
                    constraints.append(f"max: {param_spec['maximum']}")
                if 'enum' in param_spec:
                    constraints.append(f"values: {', '.join(param_spec['enum'])}")
                if 'default' in param_spec:
                    constraints.append(f"default: {param_spec['default']}")

                constraint_str = f" [{', '.join(constraints)}]" if constraints else ""

                tools_doc += f"- `{param_name}` ({param_type}){required_marker}{constraint_str}: {param_spec.get('description', '')}\n"
        else:
            tools_doc += "**Parameters:** None\n"

        tools_doc += "\n"

        # Returns
        if 'returns' in tool:
            returns_desc = tool['returns'].get('description', 'Action result')
            tools_doc += f"**Returns:** {returns_desc}\n\n"

        # Examples
        if 'examples' in tool and tool['examples']:
            tools_doc += "**Examples:**\n"
            for example in tool['examples'][:2]:  # Show max 2 examples
                example_desc = example.get('description', 'Example usage')
                example_input = example.get('input', {})
                tools_doc += f"- {example_desc}:\n"
                tools_doc += f"  ```json\n"
                if example_input:
                    tools_doc += f'  {{"op": "{tool["name"]}", "args": {json.dumps(example_input)}}}\n'
                else:
                    tools_doc += f'  {{"op": "{tool["name"]}"}}\n'
                tools_doc += f"  ```\n"
            tools_doc += "\n"

    # Add format specification
    tools_doc += "\n---\n\n"
    tools_doc += "**Action Format:** Return actions as JSON with `op` (operation name) and `args` (parameters) fields:\n"
    tools_doc += "```json\n"
    tools_doc += '{"op": "tool_name", "args": {"param1": "value1", "param2": "value2"}}\n'
    tools_doc += "```\n\n"

    # Combine task instruction with tools
    message = f"""
{tools_doc}

# Task

{task_instruction}

**Instructions:**
1. Take a screenshot first to observe the current state
2. Analyze what you see and decide on the appropriate action
3. Execute actions using the format shown above
4. After important actions, take another screenshot to verify results
5. Continue until the task is complete
6. When finished, return {{"op": "done"}}

You have a maximum of 15 steps to complete the task.
""".strip()

    return message


def _validate_white_agent_response(response_data: Dict[str, Any], tools: list[Dict[str, Any]]) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validate white agent response structure and extract action

    Validates:
    - Response has required A2A fields (role, content, metadata)
    - metadata.action exists and has required structure
    - Action op is valid (matches a known tool)
    - Action args match tool parameter requirements

    Args:
        response_data: Parsed JSON response from white agent
        tools: List of available tool specifications

    Returns:
        tuple of (is_valid, error_message, action)
        - is_valid: True if response is valid
        - error_message: Error description if invalid, None otherwise
        - action: Extracted action dict if valid, None otherwise
    """
    # Check top-level A2A message structure
    if not isinstance(response_data, dict):
        return False, "Response must be a JSON object", None

    if "role" not in response_data:
        return False, "Response missing required field: role", None

    if "content" not in response_data:
        return False, "Response missing required field: content", None

    if "metadata" not in response_data:
        return False, "Response missing required field: metadata", None

    metadata = response_data["metadata"]
    if not isinstance(metadata, dict):
        return False, "metadata must be an object", None

    # Check for action in metadata
    if "action" not in metadata:
        # Check if there's an error instead
        if "error" in metadata:
            return False, f"White agent reported error: {metadata['error']}", None
        return False, "Response metadata missing required field: action", None

    action = metadata["action"]
    if not isinstance(action, dict):
        return False, "action must be an object", None

    # Validate action structure
    if "op" not in action:
        return False, "action missing required field: op (operation name)", None

    op = action["op"]
    if not isinstance(op, str):
        return False, "action.op must be a string", None

    # Special case: "done" action
    if op == "done":
        return True, None, action

    # Check if op matches a known tool
    tool_names = [t["name"] for t in tools]
    if op not in tool_names:
        return False, f"Unknown operation: {op}. Valid operations: {', '.join(tool_names)}", None

    # Find the tool specification
    tool_spec = next((t for t in tools if t["name"] == op), None)
    if not tool_spec:
        return False, f"Tool specification not found for: {op}", None

    # Validate action args
    args = action.get("args", {})
    if not isinstance(args, dict):
        return False, f"action.args must be an object, got {type(args).__name__}", None

    # Check required parameters
    required_params = tool_spec["parameters"].get("required", [])
    for param in required_params:
        if param not in args:
            return False, f"Missing required parameter for {op}: {param}", None

    # Validate parameter types (basic validation)
    properties = tool_spec["parameters"].get("properties", {})
    for param_name, param_value in args.items():
        if param_name not in properties:
            # Warn about unknown parameters but don't fail
            logger.warning(f"Unknown parameter {param_name} for {op}")
            continue

        param_spec = properties[param_name]
        expected_type = param_spec["type"]

        # Type checking
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }

        if expected_type in type_map:
            expected_python_type = type_map[expected_type]
            if not isinstance(param_value, expected_python_type):
                return False, f"Parameter {param_name} must be {expected_type}, got {type(param_value).__name__}", None

    return True, None, action


def _validate_white_agent_action(action: Dict[str, Any], tools: list[Dict[str, Any]]) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validate white agent action structure (for stateless /decide endpoint).

    This is a simpler version of _validate_white_agent_response that validates
    the action directly (not wrapped in A2A message format).

    Validates:
    - Action has required structure (op field)
    - Action op is valid (matches a known tool or is "done"/"error")
    - Action args match tool parameter requirements

    Args:
        action: Action dict from /decide response
        tools: List of available tool specifications

    Returns:
        tuple of (is_valid, error_message, action)
        - is_valid: True if action is valid
        - error_message: Error description if invalid, None otherwise
        - action: The validated action dict if valid, None otherwise
    """
    if not isinstance(action, dict):
        return False, "Action must be a JSON object", None

    # Validate action structure
    if "op" not in action:
        return False, "Action missing required field: op (operation name)", None

    op = action["op"]
    if not isinstance(op, str):
        return False, "action.op must be a string", None

    # Special case: "done" action
    if op == "done":
        return True, None, action

    # Special case: "error" action (from white agent error handling)
    if op == "error":
        return True, None, action

    # Check if op matches a known tool
    tool_names = [t["name"] for t in tools]
    if op not in tool_names:
        return False, f"Unknown operation: {op}. Valid operations: {', '.join(tool_names)}", None

    # Find the tool specification
    tool_spec = next((t for t in tools if t["name"] == op), None)
    if not tool_spec:
        return False, f"Tool specification not found for: {op}", None

    # Validate action args
    args = action.get("args", {})
    if not isinstance(args, dict):
        return False, f"action.args must be an object, got {type(args).__name__}", None

    # Check required parameters
    required_params = tool_spec["parameters"].get("required", [])
    for param in required_params:
        if param not in args:
            return False, f"Missing required parameter for {op}: {param}", None

    # Validate parameter types (basic validation)
    properties = tool_spec["parameters"].get("properties", {})
    for param_name, param_value in args.items():
        if param_name not in properties:
            # Warn about unknown parameters but don't fail
            logger.warning(f"Unknown parameter {param_name} for {op}")
            continue

        param_spec = properties[param_name]
        expected_type = param_spec["type"]

        # Type checking
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }

        if expected_type in type_map:
            expected_python_type = type_map[expected_type]
            if not isinstance(param_value, expected_python_type):
                return False, f"Parameter {param_name} must be {expected_type}, got {type(param_value).__name__}", None

    return True, None, action


async def _execute_with_white_agent(
    task_dict: Dict[str, Any],
    white_agent_url: str,
    vm_ip: str,
    artifacts_dir: str,
    max_steps: int,
    callback_url: Optional[str],
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute assessment workflow with STATELESS white agent.

    STATELESS PROTOCOL:
    - Green agent owns trajectory state
    - Each request to white agent includes full trajectory
    - No /reset needed - white agent creates fresh agent per request
    - Supports Cloud Run auto-scaling (any instance can handle any request)

    This implements the full assessment loop:
    1. Capture initial observation
    2. For each step:
       - Send observation + trajectory to white agent
       - Get action from white agent
       - Execute action on OSWorld VM
       - Capture new observation
       - Append to trajectory
    3. Continue until task complete or max steps reached

    Args:
        task_dict: A2A task message with tools
        white_agent_url: URL of white agent endpoint
        vm_ip: IP address of OSWorld VM
        artifacts_dir: Directory to save screenshots/logs
        max_steps: Maximum number of steps allowed
        callback_url: Callback URL for real-time event pushing (optional)

    Returns:
        Assessment results with success, steps, time, etc.
    """
    import httpx
    import time
    import base64
    from pathlib import Path

    osworld_base_url = f"http://{vm_ip}:5000"
    start_time = time.time()

    # Extract assessment_id from task_dict for message tracking
    assessment_id = task_dict.get("task_id", "unknown")

    # Track assessment state
    step = 0
    success = False
    failure_reason = None

    # GREEN AGENT OWNS TRAJECTORY STATE (for stateless white agent protocol)
    # This trajectory is passed to white agent with each request
    # Format matches white_agent.rest.server.TrajectoryStep
    trajectory = []  # Full trajectory for result
    white_agent_trajectory = []  # Trajectory to send to white agent (text only, no screenshots)

    # Extract tools for validation
    tools = task_dict["metadata"].get("tools", [])

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            # NOTE: No /reset call needed - white agent is stateless
            # Each request creates a fresh PromptAgent instance
            logger.info(f"Starting stateless white agent workflow for assessment {assessment_id}")

            # Step 1: Capture initial observation
            logger.info(f"Capturing initial observation from VM at {vm_ip}")

            # Initial observation - take screenshot and get accessibility tree
            screenshot_resp = await client.get(f"{osworld_base_url}/screenshot")
            screenshot_b64 = base64.b64encode(screenshot_resp.content).decode()

            # Fetch accessibility tree for enhanced white agent reasoning
            accessibility_tree = None
            try:
                a11y_resp = await client.get(f"{osworld_base_url}/accessibility", timeout=10.0)
                if a11y_resp.status_code == 200:
                    a11y_data = a11y_resp.json()
                    accessibility_tree = a11y_data.get("AT", "")
                    if accessibility_tree:
                        logger.info(f"Fetched accessibility tree ({len(accessibility_tree)} chars)")
            except Exception as e:
                logger.warning(f"Failed to fetch accessibility tree: {e}")

            # Store initial screenshot for LLM fallback evaluation
            initial_screenshot_bytes = screenshot_resp.content
            final_screenshot_bytes = None  # Will be updated during execution

            # Save initial screenshot
            Path(f"{artifacts_dir}/step_0_initial.png").write_bytes(screenshot_resp.content)

            # Task instruction
            instruction = task_dict["message"]

            # Initialize ActionTracker for loop detection
            action_tracker = None
            stuck_feedback = None
            if LOOP_DETECTION_ENABLED and ActionTracker:
                action_tracker = ActionTracker(
                    threshold=ACTION_REPEAT_THRESHOLD,
                    coordinate_tolerance=ACTION_COORD_TOLERANCE
                )
                logger.info(f"[LoopDetection] ActionTracker initialized: threshold={ACTION_REPEAT_THRESHOLD}, tolerance={ACTION_COORD_TOLERANCE}px")

            # Assessment loop
            while step < max_steps:
                logger.info(f"Step {step}/{max_steps} (trajectory: {len(white_agent_trajectory)} steps)")

                # === PHASE 3: Enhanced Message Tracking ===
                # Track message send timestamp
                message_send_time = time.time()
                message_send_iso = datetime.now().isoformat()
                message_id = f"msg-{assessment_id}-{step}"

                logger.info(f"[{step}] Sending observation to white agent (stateless)...")

                # Push message sent event with full task payload
                await _push_event_to_webui(callback_url, {
                    "type": "message_sent",
                    "step": step,
                    "direction": "green_to_white",
                    "timestamp": message_send_iso,
                    "payload": {
                        "role": "user",
                        "instruction": instruction,
                        "done": False,
                        "has_screenshot": True,
                        "trajectory_length": len(white_agent_trajectory),
                        "observation_type": "screenshot_with_instruction"
                    }
                })

                # Build request for STATELESS white agent /decide endpoint
                # Include trajectory so white agent can rebuild context
                decide_request = {
                    "frame_id": step,
                    "image_png_b64": screenshot_b64,
                    "instruction": instruction,
                    "accessibility_tree": accessibility_tree,
                    "done": False,
                    "stuck_feedback": stuck_feedback,
                    "trajectory": white_agent_trajectory,  # Pass trajectory for stateless operation
                }
                # Add model if specified (from webui agent_config)
                if model:
                    decide_request["model"] = model

                # Clear stuck_feedback after including in request
                stuck_feedback = None

                # Get action from white agent using /decide endpoint (stateless)
                # Use structured timeout: generous read time for LLM processing (especially spreadsheet tasks),
                # and adequate write time for large payloads (screenshot + trajectory)
                decide_timeout = httpx.Timeout(
                    connect=30.0,   # 30s to establish connection
                    read=300.0,     # 5 min for LLM to process and respond
                    write=120.0,    # 2 min to send large payload
                    pool=30.0       # 30s for connection pool
                )
                response = await client.post(
                    f"{white_agent_url}/decide",
                    json=decide_request,
                    timeout=decide_timeout
                )
                response.raise_for_status()

                # Track message receive timestamp
                message_receive_time = time.time()
                message_receive_iso = datetime.now().isoformat()
                latency_ms = int((message_receive_time - message_send_time) * 1000)

                logger.info(f"[{step}] Received response from white agent (latency: {latency_ms}ms)")

                # Parse STATELESS /decide response format:
                # {action: {op, args}, thought: str, trajectory_step: {accessibility_tree, action, thought}}
                decide_response = response.json()

                # Extract action from new response format
                action = decide_response.get("action", {})
                thought = decide_response.get("thought", "")
                trajectory_step = decide_response.get("trajectory_step", {})

                # Validate action has required fields
                if not action or "op" not in action:
                    error_msg = "Response missing action.op field"
                    logger.error(f"Invalid white agent response: {error_msg}")
                    logger.error(f"Full response: {decide_response}")
                    failure_reason = f"Invalid response: {error_msg}"
                    raise RuntimeError(f"White agent response validation failed: {error_msg}")

                # Validate against tools if it's a tool action
                is_valid, error_msg, validated_action = _validate_white_agent_action(action, tools)
                validation_result = {
                    "valid": is_valid,
                    "errors": [error_msg] if not is_valid else []
                }

                # Push message received event with full response payload
                await _push_event_to_webui(callback_url, {
                    "type": "message_received",
                    "step": step,
                    "direction": "white_to_green",
                    "timestamp": message_receive_iso,
                    "latency_ms": latency_ms,
                    "payload": {
                        "role": "assistant",
                        "content": thought,
                        "action": action,
                        "done": action.get("op") == "done",
                        "trajectory_length": len(white_agent_trajectory)
                    },
                    "validation": validation_result
                })

                if not is_valid:
                    logger.error(f"Invalid white agent response: {error_msg}")
                    logger.error(f"Full response: {decide_response}")
                    failure_reason = f"Invalid response: {error_msg}"
                    raise RuntimeError(f"White agent response validation failed: {error_msg}")

                is_done = action.get("op") == "done"

                logger.info(f"White agent action: {action['op']}")

                # === LOOP DETECTION: Track action for repeated pattern detection ===
                if action_tracker and action["op"] != "done":
                    # Update action tracker with current accessibility tree for coordinate guidance
                    if accessibility_tree:
                        action_tracker.set_accessibility_tree(accessibility_tree)
                        logger.debug(f"[LoopDetection] A11y tree set for step {step} ({len(accessibility_tree)} chars)")

                    # Pass action directly - ActionTracker now uses op/args format
                    status, feedback = action_tracker.add_action(action)
                    if status == "stuck":
                        logger.warning(f"[LoopDetection] === STUCK LOOP DETECTED === Step {step}")
                        logger.warning(f"[LoopDetection] Repeated {action_tracker.repeat_count} times (threshold: {ACTION_REPEAT_THRESHOLD})")
                        stuck_feedback = feedback
                        logger.info(f"[LoopDetection] {action_tracker.get_action_history_summary()}")
                    elif status == "warning":
                        logger.info(f"[LoopDetection] WARNING: Step {step} - action repeated {action_tracker.repeat_count} times")
                        stuck_feedback = feedback
                    else:
                        logger.debug(f"[LoopDetection] Step {step} - action tracking status: {status}")

                # === PHASE 3: Build Enhanced Message Data ===
                message_data = {
                    "id": message_id,
                    "timestamp_sent": message_send_iso,
                    "timestamp_received": message_receive_iso,
                    "direction": "white_to_green",
                    "type": "response",
                    "payload": {
                        "role": "assistant",
                        "content": thought,
                        "action": action
                    },
                    "validation": validation_result,
                    "latency_ms": latency_ms
                }

                # === STATELESS: Append trajectory_step to white_agent_trajectory ===
                # This will be passed to white agent in the next request
                if trajectory_step:
                    white_agent_trajectory.append(trajectory_step)

                # === PHASE 3: Track Tool Execution (if not done) ===
                tool_data = None
                screenshot_before_path = None
                screenshot_after_path = None
                screenshot_before_url = None
                screenshot_after_url = None

                if action["op"] != "done":
                    # Capture screenshot BEFORE tool execution
                    try:
                        screenshot_before_resp = await client.get(f"{osworld_base_url}/screenshot")
                        screenshot_before_path = f"{artifacts_dir}/step_{step}_before.png"
                        Path(screenshot_before_path).write_bytes(screenshot_before_resp.content)
                        logger.info(f"[{step}] Captured before screenshot")

                        # Upload to Supabase Storage
                        screenshot_before_url = await get_upload_screenshot()(
                            assessment_id=assessment_id,
                            step=step,
                            screenshot_bytes=screenshot_before_resp.content,
                            screenshot_type="before"
                        )
                        if screenshot_before_url:
                            logger.info(f"[{step}] Uploaded before screenshot to Supabase")
                    except Exception as e:
                        logger.warning(f"Failed to capture before screenshot: {e}")

                    # Track tool execution timing
                    tool_start_time = time.time()
                    tool_start_iso = datetime.now().isoformat()
                    tool_status = "success"
                    tool_error = None

                    logger.info(f"[{step}] Executing tool: {action['op']}")

                    # Push tool execution start event
                    await _push_event_to_webui(callback_url, {
                        "type": "tool_execution_start",
                        "step": step,
                        "tool": action["op"],
                        "parameters": {k: v for k, v in action.items() if k != "op"},
                        "timestamp": tool_start_iso
                    })

                    # Execute action on OSWorld VM
                    try:
                        await _execute_osworld_action(client, osworld_base_url, action)
                    except Exception as e:
                        logger.error(f"Action execution failed: {e}")
                        tool_status = "failed"
                        tool_error = str(e)
                        failure_reason = f"Action execution failed: {str(e)}"

                        # Still build tool_data for failed execution
                        tool_end_time = time.time()
                        tool_duration_ms = int((tool_end_time - tool_start_time) * 1000)

                        tool_data = {
                            "step": step,
                            "timestamp": tool_start_iso,
                            "tool": action["op"],
                            "parameters": {k: v for k, v in action.items() if k != "op"},
                            "status": tool_status,
                            "duration_ms": tool_duration_ms,
                            "error": tool_error,
                            "screenshot_before": f"step_{step}_before.png" if screenshot_before_path else None,
                            "screenshot_after": None
                        }

                        # Push tool execution failed event
                        await _push_event_to_webui(callback_url, {
                            "type": "tool_execution_complete",
                            "step": step,
                            "tool": action["op"],
                            "status": "failed",
                            "duration_ms": tool_duration_ms,
                            "error": tool_error,
                            "screenshot_before": screenshot_before_url,
                            "screenshot_after": None,
                            "timestamp": datetime.now().isoformat()
                        })

                        # Append to trajectory even on failure
                        trajectory.append({
                            "step": step,
                            "action": action,
                            "content": message["content"],
                            "message_data": message_data,
                            "tool_data": tool_data
                        })
                        break

                    # Tool execution successful
                    tool_end_time = time.time()
                    tool_end_iso = datetime.now().isoformat()
                    tool_duration_ms = int((tool_end_time - tool_start_time) * 1000)

                    logger.info(f"[{step}] Tool executed successfully ({tool_duration_ms}ms)")

                    # Build tool data (will update after capturing after screenshot)
                    tool_data = {
                        "step": step,
                        "timestamp_start": tool_start_iso,
                        "timestamp_end": tool_end_iso,
                        "tool": action["op"],
                        "parameters": {k: v for k, v in action.items() if k != "op"},
                        "status": tool_status,
                        "duration_ms": tool_duration_ms,
                        "result": None,  # Could capture tool-specific result if needed
                        "screenshot_before": f"step_{step}_before.png" if screenshot_before_path else None,
                        "screenshot_after": f"step_{step + 1}.png"  # Will be captured below
                    }

                    # Note: Tool execution success event will be pushed after capturing after screenshot

                # === PHASE 3: Append Enhanced Trajectory ===
                trajectory.append({
                    "step": step,
                    "action": action,
                    "content": thought,  # Use thought from stateless response
                    "message_data": message_data,
                    "tool_data": tool_data
                })

                # Check if task is done
                if is_done or action["op"] == "done":
                    logger.info(f"White agent reports task done at step {step}")
                    logger.info("Will validate completion with OSWorld evaluator...")
                    # Don't set success=True here - let the evaluator decide
                    break

                # Wait a moment for action to complete
                await asyncio.sleep(0.5)

                # Capture new observation (screenshot + accessibility tree)
                screenshot_resp = await client.get(f"{osworld_base_url}/screenshot")
                screenshot_b64 = base64.b64encode(screenshot_resp.content).decode()

                # Fetch updated accessibility tree
                accessibility_tree = None
                try:
                    a11y_resp = await client.get(f"{osworld_base_url}/accessibility", timeout=10.0)
                    if a11y_resp.status_code == 200:
                        a11y_data = a11y_resp.json()
                        accessibility_tree = a11y_data.get("AT", "")
                except Exception as e:
                    logger.debug(f"Failed to fetch accessibility tree at step {step}: {e}")

                # Store as potential final screenshot for LLM fallback evaluation
                final_screenshot_bytes = screenshot_resp.content

                # Save screenshot
                screenshot_after_path = f"{artifacts_dir}/step_{step + 1}.png"
                Path(screenshot_after_path).write_bytes(screenshot_resp.content)

                # Upload after screenshot to Supabase Storage
                try:
                    screenshot_after_url = await get_upload_screenshot()(
                        assessment_id=assessment_id,
                        step=step,
                        screenshot_bytes=screenshot_resp.content,
                        screenshot_type="after"
                    )
                    if screenshot_after_url:
                        logger.info(f"[{step}] Uploaded after screenshot to Supabase")
                except Exception as e:
                    logger.warning(f"Failed to upload after screenshot: {e}")

                # Push tool execution success event with both screenshot URLs
                if action["op"] != "done":
                    await _push_event_to_webui(callback_url, {
                        "type": "tool_execution_complete",
                        "step": step,
                        "tool": action["op"],
                        "status": "success",
                        "duration_ms": tool_duration_ms,
                        "screenshot_before": screenshot_before_url,
                        "screenshot_after": screenshot_after_url,
                        "timestamp": tool_end_iso
                    })

                # Update step counter for next iteration
                step += 1

                # NOTE: For stateless protocol, we don't need to build current_task
                # The next iteration will use the updated:
                # - screenshot_b64 (captured above)
                # - accessibility_tree (captured above)
                # - white_agent_trajectory (appended above)
                # - instruction (unchanged)

            if not success and step >= max_steps:
                failure_reason = f"Maximum steps ({max_steps}) reached"

        except Exception as e:
            logger.error(f"Assessment workflow failed: {e}", exc_info=True)
            failure_reason = str(e)

    # Build result
    # Get screenshots if they were captured (they're defined in the try block)
    screenshot_before = locals().get('initial_screenshot_bytes')
    screenshot_after = locals().get('final_screenshot_bytes')

    result = {
        "success": success,
        "steps": step,
        "time_sec": time.time() - start_time,
        "trajectory": trajectory,
        "artifacts_dir": artifacts_dir,
        # Screenshots for LLM fallback evaluation
        "screenshot_before": screenshot_before,
        "screenshot_after": screenshot_after
    }

    if failure_reason:
        result["failure_reason"] = failure_reason

    # Note: We don't push assessment_complete here because it's pushed in _execute_assessment
    # This function only handles white agent execution workflow

    return result


def _validate_coordinates(x: Any, y: Any, screen_width: int = 1920, screen_height: int = 1080) -> tuple[int, int]:
    """
    Validate and sanitize screen coordinates.

    Args:
        x: X coordinate (must be integer or convertible to integer)
        y: Y coordinate (must be integer or convertible to integer)
        screen_width: Maximum screen width
        screen_height: Maximum screen height

    Returns:
        Tuple of validated (x, y) coordinates

    Raises:
        ValueError: If coordinates are invalid or out of bounds
    """
    try:
        x_int = int(x)
        y_int = int(y)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Coordinates must be integers, got x={x!r}, y={y!r}") from e

    if not (0 <= x_int <= screen_width):
        raise ValueError(f"X coordinate {x_int} out of bounds (0-{screen_width})")
    if not (0 <= y_int <= screen_height):
        raise ValueError(f"Y coordinate {y_int} out of bounds (0-{screen_height})")

    return x_int, y_int


def _validate_text(text: Any, max_length: int = 10000) -> str:
    """
    Validate and sanitize text input.

    Args:
        text: Text to validate
        max_length: Maximum allowed text length

    Returns:
        Validated text string

    Raises:
        ValueError: If text is invalid
    """
    if not isinstance(text, str):
        raise ValueError(f"Text must be string, got {type(text).__name__}")

    if len(text) > max_length:
        raise ValueError(f"Text too long ({len(text)} chars, max {max_length})")

    return text


def _validate_keys(keys: Any) -> list[str]:
    """
    Validate and sanitize keyboard keys.

    Args:
        keys: List of key names

    Returns:
        Validated list of key strings

    Raises:
        ValueError: If keys are invalid
    """
    if not isinstance(keys, list):
        raise ValueError(f"Keys must be list, got {type(keys).__name__}")

    # Allowed keys (alphanumeric + common modifiers/special keys)
    ALLOWED_KEYS = set([
        # Alphanumeric
        *[chr(i) for i in range(ord('a'), ord('z') + 1)],  # a-z
        *[chr(i) for i in range(ord('A'), ord('Z') + 1)],  # A-Z
        *[str(i) for i in range(10)],  # 0-9
        # Modifiers
        'ctrl', 'alt', 'shift', 'command', 'cmd', 'win', 'super',
        # Special keys
        'enter', 'return', 'tab', 'space', 'backspace', 'delete', 'del',
        'esc', 'escape', 'up', 'down', 'left', 'right',
        'home', 'end', 'pageup', 'pagedown', 'insert',
        # Function keys
        *[f'f{i}' for i in range(1, 13)],  # f1-f12
        # Punctuation
        ',', '.', '/', ';', "'", '[', ']', '\\', '-', '=',
        '`', '~', '!', '@', '#', '$', '%', '^', '&', '*',
        '(', ')', '_', '+', '{', '}', '|', ':', '"', '<', '>', '?'
    ])

    validated_keys = []
    for key in keys:
        if not isinstance(key, str):
            raise ValueError(f"Each key must be string, got {type(key).__name__}")
        if key.lower() not in ALLOWED_KEYS and key not in ALLOWED_KEYS:
            raise ValueError(f"Invalid key: {key!r}")
        validated_keys.append(key)

    if not validated_keys:
        raise ValueError("Keys list cannot be empty")

    return validated_keys


def _validate_number(value: Any, name: str, min_val: float = None, max_val: float = None) -> float:
    """
    Validate numeric value.

    Args:
        value: Value to validate
        name: Name of parameter (for error messages)
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Validated numeric value

    Raises:
        ValueError: If value is invalid
    """
    try:
        num = float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{name} must be numeric, got {value!r}") from e

    if min_val is not None and num < min_val:
        raise ValueError(f"{name} must be >= {min_val}, got {num}")
    if max_val is not None and num > max_val:
        raise ValueError(f"{name} must be <= {max_val}, got {num}")

    return num


async def _execute_osworld_action(
    client: httpx.AsyncClient,
    base_url: str,
    action: Dict[str, Any]
):
    """
    Execute a single action on the OSWorld VM

    Translates action dict to Python code and executes via /run_python endpoint.
    Uses safe code generation with input validation to prevent code injection.
    """
    op = action.get("op")
    args = action.get("args", {})

    # Generate Python code based on action type
    # Use safe templating with %r for automatic escaping
    python_code = None

    try:
        if op == "click":
            # Click action - validate coordinates
            x = args.get("x")
            y = args.get("y")
            button = args.get("button", "left")

            if x is not None and y is not None:
                x_safe, y_safe = _validate_coordinates(x, y)
                if button == "left":
                    python_code = f"import pyautogui\npyautogui.click({x_safe}, {y_safe})"
                elif button == "right":
                    python_code = f"import pyautogui\npyautogui.rightClick({x_safe}, {y_safe})"
                else:
                    raise ValueError(f"Invalid button: {button!r}")
            else:
                python_code = "import pyautogui\npyautogui.click()"

        elif op == "double_click":
            # Double click action - validate coordinates
            x = args.get("x")
            y = args.get("y")
            if x is not None and y is not None:
                x_safe, y_safe = _validate_coordinates(x, y)
                python_code = f"import pyautogui\npyautogui.doubleClick({x_safe}, {y_safe})"
            else:
                raise ValueError("double_click requires x and y coordinates")

        elif op == "right_click":
            # Right click action - validate coordinates
            x = args.get("x")
            y = args.get("y")
            if x is not None and y is not None:
                x_safe, y_safe = _validate_coordinates(x, y)
                python_code = f"import pyautogui\npyautogui.rightClick({x_safe}, {y_safe})"
            else:
                raise ValueError("right_click requires x and y coordinates")

        elif op == "type" or op == "type_text":
            # Type text action - validate and safely escape text
            # Support both 'type' and 'type_text' for compatibility
            text = args.get("text", "")
            text_safe = _validate_text(text)
            # Use repr() which properly escapes all special characters
            python_code = f"import pyautogui\npyautogui.write({text_safe!r})"

        elif op == "hotkey":
            # Hotkey action - validate keys
            keys = args.get("keys", [])
            keys_safe = _validate_keys(keys)
            if len(keys_safe) == 1:
                python_code = f"import pyautogui\npyautogui.press({keys_safe[0]!r})"
            else:
                # Use repr() for each key for safe escaping
                keys_repr = ", ".join(repr(k) for k in keys_safe)
                python_code = f"import pyautogui\npyautogui.hotkey({keys_repr})"

        elif op == "scroll":
            # Scroll action - validate amount
            amount = args.get("amount", 0)
            amount_safe = _validate_number(amount, "scroll amount", min_val=-10000, max_val=10000)
            # Convert to int for scroll
            python_code = f"import pyautogui\npyautogui.scroll({int(amount_safe)})"

        elif op == "move":
            # Move mouse action - validate coordinates
            x = args.get("x")
            y = args.get("y")
            if x is not None and y is not None:
                x_safe, y_safe = _validate_coordinates(x, y)
                python_code = f"import pyautogui\npyautogui.moveTo({x_safe}, {y_safe})"
            else:
                raise ValueError("move requires x and y coordinates")

        elif op == "execute_python":
            # Execute Python code directly
            # NOTE: This is intentionally allowed for flexibility, but should be restricted
            # in production to trusted agents only
            python_code = args.get("code")
            if not isinstance(python_code, str):
                raise ValueError("execute_python requires 'code' parameter as string")
            logger.warning(f"Executing arbitrary Python code from white agent: {python_code[:100]}")

        elif op == "execute_command":
            # Execute shell command via /execute endpoint
            command = args.get("command")
            if not command:
                raise ValueError("execute_command requires 'command' parameter")
            await client.post(
                f"{base_url}/execute",
                json={
                    "command": command,
                    "shell": args.get("shell", True)
                }
            )
            return

        elif op == "wait":
            # Local wait - validate duration
            duration = args.get("duration", 1.0)
            duration_safe = _validate_number(duration, "wait duration", min_val=0, max_val=60)
            await asyncio.sleep(duration_safe)
            return

        elif op == "done":
            # Task complete - no action needed
            return

        else:
            logger.warning(f"Unknown action op: {op!r}")
            raise ValueError(f"Unknown action operation: {op!r}")

    except ValueError as e:
        logger.error(f"Action validation failed for {op}: {e}")
        raise RuntimeError(f"Invalid action parameters: {e}") from e

    # Execute the Python code if we generated any
    if python_code:
        logger.info(f"Executing Python code: {python_code[:200]}...")
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


# Support running directly with environment variables for AgentBeats controller
if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting Green Agent on {GREEN_AGENT_HOST}:{GREEN_AGENT_PORT}")
    logger.info("AgentBeats controller compatible - respects HOST and AGENT_PORT environment variables")

    uvicorn.run(app, host=GREEN_AGENT_HOST, port=GREEN_AGENT_PORT)
