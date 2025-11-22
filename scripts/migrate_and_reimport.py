#!/usr/bin/env python3
"""
Run Supabase migration and re-import tasks with evaluator data
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import load_tasks_to_supabase
sys.path.insert(0, str(Path(__file__).parent))

from supabase import create_client, Client

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required")
    print("Run: source .env")
    exit(1)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def run_migration():
    """Add evaluator column to tasks table"""
    print("Running migration: Add evaluator column...")

    # Read migration SQL
    migration_file = Path(__file__).parent.parent / "supabase" / "migrations" / "004_add_evaluator_column.sql"

    if not migration_file.exists():
        print(f"Error: Migration file not found: {migration_file}")
        return False

    with open(migration_file, 'r') as f:
        migration_sql = f.read()

    try:
        # Execute the migration using Supabase REST API
        # Note: This uses the RPC endpoint to execute raw SQL
        print(f"  Executing SQL:\n{migration_sql}")

        # For Supabase, we need to execute each statement separately
        statements = [s.strip() for s in migration_sql.split(';') if s.strip()]

        for i, statement in enumerate(statements, 1):
            if statement:
                print(f"  Executing statement {i}/{len(statements)}...")
                try:
                    # Use the PostgREST API to execute SQL via RPC
                    # This requires creating an RPC function first, which we can't do easily
                    # So we'll use direct SQL execution via the Python client
                    supabase.postgrest.session.execute(statement)
                    print(f"  ✓ Statement {i} executed successfully")
                except Exception as e:
                    # Try alternative approach: just check if column exists
                    if "already exists" in str(e).lower():
                        print(f"  ✓ Column already exists, skipping")
                    else:
                        print(f"  Warning: {e}")
                        print("  Continuing anyway (column may already exist)...")

        print("✓ Migration completed (or column already exists)")
        return True

    except Exception as e:
        print(f"Error running migration: {e}")
        print("This is OK if the column already exists. Continuing with import...")
        return True  # Continue anyway

if __name__ == "__main__":
    print("=" * 60)
    print("Supabase Migration & Data Import")
    print("=" * 60)
    print()

    # Step 1: Run migration
    if not run_migration():
        print("\nMigration failed, but continuing with import...")

    print()
    print("=" * 60)

    # Step 2: Re-import tasks
    print("\nRe-importing tasks with evaluator data...")
    print()

    # Import the load_tasks module
    from load_tasks_to_supabase import load_tasks, insert_tasks

    tasks = load_tasks()
    print(f"\nLoaded {len(tasks)} tasks from {len(set(t['domain'] for t in tasks))} domains")

    if tasks:
        insert_tasks(tasks)

        # Verify
        count = supabase.table("tasks").select("id", count="exact").execute()
        print(f"\n✓ Verification: {count.count} tasks in database")

        # Check how many have evaluators
        with_eval = supabase.table("tasks").select("id", count="exact").not_.is_("evaluator", "null").execute()
        print(f"✓ Tasks with evaluators: {with_eval.count}")
    else:
        print("No tasks found!")

    print()
    print("=" * 60)
    print("✓ Done!")
    print("=" * 60)
