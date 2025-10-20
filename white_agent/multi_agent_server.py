#!/usr/bin/env python3
"""
Multi-Agent A2A Server

Wraps multiple OSWorld agent implementations with A2A protocol.
Supports dynamic agent selection and configuration.
"""

import os
import sys
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Add OSWorld mm_agents to path
OSWORLD_PATH = Path(__file__).parent.parent / "vendor" / "OSWorld"
sys.path.insert(0, str(OSWORLD_PATH))

from mm_agents.agent import PromptAgent
from mm_agents.qwen25vl_agent import Qwen25VLAgent
from mm_agents.qwen3vl_agent import Qwen3VLAgent
from mm_agents.o3_agent import O3Agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Agent Registry
# ============================================================================

AGENT_REGISTRY = {
    "gpt-4v": {
        "class": PromptAgent,
        "default_model": "gpt-4o",
        "supported_models": ["gpt-4o", "gpt-4-vision-preview", "gpt-4-turbo"],
        "default_params": {
            "observation_type": "screenshot",
            "action_space": "pyautogui",
            "max_tokens": 1500,
            "temperature": 1.0,
            "top_p": 0.9
        }
    },
    "o3": {
        "class": O3Agent,
        "default_model": "o3",
        "supported_models": ["o3"],
        "default_params": {
            "observation_type": "screenshot",
            "action_space": "pyautogui",
            "max_tokens": 1500
        }
    },
    "qwen2.5-vl": {
        "class": Qwen25VLAgent,
        "default_model": "qwen2.5-vl-72b-instruct",
        "supported_models": [
            "qwen2.5-vl-72b-instruct",
            "qwen2.5-vl-7b-instruct",
            "qwen2.5-vl-3b-instruct"
        ],
        "default_params": {
            "observation_type": "screenshot",
            "action_space": "pyautogui",
            "max_tokens": 1500,
            "temperature": 0.5,
            "top_p": 0.9,
            "history_n": 4
        }
    },
    "qwen3-vl": {
        "class": Qwen3VLAgent,
        "default_model": "qwen3-vl",
        "supported_models": ["qwen3-vl"],
        "default_params": {
            "observation_type": "screenshot",
            "action_space": "pyautogui",
            "max_tokens": 32768,
            "temperature": 0.0,
            "top_p": 0.9,
            "history_n": 4,
            "coordinate_type": "relative",
            "api_backend": "dashscope",  # or "openai"
            "enable_thinking": False,
            "thinking_budget": 32768
        }
    }
}


# ============================================================================
# Models
# ============================================================================

class TaskRequest(BaseModel):
    """A2A Task Request"""
    task_id: str
    context_id: str
    message: str
    metadata: Optional[Dict[str, Any]] = {}


class DecideRequest(BaseModel):
    """Decision request with observation"""
    observation: Dict[str, Any]


class ResetRequest(BaseModel):
    """Reset request (optional parameters)"""
    pass


class AgentConfig(BaseModel):
    """Agent configuration"""
    agent_type: str = "gpt-4v"
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    action_space: Optional[str] = None
    observation_type: Optional[str] = None
    # Additional agent-specific parameters
    extra_params: Optional[Dict[str, Any]] = {}


# ============================================================================
# Agent Manager
# ============================================================================

class AgentManager:
    """Manages multiple agent instances"""

    def __init__(self):
        self.agents: Dict[str, Any] = {}
        self.current_agent_id = "default"

    def create_agent(self, agent_id: str, config: AgentConfig):
        """Create new agent instance with given configuration"""

        agent_type = config.agent_type
        if agent_type not in AGENT_REGISTRY:
            raise ValueError(f"Unknown agent type: {agent_type}. Available: {list(AGENT_REGISTRY.keys())}")

        registry_entry = AGENT_REGISTRY[agent_type]
        agent_class = registry_entry["class"]

        # Build initialization parameters
        params = registry_entry["default_params"].copy()

        # Override with user config
        if config.model:
            if config.model not in registry_entry["supported_models"]:
                logger.warning(f"Model {config.model} not in supported list: {registry_entry['supported_models']}")
            params["model"] = config.model
        else:
            params["model"] = registry_entry["default_model"]

        if config.temperature is not None:
            params["temperature"] = config.temperature
        if config.max_tokens is not None:
            params["max_tokens"] = config.max_tokens
        if config.top_p is not None:
            params["top_p"] = config.top_p
        if config.action_space:
            params["action_space"] = config.action_space
        if config.observation_type:
            params["observation_type"] = config.observation_type

        # Add extra parameters
        if config.extra_params:
            params.update(config.extra_params)

        # Create agent
        logger.info(f"Creating {agent_type} agent with params: {params}")
        agent = agent_class(**params)

        # Store metadata
        self.agents[agent_id] = {
            "agent": agent,
            "type": agent_type,
            "class": agent_class,
            "config": params
        }

        return agent

    def get_agent(self, agent_id: str = None):
        """Get agent by ID or current agent"""
        agent_id = agent_id or self.current_agent_id
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")
        return self.agents[agent_id]["agent"]

    def reset_agent(self, agent_id: str = None):
        """Reset agent state"""
        agent = self.get_agent(agent_id)
        agent.reset()

    def list_agents(self):
        """List all active agents"""
        return {
            agent_id: {
                "type": info["type"],
                "config": info["config"]
            }
            for agent_id, info in self.agents.items()
        }


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Multi-Agent A2A Server",
    description="A2A protocol wrapper for multiple OSWorld agents",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent manager
manager = AgentManager()

# Create default agent on startup
@app.on_event("startup")
def startup():
    """Initialize default agent"""
    default_config = AgentConfig(agent_type="gpt-4v")
    manager.create_agent("default", default_config)
    logger.info("Multi-Agent A2A Server started")


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/health")
def health():
    """Health check"""
    return {
        "status": "healthy",
        "active_agents": len(manager.agents),
        "current_agent": manager.current_agent_id
    }


@app.get("/agents")
def list_agents():
    """List available agent types and active instances"""
    return {
        "available_types": {
            agent_type: {
                "default_model": info["default_model"],
                "supported_models": info["supported_models"]
            }
            for agent_type, info in AGENT_REGISTRY.items()
        },
        "active_instances": manager.list_agents()
    }


@app.post("/agents")
def create_agent(config: AgentConfig):
    """Create new agent instance"""
    import uuid
    agent_id = f"agent-{uuid.uuid4().hex[:8]}"

    try:
        manager.create_agent(agent_id, config)
        return {
            "agent_id": agent_id,
            "type": config.agent_type,
            "status": "created"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/agents/{agent_id}/switch")
def switch_agent(agent_id: str):
    """Switch current active agent"""
    if agent_id not in manager.agents:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    manager.current_agent_id = agent_id
    return {
        "current_agent": agent_id,
        "type": manager.agents[agent_id]["type"]
    }


@app.post("/reset")
def reset(agent_id: Optional[str] = None):
    """Reset agent state"""
    try:
        manager.reset_agent(agent_id)
        return {"status": "reset"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/decide")
def decide(request: DecideRequest, agent_id: Optional[str] = None):
    """Make decision based on observation"""
    try:
        agent_info = manager.agents[agent_id or manager.current_agent_id]
        agent = agent_info["agent"]
        agent_class = agent_info["class"]

        obs = request.observation
        instruction = obs.get("instruction", "Complete the task")

        # Call predict method
        result = agent.predict(instruction, obs)

        # Handle different return types
        if isinstance(result, tuple):
            # Agents that return (response, code/actions)
            response, actions = result
            if isinstance(actions, list):
                actions = actions[0] if len(actions) == 1 else actions
            return {
                "action": actions,
                "content": response,
                "metadata": {"agent_type": agent_info["type"]}
            }
        else:
            # Agents that return just response
            return {
                "action": result,
                "content": result,
                "metadata": {"agent_type": agent_info["type"]}
            }

    except Exception as e:
        logger.error(f"Decision error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/task")
def task(request: TaskRequest):
    """
    A2A Task endpoint

    Executes entire task by repeatedly calling decide until completion.
    """
    # For now, this is a simplified version
    # In production, you'd want to implement the full task loop
    return {
        "task_id": request.task_id,
        "status": "completed",
        "result": "Task execution not implemented in multi-agent server. Use /decide endpoint.",
        "metadata": {}
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Multi-Agent A2A Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9003, help="Port to bind to")

    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)
