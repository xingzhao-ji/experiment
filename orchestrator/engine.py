"""Claw Engine – main orchestration loop.

Responsible for:
1. Loading and enforcing budget
2. Selecting a dataset + question
3. Generating analysis code via the agent
4. Running code in the sandbox
5. Running the self-critic pass
6. Bundling artifacts
7. Handing off to the Discord bot for digest posting
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import yaml

from orchestrator.budget import (
    BudgetConfig,
    BudgetExceeded,
    KillSwitchActive,
    check_budget,
    load_budget,
    record_spend,
)

logger = logging.getLogger("claw.engine")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class RunResult:
    def __init__(self, run_id: str, success: bool, bundle_dir: str | None, log: str,
                 finding: dict | None = None, critic_pass: bool = False):
        self.run_id = run_id
        self.success = success
        self.bundle_dir = bundle_dir
        self.log = log
        self.finding = finding
        self.critic_pass = critic_pass

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "success": self.success,
            "bundle_dir": self.bundle_dir,
            "finding": self.finding,
            "critic_pass": self.critic_pass,
        }


def _load_questions() -> list[dict]:
    path = PROJECT_ROOT / "templates" / "questions.yaml"
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["questions"]


def _load_system_prompt() -> str:
    path = PROJECT_ROOT / "config" / "system_prompt.md"
    return path.read_text()


def _select_question(questions: list[dict], dataset_path: str) -> dict:
    """Pick a question template and fill in the dataset path."""
    import random
    q = random.choice(questions)
    q = dict(q)  # shallow copy
    q["text"] = q["text"].format(dataset_path=dataset_path)
    return q


def _build_analysis_prompt(system_prompt: str, question: dict) -> str:
    """Build the full prompt sent to the agent."""
    return (
        f"{question['text']}\n\n"
        "Write a complete Python script that performs this analysis. "
        "The script should:\n"
        "1. Read the dataset from the path given above\n"
        "2. Perform the statistical analysis\n"
        "3. Save post.md, plot.png, raw_results.csv, and reproduce.sh to the current directory\n"
        "4. Print a JSON summary to stdout as specified in the system prompt\n"
    )


def _run_critic(bundle_dir: Path, finding: dict | None) -> bool:
    """Run the self-critic checklist against the artifacts."""
    checklist_path = PROJECT_ROOT / "config" / "critic_checklist.md"
    if not checklist_path.exists():
        logger.warning("Critic checklist not found – skipping critic pass")
        return False

    required_files = ["post.md", "plot.png", "raw_results.csv", "reproduce.sh"]
    missing = [f for f in required_files if not (bundle_dir / f).exists()]
    if missing:
        logger.error("Critic FAIL: missing artifacts: %s", missing)
        return False

    if finding is None:
        logger.error("Critic FAIL: no finding JSON produced")
        return False

    if finding.get("status") != "success":
        logger.error("Critic FAIL: finding status is not 'success'")
        return False

    post_text = (bundle_dir / "post.md").read_text()
    if len(post_text.strip()) < 50:
        logger.error("Critic FAIL: post.md is too short")
        return False

    logger.info("Critic PASS: all basic checks passed")
    return True


def run(
    dataset_path: str | None = None,
    question_id: str | None = None,
    dry_run: bool = False,
    budget_path: str = "config/budget.yaml",
    use_docker: bool = False,
) -> RunResult:
    """Execute one full run of the Claw Engine.

    This is the main entry point.  The orchestrator MUST read the budget
    file before doing anything else.
    """
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    full_log_parts: list[str] = []

    def log(msg: str) -> None:
        logger.info(msg)
        full_log_parts.append(msg)

    # ── Step 0: Budget gate (MANDATORY) ──────────────────────────────
    log(f"[{run_id}] Loading budget from {budget_path}")
    try:
        budget = load_budget(budget_path)
    except (FileNotFoundError, ValueError) as e:
        log(f"[{run_id}] ABORT: {e}")
        return RunResult(run_id, False, None, "\n".join(full_log_parts))

    try:
        remaining = check_budget(budget)
    except (KillSwitchActive, BudgetExceeded) as e:
        log(f"[{run_id}] ABORT: {e}")
        return RunResult(run_id, False, None, "\n".join(full_log_parts))

    log(f"[{run_id}] Budget OK – ${remaining:.2f} remaining today")

    # ── Step 1: Select dataset ───────────────────────────────────────
    if dataset_path is None:
        from datasets.catalog import list_available
        available = list_available(local_only=True)
        if not available:
            log(f"[{run_id}] ABORT: no local datasets available")
            return RunResult(run_id, False, None, "\n".join(full_log_parts))
        entry = available[0]
        dataset_path = str(PROJECT_ROOT / entry.local_path)
        log(f"[{run_id}] Selected dataset: {entry.id} at {dataset_path}")
    else:
        log(f"[{run_id}] Using provided dataset: {dataset_path}")

    # ── Step 2: Select question ──────────────────────────────────────
    questions = _load_questions()
    if question_id:
        matching = [q for q in questions if q["id"] == question_id]
        if not matching:
            log(f"[{run_id}] ABORT: question '{question_id}' not found")
            return RunResult(run_id, False, None, "\n".join(full_log_parts))
        question = dict(matching[0])
        question["text"] = question["text"].format(dataset_path=dataset_path)
    else:
        question = _select_question(questions, dataset_path)
    log(f"[{run_id}] Question: {question['id']}")

    # ── Step 3: Generate analysis code via agent ─────────────────────
    system_prompt = _load_system_prompt()
    user_prompt = _build_analysis_prompt(system_prompt, question)

    agent_config = budget.to_agent_config()
    agent_config["dry_run"] = dry_run

    from agent.selector import select_backend
    backend = select_backend(agent_config, remaining)
    log(f"[{run_id}] Using backend: {backend.name}")

    try:
        analysis_code = backend.generate(system_prompt, user_prompt)
        log(f"[{run_id}] Agent generated {len(analysis_code)} chars of code")
    except Exception as e:
        log(f"[{run_id}] Agent error: {e}")
        if budget.fallback_enabled and backend.name != "ollama":
            log(f"[{run_id}] Trying fallback backend...")
            from agent.ollama_backend import OllamaBackend
            backend = OllamaBackend(agent_config)
            try:
                analysis_code = backend.generate(system_prompt, user_prompt)
                log(f"[{run_id}] Fallback generated {len(analysis_code)} chars")
            except Exception as e2:
                log(f"[{run_id}] Fallback also failed: {e2}")
                return RunResult(run_id, False, None, "\n".join(full_log_parts))
        else:
            return RunResult(run_id, False, None, "\n".join(full_log_parts))

    # ── Step 4: Run in sandbox ───────────────────────────────────────
    bundle_dir = Path("out") / f"bundle_{run_id}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    if use_docker:
        from sandbox.launcher import build_sandbox, run_sandbox, cleanup_sandbox
        log(f"[{run_id}] Building fresh sandbox...")
        allowlist = str(PROJECT_ROOT / "config" / "allowlist.txt")
        image_tag = build_sandbox(allowlist)
        log(f"[{run_id}] Sandbox image: {image_tag}")
        exit_code, run_output = run_sandbox(
            image_tag, analysis_code, dataset_path, str(bundle_dir)
        )
        cleanup_sandbox(image_tag)
    else:
        from sandbox.launcher import run_sandbox_local
        log(f"[{run_id}] Running locally (no Docker)...")
        exit_code, run_output = run_sandbox_local(
            analysis_code, dataset_path, str(bundle_dir)
        )

    log(f"[{run_id}] Sandbox exit code: {exit_code}")
    full_log_parts.append("--- SANDBOX OUTPUT ---")
    full_log_parts.append(run_output)

    # ── Step 5: Archive full stdout ──────────────────────────────────
    run_log_path = bundle_dir / "run_log.txt"
    run_log_path.write_text("\n".join(full_log_parts))

    # ── Step 6: Parse finding ────────────────────────────────────────
    finding = None
    for line in reversed(run_output.strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                finding = json.loads(line)
                break
            except json.JSONDecodeError:
                continue

    if finding:
        log(f"[{run_id}] Finding: {finding.get('finding', 'N/A')}")
    else:
        log(f"[{run_id}] WARNING: no JSON finding parsed from output")

    # ── Step 7: Self-critic ──────────────────────────────────────────
    critic_pass = _run_critic(bundle_dir, finding)
    log(f"[{run_id}] Critic pass: {critic_pass}")

    # ── Step 8: Record spend ─────────────────────────────────────────
    if not dry_run:
        cost = backend.estimate_cost(
            budget.max_input_tokens, budget.max_output_tokens
        )
        record_spend(cost)
        log(f"[{run_id}] Recorded spend: ${cost:.4f}")

    # ── Final: update run_log with all output ────────────────────────
    run_log_path.write_text("\n".join(full_log_parts))

    success = exit_code == 0 and critic_pass
    return RunResult(
        run_id=run_id,
        success=success,
        bundle_dir=str(bundle_dir),
        log="\n".join(full_log_parts),
        finding=finding,
        critic_pass=critic_pass,
    )
