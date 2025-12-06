"""
Database module for WebUI
Stores assessment history and provides query interface
"""

import sqlite3
import json
import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class AssessmentDB:
    """SQLite database for assessment history"""

    def __init__(self, db_path: str = "assessments.db"):
        """Initialize database connection"""
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS assessments (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    domain TEXT,
                    status TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    steps INTEGER,
                    success INTEGER,
                    evaluation_score REAL,
                    evaluation_method TEXT,
                    failure_reason TEXT,
                    time_sec REAL,
                    vm_cost REAL,
                    config TEXT,
                    result TEXT,
                    trajectory TEXT,
                    run_number INTEGER DEFAULT 1,
                    batch_id TEXT
                )
            """)

            # Run migration to add new columns to existing databases FIRST
            self._migrate_schema(conn)

            # Create indexes (after migration ensures columns exist)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_started_at ON assessments(started_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON assessments(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_id ON assessments(task_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_domain ON assessments(domain)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_batch_id ON assessments(batch_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_run_number ON assessments(run_number)")

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    def _migrate_schema(self, conn):
        """Migrate existing database schema to add new columns"""
        try:
            # Check if run_number column exists
            cursor = conn.execute("PRAGMA table_info(assessments)")
            columns = [row[1] for row in cursor.fetchall()]

            if "run_number" not in columns:
                logger.info("Migrating database: adding run_number column")
                conn.execute("ALTER TABLE assessments ADD COLUMN run_number INTEGER DEFAULT 1")

            if "batch_id" not in columns:
                logger.info("Migrating database: adding batch_id column")
                conn.execute("ALTER TABLE assessments ADD COLUMN batch_id TEXT")

        except Exception as e:
            logger.warning(f"Schema migration warning: {e}")

    @contextmanager
    def _get_connection(self):
        """Get database connection context manager"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dicts
        try:
            yield conn
        finally:
            conn.close()

    def save_assessment(self, assessment_data: Dict[str, Any]) -> None:
        """Save or update assessment"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO assessments VALUES (
                    :id, :task_id, :domain, :status, :started_at, :completed_at,
                    :steps, :success, :evaluation_score, :evaluation_method,
                    :failure_reason, :time_sec, :vm_cost, :config, :result, :trajectory,
                    :run_number, :batch_id
                )
            """, {
                "id": assessment_data["id"],
                "task_id": assessment_data.get("task_id"),
                "domain": assessment_data.get("domain"),
                "status": assessment_data.get("status", "running"),
                "started_at": assessment_data.get("started_at"),
                "completed_at": assessment_data.get("completed_at"),
                "steps": assessment_data.get("steps", 0),
                "success": assessment_data.get("success"),
                "evaluation_score": assessment_data.get("evaluation_score"),
                "evaluation_method": assessment_data.get("evaluation_method"),
                "failure_reason": assessment_data.get("failure_reason"),
                "time_sec": assessment_data.get("time_sec"),
                "vm_cost": assessment_data.get("vm_cost"),
                "config": json.dumps(assessment_data.get("config", {})),
                "result": json.dumps(assessment_data.get("result", {})),
                "trajectory": json.dumps(assessment_data.get("trajectory", [])),
                "run_number": assessment_data.get("run_number", 1),
                "batch_id": assessment_data.get("batch_id")
            })
            conn.commit()

    def get_assessment(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        """Get single assessment by ID"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM assessments WHERE id = ?",
                (assessment_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_dict(row)

    def list_assessments(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        domain: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List assessments with optional filtering"""
        query = "SELECT * FROM assessments WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if domain:
            query += " AND domain = ?"
            params.append(domain)

        if task_id:
            query += " AND task_id LIKE ?"
            params.append(f"%{task_id}%")

        query += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics"""
        with self._get_connection() as conn:
            # Total assessments
            cursor = conn.execute("SELECT COUNT(*) as count FROM assessments")
            total = cursor.fetchone()["count"]

            # Running assessments
            cursor = conn.execute("SELECT COUNT(*) as count FROM assessments WHERE status = 'running'")
            running = cursor.fetchone()["count"]

            # Success rate (last 24 hours)
            cursor = conn.execute("""
                SELECT
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                    COUNT(*) as total
                FROM assessments
                WHERE completed_at >= datetime('now', '-24 hours')
                AND status = 'completed'
            """)
            row = cursor.fetchone()
            success_rate = (row["successes"] / row["total"] * 100) if row["total"] > 0 else 0

            # Average time
            cursor = conn.execute("""
                SELECT AVG(time_sec) as avg_time
                FROM assessments
                WHERE status = 'completed'
                AND time_sec IS NOT NULL
            """)
            avg_time = cursor.fetchone()["avg_time"] or 0

            # Total cost
            cursor = conn.execute("SELECT SUM(vm_cost) as total_cost FROM assessments WHERE vm_cost IS NOT NULL")
            total_cost = cursor.fetchone()["total_cost"] or 0

            return {
                "total_assessments": total,
                "running_assessments": running,
                "success_rate_24h": round(success_rate, 1),
                "avg_time_sec": round(avg_time, 1),
                "total_cost": round(total_cost, 4)
            }

    def get_batch_assessments(self, batch_id: str) -> List[Dict[str, Any]]:
        """Get all assessments in a batch"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM assessments WHERE batch_id = ? ORDER BY run_number",
                (batch_id,)
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_task_statistics(self, task_id: str, config_hash: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate rolling average statistics for all historical runs of a task

        Args:
            task_id: Task identifier
            config_hash: Optional configuration hash to filter by

        Returns:
            Dictionary with rolling average statistics
        """
        query = """
            SELECT
                COUNT(*) as total_runs,
                AVG(CAST(success AS FLOAT)) * 100 as success_rate,
                AVG(steps) as avg_steps,
                AVG(time_sec) as avg_time_sec,
                AVG(evaluation_score) as avg_evaluation_score,
                AVG(vm_cost) as avg_vm_cost
            FROM assessments
            WHERE task_id = ? AND status = 'completed'
        """
        params = [task_id]

        if config_hash:
            # For now, we'll skip config filtering since we need to implement config hashing
            # This will be added in the next iteration
            pass

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()

            if not row or row["total_runs"] == 0:
                return {
                    "total_runs": 0,
                    "success_rate": 0.0,
                    "avg_steps": 0.0,
                    "avg_time_sec": 0.0,
                    "avg_evaluation_score": None,
                    "avg_vm_cost": 0.0
                }

            return {
                "total_runs": row["total_runs"],
                "success_rate": round(row["success_rate"], 1) if row["success_rate"] else 0.0,
                "avg_steps": round(row["avg_steps"], 1) if row["avg_steps"] else 0.0,
                "avg_time_sec": round(row["avg_time_sec"], 1) if row["avg_time_sec"] else 0.0,
                "avg_evaluation_score": round(row["avg_evaluation_score"], 3) if row["avg_evaluation_score"] else None,
                "avg_vm_cost": round(row["avg_vm_cost"], 4) if row["avg_vm_cost"] else 0.0
            }

    def get_task_leaderboard(
        self,
        task_id: str,
        metric: str = "success_rate",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get leaderboard for a specific task

        Args:
            task_id: Task identifier
            metric: Metric to rank by (success_rate, avg_steps, avg_time_sec, avg_evaluation_score)
            limit: Maximum number of entries to return

        Returns:
            List of agent configurations ranked by metric
        """
        # Map metric names to SQL expressions
        metric_expressions = {
            "success_rate": "AVG(CAST(success AS FLOAT)) * 100",
            "avg_steps": "AVG(steps)",
            "avg_time_sec": "AVG(time_sec)",
            "avg_evaluation_score": "AVG(evaluation_score)"
        }

        # Determine sort order (DESC for success/score, ASC for steps/time)
        sort_order = "DESC" if metric in ["success_rate", "avg_evaluation_score"] else "ASC"

        if metric not in metric_expressions:
            raise ValueError(f"Invalid metric: {metric}")

        query = f"""
            SELECT
                config,
                COUNT(*) as total_runs,
                AVG(CAST(success AS FLOAT)) * 100 as success_rate,
                AVG(steps) as avg_steps,
                AVG(time_sec) as avg_time_sec,
                AVG(evaluation_score) as avg_evaluation_score,
                AVG(vm_cost) as avg_vm_cost
            FROM assessments
            WHERE task_id = ? AND status = 'completed'
            GROUP BY config
            ORDER BY {metric_expressions[metric]} {sort_order}
            LIMIT ?
        """

        with self._get_connection() as conn:
            cursor = conn.execute(query, (task_id, limit))
            results = []

            for rank, row in enumerate(cursor.fetchall(), 1):
                config = json.loads(row["config"]) if row["config"] else {}
                results.append({
                    "rank": rank,
                    "config": config,
                    "config_hash": self._compute_config_hash(config),
                    "success_rate": round(row["success_rate"], 1) if row["success_rate"] else 0.0,
                    "avg_steps": round(row["avg_steps"], 1) if row["avg_steps"] else 0.0,
                    "avg_time_sec": round(row["avg_time_sec"], 1) if row["avg_time_sec"] else 0.0,
                    "avg_evaluation_score": round(row["avg_evaluation_score"], 3) if row["avg_evaluation_score"] else None,
                    "total_runs": row["total_runs"]
                })

            return results

    def get_global_leaderboard(
        self,
        metric: str = "success_rate",
        limit: int = 50,
        domain: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get global leaderboard across all tasks

        Args:
            metric: Metric to rank by
            limit: Maximum number of entries
            domain: Optional domain filter

        Returns:
            List of agent configurations ranked by metric
        """
        metric_expressions = {
            "success_rate": "AVG(CAST(success AS FLOAT)) * 100",
            "avg_steps": "AVG(steps)",
            "avg_time_sec": "AVG(time_sec)",
            "avg_evaluation_score": "AVG(evaluation_score)"
        }

        sort_order = "DESC" if metric in ["success_rate", "avg_evaluation_score"] else "ASC"

        if metric not in metric_expressions:
            raise ValueError(f"Invalid metric: {metric}")

        where_clause = "status = 'completed'"
        params = []

        if domain:
            where_clause += " AND domain = ?"
            params.append(domain)

        query = f"""
            SELECT
                config,
                COUNT(*) as total_runs,
                COUNT(DISTINCT task_id) as tasks_attempted,
                AVG(CAST(success AS FLOAT)) * 100 as success_rate,
                AVG(steps) as avg_steps,
                AVG(time_sec) as avg_time_sec,
                AVG(evaluation_score) as avg_evaluation_score,
                AVG(vm_cost) as avg_vm_cost
            FROM assessments
            WHERE {where_clause}
            GROUP BY config
            ORDER BY {metric_expressions[metric]} {sort_order}
            LIMIT ?
        """

        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            results = []

            for rank, row in enumerate(cursor.fetchall(), 1):
                config = json.loads(row["config"]) if row["config"] else {}
                results.append({
                    "rank": rank,
                    "config": config,
                    "config_hash": self._compute_config_hash(config),
                    "tasks_attempted": row["tasks_attempted"],
                    "success_rate": round(row["success_rate"], 1) if row["success_rate"] else 0.0,
                    "avg_steps": round(row["avg_steps"], 1) if row["avg_steps"] else 0.0,
                    "avg_time_sec": round(row["avg_time_sec"], 1) if row["avg_time_sec"] else 0.0,
                    "avg_evaluation_score": round(row["avg_evaluation_score"], 3) if row["avg_evaluation_score"] else None,
                    "total_runs": row["total_runs"]
                })

            return results

    def get_available_metrics(self) -> List[str]:
        """Get list of available metrics for leaderboards"""
        return ["success_rate", "avg_steps", "avg_time_sec", "avg_evaluation_score"]

    @staticmethod
    def _compute_config_hash(config: Dict[str, Any]) -> str:
        """Compute deterministic hash of agent configuration"""
        # Create canonical string representation
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()[:8]

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert SQLite row to dict"""
        data = dict(row)

        # Parse JSON fields
        if data.get("config"):
            data["config"] = json.loads(data["config"])
        if data.get("result"):
            data["result"] = json.loads(data["result"])
        if data.get("trajectory"):
            data["trajectory"] = json.loads(data["trajectory"])

        return data
