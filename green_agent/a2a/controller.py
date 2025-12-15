"""
Custom AgentBeats Controller with A2A Root Proxy

This module patches the earthshaker controller to add:
- POST / - Proxies A2A JSON-RPC requests to the underlying agent
- GET /.well-known/agent-card.json - Proxies agent card discovery

The patching happens at import time, so the standard `agentbeats run_ctrl`
command will use the enhanced routes.

Usage in Dockerfile:
    # Import this module before running the controller
    CMD ["python", "-c", "import green_agent.a2a.controller; from agentbeats.cli import app; app()"]

Or simpler - just use run_ctrl after importing:
    CMD ["sh", "-c", "python -c 'import green_agent.a2a.controller' && agentbeats run_ctrl"]
"""

import os
import logging

import httpx
from fastapi import Request
from fastapi.responses import Response, JSONResponse

# Import the earthshaker controller app - this registers it
from agentbeats.controller import app as earthshaker_app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_first_agent_port() -> int | None:
    """Get the port of the first (and usually only) agent."""
    agents_folder = os.path.join(".ab", "agents")
    if not os.path.exists(agents_folder):
        return None

    try:
        agent_ids = os.listdir(agents_folder)
    except FileNotFoundError:
        return None

    if not agent_ids:
        return None

    # Get the first agent that has a port file
    for agent_id in agent_ids:
        port_file = os.path.join(agents_folder, agent_id, "port")
        if os.path.exists(port_file):
            try:
                with open(port_file, "r") as f:
                    return int(f.read().strip())
            except (ValueError, FileNotFoundError):
                continue
    return None


# Patch: Add POST handler for root URL to proxy A2A JSON-RPC requests
@earthshaker_app.post("/")
async def proxy_root_to_agent(request: Request):
    """
    Proxy A2A JSON-RPC requests from root to the underlying agent.

    The AgentBeats runner sends message/send requests to the controller root URL,
    but the agent is running on a different port. This handler proxies the request
    to the first available agent.
    """
    agent_port = get_first_agent_port()

    if agent_port is None:
        logger.error("No agent available to proxy request")
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": "No agent available"
                },
                "id": None
            },
            status_code=503
        )

    agent_url = f"http://localhost:{agent_port}/"
    logger.info(f"Proxying POST / to agent at port {agent_port}")

    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.request(
                method="POST",
                url=agent_url,
                content=await request.body(),
                headers={
                    k: v for k, v in request.headers.items()
                    if k.lower() not in ('host', 'content-length')
                },
            )

            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={
                    k: v for k, v in response.headers.items()
                    if k.lower() not in ('content-length', 'transfer-encoding')
                },
            )
    except httpx.TimeoutException:
        logger.error("Request to agent timed out")
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": "Agent request timed out"
                },
                "id": None
            },
            status_code=504
        )
    except Exception as e:
        logger.error(f"Error proxying request to agent: {e}")
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                },
                "id": None
            },
            status_code=500
        )


# Patch: Add GET /.well-known/agent-card.json for A2A discovery
@earthshaker_app.get("/.well-known/agent-card.json")
async def proxy_agent_card(request: Request):
    """Proxy agent card discovery to the underlying agent."""
    agent_port = get_first_agent_port()

    if agent_port is None:
        return JSONResponse(
            {"error": "No agent available"},
            status_code=503
        )

    agent_url = f"http://localhost:{agent_port}/.well-known/agent-card.json"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(agent_url)
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={
                    k: v for k, v in response.headers.items()
                    if k.lower() not in ('content-length', 'transfer-encoding')
                },
            )
    except Exception as e:
        logger.error(f"Error fetching agent card: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


# Patch: Add GET /.well-known/agent.json (legacy path)
@earthshaker_app.get("/.well-known/agent.json")
async def proxy_agent_card_legacy(request: Request):
    """Proxy legacy agent card discovery to the underlying agent."""
    return await proxy_agent_card(request)


def get_agent_port_by_id(agent_id: str) -> int | None:
    """Get the port for a specific agent by ID."""
    port_file = os.path.join(".ab", "agents", agent_id, "port")
    if os.path.exists(port_file):
        try:
            with open(port_file, "r") as f:
                return int(f.read().strip())
        except (ValueError, FileNotFoundError):
            return None
    return None


# Patch: Override /to_agent/{agent_id}/.well-known/agent-card.json with better error handling
# This prevents 500 errors when agents are still starting up
@earthshaker_app.get("/to_agent/{agent_id}/.well-known/agent-card.json")
async def proxy_agent_card_by_id(agent_id: str, request: Request):
    """Proxy agent card with graceful handling when agent not ready."""
    agent_port = get_agent_port_by_id(agent_id)

    if agent_port is None:
        logger.warning(f"Agent {agent_id} not ready yet (no port file)")
        return JSONResponse(
            {"error": f"Agent {agent_id} is not ready yet. Try again in a few seconds."},
            status_code=503  # Service Unavailable - indicates temporary condition
        )

    agent_url = f"http://localhost:{agent_port}/.well-known/agent-card.json"
    logger.info(f"Proxying agent card for {agent_id} to port {agent_port}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(agent_url)
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={
                    k: v for k, v in response.headers.items()
                    if k.lower() not in ('content-length', 'transfer-encoding')
                },
            )
    except httpx.ConnectError:
        logger.warning(f"Agent {agent_id} port {agent_port} not accepting connections yet")
        return JSONResponse(
            {"error": f"Agent {agent_id} is starting up. Try again in a few seconds."},
            status_code=503
        )
    except Exception as e:
        logger.error(f"Error fetching agent card for {agent_id}: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


logger.info("A2A root proxy routes added to earthshaker controller")
logger.info("  POST / -> proxies to agent JSON-RPC endpoint")
logger.info("  GET /.well-known/agent-card.json -> proxies to agent")
logger.info("  GET /to_agent/{id}/.well-known/agent-card.json -> graceful startup handling")


def run_ctrl():
    """
    Run the enhanced controller.

    This is equivalent to `agentbeats run_ctrl` but with the patched routes.
    The patching happens at module import time (above), then we call
    the standard controller_main which uses the patched app.
    """
    from agentbeats.controller import main as controller_main
    controller_main()


if __name__ == "__main__":
    run_ctrl()
