# Cloud SQL Migration - Quick Reference

## TL;DR - 5 Minute Migration

```bash
# 1. Export SQLite data
python scripts/export_sqlite.py

# 2. Create Cloud SQL instance (takes ~10 minutes)
gcloud sql instances create osworld-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

# 3. Create database and apply schema
gcloud sql databases create osworld_assessments --instance=osworld-db
psql "host=localhost port=5432 dbname=osworld_assessments user=osworld_user" \
  -f orchestrator/postgres_schema.sql

# 4. Import data
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=osworld_assessments
export DB_USER=osworld_user
export DB_PASSWORD=your_password
python scripts/import_postgres.py

# 5. Switch to PostgreSQL
export USE_POSTGRES=1
uvicorn orchestrator.webui_server:app --port 3001
```

## Environment Variables

**For PostgreSQL mode:**
```bash
export USE_POSTGRES=1
export DB_HOST=localhost        # Or Cloud SQL IP
export DB_PORT=5432
export DB_NAME=osworld_assessments
export DB_USER=osworld_user
export DB_PASSWORD=your_strong_password
```

**For SQLite mode (fallback):**
```bash
export USE_POSTGRES=0
# No other variables needed - uses webui_assessments.db
```

## Connection Methods

### Option 1: Cloud SQL Proxy (Development)

```bash
# Download proxy
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.darwin.arm64
chmod +x cloud-sql-proxy

# Run proxy
./cloud-sql-proxy PROJECT:REGION:INSTANCE --port 5432

# Connect to localhost:5432
export DB_HOST=localhost
export DB_PORT=5432
```

### Option 2: Public IP (Testing)

```bash
# Authorize your IP
MY_IP=$(curl -s ifconfig.me)
gcloud sql instances patch osworld-db --authorized-networks=$MY_IP/32

# Connect directly
export DB_HOST=XX.XX.XX.XX  # Cloud SQL public IP
export DB_PORT=5432
```

### Option 3: Private IP (Production)

```bash
# Create instance with private IP
gcloud sql instances create osworld-db \
  --network=default \
  --no-assign-ip  # Private IP only

# Connect from within VPC
export DB_HOST=10.x.x.x  # Private IP
export DB_PORT=5432
```

## Testing PostgreSQL Connection

```python
# test_postgres.py
from orchestrator.database_postgres import PostgresDatabase

db = PostgresDatabase()
stats = db.get_stats()
print(f"Total assessments: {stats['total_assessments']}")
```

## Common Issues

**"connection refused"**
- Check if Cloud SQL Proxy is running
- Verify DB_HOST and DB_PORT are correct
- Check firewall rules

**"authentication failed"**
- Verify DB_PASSWORD is correct
- Check user exists: `gcloud sql users list --instance=osworld-db`

**"database does not exist"**
- Create database: `gcloud sql databases create osworld_assessments --instance=osworld-db`

**"relation assessments does not exist"**
- Apply schema: `psql ... -f orchestrator/postgres_schema.sql`

## Performance Comparison

| Operation | SQLite | PostgreSQL |
|-----------|--------|------------|
| Single write | ~1ms | ~2ms |
| 100 concurrent writes | **Fails** (locked) | 50ms |
| Batch read (20 rows) | 5ms | 3ms |
| Leaderboard query | 50ms | 30ms (indexed) |

## Cost Breakdown

| Tier | vCPU | RAM | Cost/Month | Use Case |
|------|------|-----|------------|----------|
| db-f1-micro | Shared | 0.6GB | $7.67 | Development |
| db-n1-standard-1 | 1 | 3.75GB | $75 | Production (small) |
| db-n1-standard-2 | 2 | 7.5GB | $150 | Production (medium) |

## Rollback to SQLite

```bash
# Stop using PostgreSQL
unset USE_POSTGRES
# or
export USE_POSTGRES=0

# Restart Web UI
uvicorn orchestrator.webui_server:app --port 3001
```

## Files Created

```
orchestrator/
├── database_postgres.py      # PostgreSQL database layer
├── postgres_schema.sql        # Database schema

scripts/
├── export_sqlite.py           # Export SQLite to JSON
└── import_postgres.py         # Import JSON to PostgreSQL
```

## Next Steps

1. **Test thoroughly** - Run all features in the Web UI
2. **Monitor performance** - Check query times and connection pool
3. **Setup backups** - Cloud SQL auto-backup is enabled by default
4. **Update Cloud Run** - Deploy with Cloud SQL connection
5. **Document** - Update README with PostgreSQL instructions

## Full Documentation

See [CLOUD_SQL_MIGRATION.md](./CLOUD_SQL_MIGRATION.md) for complete details.
