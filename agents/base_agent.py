from typing import Any, Dict, Optional
from loguru import logger


class BaseAgent:
    AGENT_NAME: str = "base"
    PROMPT_TEMPLATE: str = ""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        logger.debug(f"Agent initialized: {agent_name}")

    def execute(self, **kwargs) -> Any:
        raise NotImplementedError
