"""PostgreSQL database layer for OSWorld assessments"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PostgresDatabase:
    """PostgreSQL database layer for assessments"""

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize PostgreSQL connection

        Args:
            connection_string: PostgreSQL connection string or None to use env vars
                Format: "host=X port=Y dbname=Z user=W password=V"
        """
        if connection_string:
            self.conn_params = connection_string
        else:
            # Build from environment variables
            self.conn_params = {
                "host": os.getenv("DB_HOST", "localhost"),
                "port": int(os.getenv("DB_PORT", "5432")),
                "dbname": os.getenv("DB_NAME", "osworld_assessments"),
                "user": os.getenv("DB_USER", "osworld_user"),
                "password": os.getenv("DB_PASSWORD", ""),
            }

        # Test connection
        self._test_connection()
        logger.info("PostgreSQL database initialized")

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = psycopg2.connect(**self.conn_params)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise e
        finally:
            conn.close()

    def _test_connection(self):
        """Test database connection"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            logger.info("Database connection successful")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def create_assessment(self, assessment: Dict[str, Any]) -> str:
        """Create new assessment record"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Convert Python dicts to JSON
                trajectory_json = Json(assessment.get("trajectory")) if assessment.get("trajectory") else None
                artifacts_json = Json(assessment.get("artifacts")) if assessment.get("artifacts") else None
                config_json = Json(assessment.get("config")) if assessment.get("config") else None

                cur.execute("""
                    INSERT INTO assessments (
                        id, task_id, domain, status, success, evaluation_score,
                        steps, time_sec, vm_cost, failure_reason, started_at,
                        completed_at, trajectory, artifacts, config, batch_id, run_number
                    ) VALUES (
                        %(id)s, %(task_id)s, %(domain)s, %(status)s, %(success)s, %(evaluation_score)s,
                        %(steps)s, %(time_sec)s, %(vm_cost)s, %(failure_reason)s, %(started_at)s,
                        %(completed_at)s, %(trajectory)s, %(artifacts)s, %(config)s, %(batch_id)s, %(run_number)s
                    )
                """, {
                    "id": assessment.get("id"),
                    "task_id": assessment.get("task_id"),
                    "domain": assessment.get("domain"),
                    "status": assessment.get("status"),
                    "success": assessment.get("success"),
                    "evaluation_score": assessment.get("evaluation_score"),
                    "steps": assessment.get("steps"),
                    "time_sec": assessment.get("time_sec"),
                    "vm_cost": assessment.get("vm_cost"),
                    "failure_reason": assessment.get("failure_reason"),
                    "started_at": assessment.get("started_at"),
                    "completed_at": assessment.get("completed_at"),
                    "trajectory": trajectory_json,
                    "artifacts": artifacts_json,
                    "config": config_json,
                    "batch_id": assessment.get("batch_id"),
                    "run_number": assessment.get("run_number"),
                })

        logger.info(f"Created assessment: {assessment['id']}")
        return assessment["id"]

    def update_assessment(self, assessment_id: str, updates: Dict[str, Any]):
        """Update assessment record"""
        # Convert JSON fields
        if "trajectory" in updates and updates["trajectory"]:
            updates["trajectory"] = Json(updates["trajectory"])
        if "artifacts" in updates and updates["artifacts"]:
            updates["artifacts"] = Json(updates["artifacts"])
        if "config" in updates and updates["config"]:
            updates["config"] = Json(updates["config"])

        # Build SET clause dynamically
        set_parts = [f"{key} = %({key})s" for key in updates.keys()]
        set_clause = ", ".join(set_parts)

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE assessments SET {set_clause} WHERE id = %(id)s",
                    {**updates, "id": assessment_id}
                )

        logger.info(f"Updated assessment: {assessment_id}")

    def get_assessment(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        """Get assessment by ID"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM assessments WHERE id = %s", (assessment_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def list_assessments(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        domain: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """List assessments with filters"""
        conditions = []
        params = {"limit": limit, "offset": offset}

        if status:
            conditions.append("status = %(status)s")
            params["status"] = status
        if domain:
            conditions.append("domain = %(domain)s")
            params["domain"] = domain
        if task_id:
            conditions.append("task_id LIKE %(task_id)s")
            params["task_id"] = f"%{task_id}%"

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get total count
                cur.execute(f"SELECT COUNT(*) as total FROM assessments {where_clause}", params)
                total = cur.fetchone()["total"]

                # Get assessments
                cur.execute(f"""
                    SELECT * FROM assessments {where_clause}
                    ORDER BY started_at DESC
                    LIMIT %(limit)s OFFSET %(offset)s
                """, params)

                assessments = [dict(row) for row in cur.fetchall()]

        return {
            "assessments": assessments,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get batch status and runs"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        batch_id,
                        COUNT(*) as total_runs,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_runs,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_runs,
                        AVG(CASE WHEN success = 1 THEN 100.0 ELSE 0.0 END) as success_rate,
                        AVG(steps) as avg_steps,
                        AVG(time_sec) as avg_time_sec
                    FROM assessments
                    WHERE batch_id = %s
                    GROUP BY batch_id
                """, (batch_id,))

                batch_stats = cur.fetchone()
                if not batch_stats:
                    return None

                # Get individual runs
                cur.execute("""
                    SELECT id, status, success, steps, time_sec, failure_reason
                    FROM assessments
                    WHERE batch_id = %s
                    ORDER BY run_number
                """, (batch_id,))

                runs = [dict(row) for row in cur.fetchall()]

        return {
            **dict(batch_stats),
            "runs": runs
        }

    def get_global_leaderboard(
        self,
        metric: str = "success_rate",
        domain: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get global leaderboard"""
        domain_filter = "AND domain = %(domain)s" if domain else ""

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT
                        config,
                        COUNT(DISTINCT task_id) as tasks_attempted,
                        COUNT(*) as total_runs,
                        AVG(CASE WHEN success = 1 THEN 100.0 ELSE 0.0 END) as success_rate,
                        AVG(steps) as avg_steps,
                        AVG(time_sec) as avg_time_sec,
                        AVG(evaluation_score) as avg_evaluation_score
                    FROM assessments
                    WHERE status = 'completed' {domain_filter}
                    GROUP BY config
                    ORDER BY {metric} {"ASC" if "steps" in metric or "time" in metric else "DESC"}
                """, {"domain": domain} if domain else {})

                leaderboard = [dict(row) for row in cur.fetchall()]

                # Add rank
                for i, entry in enumerate(leaderboard, 1):
                    entry["rank"] = i

                return leaderboard

    def get_task_leaderboard(
        self,
        task_id: str,
        metric: str = "success_rate"
    ) -> List[Dict[str, Any]]:
        """Get per-task leaderboard"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT
                        config,
                        COUNT(*) as total_runs,
                        AVG(CASE WHEN success = 1 THEN 100.0 ELSE 0.0 END) as success_rate,
                        AVG(steps) as avg_steps,
                        AVG(time_sec) as avg_time_sec,
                        AVG(evaluation_score) as avg_evaluation_score
                    FROM assessments
                    WHERE status = 'completed' AND task_id = %s
                    GROUP BY config
                    ORDER BY {metric} {"ASC" if "steps" in metric or "time" in metric else "DESC"}
                """, (task_id,))

                leaderboard = [dict(row) for row in cur.fetchall()]

                # Add rank
                for i, entry in enumerate(leaderboard, 1):
                    entry["rank"] = i

                return leaderboard

    def get_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) as total_assessments,
                        SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_assessments,
                        AVG(CASE WHEN status = 'completed' AND started_at > NOW() - INTERVAL '24 hours'
                            THEN CASE WHEN success = 1 THEN 100.0 ELSE 0.0 END END) as success_rate_24h,
                        AVG(time_sec) as avg_time_sec,
                        SUM(vm_cost) as total_cost
                    FROM assessments
                """)

                stats = dict(cur.fetchone())

                # Handle None values
                stats["success_rate_24h"] = stats["success_rate_24h"] or 0
                stats["avg_time_sec"] = stats["avg_time_sec"] or 0
                stats["total_cost"] = stats["total_cost"] or 0

                return stats
