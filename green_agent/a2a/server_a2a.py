"""
A2A-Compliant Green Agent Server

This module provides the A2A protocol compliant server using the a2a-sdk.
It replaces the custom REST API with proper JSON-RPC handling at the root endpoint.

Usage:
    python -m green_agent.a2a.server_a2a

Or via uvicorn:
    uvicorn green_agent.a2a.server_a2a:app --host 0.0.0.0 --port 8001
"""

import logging
import os
import signal
import sys
import atexit
from typing import Optional

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentSkill, AgentCard, AgentCapabilities, AgentProvider

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import configuration
from green_agent.config import (
    GREEN_AGENT_API_KEY,
    GREEN_AGENT_HOST,
    GREEN_AGENT_PORT,
    CLOUDRUN_HOST,
    HTTPS_ENABLED,
    get_agent_url,
)

# Import executor
from green_agent.a2a.executor import GreenAgentExecutor

# Global executor instance (for cleanup and monitoring)
_executor: Optional[GreenAgentExecutor] = None
_is_shutting_down = False


def get_executor() -> GreenAgentExecutor:
    """Get or create the global executor instance."""
    global _executor
    if _executor is None:
        _executor = GreenAgentExecutor()
    return _executor


def prepare_agent_card(url: Optional[str] = None) -> AgentCard:
    """Prepare the A2A-compliant agent card."""
    if url is None:
        url = get_agent_url()

    skills = [
        AgentSkill(
            id="osworld-assessment",
            name="OSWorld Assessment",
            description="Run OSWorld desktop automation benchmark assessments. "
                        "Creates VMs, orchestrates task execution with white agents, "
                        "and reports standardized metrics.",
            tags=["benchmark", "desktop", "automation", "assessment", "osworld"],
            examples=[],
        ),
        AgentSkill(
            id="chrome-task",
            name="Chrome Browser Tasks",
            description="Execute Chrome browser automation tasks within OSWorld environment",
            tags=["chrome", "browser", "web", "automation"],
            examples=[],
        ),
        AgentSkill(
            id="os-task",
            name="OS-Level Tasks",
            description="Execute operating system level tasks (file management, settings, applications)",
            tags=["os", "files", "settings", "gnome", "linux"],
            examples=[],
        ),
    ]

    return AgentCard(
        name="OSWorld Assessment Agent",
        description=(
            "Green agent for conducting OSWorld desktop automation assessments. "
            "Creates VMs from golden images, orchestrates task execution with white agents, "
            "and reports standardized metrics (success rate, steps, execution time)."
        ),
        url=url,
        version="2.0.0",  # Bump version for A2A compliance
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(
            streaming=True,  # We send progress updates
            pushNotifications=True,
            stateTransitionHistory=True
        ),
        skills=skills,
        provider=AgentProvider(
            organization="Berkeley CS294",
            url="https://github.com/agentbeats/green-agent"
        ),
    )


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware to verify API key for protected endpoints.

    Only requires API key for POST requests to the JSON-RPC endpoint (/).
    This protects against DoS attacks and unauthorized VM creation.
    """

    async def dispatch(self, request: Request, call_next):
        # Only check API key for POST to root (JSON-RPC endpoint)
        if request.method == "POST" and request.url.path == "/":
            if GREEN_AGENT_API_KEY:
                api_key = request.headers.get("X-API-Key")
                if api_key != GREEN_AGENT_API_KEY:
                    logger.warning(f"Unauthorized access attempt from {request.client.host}")
                    return JSONResponse(
                        {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32001,
                                "message": "Unauthorized: Invalid or missing API key"
                            },
                            "id": None
                        },
                        status_code=401
                    )
        return await call_next(request)


async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint."""
    executor = get_executor()
    active_count = len([
        a for a in executor.get_active_assessments().values()
        if a.get("status") == "running"
    ])

    return JSONResponse({
        "status": "healthy",
        "agent_type": "green",
        "protocol": "a2a",
        "version": "2.0.0",
        "assessment_types": ["osworld"],
        "active_assessments": active_count
    })


async def list_assessments(request: Request) -> JSONResponse:
    """List all assessments (for debugging/monitoring)."""
    executor = get_executor()
    return JSONResponse({
        "assessments": executor.get_active_assessments()
    })


def _cleanup_handler():
    """Cleanup handler for graceful shutdown."""
    global _is_shutting_down

    if _is_shutting_down:
        return
    _is_shutting_down = True

    logger.info("Graceful shutdown: cleaning up VMs...")
    if _executor:
        _executor.cleanup_all_vms()
    logger.info("Cleanup complete")


def _signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM for graceful shutdown."""
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logger.warning(f"Received {sig_name} - initiating graceful shutdown...")
    _cleanup_handler()
    # Raise KeyboardInterrupt to let uvicorn handle shutdown
    raise KeyboardInterrupt


def create_app() -> Starlette:
    """
    Create the A2A-compliant Starlette application.

    This sets up:
    - A2A JSON-RPC endpoint at /
    - Agent card endpoints at /.well-known/agent-card.json and /.well-known/agent.json
    - Custom health and monitoring endpoints
    - API key authentication middleware
    """
    # Determine agent URL
    if CLOUDRUN_HOST:
        protocol = "https" if HTTPS_ENABLED else "http"
        agent_url = f"{protocol}://{CLOUDRUN_HOST}"
    else:
        agent_url = get_agent_url()

    logger.info(f"Agent URL: {agent_url}")

    # Create agent card
    card = prepare_agent_card(agent_url)

    # Create request handler with our executor
    request_handler = DefaultRequestHandler(
        agent_executor=get_executor(),
        task_store=InMemoryTaskStore(),
    )

    # Create A2A application
    a2a_app = A2AStarletteApplication(
        agent_card=card,
        http_handler=request_handler,
    )

    # Build base Starlette app with middleware
    middleware = []
    if GREEN_AGENT_API_KEY:
        middleware.append(Middleware(APIKeyMiddleware))
        logger.info("API key authentication enabled")

    # Get A2A routes
    a2a_routes = a2a_app.routes()

    # Add custom routes
    custom_routes = [
        Route("/health", health_check, methods=["GET"]),
        Route("/assessments", list_assessments, methods=["GET"]),
        # Legacy endpoint for backwards compatibility
        Route("/agent-card", lambda r: JSONResponse(card.model_dump(by_alias=True, exclude_none=True)), methods=["GET"]),
    ]

    # Combine routes
    all_routes = a2a_routes + custom_routes

    # Create Starlette app
    app = Starlette(
        routes=all_routes,
        middleware=middleware,
        on_startup=[_on_startup],
        on_shutdown=[_on_shutdown],
    )

    return app


async def _on_startup():
    """Startup event handler."""
    logger.info("Green Agent A2A Server starting up...")
    logger.info(f"Protocol: A2A JSON-RPC")
    logger.info(f"Endpoints:")
    logger.info(f"  POST /              - A2A JSON-RPC (message/send, etc.)")
    logger.info(f"  GET /.well-known/agent-card.json - Agent card")
    logger.info(f"  GET /health         - Health check")
    logger.info(f"  GET /assessments    - List assessments")


async def _on_shutdown():
    """Shutdown event handler."""
    logger.info("Green Agent A2A Server shutting down...")
    _cleanup_handler()


# Register signal handlers
try:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    logger.info("Registered signal handlers for graceful shutdown")
except Exception as e:
    logger.warning(f"Could not register signal handlers: {e}")

# Register atexit handler as fallback
atexit.register(_cleanup_handler)

# Create the app instance for uvicorn
app = create_app()


def start_server(host: str = None, port: int = None):
    """Start the A2A server."""
    host = host or GREEN_AGENT_HOST
    port = port or GREEN_AGENT_PORT

    logger.info(f"Starting Green Agent A2A Server on {host}:{port}")

    uvicorn.run(
        "green_agent.a2a.server_a2a:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    start_server()
