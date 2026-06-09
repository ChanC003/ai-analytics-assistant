"""One class for every OpenAI-compatible vendor.

Gemini, OpenAI, DeepSeek and Groq all speak the same chat.completions API, so
they differ only by base_url + api_key + model. The openai SDK handles all four.
"""

from __future__ import annotations

from openai import OpenAI

from src.llm.base import LLMError, LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, model: str, api_key: str, base_url: str) -> None:
        super().__init__(model)
        if not api_key:
            raise LLMError("Missing API key for this provider.")
        self._client = OpenAI(api_key=api_key, base_url=base_url or None)

    def complete(self, system: str, user: str) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0,  # deterministic SQL
            )
        except Exception as exc:  # noqa: BLE001 — surface any vendor error uniformly
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc

        content = (resp.choices[0].message.content or "").strip()
        if not content:
            raise LLMError("Empty response from model.")
        return content
