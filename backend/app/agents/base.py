"""Base agent classes and utilities for financial AI system."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger(__name__)


class LLMConfig:
    """Configuration for LLM calls via OpenRouter."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "neomorph/nemotron-3-ultra",
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
    ) -> str:
        """Call LLM via OpenRouter."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "Personal Finance OS",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    **({"response_format": {"type": "json_object"}} if json_mode else {}),
                },
            )

            if response.status_code != 200:
                raise RuntimeError(
                    f"LLM API error {response.status_code}: {response.text}"
                )

            data = response.json()
            return data["choices"][0]["message"]["content"]


class FinancialAgent(ABC):
    """Base class for financial AI agents."""

    def __init__(self, llm_config: LLMConfig, name: str):
        self.llm = llm_config
        self.name = name

    @abstractmethod
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the agent."""
        pass

    def _log(self, message: str):
        """Log agent activity."""
        logger.info(f"[{self.name}] {message}")


class AgentResult:
    """Result from agent execution."""

    def __init__(
        self,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        self.success = success
        self.data = data or {}
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
        }
