"""Abstract base class for model backends used by the Claw Engine agent."""

from abc import ABC, abstractmethod


class ModelBackend(ABC):
    """Base interface that every LLM backend must implement."""

    def __init__(self, config: dict) -> None:
        self._config = config

    @property
    def config(self) -> dict:
        return self._config

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier for this backend (e.g. 'claude', 'ollama')."""
        ...

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompts to the model and return the assistant's text response."""
        ...

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Return estimated USD cost for a call with the given token counts."""
        ...
