.PHONY: demo test install clean

PYTHON ?= python3

# ── Install dependencies ────────────────────────────────────────────
install:
	pip install -e ".[dev]"

# ── Run the full demo (dry-run, local sandbox, local Discord) ───────
demo:
	@echo "═══════════════════════════════════════════════════════════"
	@echo "  Claw Engine – Demo Run (dry-run mode)"
	@echo "═══════════════════════════════════════════════════════════"
	$(PYTHON) run.py --dry-run --question diff_expr --verbose

# ── Run tests ───────────────────────────────────────────────────────
test:
	$(PYTHON) -m pytest tests/ -v --tb=short

# ── Clean up generated artifacts ────────────────────────────────────
clean:
	rm -rf out/bundle_*
	rm -f out/.spend_log.yaml
	@echo "Cleaned build artifacts."
