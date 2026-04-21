"""End-to-end dry-run test for the Claw Engine.

This exercises the full pipeline: budget loading → dataset selection →
agent (dry-run) → local sandbox execution → critic → artifact bundling.
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure project root is importable.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_full_dry_run():
    """A dry-run must produce a valid artifact bundle."""
    # Run from the project root so relative paths in the engine resolve.
    original_cwd = os.getcwd()
    os.chdir(PROJECT_ROOT)

    try:
        from orchestrator.engine import run

        result = run(
            dry_run=True,
            use_docker=False,
            question_id="diff_expr",
        )

        # Basic success checks
        assert result.run_id, "run_id should be set"
        assert result.bundle_dir is not None, "bundle_dir should be set"

        bundle = Path(result.bundle_dir)
        assert bundle.exists(), f"Bundle dir should exist: {bundle}"

        # Check all required artifacts
        assert (bundle / "post.md").exists(), "post.md missing"
        assert (bundle / "plot.png").exists(), "plot.png missing"
        assert (bundle / "raw_results.csv").exists(), "raw_results.csv missing"
        assert (bundle / "run_log.txt").exists(), "run_log.txt missing"
        assert (bundle / "reproduce.sh").exists(), "reproduce.sh missing"

        # Check post.md has content
        post_text = (bundle / "post.md").read_text()
        assert len(post_text) > 50, "post.md should have meaningful content"

        # Check finding was parsed
        assert result.finding is not None, "finding should be parsed"
        assert result.finding.get("status") == "success"
        assert result.finding.get("p_value") is not None

        # Critic should pass
        assert result.critic_pass, "critic should pass on valid artifacts"
        assert result.success, "overall run should succeed"

        # Full log should be archived
        log_text = (bundle / "run_log.txt").read_text()
        assert "Budget OK" in log_text

    finally:
        os.chdir(original_cwd)


def test_dry_run_discord_local():
    """The local Discord digest must format correctly."""
    original_cwd = os.getcwd()
    os.chdir(PROJECT_ROOT)

    try:
        from orchestrator.engine import run
        from discord_bot.bot import post_digest_local

        result = run(dry_run=True, use_docker=False, question_id="diff_expr")
        digest_result = post_digest_local(result)

        assert digest_result["mode"] == "local"
        assert digest_result["digest"]  # non-empty string
        assert "Claw Engine Run Report" in digest_result["digest"]

        if result.success:
            assert digest_result["published"] is True
    finally:
        os.chdir(original_cwd)
