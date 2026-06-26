"""OpenRouter key rotation and multi-model management."""

import logging
import os
from typing import Optional
import httpx
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OpenRouterKeyManager:
    """Manage OpenRouter API keys with smart rotation and fallback."""

    def __init__(self):
        """Initialize key manager from environment."""
        # Parse comma-separated keys from env
        keys_str = os.getenv("OPENROUTER_API_KEYS", "")
        self.keys = [k.strip() for k in keys_str.split(",") if k.strip()]

        if not self.keys:
            # Fallback to single key if env var not set
            single_key = os.getenv("OPENROUTER_API_KEY", "")
            self.keys = [single_key] if single_key else []

        self.current_idx = 0
        self.api_url = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1")
        self.key_stats = {key: {"used": 0, "errors": 0, "last_used": None} for key in self.keys}

    def get_current_key(self) -> str:
        """Get current active API key."""
        if not self.keys:
            raise ValueError("No OpenRouter API keys configured")
        return self.keys[self.current_idx]

    def rotate_key(self, reason: str = "rate_limit") -> str:
        """Rotate to next available key."""
        if len(self.keys) <= 1:
            logger.warning(f"Only one key available, cannot rotate ({reason})")
            return self.get_current_key()

        old_idx = self.current_idx
        self.current_idx = (self.current_idx + 1) % len(self.keys)
        new_key = self.get_current_key()

        logger.info(
            f"Rotated key {old_idx} → {self.current_idx} (reason: {reason}). "
            f"Stats: {self.key_stats[self.keys[old_idx]]}"
        )

        return new_key

    def mark_success(self, key: str, tokens_used: int = 0):
        """Record successful API call."""
        if key in self.key_stats:
            self.key_stats[key]["used"] += 1
            self.key_stats[key]["last_used"] = datetime.utcnow().isoformat()

    def mark_error(self, key: str, error_type: str):
        """Record API error."""
        if key in self.key_stats:
            self.key_stats[key]["errors"] += 1
            if error_type == "rate_limit":
                self.rotate_key(reason=f"rate_limit on key {self.keys.index(key)}")

    def get_stats(self) -> dict:
        """Get key usage statistics."""
        return {
            "current_key_index": self.current_idx,
            "total_keys": len(self.keys),
            "stats": self.key_stats,
        }


# Global instance
_key_manager: Optional[OpenRouterKeyManager] = None


def get_key_manager() -> OpenRouterKeyManager:
    """Get or create global key manager."""
    global _key_manager
    if _key_manager is None:
        _key_manager = OpenRouterKeyManager()
    return _key_manager


class OpenRouterClient:
    """OpenRouter LLM client with automatic key rotation and fallback."""

    def __init__(self, key_manager: Optional[OpenRouterKeyManager] = None):
        """Initialize client with key manager."""
        self.key_manager = key_manager or get_key_manager()
        self.api_url = self.key_manager.api_url

    async def call_llm(
        self,
        model: str,
        messages: list,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        fallback_model: Optional[str] = None,
    ) -> dict:
        """
        Call LLM via OpenRouter with automatic rotation on failure.

        Args:
            model: Primary model to use
            messages: Chat messages
            max_tokens: Max response tokens
            temperature: Sampling temperature
            fallback_model: Model to use if primary fails

        Returns:
            Response dict with 'content' and 'usage' keys
        """
        attempts = 0
        max_attempts = min(3, len(self.key_manager.keys) + 1)
        last_error = None

        while attempts < max_attempts:
            try:
                current_model = model if attempts == 0 else (fallback_model or "openrouter/auto")
                key = self.key_manager.get_current_key()

                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(
                        f"{self.api_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {key}",
                            "HTTP-Referer": "http://localhost:3000",
                            "X-Title": "Personal Finance OS",
                        },
                        json={
                            "model": current_model,
                            "messages": messages,
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                        },
                    )

                    if response.status_code == 200:
                        data = response.json()
                        self.key_manager.mark_success(key)
                        return {
                            "content": data["choices"][0]["message"]["content"],
                            "usage": data.get("usage", {}),
                            "model": current_model,
                        }
                    elif response.status_code == 429:  # Rate limit
                        self.key_manager.mark_error(key, "rate_limit")
                        attempts += 1
                        continue
                    else:
                        last_error = f"Status {response.status_code}: {response.text}"
                        self.key_manager.mark_error(key, "error")
                        attempts += 1
                        continue

            except Exception as e:
                last_error = str(e)
                self.key_manager.mark_error(self.key_manager.get_current_key(), "exception")
                attempts += 1

        raise RuntimeError(
            f"All LLM attempts failed after {attempts} tries. "
            f"Last error: {last_error}. Key stats: {self.key_manager.get_stats()}"
        )
