"""Multi-provider LLM client with Gemini key rotation and OpenRouter fallback.

Design goals (see the ingestion/categorization notes):
  * PRIMARY: Google Gemini (Google AI Studio). Several free-tier keys are kept in
    the ``GEMINI_API_KEYS`` env var (comma separated). We round-robin across them
    and, when a key returns a quota/429, put that key on a short cooldown and move
    to the next one. This stretches free-tier limits across N keys.
  * FALLBACK: when every Gemini key is cooling down (or none are configured), we
    fall back to OpenRouter's free Nemotron model so the feature still works.
  * If nothing is configured/available, callers get ``LLMUnavailable`` and are
    expected to degrade gracefully (e.g. keep rule-based categorization).

The client is intentionally dependency-light (uses ``requests``) and exposes a
sync ``complete``/``complete_json`` plus async wrappers so it can be awaited from
the ingestion path without blocking the event loop.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import threading
import time
from typing import Any, Optional

import requests

from app.core.config import get_settings

logger = logging.getLogger("tally.llm")

# How long (seconds) to rest a Gemini key after it reports a quota/rate error.
_KEY_COOLDOWN_SECONDS = 60
_HTTP_TIMEOUT = 30


class LLMUnavailable(Exception):
    """Raised when no provider could satisfy the request."""


class _GeminiKeyPool:
    """Thread-safe round-robin over Gemini keys with per-key cooldowns."""

    def __init__(self, keys: list[str]):
        self._keys = keys
        self._cooldown_until: dict[str, float] = {}
        self._cycle = itertools.cycle(keys) if keys else None
        self._lock = threading.Lock()

    def has_keys(self) -> bool:
        return bool(self._keys)

    def next_available(self) -> Optional[str]:
        """Return a key that isn't cooling down, or None if all are resting."""
        if not self._keys:
            return None
        now = time.monotonic()
        with self._lock:
            for _ in range(len(self._keys)):
                key = next(self._cycle)
                if self._cooldown_until.get(key, 0) <= now:
                    return key
        return None

    def penalize(self, key: str) -> None:
        with self._lock:
            self._cooldown_until[key] = time.monotonic() + _KEY_COOLDOWN_SECONDS
        logger.warning("[llm] gemini key rate-limited; cooling down for %ss", _KEY_COOLDOWN_SECONDS)


# Built lazily so tests / imports don't require settings at import time.
_pool: Optional[_GeminiKeyPool] = None
_pool_lock = threading.Lock()


def _get_pool() -> _GeminiKeyPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = _GeminiKeyPool(get_settings().gemini_keys_list)
    return _pool


def is_available() -> bool:
    """True if at least one provider is configured (Gemini keys or OpenRouter)."""
    settings = get_settings()
    return bool(settings.gemini_keys_list) or bool(settings.openrouter_api_key)


def _call_gemini(key: str, prompt: str, max_tokens: int, temperature: float) -> str:
    settings = get_settings()
    url = f"{settings.gemini_api_url}/models/{settings.gemini_model}:generateContent"
    resp = requests.post(
        url,
        params={"key": key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        },
        timeout=_HTTP_TIMEOUT,
    )
    if resp.status_code == 429 or (resp.status_code == 403 and "quota" in resp.text.lower()):
        raise _RateLimited()
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError(f"gemini returned no candidates: {str(data)[:200]}")
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()


def _call_openrouter(prompt: str, max_tokens: int, temperature: float) -> str:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise LLMUnavailable("no openrouter api key configured")
    resp = requests.post(
        f"{settings.openrouter_api_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "Tally Personal Finance OS",
        },
        json={
            "model": settings.openrouter_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


class _RateLimited(Exception):
    """Internal signal that a Gemini key hit its quota."""


def complete(prompt: str, max_tokens: int = 512, temperature: float = 0.0) -> str:
    """Get a completion, trying Gemini keys (rotating) then OpenRouter.

    Raises:
        LLMUnavailable: if no provider could produce a result.
    """
    pool = _get_pool()

    # Try each currently-available Gemini key once.
    if pool.has_keys():
        while True:
            key = pool.next_available()
            if key is None:
                break  # all keys cooling down -> fall through to OpenRouter
            try:
                return _call_gemini(key, prompt, max_tokens, temperature)
            except _RateLimited:
                pool.penalize(key)
                continue
            except Exception as e:
                logger.warning("[llm] gemini call failed (%s); trying next provider", e)
                break

    # Fallback: OpenRouter free model.
    try:
        return _call_openrouter(prompt, max_tokens, temperature)
    except LLMUnavailable:
        raise
    except Exception as e:
        raise LLMUnavailable(f"all providers failed: {e}") from e


def complete_json(prompt: str, max_tokens: int = 1024, temperature: float = 0.0) -> Any:
    """Like ``complete`` but parses the model output as JSON.

    Tolerates ```json fenced blocks. Raises ``LLMUnavailable`` on unparseable
    output so callers can degrade gracefully.
    """
    raw = complete(prompt, max_tokens=max_tokens, temperature=temperature)
    text = raw.strip()
    if text.startswith("```"):
        # Strip a leading ```json / ``` fence and the trailing ```.
        text = text.split("\n", 1)[-1] if "\n" in text else text
        if text.endswith("```"):
            text = text[: -3]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: grab the outermost JSON object/array.
        for open_c, close_c in (("{", "}"), ("[", "]")):
            start, end = text.find(open_c), text.rfind(close_c)
            if start != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    continue
        raise LLMUnavailable(f"could not parse JSON from model output: {raw[:200]}")


async def acomplete(prompt: str, max_tokens: int = 512, temperature: float = 0.0) -> str:
    """Async wrapper (runs the blocking HTTP call in a thread)."""
    return await asyncio.to_thread(complete, prompt, max_tokens, temperature)


async def acomplete_json(prompt: str, max_tokens: int = 1024, temperature: float = 0.0) -> Any:
    """Async wrapper for ``complete_json``."""
    return await asyncio.to_thread(complete_json, prompt, max_tokens, temperature)
