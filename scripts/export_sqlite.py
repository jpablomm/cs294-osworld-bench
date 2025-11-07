#!/usr/bin/env python3
"""Export SQLite database to JSON for migration to PostgreSQL"""

import sqlite3
import json
import sys
from pathlib import Path

def export_sqlite_to_json(sqlite_path: str, output_path: str):
    """Export SQLite database to JSON"""
    if not Path(sqlite_path).exists():
        print(f"Error: SQLite database not found at {sqlite_path}")
        sys.exit(1)

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get all assessments
    try:
        cur.execute("SELECT * FROM assessments ORDER BY created_at")
    except sqlite3.OperationalError as e:
        print(f"Error reading assessments table: {e}")
        print("Make sure the database exists and has the assessments table")
        sys.exit(1)

    rows = cur.fetchall()

    assessments = []
    for row in rows:
        assessment = dict(row)

        # Parse JSON fields
        for field in ["trajectory", "artifacts", "config"]:
            if assessment.get(field):
                try:
                    assessment[field] = json.loads(assessment[field])
                except (json.JSONDecodeError, TypeError):
                    # If already a dict or invalid JSON, keep as-is
                    pass

        assessments.append(assessment)

    conn.close()

    # Write to JSON file
    with open(output_path, "w") as f:
        json.dump(assessments, f, indent=2, default=str)

    print(f"✓ Exported {len(assessments)} assessments to {output_path}")
    print(f"  File size: {Path(output_path).stat().st_size / 1024:.1f} KB")

    # Print summary stats
    statuses = {}
    domains = {}
    for a in assessments:
        statuses[a.get("status", "unknown")] = statuses.get(a.get("status", "unknown"), 0) + 1
        domains[a.get("domain", "unknown")] = domains.get(a.get("domain", "unknown"), 0) + 1

    print("\nSummary:")
    print(f"  Status breakdown: {dict(statuses)}")
    print(f"  Domain breakdown: {dict(domains)}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export SQLite database to JSON")
    parser.add_argument(
        "--sqlite",
        default="webui_assessments.db",
        help="Path to SQLite database file (default: webui_assessments.db)"
    )
    parser.add_argument(
        "--output",
        default="assessments_export.json",
        help="Output JSON file path (default: assessments_export.json)"
    )

    args = parser.parse_args()

    export_sqlite_to_json(args.sqlite, args.output)
