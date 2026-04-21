"""Budget enforcement for Claw Engine runs.

The orchestrator MUST call load_budget() and check_budget() before
every run.  If the budget file is missing the run MUST abort.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


SPEND_LOG = Path("out/.spend_log.yaml")


@dataclass
class BudgetConfig:
    daily_budget_usd: float
    monthly_budget_usd: float
    max_input_tokens: int
    max_output_tokens: int
    fallback_enabled: bool
    fallback_model: str
    kill_switch: bool

    def to_agent_config(self) -> dict:
        return {
            "daily_budget_usd": self.daily_budget_usd,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "fallback_enabled": self.fallback_enabled,
            "fallback_model": self.fallback_model,
        }


class BudgetExceeded(Exception):
    pass


class KillSwitchActive(Exception):
    pass


def load_budget(path: str | Path = "config/budget.yaml") -> BudgetConfig:
    """Load and validate budget configuration.  Raises on any problem."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Budget file not found: {path}.  "
            "The orchestrator refuses to run without a budget."
        )

    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Budget file {path} is malformed (expected a YAML mapping)")

    required = [
        "daily_budget_usd",
        "monthly_budget_usd",
        "max_input_tokens",
        "max_output_tokens",
        "kill_switch",
    ]
    missing = [k for k in required if k not in raw]
    if missing:
        raise ValueError(f"Budget file missing required keys: {missing}")

    return BudgetConfig(
        daily_budget_usd=float(raw["daily_budget_usd"]),
        monthly_budget_usd=float(raw["monthly_budget_usd"]),
        max_input_tokens=int(raw["max_input_tokens"]),
        max_output_tokens=int(raw["max_output_tokens"]),
        fallback_enabled=bool(raw.get("fallback_enabled", True)),
        fallback_model=str(raw.get("fallback_model", "qwen3:32b")),
        kill_switch=bool(raw["kill_switch"]),
    )


def _load_spend_log() -> dict:
    if SPEND_LOG.exists():
        with open(SPEND_LOG) as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_spend_log(log: dict) -> None:
    SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SPEND_LOG, "w") as f:
        yaml.safe_dump(log, f)


def get_daily_spend() -> float:
    """Return total USD spent today."""
    from datetime import date

    log = _load_spend_log()
    today = str(date.today())
    return float(log.get("daily", {}).get(today, 0.0))


def get_monthly_spend() -> float:
    """Return total USD spent this calendar month."""
    from datetime import date

    log = _load_spend_log()
    today = date.today()
    month_key = today.strftime("%Y-%m")
    return float(log.get("monthly", {}).get(month_key, 0.0))


def record_spend(amount_usd: float) -> None:
    """Record a spend event."""
    from datetime import date

    log = _load_spend_log()
    today = date.today()
    day_key = str(today)
    month_key = today.strftime("%Y-%m")

    daily = log.setdefault("daily", {})
    daily[day_key] = float(daily.get(day_key, 0.0)) + amount_usd

    monthly = log.setdefault("monthly", {})
    monthly[month_key] = float(monthly.get(month_key, 0.0)) + amount_usd

    _save_spend_log(log)


def check_budget(budget: BudgetConfig) -> float:
    """Check budget constraints.  Returns remaining daily budget in USD.

    Raises KillSwitchActive if kill switch is on.
    Raises BudgetExceeded if daily or monthly cap is hit.
    """
    if budget.kill_switch:
        raise KillSwitchActive("Kill switch is active in budget.yaml – aborting run")

    daily_spent = get_daily_spend()
    if daily_spent >= budget.daily_budget_usd:
        raise BudgetExceeded(
            f"Daily budget exhausted: ${daily_spent:.2f} / ${budget.daily_budget_usd:.2f}"
        )

    monthly_spent = get_monthly_spend()
    if monthly_spent >= budget.monthly_budget_usd:
        raise BudgetExceeded(
            f"Monthly budget exhausted: ${monthly_spent:.2f} / ${budget.monthly_budget_usd:.2f}"
        )

    return budget.daily_budget_usd - daily_spent
