"""Groq integration helpers.

Centralizes Groq client setup and JSON completion calls so app routes can
import a single function instead of embedding provider-specific logic.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from groq import Groq

DEFAULT_MODEL = "llama-3.3-70b-versatile"

_client: Groq | None = None


def _get_client() -> Groq:
    """Return a cached Groq client built from GROQ_API_KEY."""
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        _client = Groq(api_key=api_key)
    return _client


def get_model_name() -> str:
    """Resolve model name from environment with a sensible default."""
    return os.getenv("GROQ_MODEL", DEFAULT_MODEL)


def _parse_json_content(raw: str) -> dict[str, Any]:
    """Parse model output as JSON, tolerating accidental markdown fences."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = re.sub(r"```json|```", "", raw).strip()
        return json.loads(cleaned)


def call_groq(
    system_prompt: str,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 1024,
    model: str | None = None,
) -> dict[str, Any]:
    """Call Groq chat completions and return parsed JSON output."""
    groq_messages = [{"role": "system", "content": system_prompt}, *messages]

    response = _get_client().chat.completions.create(
        model=model or get_model_name(),
        messages=groq_messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    return _parse_json_content(raw)
