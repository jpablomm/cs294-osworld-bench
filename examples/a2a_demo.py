#!/usr/bin/env python3
"""
A2A Demo - Simple demonstration of AgentBeats A2A protocol

This script shows how to:
1. Query agent cards
2. Send A2A tasks
3. Receive A2A messages

It can be used for testing and understanding the A2A protocol flow.
"""

import asyncio
import httpx
import json


async def demo_agent_card(url: str, name: str):
    """Demonstrate agent card retrieval"""
    print(f"\n{'=' * 60}")
    print(f"Fetching {name} Agent Card")
    print('=' * 60)

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{url}/agent-card")
        card = response.json()

        print(f"\nName: {card['name']}")
        print(f"Version: {card['version']}")
        print(f"Description: {card['description']}")
        print(f"Protocols: {', '.join(card['protocols'])}")
        print(f"Capabilities:")
        for cap in card['capabilities']:
            print(f"  - {cap}")

        return card


async def demo_green_agent_task():
    """Demonstrate sending a task to the green agent"""
    print(f"\n{'=' * 60}")
    print("Sending A2A Task to Green Agent")
    print('=' * 60)

    green_url = "http://localhost:8001"
    white_url = "http://localhost:9001"

    # Example A2A task
    task = {
        "task_id": "demo-001",
        "context_id": "demo-001",
        "message": "Run a simple OSWorld assessment",
        "metadata": {
            "osworld_task_id": "osworld-ubuntu-tiny",
            "white_agent_url": white_url,
            "max_steps": 5,
            "vm_image": "osworld-golden-v3-gnome"
        }
    }

    print("\nTask payload:")
    print(json.dumps(task, indent=2))

    print("\nSending task (this may take several minutes)...")

    async with httpx.AsyncClient(timeout=900.0) as client:
        try:
            response = await client.post(f"{green_url}/task", json=task)
            message = response.json()

            print(f"\n{'=' * 60}")
            print("Received A2A Message")
            print('=' * 60)

            print(f"\nMessage ID: {message['message_id']}")
            print(f"Task ID: {message['task_id']}")
            print(f"Role: {message['role']}")
            print(f"\nContent:")
            print(message['content'])

            print(f"\nMetadata:")
            print(json.dumps(message['metadata'], indent=2))

            return message

        except httpx.TimeoutException:
            print("\nTask timed out. This is normal for long-running assessments.")
        except Exception as e:
            print(f"\nError: {e}")


async def demo_white_agent_interaction():
    """Demonstrate white agent interaction"""
    print(f"\n{'=' * 60}")
    print("White Agent Interaction Demo")
    print('=' * 60)

    white_url = "http://localhost:9001"

    # Simulate what the green agent sends to white agent
    task = {
        "task_id": "white-demo-001",
        "context_id": "white-demo-001",
        "message": "Click the Chrome icon to open the browser",
        "metadata": {
            "observation": {
                "frame_id": 0,
                "image_png_b64": "",  # Would contain base64 screenshot
                "instruction": "Open Chrome browser",
                "done": False
            },
            "tools": [
                {
                    "name": "click",
                    "description": "Click at screen coordinates",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"}
                        },
                        "required": ["x", "y"]
                    }
                }
            ]
        }
    }

    print("\nSending observation to white agent...")
    print(json.dumps(task, indent=2))

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{white_url}/task", json=task)
            message = response.json()

            print(f"\n{'=' * 60}")
            print("White Agent Response")
            print('=' * 60)

            print(f"\nContent: {message['content']}")
            print(f"\nAction: {json.dumps(message['metadata']['action'], indent=2)}")

        except Exception as e:
            print(f"\nError: {e}")


async def demo_health_check():
    """Check health of both agents"""
    print(f"\n{'=' * 60}")
    print("Health Check")
    print('=' * 60)

    urls = {
        "Green Agent": "http://localhost:8001",
        "White Agent": "http://localhost:9001"
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in urls.items():
            try:
                response = await client.get(f"{url}/health")
                health = response.json()
                print(f"\n{name}:")
                print(f"  Status: {health['status']}")
                print(f"  Type: {health['agent_type']}")
                print(f"  Protocol: {health['protocol']}")
            except Exception as e:
                print(f"\n{name}: NOT REACHABLE ({e})")


async def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║        OSWorld A2A Protocol Demonstration                ║
║        AgentBeats-Compliant Assessment System            ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)

    print("\nThis demo requires both agents to be running:")
    print("  Terminal 1: uvicorn orchestrator.a2a_green_agent:app --port 8001")
    print("  Terminal 2: uvicorn white_agent.a2a_adapter:app --port 9001")

    input("\nPress Enter to continue...")

    # Demo 1: Health Check
    await demo_health_check()

    input("\nPress Enter to continue...")

    # Demo 2: Agent Cards
    await demo_agent_card("http://localhost:8001", "Green")
    await demo_agent_card("http://localhost:9001", "White")

    input("\nPress Enter to continue...")

    # Demo 3: White Agent Interaction
    print("\nDemo 3: White Agent Interaction (simplified)")
    await demo_white_agent_interaction()

    input("\nPress Enter to continue...")

    # Demo 4: Full Assessment (optional)
    print("\nDemo 4: Full Assessment")
    print("This will create a VM and run a full assessment (takes ~5-10 minutes)")
    choice = input("Run full assessment? (y/n): ")

    if choice.lower() == 'y':
        await demo_green_agent_task()
    else:
        print("Skipped full assessment demo.")

    print(f"\n{'=' * 60}")
    print("Demo Complete!")
    print('=' * 60)
    print("\nNext steps:")
    print("1. Use launcher_a2a.py for production assessments")
    print("2. Integrate with AgentBeats platform")
    print("3. Create custom assessment configurations")


if __name__ == "__main__":
    asyncio.run(main())
