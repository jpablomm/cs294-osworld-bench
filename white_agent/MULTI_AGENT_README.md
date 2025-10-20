# Multi-Agent A2A Server

Extensible wrapper supporting multiple OSWorld agent implementations through the A2A protocol.

## Supported Agents

| Agent Type | Models | Description |
|------------|--------|-------------|
| `gpt-4v` | gpt-4o, gpt-4-vision-preview, gpt-4-turbo | OpenAI GPT-4V (default) |
| `o3` | o3 | OpenAI O3 reasoning model |
| `qwen2.5-vl` | qwen2.5-vl-72b-instruct, 7b, 3b | Alibaba Qwen 2.5 VL |
| `qwen3-vl` | qwen3-vl | Alibaba Qwen 3 VL with thinking mode |

## Quick Start

### 1. Start the Multi-Agent Server

```bash
# Default port 9003
python white_agent/multi_agent_server.py

# Custom port
python white_agent/multi_agent_server.py --port 9004
```

### 2. Check Available Agents

```bash
curl http://localhost:9003/agents
```

Response:
```json
{
  "available_types": {
    "gpt-4v": {
      "default_model": "gpt-4o",
      "supported_models": ["gpt-4o", "gpt-4-vision-preview", "gpt-4-turbo"]
    },
    "qwen2.5-vl": {
      "default_model": "qwen2.5-vl-72b-instruct",
      "supported_models": ["qwen2.5-vl-72b-instruct", "qwen2.5-vl-7b-instruct", ...]
    },
    ...
  },
  "active_instances": {
    "default": {
      "type": "gpt-4v",
      "config": {...}
    }
  }
}
```

### 3. Create Agent with Custom Configuration

```bash
curl -X POST http://localhost:9003/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "qwen2.5-vl",
    "model": "qwen2.5-vl-72b-instruct",
    "temperature": 0.5,
    "max_tokens": 2000,
    "extra_params": {
      "history_n": 6
    }
  }'
```

Response:
```json
{
  "agent_id": "agent-abc123",
  "type": "qwen2.5-vl",
  "status": "created"
}
```

### 4. Switch Active Agent

```bash
curl -X POST http://localhost:9003/agents/agent-abc123/switch
```

### 5. Use Agent for Decisions

```bash
curl -X POST http://localhost:9003/decide \
  -H "Content-Type: application/json" \
  -d '{
    "observation": {
      "instruction": "Open Firefox",
      "screenshot": "<base64-encoded-png>"
    }
  }'
```

## Environment Setup

### For GPT-4V / O3
```bash
export OPENAI_API_KEY="your-key-here"
```

### For Qwen Models (DashScope)
```bash
export DASHSCOPE_API_KEY="your-key-here"
# Optional: custom endpoint
export DASHSCOPE_BASE_URL="https://dashscope.aliyuncs.com/api/v1"
```

### For Qwen Models (OpenAI-compatible)
```bash
export OPENAI_API_KEY="your-key-here"
export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
```

## Integration with Green Agent

Update the orchestrator to use the multi-agent server:

```python
# In orchestrator/a2a_green_agent.py
WHITE_AGENT_URL = "http://localhost:9003"

# Before starting assessment, create custom agent
import httpx
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{WHITE_AGENT_URL}/agents",
        json={
            "agent_type": "qwen2.5-vl",
            "model": "qwen2.5-vl-72b-instruct",
            "temperature": 0.3
        }
    )
    agent_id = response.json()["agent_id"]

    # Switch to new agent
    await client.post(f"{WHITE_AGENT_URL}/agents/{agent_id}/switch")
```

## Adding New Agents

To add a new agent type, update `AGENT_REGISTRY` in `multi_agent_server.py`:

```python
AGENT_REGISTRY["my-agent"] = {
    "class": MyAgentClass,
    "default_model": "my-model-v1",
    "supported_models": ["my-model-v1", "my-model-v2"],
    "default_params": {
        "observation_type": "screenshot",
        "action_space": "pyautogui",
        "max_tokens": 1500,
        # ... agent-specific params
    }
}
```

Requirements:
- Agent class must have `predict(instruction: str, obs: Dict)` method
- Agent class must have `reset(_logger=None)` method
- Import the agent class at the top of the file

## WebUI Integration

The WebUI can be updated to:

1. **List available agent types** from `/agents` endpoint
2. **Show agent selection dropdown** in launch configuration
3. **Display active agent type** in monitor view
4. **Allow switching agents** mid-assessment (advanced)

Example UI flow:
```
Launch Page:
┌─────────────────────────────────┐
│ Agent Type: [gpt-4v ▼]          │
│ Model: [gpt-4o ▼]               │
│ Temperature: [1.0]              │
└─────────────────────────────────┘
```

## API Reference

### GET /health
Returns server health and active agent count

### GET /agents
List available agent types and active instances

### POST /agents
Create new agent instance with configuration

Body:
```json
{
  "agent_type": "gpt-4v",
  "model": "gpt-4o",
  "temperature": 1.0,
  "max_tokens": 1500,
  "top_p": 0.9,
  "action_space": "pyautogui",
  "observation_type": "screenshot",
  "extra_params": {}
}
```

### POST /agents/{agent_id}/switch
Switch current active agent

### POST /reset
Reset agent state

Optional query param: `agent_id`

### POST /decide
Make decision based on observation

Body:
```json
{
  "observation": {
    "instruction": "Task instruction",
    "screenshot": "base64-encoded-image",
    "...": "other observation data"
  }
}
```

Optional query param: `agent_id` (uses current agent if not specified)

## Comparison: Single vs Multi-Agent Server

| Feature | gpt4v_server.py | multi_agent_server.py |
|---------|-----------------|------------------------|
| Agents | GPT-4V only | GPT-4V, O3, Qwen, etc. |
| Runtime switching | No | Yes |
| Multiple concurrent agents | No | Yes |
| Agent registry | No | Yes |
| Backward compatible | - | Yes (default agent) |

## Performance Notes

- Each agent instance maintains its own history/state
- Creating new agents is fast (no model loading, just initialization)
- Switching agents is instant
- No additional overhead compared to single-agent server
- API calls are the bottleneck, not the wrapper

## Troubleshooting

**Agent creation fails with "Unknown agent type"**
- Check that agent type is in AGENT_REGISTRY
- Verify agent class is imported

**API key errors**
- Check environment variables are set
- For Qwen: verify DASHSCOPE_API_KEY or OPENAI_API_KEY + OPENAI_BASE_URL

**"Agent not found" when calling /decide**
- Agent was deleted or server restarted
- Create new agent or use default agent

**Different return formats from agents**
- The wrapper handles this automatically
- All agents return `{"action": ..., "content": ..., "metadata": ...}`
