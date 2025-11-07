# Migration Guide: SQLite to GCP Cloud SQL

## Overview

This guide covers migrating the OSWorld Green Agent orchestrator from SQLite to GCP Cloud SQL (PostgreSQL) for production scalability.

## Why Migrate?

**SQLite Limitations:**
- ❌ No concurrent writes (locks entire database)
- ❌ File-based (not suitable for distributed systems)
- ❌ No built-in replication or high availability
- ❌ Limited for Cloud Run (ephemeral filesystem)

**Cloud SQL Benefits:**
- ✅ Concurrent reads and writes
- ✅ High availability with automatic failover
- ✅ Automatic backups and point-in-time recovery
- ✅ Scalable (vertical and read replicas)
- ✅ Managed service (no maintenance)
- ✅ Connection pooling support

## Migration Strategy

We'll use **PostgreSQL** on Cloud SQL for better JSON support and standard SQL compliance.

### Phase 1: Setup Cloud SQL Instance

#### 1.1 Create Cloud SQL Instance

```bash
# Set variables
PROJECT_ID=$(gcloud config get-value project)
INSTANCE_NAME="osworld-db"
REGION="us-central1"
DATABASE_VERSION="POSTGRES_15"
TIER="db-f1-micro"  # For testing; use db-n1-standard-1+ for production

# Create instance (takes ~10 minutes)
gcloud sql instances create $INSTANCE_NAME \
  --database-version=$DATABASE_VERSION \
  --tier=$TIER \
  --region=$REGION \
  --backup-start-time=03:00 \
  --backup-location=$REGION \
  --maintenance-window-day=SUN \
  --maintenance-window-hour=4 \
  --enable-bin-log \
  --retained-backups-count=7 \
  --database-flags=max_connections=100

# Create database
gcloud sql databases create osworld_assessments \
  --instance=$INSTANCE_NAME

# Create user
gcloud sql users create osworld_user \
  --instance=$INSTANCE_NAME \
  --password=$(openssl rand -base64 32)
```

**Cost Estimate:**
- `db-f1-micro`: ~$7.67/month (shared CPU, 0.6GB RAM) - Development only
- `db-n1-standard-1`: ~$75/month (1 vCPU, 3.75GB RAM) - Production minimum
- `db-n1-standard-2`: ~$150/month (2 vCPU, 7.5GB RAM) - Recommended for production

#### 1.2 Configure Networking

**Option A: Public IP with Authorized Networks** (Simpler, less secure)
```bash
# Get your IP
MY_IP=$(curl -s ifconfig.me)

# Authorize your IP
gcloud sql instances patch $INSTANCE_NAME \
  --authorized-networks=$MY_IP/32

# Get connection name
gcloud sql instances describe $INSTANCE_NAME --format="value(connectionName)"
# Output: PROJECT_ID:REGION:INSTANCE_NAME
```

**Option B: Private IP with VPC** (Recommended for production)
```bash
# Enable Service Networking API
gcloud services enable servicenetworking.googleapis.com

# Allocate IP range for Cloud SQL
gcloud compute addresses create google-managed-services-default \
  --global \
  --purpose=VPC_PEERING \
  --prefix-length=16 \
  --network=default

# Create private connection
gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=google-managed-services-default \
  --network=default

# Create Cloud SQL instance with private IP
gcloud sql instances create $INSTANCE_NAME \
  --database-version=$DATABASE_VERSION \
  --tier=$TIER \
  --region=$REGION \
  --network=projects/$PROJECT_ID/global/networks/default \
  --no-assign-ip  # Private IP only
```

**Option C: Cloud SQL Proxy** (Best for development/testing)
```bash
# Download Cloud SQL Proxy
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.darwin.arm64
chmod +x cloud-sql-proxy

# Run proxy (in separate terminal)
./cloud-sql-proxy $PROJECT_ID:$REGION:$INSTANCE_NAME --port 5432

# Now connect to localhost:5432
```

### Phase 2: Update Database Schema

#### 2.1 Create PostgreSQL Schema

Create `orchestrator/postgres_schema.sql`:

```sql
-- PostgreSQL schema for OSWorld assessments

CREATE TABLE IF NOT EXISTS assessments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    domain TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    success INTEGER CHECK (success IN (0, 1)),
    evaluation_score REAL,
    steps INTEGER,
    time_sec REAL,
    vm_cost REAL,
    failure_reason TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    trajectory JSONB,  -- PostgreSQL native JSON
    artifacts JSONB,   -- PostgreSQL native JSON
    config JSONB,      -- PostgreSQL native JSON
    batch_id TEXT,
    run_number INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_assessments_batch_id ON assessments(batch_id);
CREATE INDEX IF NOT EXISTS idx_assessments_run_number ON assessments(run_number);
CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments(status);
CREATE INDEX IF NOT EXISTS idx_assessments_domain ON assessments(domain);
CREATE INDEX IF NOT EXISTS idx_assessments_task_id ON assessments(task_id);
CREATE INDEX IF NOT EXISTS idx_assessments_started_at ON assessments(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_assessments_config ON assessments USING gin(config);  -- For JSON queries

-- Updated timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_assessments_updated_at BEFORE UPDATE ON assessments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- View for leaderboard (global)
CREATE OR REPLACE VIEW leaderboard_global AS
SELECT
    config,
    COUNT(DISTINCT task_id) as tasks_attempted,
    COUNT(*) as total_runs,
    AVG(CASE WHEN success = 1 THEN 100.0 ELSE 0.0 END) as success_rate,
    AVG(steps) as avg_steps,
    AVG(time_sec) as avg_time_sec,
    AVG(evaluation_score) as avg_evaluation_score
FROM assessments
WHERE status = 'completed'
GROUP BY config;

-- View for leaderboard (per-task)
CREATE OR REPLACE VIEW leaderboard_per_task AS
SELECT
    task_id,
    config,
    COUNT(*) as total_runs,
    AVG(CASE WHEN success = 1 THEN 100.0 ELSE 0.0 END) as success_rate,
    AVG(steps) as avg_steps,
    AVG(time_sec) as avg_time_sec,
    AVG(evaluation_score) as avg_evaluation_score
FROM assessments
WHERE status = 'completed'
GROUP BY task_id, config;
```

#### 2.2 Apply Schema

```bash
# Using psql (if installed)
psql "host=localhost port=5432 dbname=osworld_assessments user=osworld_user password=YOUR_PASSWORD" \
  -f orchestrator/postgres_schema.sql

# Or via Cloud SQL proxy
./cloud-sql-proxy $PROJECT_ID:$REGION:$INSTANCE_NAME --port 5432 &
psql "host=localhost port=5432 dbname=osworld_assessments user=osworld_user" \
  -f orchestrator/postgres_schema.sql
```

### Phase 3: Update Application Code

#### 3.1 Update Dependencies

Add to `requirements.txt`:
```text
# PostgreSQL support
psycopg2-binary==2.9.9  # PostgreSQL adapter
sqlalchemy==2.0.23      # ORM (optional, for easier migration)
cloud-sql-python-connector[pg8000]==1.5.0  # Cloud SQL connector
```

Install:
```bash
pip install -r requirements.txt
```

#### 3.2 Create Database Abstraction Layer

Create `orchestrator/database_postgres.py`:

```python
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

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = psycopg2.connect(**self.conn_params)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
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
                    **assessment,
                    "trajectory": trajectory_json,
                    "artifacts": artifacts_json,
                    "config": config_json,
                })

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

    def get_batch(self, batch_id: str) -> Dict[str, Any]:
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

                return dict(cur.fetchone())
```

#### 3.3 Update webui_server.py

Update `orchestrator/webui_server.py` to support both databases:

```python
import os
from orchestrator.database import Database as SQLiteDatabase
from orchestrator.database_postgres import PostgresDatabase

# Determine which database to use
USE_POSTGRES = os.getenv("USE_POSTGRES", "0") == "1"

if USE_POSTGRES:
    db = PostgresDatabase()
    logger.info("Using PostgreSQL database")
else:
    db = SQLiteDatabase("webui_assessments.db")
    logger.info("Using SQLite database")
```

### Phase 4: Data Migration

#### 4.1 Export SQLite Data

Create `scripts/export_sqlite.py`:

```python
import sqlite3
import json
from datetime import datetime

def export_sqlite_to_json(sqlite_path: str, output_path: str):
    """Export SQLite database to JSON"""
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM assessments")
    rows = cur.fetchall()

    assessments = []
    for row in rows:
        assessment = dict(row)
        # Parse JSON fields
        if assessment.get("trajectory"):
            assessment["trajectory"] = json.loads(assessment["trajectory"])
        if assessment.get("artifacts"):
            assessment["artifacts"] = json.loads(assessment["artifacts"])
        if assessment.get("config"):
            assessment["config"] = json.loads(assessment["config"])
        assessments.append(assessment)

    conn.close()

    with open(output_path, "w") as f:
        json.dump(assessments, f, indent=2, default=str)

    print(f"Exported {len(assessments)} assessments to {output_path}")

if __name__ == "__main__":
    export_sqlite_to_json("webui_assessments.db", "assessments_export.json")
```

Run:
```bash
python scripts/export_sqlite.py
```

#### 4.2 Import to PostgreSQL

Create `scripts/import_postgres.py`:

```python
import json
from orchestrator.database_postgres import PostgresDatabase

def import_json_to_postgres(json_path: str):
    """Import JSON data to PostgreSQL"""
    db = PostgresDatabase()

    with open(json_path) as f:
        assessments = json.load(f)

    for assessment in assessments:
        try:
            db.create_assessment(assessment)
        except Exception as e:
            print(f"Error importing {assessment['id']}: {e}")

    print(f"Imported {len(assessments)} assessments")

if __name__ == "__main__":
    import_json_to_postgres("assessments_export.json")
```

Run:
```bash
export USE_POSTGRES=1
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=osworld_assessments
export DB_USER=osworld_user
export DB_PASSWORD=YOUR_PASSWORD

python scripts/import_postgres.py
```

### Phase 5: Testing

#### 5.1 Test Database Operations

```bash
# Set environment variables
export USE_POSTGRES=1
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=osworld_assessments
export DB_USER=osworld_user
export DB_PASSWORD=YOUR_PASSWORD

# Start Web UI
uvicorn orchestrator.webui_server:app --port 3001

# Test in browser
open http://localhost:3001
```

#### 5.2 Performance Testing

```python
# scripts/test_performance.py
import time
from orchestrator.database_postgres import PostgresDatabase

db = PostgresDatabase()

# Test concurrent writes
start = time.time()
for i in range(100):
    db.create_assessment({
        "id": f"test-{i}",
        "task_id": "performance-test",
        "status": "completed",
        "success": 1
    })
duration = time.time() - start
print(f"100 writes: {duration:.2f}s ({100/duration:.1f} writes/sec)")

# Test batch queries
start = time.time()
for i in range(100):
    db.list_assessments(limit=20)
duration = time.time() - start
print(f"100 list queries: {duration:.2f}s ({100/duration:.1f} queries/sec)")
```

### Phase 6: Production Deployment

#### 6.1 Update Cloud Run Configuration

Update `deploy_orchestrator.sh`:

```bash
# Deploy with Cloud SQL connection
gcloud run deploy osworld-orchestrator \
  --image gcr.io/$PROJECT_ID/osworld-orchestrator \
  --region us-central1 \
  --platform managed \
  --add-cloudsql-instances $PROJECT_ID:us-central1:osworld-db \
  --set-env-vars USE_POSTGRES=1 \
  --set-env-vars DB_HOST=/cloudsql/$PROJECT_ID:us-central1:osworld-db \
  --set-env-vars DB_NAME=osworld_assessments \
  --set-env-vars DB_USER=osworld_user \
  --set-secrets DB_PASSWORD=osworld-db-password:latest
```

#### 6.2 Store Secrets

```bash
# Create secret for database password
echo -n "YOUR_STRONG_PASSWORD" | gcloud secrets create osworld-db-password \
  --data-file=-

# Grant Cloud Run service account access
gcloud secrets add-iam-policy-binding osworld-db-password \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Phase 7: Monitoring and Maintenance

#### 7.1 Enable Cloud SQL Monitoring

```bash
# Create uptime check
gcloud monitoring uptime create sql-health-check \
  --resource-type=cloudsql-database \
  --resource-labels=database_id=$PROJECT_ID:osworld-db

# Create alert policy
gcloud alpha monitoring policies create \
  --notification-channels=YOUR_CHANNEL_ID \
  --display-name="Cloud SQL High Connections" \
  --condition-display-name="Connection count > 80" \
  --condition-threshold-value=80
```

#### 7.2 Backup Strategy

Cloud SQL automatically backs up daily. To restore:

```bash
# List backups
gcloud sql backups list --instance=$INSTANCE_NAME

# Restore from backup
gcloud sql backups restore BACKUP_ID \
  --backup-instance=$INSTANCE_NAME \
  --backup-instance=$INSTANCE_NAME
```

## Rollback Plan

If issues occur, rollback to SQLite:

```bash
# Stop using PostgreSQL
export USE_POSTGRES=0

# Restart Web UI
uvicorn orchestrator.webui_server:app --port 3001
```

## Cost Optimization

**Development:**
- Use `db-f1-micro` (~$7.67/month)
- No high availability
- Shared CPU

**Production:**
- Use `db-n1-standard-1` or higher
- Enable high availability (+100% cost)
- Enable automated backups (included)
- Consider read replicas for read-heavy workloads

## Checklist

- [ ] Create Cloud SQL instance
- [ ] Apply PostgreSQL schema
- [ ] Install dependencies (psycopg2, etc.)
- [ ] Create `database_postgres.py`
- [ ] Update `webui_server.py` to support both databases
- [ ] Export SQLite data to JSON
- [ ] Import JSON data to PostgreSQL
- [ ] Test all CRUD operations
- [ ] Test leaderboard queries
- [ ] Test batch operations
- [ ] Performance test (concurrent writes/reads)
- [ ] Update Cloud Run deployment
- [ ] Store database password in Secret Manager
- [ ] Enable monitoring and alerts
- [ ] Document rollback procedure
- [ ] Update README.md

## References

- [Cloud SQL for PostgreSQL](https://cloud.google.com/sql/docs/postgres)
- [Cloud SQL Proxy](https://cloud.google.com/sql/docs/postgres/sql-proxy)
- [Connecting from Cloud Run](https://cloud.google.com/sql/docs/postgres/connect-run)
- [psycopg2 Documentation](https://www.psycopg.org/docs/)
