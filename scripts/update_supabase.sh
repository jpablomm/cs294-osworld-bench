#!/bin/bash
set -e

echo "============================================"
echo "Updating Supabase with evaluator support"
echo "============================================"
echo

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

# Check required variables
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_KEY" ]; then
    echo "Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env"
    exit 1
fi

# Extract PostgreSQL connection string from Supabase URL
PROJECT_ID=$(echo $SUPABASE_URL | sed 's/https:\/\///' | sed 's/.supabase.co//')

echo "Step 1: Adding evaluator column to tasks table..."
echo "Please run this SQL in your Supabase dashboard SQL editor:"
echo "https://app.supabase.com/project/$PROJECT_ID/sql"
echo
echo "  ALTER TABLE tasks ADD COLUMN IF NOT EXISTS evaluator JSONB;"
echo "  CREATE INDEX IF NOT EXISTS idx_tasks_has_evaluator ON tasks((evaluator IS NOT NULL));"
echo
read -p "Press Enter after running the SQL in dashboard..."

echo
echo "Step 2: Re-importing tasks with evaluator data..."
python3 scripts/load_tasks_to_supabase.py

echo
echo "============================================"
echo "✓ Done!"
echo "============================================"
