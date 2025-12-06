#!/usr/bin/env python3
"""
Minimal test server to debug subprocess startup issues.
No external dependencies beyond FastAPI/uvicorn.
"""

import os
import logging
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Test White Agent")

class AgentCard(BaseModel):
    name: str
    description: str
    url: str
    version: str

@app.on_event("startup")
async def startup():
    logger.info("=== TEST SERVER STARTUP ===")
    logger.info(f"HOST: {os.getenv('HOST')}")
    logger.info(f"AGENT_PORT: {os.getenv('AGENT_PORT')}")
    logger.info(f"PORT: {os.getenv('PORT')}")

@app.get("/health")
def health():
    return {"status": "healthy", "agent": "test"}

@app.get("/status")
def status():
    return {"status": "running", "agent": "test"}

@app.get("/.well-known/agent-card.json")
def agent_card():
    # AGENT_URL is set by earthshaker controller
    url = os.getenv("AGENT_URL")
    if not url:
        # Fallback for local testing
        host = os.getenv("HOST", "localhost")
        port = os.getenv("AGENT_PORT", "8001")
        url = f"http://{host}:{port}"
    logger.info(f"Agent card requested, URL: {url}")
    return AgentCard(
        name="Test Agent",
        description="Minimal test agent for debugging",
        url=url,
        version="1.0.0"
    )

@app.get("/agent-card")
def agent_card_alt():
    return agent_card()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("AGENT_PORT", os.environ.get("PORT", "8001")))
    host = os.environ.get("HOST", "0.0.0.0")
    logger.info(f"Starting test server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
