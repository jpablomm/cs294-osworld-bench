#!/usr/bin/env python3
"""Test PostgreSQL database connection and operations"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.database_postgres import PostgresDatabase
import uuid
from datetime import datetime

def test_connection():
    """Test basic connection"""
    print("1. Testing connection...")
    try:
        db = PostgresDatabase()
        print("   ✓ Connection successful")
        return db
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        sys.exit(1)

def test_create_assessment(db):
    """Test creating an assessment"""
    print("\n2. Testing create assessment...")
    try:
        assessment_id = f"test-{uuid.uuid4().hex[:8]}"
        assessment = {
            "id": assessment_id,
            "task_id": "test-task",
            "domain": "os",
            "status": "completed",
            "success": 1,
            "evaluation_score": 0.95,
            "steps": 10,
            "time_sec": 45.5,
            "vm_cost": 0.015,
            "started_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
            "trajectory": {"actions": ["click", "type"]},
            "artifacts": ["screenshot1.png", "screenshot2.png"],
            "config": {"model": "gpt-4o", "temp": 0.7},
            "batch_id": "test-batch",
            "run_number": 1
        }

        db.create_assessment(assessment)
        print(f"   ✓ Created assessment: {assessment_id}")
        return assessment_id
    except Exception as e:
        print(f"   ✗ Create failed: {e}")
        sys.exit(1)

def test_get_assessment(db, assessment_id):
    """Test retrieving an assessment"""
    print("\n3. Testing get assessment...")
    try:
        assessment = db.get_assessment(assessment_id)
        if assessment and assessment["id"] == assessment_id:
            print(f"   ✓ Retrieved assessment: {assessment_id}")
            print(f"      Status: {assessment['status']}")
            print(f"      Success: {assessment['success']}")
        else:
            print(f"   ✗ Assessment not found or mismatch")
            sys.exit(1)
    except Exception as e:
        print(f"   ✗ Get failed: {e}")
        sys.exit(1)

def test_list_assessments(db):
    """Test listing assessments"""
    print("\n4. Testing list assessments...")
    try:
        result = db.list_assessments(limit=5)
        count = len(result["assessments"])
        total = result["total"]
        print(f"   ✓ Listed {count} assessments (total: {total})")
    except Exception as e:
        print(f"   ✗ List failed: {e}")
        sys.exit(1)

def test_update_assessment(db, assessment_id):
    """Test updating an assessment"""
    print("\n5. Testing update assessment...")
    try:
        db.update_assessment(assessment_id, {
            "status": "failed",
            "failure_reason": "Test failure"
        })

        updated = db.get_assessment(assessment_id)
        if updated["status"] == "failed":
            print(f"   ✓ Updated assessment status to 'failed'")
        else:
            print(f"   ✗ Update did not persist")
            sys.exit(1)
    except Exception as e:
        print(f"   ✗ Update failed: {e}")
        sys.exit(1)

def test_stats(db):
    """Test getting statistics"""
    print("\n6. Testing stats...")
    try:
        stats = db.get_stats()
        print(f"   ✓ Statistics retrieved:")
        print(f"      Total assessments: {stats['total_assessments']}")
        print(f"      Running: {stats['running_assessments']}")
        print(f"      Success rate (24h): {stats['success_rate_24h']:.1f}%")
    except Exception as e:
        print(f"   ✗ Stats failed: {e}")
        sys.exit(1)

def test_leaderboard(db):
    """Test leaderboard queries"""
    print("\n7. Testing leaderboard...")
    try:
        leaderboard = db.get_global_leaderboard()
        print(f"   ✓ Global leaderboard retrieved ({len(leaderboard)} entries)")

        if len(leaderboard) > 0:
            print(f"      Top entry: {leaderboard[0]['config']}")
            print(f"      Success rate: {leaderboard[0]['success_rate']:.1f}%")
    except Exception as e:
        print(f"   ✗ Leaderboard failed: {e}")
        sys.exit(1)

def test_batch(db):
    """Test batch queries"""
    print("\n8. Testing batch queries...")
    try:
        batch = db.get_batch("test-batch")
        if batch:
            print(f"   ✓ Batch retrieved:")
            print(f"      Total runs: {batch['total_runs']}")
            print(f"      Success rate: {batch['success_rate']:.1f}%")
        else:
            print(f"   ℹ No batch found (this is okay for first run)")
    except Exception as e:
        print(f"   ✗ Batch failed: {e}")
        sys.exit(1)

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("PostgreSQL Database Test Suite")
    print("=" * 60)

    # Check environment
    required_env = ["DB_HOST", "DB_NAME", "DB_USER"]
    missing = [env for env in required_env if not os.getenv(env)]
    if missing:
        print(f"\n✗ Missing environment variables: {', '.join(missing)}")
        print("\nPlease set:")
        print("  export DB_HOST=localhost")
        print("  export DB_PORT=5432")
        print("  export DB_NAME=osworld_assessments")
        print("  export DB_USER=osworld_user")
        print("  export DB_PASSWORD=your_password")
        sys.exit(1)

    db = test_connection()
    assessment_id = test_create_assessment(db)
    test_get_assessment(db, assessment_id)
    test_update_assessment(db, assessment_id)
    test_list_assessments(db)
    test_stats(db)
    test_leaderboard(db)
    test_batch(db)

    print("\n" + "=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)
    print("\nYour PostgreSQL database is ready to use.")
    print("To switch to PostgreSQL mode:")
    print("  export USE_POSTGRES=1")
    print("  uvicorn orchestrator.webui_server:app --port 3001")

if __name__ == "__main__":
    run_all_tests()
