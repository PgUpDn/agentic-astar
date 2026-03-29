"""Thin async wrapper around the OpenAI chat-completions API."""

from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

from .config import settings

log = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    return _client


async def chat(
    system: str,
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    **kwargs: Any,
) -> str:
    """Send a chat completion request and return the assistant reply."""
    client = get_client()
    full_messages = [{"role": "system", "content": system}] + messages

    try:
        resp = await client.chat.completions.create(
            model=model or settings.openai_model,
            messages=full_messages,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            **kwargs,
        )
        content = resp.choices[0].message.content or ""
        log.debug("LLM response (%d chars): %s…", len(content), content[:120])
        return content
    except Exception:
        log.exception("LLM call failed")
        raise
