#!/usr/bin/env python3
"""Import JSON data to PostgreSQL"""

import json
import sys
import os
from pathlib import Path

# Add parent directory to path to import orchestrator module
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.database_postgres import PostgresDatabase

def import_json_to_postgres(json_path: str, dry_run: bool = False):
    """Import JSON data to PostgreSQL"""
    if not Path(json_path).exists():
        print(f"Error: JSON file not found at {json_path}")
        sys.exit(1)

    # Check environment variables
    required_env = ["DB_HOST", "DB_NAME", "DB_USER"]
    missing = [env for env in required_env if not os.getenv(env)]
    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}")
        print("\nPlease set:")
        print("  export DB_HOST=localhost")
        print("  export DB_PORT=5432")
        print("  export DB_NAME=osworld_assessments")
        print("  export DB_USER=osworld_user")
        print("  export DB_PASSWORD=your_password")
        sys.exit(1)

    # Load JSON data
    print(f"Loading data from {json_path}...")
    with open(json_path) as f:
        assessments = json.load(f)

    print(f"Found {len(assessments)} assessments to import")

    if dry_run:
        print("\nDRY RUN - No data will be imported")
        print("\nSample assessment:")
        print(json.dumps(assessments[0], indent=2, default=str))
        return

    # Connect to PostgreSQL
    print("\nConnecting to PostgreSQL...")
    try:
        db = PostgresDatabase()
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        sys.exit(1)

    # Import assessments
    print("\nImporting assessments...")
    success_count = 0
    error_count = 0

    for i, assessment in enumerate(assessments, 1):
        try:
            db.create_assessment(assessment)
            success_count += 1

            if i % 10 == 0:
                print(f"  Progress: {i}/{len(assessments)} ({i/len(assessments)*100:.1f}%)")

        except Exception as e:
            error_count += 1
            print(f"  Error importing {assessment.get('id', 'unknown')}: {e}")

    print(f"\n✓ Import complete!")
    print(f"  Successful: {success_count}")
    print(f"  Errors: {error_count}")
    print(f"  Total: {len(assessments)}")

    # Verify import
    print("\nVerifying import...")
    stats = db.get_stats()
    print(f"  Total assessments in database: {stats['total_assessments']}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import JSON data to PostgreSQL")
    parser.add_argument(
        "--input",
        default="assessments_export.json",
        help="Input JSON file path (default: assessments_export.json)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without actually importing"
    )

    args = parser.parse_args()

    import_json_to_postgres(args.input, dry_run=args.dry_run)
