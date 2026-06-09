"""The one interface every LLM provider implements.

The pipeline only ever calls `provider.complete(system, user)` — it has no idea
which vendor is behind it. That is what makes the LLM swappable from the UI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMError(RuntimeError):
    """Raised when a provider call fails (auth, network, bad response)."""


class LLMProvider(ABC):
    def __init__(self, model: str) -> None:
        self.model = model

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Return the model's text completion for a system + user prompt."""
        raise NotImplementedError
