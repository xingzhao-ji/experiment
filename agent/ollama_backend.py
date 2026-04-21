"""Ollama (local) backend for the Claw Engine agent."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from agent.base import ModelBackend

# Default endpoint for the Ollama HTTP API.
_DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"

# Default model served by Ollama.
_DEFAULT_MODEL = "qwen3:32b"

# Import the same dry-run analysis script used by the Claude backend so
# both backends exercise the full pipeline identically in demo mode.
from agent.claude_backend import _DRY_RUN_SCRIPT


class OllamaBackend(ModelBackend):
    """Local Ollama backend (zero cost)."""

    def __init__(self, config: dict) -> None:
        super().__init__(config)

        self._model: str = config.get("fallback_model", _DEFAULT_MODEL)
        self._dry_run: bool = config.get("dry_run", False)
        self._base_url: str = config.get("ollama_url", _DEFAULT_OLLAMA_URL)

    # ------------------------------------------------------------------
    # ModelBackend interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "ollama"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if self._dry_run:
            return _DRY_RUN_SCRIPT

        payload = json.dumps(
            {
                "model": self._model,
                "system": system_prompt,
                "prompt": user_prompt,
                "stream": False,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            self._base_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not connect to Ollama at {self._base_url}. "
                f"Make sure the Ollama server is running "
                f"('ollama serve' in another terminal). "
                f"Original error: {exc}"
            ) from exc
        except ConnectionError as exc:
            raise RuntimeError(
                f"Connection to Ollama at {self._base_url} was refused. "
                f"Ensure Ollama is running and the URL is correct. "
                f"Original error: {exc}"
            ) from exc

        return body.get("response", "")

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        # Local inference has no dollar cost.
        return 0.0
