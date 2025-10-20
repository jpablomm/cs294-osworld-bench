"""
Database module for WebUI
Stores assessment history and provides query interface
"""

import sqlite3
import json
import logging
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
                    trajectory TEXT
                )
            """)

            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_started_at ON assessments(started_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON assessments(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_id ON assessments(task_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_domain ON assessments(domain)")

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

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
                    :failure_reason, :time_sec, :vm_cost, :config, :result, :trajectory
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
                "trajectory": json.dumps(assessment_data.get("trajectory", []))
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
