"""Shared fixtures for Claw Engine tests."""

import os
import sys
from pathlib import Path

import pytest

# Ensure the project root is on sys.path so imports work.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def project_root():
    return PROJECT_ROOT


@pytest.fixture
def budget_path(project_root):
    return str(project_root / "config" / "budget.yaml")


@pytest.fixture
def toy_dataset_path(project_root):
    return str(project_root / "datasets" / "toy_data" / "toy_expression.csv")
