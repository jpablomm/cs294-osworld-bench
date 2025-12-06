#!/usr/bin/env python3
"""
Load OSWorld tasks from JSON files into Supabase
"""
import json
import os
from pathlib import Path
from supabase import create_client, Client

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required")
    print("Load them from .env file or export them")
    exit(1)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Path to OSWorld examples
EXAMPLES_DIR = Path(__file__).parent.parent / "green_agent" / "tasks_config"

def load_tasks():
    """Load all tasks from OSWorld examples directory"""
    tasks = []

    if not EXAMPLES_DIR.exists():
        print(f"Error: Examples directory not found: {EXAMPLES_DIR}")
        return tasks

    # Iterate through domain subdirectories
    for domain_dir in EXAMPLES_DIR.iterdir():
        if not domain_dir.is_dir():
            continue

        domain = domain_dir.name
        print(f"Loading tasks from domain: {domain}")

        # Load all JSON files in the domain directory
        json_files = list(domain_dir.glob("*.json"))
        print(f"  Found {len(json_files)} task files")

        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)

                # Extract task info
                task = {
                    "id": data.get("id", json_file.stem),
                    "instruction": data.get("instruction") or data.get("task", ""),
                    "domain": data.get("domain", domain),
                    "difficulty": data.get("difficulty"),
                    "source_id": data.get("source_id"),
                    "config": data.get("config"),
                    "evaluator": data.get("evaluator"),
                }

                tasks.append(task)
            except Exception as e:
                print(f"  Error loading {json_file.name}: {e}")

    return tasks

def create_table_if_not_exists():
    """Create tasks table if it doesn't exist"""
    print("Ensuring tasks table exists...")
    try:
        # Try to query the table
        supabase.table("tasks").select("id").limit(1).execute()
        print("  Table exists")
    except Exception as e:
        if "PGRST205" in str(e):  # Table doesn't exist
            print("  Table doesn't exist, will create on first insert")
        else:
            print(f"  Warning: {e}")

def insert_tasks(tasks):
    """Insert tasks into Supabase"""
    print(f"\nInserting {len(tasks)} tasks into Supabase...")

    # Try to clear existing tasks (table might not exist yet)
    try:
        print("Clearing existing tasks...")
        supabase.table("tasks").delete().neq("id", "").execute()
    except Exception as e:
        print(f"  Could not clear (table might not exist): {e}")
        print("  Will insert tasks (table will be created)")

    # Insert in batches of 100
    batch_size = 100
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i + batch_size]
        try:
            result = supabase.table("tasks").insert(batch).execute()
            print(f"  Inserted batch {i//batch_size + 1} ({len(batch)} tasks)")
        except Exception as e:
            print(f"  Error inserting batch {i//batch_size + 1}: {e}")

    print("\nDone!")

if __name__ == "__main__":
    print("Loading OSWorld tasks from filesystem...")
    tasks = load_tasks()

    print(f"\nLoaded {len(tasks)} tasks from {len(set(t['domain'] for t in tasks))} domains")

    if tasks:
        insert_tasks(tasks)

        # Verify
        count = supabase.table("tasks").select("id", count="exact").execute()
        print(f"\nVerification: {count.count} tasks in database")
    else:
        print("No tasks found!")
