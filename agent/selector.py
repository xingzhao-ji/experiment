"""Backend selection logic for the Claw Engine agent.

Reads a config dict (typically sourced from config/budget.yaml) and decides
whether to use the Claude or Ollama backend, respecting budget limits and
the fallback_enabled flag.
"""

from __future__ import annotations

import logging

from agent.base import ModelBackend
from agent.claude_backend import ClaudeBackend, _INPUT_PRICE_PER_M, _OUTPUT_PRICE_PER_M
from agent.ollama_backend import OllamaBackend

log = logging.getLogger(__name__)

# Rough per-call cost estimate used by select_backend() when the caller
# only provides the remaining budget (not the exact token counts).
# Based on budget.yaml defaults: 30 000 input + 8 000 output tokens.
_ESTIMATED_INPUT_TOKENS = 30_000
_ESTIMATED_OUTPUT_TOKENS = 8_000


def get_backend(config: dict) -> ModelBackend:
    """Return the best available backend according to *config*.

    Default behaviour:
        1. Try to instantiate ClaudeBackend.
        2. If ``fallback_enabled`` is truthy and Claude cannot be created
           (missing API key, missing package, etc.), fall back to Ollama.
        3. If fallback is disabled, let the exception propagate.
    """
    fallback_enabled: bool = config.get("fallback_enabled", False)

    try:
        backend = ClaudeBackend(config)
        log.info("Selected Claude backend (model=%s)", backend._model)
        return backend
    except Exception as exc:
        if not fallback_enabled:
            raise
        log.warning(
            "Claude backend unavailable (%s); falling back to Ollama.", exc
        )
        backend = OllamaBackend(config)
        log.info("Selected Ollama backend (model=%s)", backend._model)
        return backend


def select_backend(config: dict, budget_remaining: float) -> ModelBackend:
    """Pick the right backend considering the remaining budget.

    If the estimated cost of a Claude call exceeds *budget_remaining* and
    ``fallback_enabled`` is set, Ollama is returned instead.
    """
    fallback_enabled: bool = config.get("fallback_enabled", False)

    # Estimate what a Claude call would cost using its published pricing.
    estimated_cost = (
        (_ESTIMATED_INPUT_TOKENS / 1_000_000) * _INPUT_PRICE_PER_M
        + (_ESTIMATED_OUTPUT_TOKENS / 1_000_000) * _OUTPUT_PRICE_PER_M
    )

    if estimated_cost > budget_remaining:
        if fallback_enabled:
            log.info(
                "Estimated Claude cost $%.4f exceeds remaining budget "
                "$%.4f; selecting Ollama.",
                estimated_cost,
                budget_remaining,
            )
            return OllamaBackend(config)
        log.warning(
            "Estimated Claude cost $%.4f exceeds remaining budget "
            "$%.4f but fallback is disabled.",
            estimated_cost,
            budget_remaining,
        )
        # Still return Claude -- let the orchestrator enforce the hard cap.

    return get_backend(config)
