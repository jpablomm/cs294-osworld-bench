# white_agent/agents/langchain_agent.py

"""
LangChain Agent Implementation.
"""

import base64
import logging
import os
from typing import Any, Dict, Tuple

from .base import BaseAgent
from ..config import AgentConfig

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a GUI automation agent. Analyze the screenshot and determine the next action.

Output format:
Thought: <your reasoning>
Action: <pyautogui command>

Available actions:
- pyautogui.click(x, y)
- pyautogui.doubleClick(x, y)
- pyautogui.write('text')
- pyautogui.hotkey('key1', 'key2')
- pyautogui.scroll(amount)
- DONE (task complete)
- FAIL (task impossible)
"""


class LangChainAgent(BaseAgent):
    """LangChain-based agent for OSWorld tasks."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._llm = None

    def ensure_initialized(self) -> None:
        if self._initialized:
            return

        try:
            from langchain.chat_models import init_chat_model
        except ImportError:
            raise ImportError("Install langchain: pip install langchain")

        try:
            from deepagents import create_deep_agent
        except ImportError:
            raise ImportError("Install deepagents: pip install deepagents")
        
        try:
            from tavily import TavilyClient
        except ImportError:
            raise ImportError("Install tavily: pip install tavily-python")

        api_key = self.config.get_api_key()
        tavily_api_key = os.environ["TAVILY_API_KEY"]

        tavily_client = TavilyClient(api_key=tavily_api_key)

        def tavily_search(query: str, max_results: int = 5, include_raw_content: bool = False):
            """Run a web search"""
            return tavily_client.search(
                query,
                max_results=max_results,
                include_raw_content=include_raw_content,
                topic="general",
            )

        self._llm = init_chat_model(
            model=self.config.model,
            api_key=api_key,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        self._llm = create_deep_agent(model=self._llm, system_prompt=SYSTEM_PROMPT, tools=[tavily_search])

        logger.info(f"Initialized LangChainAgent with model={self.config.model}")
        self._initialized = True

    def predict(
        self,
        instruction: str,
        observation: Dict[str, Any]
    ) -> Tuple[str, str]:
        self.ensure_initialized()

        from langchain_core.messages import HumanMessage, SystemMessage

        # Convert screenshot to base64
        screenshot_bytes = observation["screenshot"]
        image_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        # Build messages
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=[
                {"type": "text", "text": f"Task: {instruction}"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                },
            ]),
        ]

        # Add trajectory context
        trajectory = self.get_trajectory_context()
        if trajectory:
            history_text = "\n".join(
                f"Step {s['step']}: {s['action']}" for s in trajectory
            )
            messages[1].content.insert(0, {
                "type": "text",
                "text": f"Previous actions:\n{history_text}"
            })

        # Call LLM
        response = self._llm.invoke(messages)
        response_text = response.content

        # Parse response
        reasoning, action = self._parse_response(response_text)

        self.add_to_history(thought=reasoning, action=action)
        return reasoning, action

    def _parse_response(self, response: str) -> Tuple[str, str]:
        """Parse LLM response into reasoning and action."""
        lines = response.strip().split("\n")

        reasoning = ""
        action = "FAIL"

        for line in lines:
            line = line.strip()
            if line.lower().startswith("thought:"):
                reasoning = line[8:].strip()
            elif line.lower().startswith("action:"):
                action = line[7:].strip()

        # Fallback: use full response as reasoning
        if not reasoning:
            reasoning = response

        return reasoning, action

    def reset(self) -> None:
        super().reset()