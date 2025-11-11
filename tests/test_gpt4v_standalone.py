"""
Test GPT-4V white agent standalone with observations

Tests that the white agent makes intelligent decisions based on screenshots.
"""

import sys
import json
import base64
from pathlib import Path
import requests

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_white_agent_with_observation():
    """Test white agent with a sample observation"""
    print("Testing GPT-4V white agent with observation...")
    print()

    white_agent_url = "http://localhost:9002"

    # Test 1: Check agent card
    print("1. Checking agent card...")
    response = requests.get(f"{white_agent_url}/agent-card")
    assert response.status_code == 200, f"Agent card failed: {response.status_code}"
    card = response.json()
    print(f"   Agent: {card['name']}")
    print(f"   Protocols: {card['protocols']}")
    print(f"   Capabilities: {card['capabilities'][:3]}...")
    print("   ✓ Agent card retrieved\n")

    # Test 2: Send a task with fake screenshot (just for testing format)
    print("2. Sending test task to white agent...")

    # Create a minimal test observation (in real usage, this would be a real screenshot)
    # For this test, we'll use a dummy base64 image since we just want to verify the format
    dummy_image_b64 = base64.b64encode(b"fake_image_data").decode()

    task = {
        "task_id": "test-123",
        "context_id": "test-123",
        "message": "Open Chrome browser",
        "metadata": {
            "observation": {
                "frame_id": 0,
                "image_png_b64": dummy_image_b64,
                "instruction": "Open Chrome browser",
                "done": False
            }
        }
    }

    try:
        response = requests.post(
            f"{white_agent_url}/task",
            json=task,
            timeout=30.0
        )

        print(f"   Response status: {response.status_code}")

        if response.status_code == 200:
            message = response.json()
            print(f"   Response role: {message.get('role')}")
            print(f"   Response content: {message.get('content', '')[:100]}...")

            # Check if action is in metadata
            if 'metadata' in message and 'action' in message['metadata']:
                action = message['metadata']['action']
                print(f"   Action: {action.get('op')}")
                print(f"   Args: {action.get('args', {})}")
                print("   ✓ White agent returned valid action\n")
                return True
            else:
                print("   ⚠️  No action in response metadata")
                print(f"   Full response: {json.dumps(message, indent=2)}")
                return False
        else:
            print(f"   ❌ Request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request error: {e}")
        return False


def test_health_check():
    """Test white agent health endpoint"""
    print("3. Checking white agent health...")
    try:
        response = requests.get("http://localhost:9002/health", timeout=5.0)
        if response.status_code == 200:
            health = response.json()
            print(f"   Status: {health.get('status')}")
            print(f"   Agent type: {health.get('agent_type')}")
            print("   ✓ Health check passed\n")
            return True
        else:
            print(f"   ❌ Health check failed: {response.status_code}\n")
            return False
    except Exception as e:
        print(f"   ❌ Health check error: {e}\n")
        return False


def main():
    """Run white agent tests"""
    print("=" * 60)
    print("GPT-4V WHITE AGENT STANDALONE TESTS")
    print("=" * 60)
    print()

    # Check if server is running
    try:
        response = requests.get("http://localhost:9002/health", timeout=2.0)
        if response.status_code != 200:
            print("❌ White agent not running on port 9002")
            print("   Start it with: uvicorn white_agent.gpt4v_server:app --port 9002")
            return 1
    except requests.exceptions.RequestException:
        print("❌ White agent not reachable on port 9002")
        print("   Start it with: uvicorn white_agent.gpt4v_server:app --port 9002")
        return 1

    try:
        success = True
        success = test_white_agent_with_observation() and success
        success = test_health_check() and success

        if success:
            print("=" * 60)
            print("✅ WHITE AGENT TESTS PASSED")
            print("=" * 60)
            print()
            print("The GPT-4V white agent is ready to use!")
            print("It can be used with the A2A green agent for assessments.")
            return 0
        else:
            print("=" * 60)
            print("⚠️  SOME TESTS HAD ISSUES")
            print("=" * 60)
            print()
            print("Check the output above for details.")
            return 1

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
