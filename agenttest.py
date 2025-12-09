from white_agent.config import AgentConfig
from white_agent.agents import create_agent

from dotenv import load_dotenv
load_dotenv()

import json
import base64

with open("screenshot.png", "rb") as f:
    observation_b64 = base64.b64encode(f.read()).decode("utf-8")
    observation = {"screenshot": f.read()}

instruction = json.dumps({
     "task_id": "task_123",
    "context_id": "ctx_456",
    "message": "Please enable Bluetooth on my device.",
    "metadata": {
        "observation": {
            "frame_id": 0,
            "image_png_b64": f"{observation_b64}",
            "instruction": "Turn on Bluetooth",
            "accessibility_tree": "<xml>...</xml>",
            "done": False
        }
    }
})

config = AgentConfig(agent_type="langchain", model="gpt-4o")
agent = create_agent(config)
reasoning, action = agent.predict(instruction, observation)