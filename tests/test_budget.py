"""Tests for the budget enforcement module."""

import tempfile
from pathlib import Path

import pytest
import yaml

from orchestrator.budget import (
    BudgetConfig,
    BudgetExceeded,
    KillSwitchActive,
    check_budget,
    load_budget,
)


def test_load_budget_from_real_config(budget_path):
    """The shipped config/budget.yaml must parse correctly."""
    budget = load_budget(budget_path)
    assert isinstance(budget, BudgetConfig)
    assert budget.daily_budget_usd > 0
    assert budget.monthly_budget_usd > 0
    assert budget.kill_switch is False


def test_load_budget_missing_file():
    """Must raise FileNotFoundError when the file doesn't exist."""
    with pytest.raises(FileNotFoundError, match="Budget file not found"):
        load_budget("/nonexistent/budget.yaml")


def test_load_budget_malformed():
    """Must raise ValueError for non-mapping YAML."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("just a string\n")
        f.flush()
        with pytest.raises(ValueError, match="malformed"):
            load_budget(f.name)


def test_load_budget_missing_keys():
    """Must raise ValueError when required keys are absent."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump({"daily_budget_usd": 1.0}, f)
        f.flush()
        with pytest.raises(ValueError, match="missing required keys"):
            load_budget(f.name)


def test_kill_switch_raises():
    budget = BudgetConfig(
        daily_budget_usd=10,
        monthly_budget_usd=100,
        max_input_tokens=30000,
        max_output_tokens=8000,
        fallback_enabled=True,
        fallback_model="qwen3:32b",
        kill_switch=True,
    )
    with pytest.raises(KillSwitchActive):
        check_budget(budget)


def test_check_budget_returns_remaining(budget_path):
    budget = load_budget(budget_path)
    remaining = check_budget(budget)
    assert remaining > 0
    assert remaining <= budget.daily_budget_usd
