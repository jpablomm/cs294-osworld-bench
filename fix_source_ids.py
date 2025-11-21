#!/usr/bin/env python3
"""
Fix missing source_id values in Supabase tasks table
The source_id should be the OSWorld task filename (UUID without .json extension)
which is the same as the task ID
"""

import os
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    exit(1)

# Create Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

print("Fetching all tasks with missing source_id...")
response = supabase.table("tasks").select("id").is_("source_id", "null").execute()

if not response.data:
    print("No tasks found with missing source_id")
    exit(0)

tasks_to_update = response.data
print(f"Found {len(tasks_to_update)} tasks to update")

# Update each task's source_id to match its id
print("Updating tasks...")
for i, task in enumerate(tasks_to_update, 1):
    task_id = task["id"]

    # Update source_id to be the same as id (the OSWorld task filename)
    supabase.table("tasks").update({"source_id": task_id}).eq("id", task_id).execute()

    if i % 50 == 0:
        print(f"  Updated {i}/{len(tasks_to_update)} tasks...")

print(f"\n✓ Successfully updated {len(tasks_to_update)} tasks")

# Verify the specific task
task_id = "ec4e3f68-9ea4-4c18-a5c9-69f89d1178b3"
response = supabase.table("tasks").select("id, source_id").eq("id", task_id).execute()
if response.data:
    task = response.data[0]
    print(f"\nVerification - Task {task_id}:")
    print(f"  source_id: {task.get('source_id')}")
