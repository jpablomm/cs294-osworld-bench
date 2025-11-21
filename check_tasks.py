#!/usr/bin/env python3
"""Check tasks in Supabase database"""

import os
from supabase import create_client

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    exit(1)

# Create Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Check specific task
task_id = "ec4e3f68-9ea4-4c18-a5c9-69f89d1178b3"
print(f"Checking task: {task_id}")
print("-" * 50)

response = supabase.table("tasks").select("*").eq("id", task_id).execute()

if response.data:
    task = response.data[0]
    print(f"Task found!")
    print(f"  ID: {task.get('id')}")
    print(f"  Source ID: {task.get('source_id')}")
    print(f"  Domain: {task.get('domain')}")
    print(f"  Instruction: {task.get('instruction')[:100]}...")
else:
    print(f"Task NOT found!")

print("\n" + "-" * 50)
print("Checking all tasks...")
response = supabase.table("tasks").select("id, source_id, domain").limit(5).execute()

if response.data:
    print(f"Found {len(response.data)} tasks (showing first 5):")
    for task in response.data:
        print(f"  - {task.get('id')}: source_id={task.get('source_id')}, domain={task.get('domain')}")
else:
    print("No tasks found in database!")
