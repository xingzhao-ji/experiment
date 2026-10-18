"""Run artifacts must never be reused as evidence for a later analysis."""
from datetime import datetime
from pathlib import Path

from orchestrator import engine


def test_runs_in_same_second_keep_separate_artifacts(monkeypatch, tmp_path, budget_path, toy_dataset_path):
    class FrozenDatetime:
        @staticmethod
        def now():
            return datetime(2026, 10, 18, 12, 0, 0)

    class Backend:
        name = "offline-fixture"

        def generate(self, system_prompt, user_prompt):
            return "# fixture analysis"

    calls = 0

    def sandbox_run(script, dataset, output):
        nonlocal calls
        calls += 1
        if calls == 1:
            bundle = Path(output)
            (bundle / "post.md").write_text("Synthetic first-run finding. " * 4)
            for name in ["plot.png", "raw_results.csv", "reproduce.sh"]:
                (bundle / name).write_text("first-run artifact")
        return 0, '{"status":"success","finding":"fixture"}'

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(engine, "datetime", FrozenDatetime)
    monkeypatch.setattr("agent.selector.select_backend", lambda *args: Backend())
    monkeypatch.setattr("sandbox.launcher.run_sandbox_local", sandbox_run)
    arguments = dict(dry_run=True, dataset_path=toy_dataset_path,
                     question_id="diff_expr", budget_path=budget_path)
    first = engine.run(**arguments)
    second = engine.run(**arguments)

    assert first.success
    assert not second.success, "A run without artifacts must not inherit a previous critic pass"
    assert first.run_id != second.run_id
    assert first.bundle_dir != second.bundle_dir
    assert (Path(first.bundle_dir) / "post.md").read_text().startswith("Synthetic first-run")
    assert not (Path(second.bundle_dir) / "post.md").exists()
