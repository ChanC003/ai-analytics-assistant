"""Anthropic (Claude) provider — uses the official anthropic SDK.

Claude is NOT OpenAI-compatible: it has its own client and a `messages.create`
API where the system prompt is a top-level argument, not a message role.
"""

from __future__ import annotations

from anthropic import Anthropic

from src.llm.base import LLMError, LLMProvider

# Generous cap for an explained SQL statement; cheap models stop well short.
_MAX_TOKENS = 2048


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str, api_key: str) -> None:
        super().__init__(model)
        if not api_key:
            raise LLMError("Missing API key for Anthropic (Claude).")
        self._client = Anthropic(api_key=api_key)

    def complete(self, system: str, user: str) -> str:
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=_MAX_TOKENS,
                system=system,                      # top-level, not a message
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # noqa: BLE001 — surface any vendor error uniformly
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc

        # content is a list of blocks; take the first text block.
        text = next((b.text for b in resp.content if b.type == "text"), "").strip()
        if not text:
            raise LLMError("Empty response from Claude.")
        return text
