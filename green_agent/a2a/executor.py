"""
Green Agent Executor - A2A Protocol Implementation

This module implements the AgentExecutor interface from the A2A SDK,
wrapping the existing OSWorld orchestrator functionality.
"""

import json
import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import TaskState
from a2a.utils import new_agent_text_message

logger = logging.getLogger(__name__)


def make_json_serializable(obj: Any) -> Any:
    """Recursively convert an object to be JSON serializable."""
    if isinstance(obj, bytes):
        return None  # Remove bytes (e.g., screenshot data)
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return str(obj)  # Fallback: convert to string

# Import configuration
from green_agent.config import (
    ACTION_REPEAT_THRESHOLD,
    ACTION_COORD_TOLERANCE,
    GCP_PROJECT,
    SETUP_STABILIZATION_WAIT,
    EVAL_STABILIZATION_WAIT,
)

# Import ActionTracker for loop detection
try:
    from green_agent.action_tracker import ActionTracker
    LOOP_DETECTION_ENABLED = True
    logger.info("[LoopDetection] ActionTracker imported successfully")
except ImportError:
    ActionTracker = None
    LOOP_DETECTION_ENABLED = False
    logger.warning("[LoopDetection] ActionTracker not available - loop detection disabled")


class GreenAgentExecutor(AgentExecutor):
    """
    A2A Agent Executor for OSWorld Assessment.

    This executor handles incoming A2A messages and orchestrates:
    1. VM creation and management
    2. OSWorld task setup
    3. White agent interaction loop
    4. Task evaluation
    5. Cleanup
    """

    def __init__(self):
        """Initialize the executor with lazy-loaded managers."""
        self._vm_manager = None
        self._task_executor = None
        self.active_assessments: Dict[str, Dict[str, Any]] = {}
        logger.info("GreenAgentExecutor initialized")

    def _get_vm_manager(self):
        """Lazily initialize VMManager on first use."""
        if self._vm_manager is None:
            from green_agent.a2a.vm_manager import VMManager
            logger.info(f"Initializing VMManager with project_id: {GCP_PROJECT}")
            self._vm_manager = VMManager(project_id=GCP_PROJECT)
        return self._vm_manager

    def _get_task_executor(self):
        """Lazily initialize TaskExecutor on first use."""
        if self._task_executor is None:
            from green_agent.a2a.task_executor import TaskExecutor
            self._task_executor = TaskExecutor()
        return self._task_executor

    def _get_upload_screenshot(self):
        """Lazily import upload_screenshot function."""
        from green_agent.a2a.supabase_storage import upload_screenshot
        return upload_screenshot

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """
        Execute the agent's logic for a given request context.

        This is the main entry point for A2A task handling. It:
        1. Parses the incoming message and metadata
        2. Sends an acknowledgment
        3. Runs the assessment
        4. Sends the final result

        Args:
            context: The request context containing the message, task ID, etc.
            event_queue: The queue to publish events to.
        """
        task_id = context.task_id
        context_id = context.context_id

        logger.info(f"[A2A] Received task: {task_id}")

        try:
            # Parse configuration from message and metadata
            user_input = context.get_user_input()
            metadata = context.metadata

            config = self._parse_task_config(user_input, metadata)
            logger.info(f"[A2A] Parsed config for {task_id}: {list(config.keys())}")

            # Send acknowledgment
            await event_queue.enqueue_event(
                new_agent_text_message(
                    json.dumps({
                        "status": "accepted",
                        "assessment_id": task_id,
                        "message": "Assessment accepted and starting execution"
                    }),
                    context_id=context_id,
                    task_id=task_id
                )
            )

            # Execute the assessment
            result = await self._execute_assessment(
                assessment_id=task_id,
                config=config,
                context_id=context_id,
                event_queue=event_queue
            )

            # Send final result (convert to JSON-serializable format)
            result_for_json = make_json_serializable(result)
            await event_queue.enqueue_event(
                new_agent_text_message(
                    json.dumps(result_for_json),
                    context_id=context_id,
                    task_id=task_id
                )
            )

            logger.info(f"[A2A] Assessment {task_id} completed: success={result.get('success')}")

        except Exception as e:
            logger.error(f"[A2A] Assessment {task_id} failed: {e}", exc_info=True)

            # Send error response
            await event_queue.enqueue_event(
                new_agent_text_message(
                    json.dumps({
                        "status": "failed",
                        "error": str(e),
                        "assessment_id": task_id
                    }),
                    context_id=context_id,
                    task_id=task_id
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """
        Cancel an ongoing assessment.

        This will:
        1. Mark the assessment as cancelled
        2. Cleanup any running VMs
        3. Send cancellation confirmation

        Args:
            context: The request context containing the task ID to cancel.
            event_queue: The queue to publish the cancellation status update to.
        """
        task_id = context.task_id
        context_id = context.context_id

        logger.info(f"[A2A] Cancel requested for task: {task_id}")

        if task_id in self.active_assessments:
            assessment = self.active_assessments[task_id]

            # Cleanup VM if running
            if assessment.get("status") == "running" and assessment.get("vm_info"):
                try:
                    logger.info(f"[A2A] Cleaning up VM for cancelled task {task_id}")
                    await asyncio.to_thread(
                        self._get_vm_manager().delete_vm,
                        task_id
                    )
                except Exception as e:
                    logger.error(f"[A2A] VM cleanup failed for {task_id}: {e}")

            assessment["status"] = "cancelled"

        # Send cancellation confirmation
        await event_queue.enqueue_event(
            new_agent_text_message(
                json.dumps({
                    "status": "cancelled",
                    "assessment_id": task_id,
                    "message": "Assessment cancelled"
                }),
                context_id=context_id,
                task_id=task_id
            )
        )

    def _parse_task_config(self, message: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse task configuration from A2A message and metadata.

        Supports:
        1. Structured config in metadata
        2. JSON in message
        3. Key fields in metadata
        """
        # Option 1: Check metadata for structured config
        if metadata and "config" in metadata:
            return metadata["config"]

        # Option 2: Try parsing message as JSON
        try:
            config = json.loads(message)
            if isinstance(config, dict):
                return config
        except json.JSONDecodeError:
            pass

        # Option 3: Extract from metadata fields
        config = {}

        # Extract white_agent_url (required)
        if metadata.get("white_agent_url"):
            config["white_agent_url"] = metadata["white_agent_url"]
        else:
            raise ValueError("white_agent_url must be provided in metadata")

        # Extract osworld_task_id (required)
        if metadata.get("osworld_task_id"):
            config["osworld_task_id"] = metadata["osworld_task_id"]
        elif metadata.get("task_id"):
            config["osworld_task_id"] = metadata["task_id"]
        else:
            raise ValueError("osworld_task_id must be provided in metadata")

        # Extract optional parameters
        config["max_steps"] = metadata.get("max_steps", 15)
        config["vm_image"] = metadata.get("vm_image", "osworld-golden-v12-gnome")
        config["metrics"] = metadata.get("metrics", ["success", "steps", "time_sec"])
        config["domain"] = metadata.get("domain")

        # Extract full OSWorld task if provided
        if "osworld_task" in metadata:
            config["osworld_task"] = metadata["osworld_task"]

        # Extract callback_url for real-time updates
        if "callback_url" in metadata:
            config["callback_url"] = metadata["callback_url"]

        return config

    async def _execute_assessment(
        self,
        assessment_id: str,
        config: Dict[str, Any],
        context_id: str,
        event_queue: EventQueue
    ) -> Dict[str, Any]:
        """
        Execute OSWorld assessment.

        This is the core orchestration logic, preserved from the original server.
        """
        import httpx
        import base64

        logger.info(f"Starting assessment {assessment_id}")
        start_time = time.time()

        # Track assessment
        self.active_assessments[assessment_id] = {
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "config": config
        }

        vm_info = None
        callback_url = config.get("callback_url")

        try:
            # Step 1: Create VM
            logger.info("Creating VM...")
            await self._send_progress(event_queue, context_id, assessment_id, {
                "type": "vm_creation_started",
                "vm_image": config.get("vm_image", "osworld-golden-v12-gnome")
            })

            vm_info = await asyncio.to_thread(
                self._get_vm_manager().create_vm,
                assessment_id
            )
            logger.info(f"VM created: {vm_info['vm_name']} at {vm_info['vm_ip']}")

            self.active_assessments[assessment_id]["vm_info"] = vm_info

            await self._send_progress(event_queue, context_id, assessment_id, {
                "type": "vm_created",
                "vm_name": vm_info['vm_name'],
                "vm_ip": vm_info['vm_ip']
            })

            # Step 2: Wait for VM ready
            logger.info("Waiting for VM to be ready...")
            await self._send_progress(event_queue, context_id, assessment_id, {
                "type": "vm_waiting",
                "message": "Waiting for VM to boot and OSWorld server to start"
            })

            vm_ready = await asyncio.to_thread(
                self._get_vm_manager().wait_for_vm_ready,
                vm_info["vm_ip"],
                timeout=600
            )

            if not vm_ready:
                raise TimeoutError(f"VM {vm_info['vm_ip']} failed to become ready")

            await self._send_progress(event_queue, context_id, assessment_id, {
                "type": "vm_ready",
                "vm_ip": vm_info["vm_ip"]
            })

            # Step 3: Execute OSWorld task setup
            osworld_task = config.get("osworld_task")
            if not osworld_task:
                try:
                    osworld_task = self._get_task_executor().load_task(
                        config["osworld_task_id"],
                        domain=config.get("domain")
                    )
                except FileNotFoundError:
                    logger.warning(f"OSWorld task not found: {config['osworld_task_id']}")

            if osworld_task and osworld_task.get("config"):
                await self._send_progress(event_queue, context_id, assessment_id, {
                    "type": "setup_started",
                    "num_steps": len(osworld_task["config"])
                })

                setup_success = await asyncio.to_thread(
                    self._execute_osworld_setup,
                    vm_info["vm_ip"],
                    osworld_task["config"]
                )

                if not setup_success:
                    raise Exception("Task setup failed")

                await self._send_progress(event_queue, context_id, assessment_id, {
                    "type": "setup_completed"
                })

                if SETUP_STABILIZATION_WAIT > 0:
                    await asyncio.sleep(SETUP_STABILIZATION_WAIT)

            # Step 4: Execute with white agent
            logger.info("Sending task to white agent...")
            tools = self._build_osworld_tool_descriptions(vm_info["vm_ip"])

            task_instruction = osworld_task.get("instruction", "Complete the task") if osworld_task else "Complete the task"

            white_agent_task = {
                "task_id": assessment_id,
                "context_id": assessment_id,
                "message": self._format_task_message_with_tools(
                    {"instruction": task_instruction},
                    tools
                ),
                "metadata": {
                    "osworld_server": f"http://{vm_info['vm_ip']}:5000",
                    "tools": tools,
                    "max_steps": config.get("max_steps", 15)
                }
            }

            await self._send_progress(event_queue, context_id, assessment_id, {
                "type": "white_agent_started",
                "white_agent_url": config["white_agent_url"],
                "max_steps": config.get("max_steps", 15)
            })

            artifacts_dir = f"./temp_artifacts/{assessment_id}"
            Path(artifacts_dir).mkdir(parents=True, exist_ok=True)

            result = await self._execute_with_white_agent(
                white_agent_task,
                config["white_agent_url"],
                vm_info["vm_ip"],
                artifacts_dir,
                config.get("max_steps", 15),
                callback_url
            )

            await self._send_progress(event_queue, context_id, assessment_id, {
                "type": "white_agent_completed",
                "steps_taken": result.get("steps", 0)
            })

            # Step 5: Evaluate
            if osworld_task and "evaluator" in osworld_task:
                if EVAL_STABILIZATION_WAIT > 0:
                    await asyncio.sleep(EVAL_STABILIZATION_WAIT)

                await self._send_progress(event_queue, context_id, assessment_id, {
                    "type": "evaluation_started"
                })

                try:
                    from green_agent.osworld_evaluator import evaluate_task_with_llm_fallback

                    last_action = self._extract_last_action(result.get("trajectory", []))

                    evaluation_result = await evaluate_task_with_llm_fallback(
                        vm_ip=vm_info["vm_ip"],
                        evaluator_config=osworld_task["evaluator"],
                        task_id=osworld_task.get("id", config["osworld_task_id"]),
                        task_instruction=osworld_task.get("instruction", ""),
                        server_port=5000,
                        cache_dir="cache",
                        last_action=last_action,
                        steps_taken=result.get("steps", 0),
                        trajectory=result.get("trajectory", []),
                        max_steps=config.get("max_steps", 15),
                        enable_llm_fallback=config.get("enable_llm_fallback", True),
                        llm_provider=config.get("llm_judge_provider", "openai"),
                        llm_model=config.get("llm_judge_model"),
                        llm_confidence_threshold=config.get("llm_judge_confidence", 0.7),
                        screenshot_before=result.get("screenshot_before"),
                        screenshot_after=result.get("screenshot_after")
                    )

                    evaluation_score = evaluation_result.get("score", 0.0)
                    result["success"] = 1 if evaluation_score >= 1.0 else 0
                    result["evaluation_score"] = evaluation_score
                    result["evaluation_method"] = evaluation_result.get("evaluation_method", "rule_based")
                    result["evaluation_details"] = evaluation_result

                    await self._send_progress(event_queue, context_id, assessment_id, {
                        "type": "evaluation_completed",
                        "success": result["success"] == 1,
                        "evaluation_score": evaluation_score
                    })

                except Exception as e:
                    logger.error(f"Evaluation error: {e}", exc_info=True)
                    result["success"] = 0
                    result["evaluation_error"] = str(e)
            else:
                result["success"] = 0
                result["evaluation_method"] = "no_evaluator"

            # Add metadata
            result["vm_cost"] = self._get_vm_manager().get_vm_cost(time.time() - start_time)
            result["vm_info"] = vm_info
            result["assessment_id"] = assessment_id
            result["total_time_sec"] = time.time() - start_time

            # Cleanup VM
            logger.info("Cleaning up VM...")
            await asyncio.to_thread(
                self._get_vm_manager().delete_vm,
                assessment_id
            )

            self.active_assessments[assessment_id]["status"] = "completed"
            return result

        except Exception as e:
            logger.error(f"Assessment failed: {e}", exc_info=True)

            # Cleanup VM on failure
            if vm_info:
                try:
                    await asyncio.to_thread(
                        self._get_vm_manager().delete_vm,
                        assessment_id
                    )
                except Exception as cleanup_error:
                    logger.error(f"VM cleanup failed: {cleanup_error}")

            self.active_assessments[assessment_id]["status"] = "failed"
            self.active_assessments[assessment_id]["error"] = str(e)

            raise

    async def _send_progress(
        self,
        event_queue: EventQueue,
        context_id: str,
        task_id: str,
        data: Dict[str, Any]
    ):
        """Send progress update via event queue."""
        data["timestamp"] = datetime.utcnow().isoformat()
        await event_queue.enqueue_event(
            new_agent_text_message(
                json.dumps({"progress": data}),
                context_id=context_id,
                task_id=task_id
            )
        )

    def _extract_last_action(self, trajectory: list) -> Optional[str]:
        """Extract last action from trajectory for evaluation."""
        if not trajectory:
            return None

        last_entry = trajectory[-1]
        raw_actions = (
            last_entry
            .get("message_data", {})
            .get("payload", {})
            .get("metadata", {})
            .get("raw_actions", "")
        )
        raw_actions_str = str(raw_actions).upper()

        if "FAIL" in raw_actions_str:
            return "FAIL"
        elif "DONE" in raw_actions_str:
            return "DONE"
        return None

    def _execute_osworld_setup(self, vm_ip: str, task_config: list) -> bool:
        """Execute OSWorld task setup using SetupController."""
        # Lazy import
        from desktop_env.controllers.setup import SetupController

        logger.info("Executing OSWorld task setup...")

        try:
            cache_dir = Path("cache")
            cache_dir.mkdir(exist_ok=True)

            setup_controller = SetupController(
                vm_ip=vm_ip,
                server_port=5000,
                chromium_port=9222
            )

            # Kill GNOME keyring daemon
            keyring_kill_config = [{
                "type": "execute",
                "parameters": {
                    "command": ["pkill", "-f", "gnome-keyring-daemon"],
                    "shell": False
                }
            }]
            setup_controller.setup(keyring_kill_config)

            if not task_config:
                return True

            success = setup_controller.setup(task_config)
            logger.info(f"Setup {'succeeded' if success else 'failed'}")
            return success

        except Exception as e:
            logger.error(f"Setup failed: {e}", exc_info=True)
            raise

    def _build_osworld_tool_descriptions(self, vm_ip: str) -> list:
        """Build tool descriptions for OSWorld REST API."""
        # Import from original server to avoid duplication
        from green_agent.a2a.server import _build_osworld_tool_descriptions
        return _build_osworld_tool_descriptions(vm_ip)

    def _format_task_message_with_tools(self, task: Dict[str, Any], tools: list) -> str:
        """Format task message with embedded tool descriptions."""
        from green_agent.a2a.server import _format_task_message_with_tools
        return _format_task_message_with_tools(task, tools)

    async def _execute_with_white_agent(
        self,
        task_dict: Dict[str, Any],
        white_agent_url: str,
        vm_ip: str,
        artifacts_dir: str,
        max_steps: int,
        callback_url: Optional[str]
    ) -> Dict[str, Any]:
        """Execute assessment workflow with white agent."""
        # Import from original server
        from green_agent.a2a.server import _execute_with_white_agent
        return await _execute_with_white_agent(
            task_dict, white_agent_url, vm_ip, artifacts_dir, max_steps, callback_url
        )

    def get_active_assessments(self) -> Dict[str, Dict[str, Any]]:
        """Get all active assessments (for monitoring)."""
        return self.active_assessments

    def cleanup_all_vms(self):
        """Cleanup all running VMs (for graceful shutdown)."""
        running = [
            (aid, data) for aid, data in self.active_assessments.items()
            if data.get("status") == "running"
        ]

        if not running:
            logger.info("No running assessments to cleanup")
            return

        logger.warning(f"Cleaning up {len(running)} running assessment(s)...")

        for assessment_id, data in running:
            try:
                self._get_vm_manager().delete_vm(assessment_id)
                logger.info(f"VM for {assessment_id} deleted")
            except Exception as e:
                logger.error(f"Failed to cleanup VM for {assessment_id}: {e}")
