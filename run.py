#!/usr/bin/env python3
"""Claw Engine CLI – run the engine from the command line."""

import argparse
import logging
import os
import sys
from pathlib import Path

# Ensure the project root is on the path.
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)


def main():
    parser = argparse.ArgumentParser(description="Claw Engine – research agent runner")
    parser.add_argument("--dry-run", action="store_true", help="Use dry-run mode (no API calls)")
    parser.add_argument("--docker", action="store_true", help="Use Docker sandbox (default: local)")
    parser.add_argument("--dataset", type=str, default=None, help="Path to dataset CSV")
    parser.add_argument("--question", type=str, default=None, help="Question ID from templates")
    parser.add_argument("--budget", type=str, default="config/budget.yaml", help="Path to budget config")
    parser.add_argument("--local-discord", action="store_true", default=True, help="Use local Discord test mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    from orchestrator.engine import run
    from discord_bot.bot import run_bot

    print("=" * 60)
    print("  Claw Engine MVP")
    print("=" * 60)

    result = run(
        dataset_path=args.dataset,
        question_id=args.question,
        dry_run=args.dry_run,
        budget_path=args.budget,
        use_docker=args.docker,
    )

    print(f"\nRun {result.run_id}: {'SUCCESS' if result.success else 'FAILED'}")

    if result.bundle_dir:
        print(f"Bundle: {result.bundle_dir}")

    # Post digest
    digest_result = run_bot(result, local_mode=args.local_discord)

    if digest_result.get("published"):
        print("\nBundle published successfully.")
    elif result.success:
        print("\nBundle ready but not yet published (awaiting approval).")

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
