"""
Task Executor - Assessment Runner

Executes OSWorld assessments on VMs, reusing Green Agent logic.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Callable

from green_agent.white_client import WhiteClient
from green_agent.osworld_adapter import run_osworld

logger = logging.getLogger(__name__)


class TaskExecutor:
    """Executes OSWorld assessment tasks"""

    def __init__(self, tasks_dir: str = None):
        """
        Initialize Task Executor

        Args:
            tasks_dir: Directory containing OSWorld task JSON files organized by domain.
                       Defaults to green_agent/tasks_config
        """
        if tasks_dir is None:
            tasks_dir = Path(__file__).parent.parent / "tasks_config"
        self.tasks_dir = Path(tasks_dir)
        if not self.tasks_dir.exists():
            logger.warning(f"Tasks directory does not exist: {self.tasks_dir}")

    def load_task(self, task_id: str, domain: str = None) -> Dict[str, Any]:
        """
        Load OSWorld task JSON from tasks_config directory

        Args:
            task_id: Task identifier (UUID)
            domain: Task domain (os, chrome, vlc, etc.). If None, searches all domains.

        Returns:
            Task configuration dict with config array and evaluator

        Raises:
            FileNotFoundError if task does not exist
        """
        # If domain specified, only check that domain
        if domain:
            task_file = self.tasks_dir / domain / f"{task_id}.json"
            if task_file.exists():
                with open(task_file, "r") as f:
                    task = json.load(f)
                logger.info(f"Loaded task {task_id} from domain {domain}")
                return task
            raise FileNotFoundError(f"Task not found: {task_id} in domain {domain}")

        # Otherwise, search all domains
        for domain_dir in self.tasks_dir.iterdir():
            if not domain_dir.is_dir():
                continue

            task_file = domain_dir / f"{task_id}.json"
            if task_file.exists():
                with open(task_file, "r") as f:
                    task = json.load(f)
                logger.info(f"Loaded task {task_id} from domain {domain_dir.name}")
                return task

        raise FileNotFoundError(f"Task not found: {task_id} in any domain")

    def run_assessment(
        self,
        task_id: str,
        vm_ip: str,
        white_agent_url: str,
        artifacts_dir: str,
        domain: str = None,
    ) -> Dict[str, Any]:
        """
        Run assessment on VM using White Agent + Green Agent workflow

        Args:
            task_id: Task identifier
            vm_ip: VM external IP address
            white_agent_url: White Agent API URL
            artifacts_dir: Directory to store artifacts
            domain: Optional OSWorld task domain for loading full task config

        Returns:
            Results dictionary with success, steps, time_sec, etc.
        """
        logger.info(f"Running assessment for task {task_id} on VM {vm_ip}")

        # Load task configuration
        try:
            task = self.load_task(task_id, domain=domain)
        except FileNotFoundError as e:
            return {
                "success": 0,
                "steps": 0,
                "time_sec": 0.0,
                "failure_reason": str(e),
                "artifacts": {},
            }

        # Create artifacts directory
        artifacts_path = Path(artifacts_dir)
        artifacts_path.mkdir(parents=True, exist_ok=True)

        # Initialize White Agent client
        white = WhiteClient(white_agent_url)
        try:
            white.reset()
            logger.info(f"White Agent reset completed: {white_agent_url}")
        except Exception as e:
            logger.error(f"Failed to reset White Agent: {e}")
            return {
                "success": 0,
                "steps": 0,
                "time_sec": 0.0,
                "failure_reason": f"white_agent_error: {e}",
                "artifacts": {},
            }

        # Track execution
        t0 = time.time()
        steps = 0

        def white_decide(obs: Dict[str, Any]) -> Dict[str, Any]:
            nonlocal steps
            steps += 1
            logger.debug(f"Step {steps}: Requesting decision from White Agent")
            return white.decide(obs)

        # Set OSWorld server URL for this VM
        osworld_server_url = f"http://{vm_ip}:5000"
        logger.info(f"Using OSWorld server: {osworld_server_url}")

        # Temporarily set environment variable for run_osworld
        old_url = os.environ.get("OSWORLD_SERVER_URL")
        os.environ["OSWORLD_SERVER_URL"] = osworld_server_url

        try:
            logger.info("Starting OSWorld execution...")
            result = run_osworld(
                task,
                white_decide,
                str(artifacts_path),
                white_agent_url=white_agent_url,
            )

            logger.info(
                f"Assessment completed: success={result.get('success')}, "
                f"steps={result.get('steps')}, time={result.get('time_sec', 0):.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"Assessment execution error: {e}", exc_info=True)
            return {
                "success": 0,
                "steps": steps,
                "time_sec": time.time() - t0,
                "failure_reason": f"adapter_error: {e}",
                "artifacts": {},
            }

        finally:
            # Restore environment variable
            if old_url is not None:
                os.environ["OSWORLD_SERVER_URL"] = old_url
            else:
                os.environ.pop("OSWORLD_SERVER_URL", None)
