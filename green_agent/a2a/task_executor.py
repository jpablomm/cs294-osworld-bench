"""
Task Executor - Task Configuration Loader

Loads OSWorld task configurations from JSON files.
The actual assessment execution is handled by a2a/server.py.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class TaskExecutor:
    """Loads OSWorld task configurations from JSON files"""

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
