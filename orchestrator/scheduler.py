"""Nightly scheduler for Claw Engine.

Provides a simple cron-like scheduler that triggers one run per night.
In production this would be invoked by a system cron job or a container
scheduler.  This module provides the logic for selecting *what* to run.
"""

from __future__ import annotations

import random
from datetime import date, datetime

import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def pick_nightly_config() -> dict:
    """Select the dataset and question for tonight's run.

    Returns a dict with keys: dataset_id, question_id, run_date
    """
    from datasets.catalog import list_available

    available = list_available(local_only=True)
    if not available:
        raise RuntimeError("No local datasets available for nightly run")

    # Deterministic-ish selection based on date so reruns on the same
    # night pick the same config.
    today = date.today()
    rng = random.Random(today.toordinal())

    dataset = rng.choice(available)

    questions_path = PROJECT_ROOT / "templates" / "questions.yaml"
    with open(questions_path) as f:
        questions = yaml.safe_load(f)["questions"]

    # Filter to questions whose task_type matches the dataset
    compatible = [q for q in questions if q["task_type"] in dataset.task_types]
    if not compatible:
        compatible = questions  # fallback to any question

    question = rng.choice(compatible)

    return {
        "dataset_id": dataset.id,
        "question_id": question["id"],
        "run_date": str(today),
    }


def should_run_tonight() -> bool:
    """Check if a run should happen tonight (simple daily gate)."""
    from orchestrator.budget import load_budget, check_budget, KillSwitchActive, BudgetExceeded

    try:
        budget = load_budget()
        check_budget(budget)
        return True
    except (FileNotFoundError, ValueError, KillSwitchActive, BudgetExceeded):
        return False
