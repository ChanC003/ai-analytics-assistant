"""Local Ollama provider — plain HTTP, no API key, works offline."""

from __future__ import annotations

import requests

from src.llm.base import LLMError, LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self, model: str, base_url: str) -> None:
        super().__init__(model)
        self._base_url = (base_url or "http://localhost:11434").rstrip("/")

    def complete(self, system: str, user: str) -> str:
        try:
            resp = requests.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "options": {"temperature": 0},
                },
                timeout=120,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError(
                f"Cannot reach Ollama at {self._base_url} — is it running? ({exc})"
            ) from exc

        content = (resp.json().get("message", {}).get("content") or "").strip()
        if not content:
            raise LLMError("Empty response from Ollama.")
        return content
