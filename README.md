# Claw Engine MVP

Nightly research agent that re-analyzes public datasets and reports one testable finding per run.

## Architecture

```
orchestrator/   – nightly run loop, budget enforcement
agent/          – swappable model backend (Claude Sonnet 4.5 / Ollama qwen3:32b)
sandbox/        – Dockerfile + launcher, rebuilt fresh every run
datasets/       – catalog, download helpers, bundled toy data
templates/      – question templates (YAML)
config/         – budget.yaml, allowlist.txt, system_prompt.md, critic_checklist.md
discord_bot/    – digest posting, publish/kill/rerun buttons
out/            – artifact bundles and published results
tests/          – dry-run harness, budget tests
```

## Setup

**Requirements:** Python 3.12+, pip

```bash
# Clone and install
pip install -e ".[dev]"
```

**Optional (for production mode):**
- Docker (for sandboxed execution)
- Anthropic API key: `export ANTHROPIC_API_KEY=sk-ant-...`
- Discord bot token: `export DISCORD_BOT_TOKEN=...` and `export DISCORD_CHANNEL_ID=...`
- Ollama running locally with `qwen3:32b` pulled

## Quick Start

### Run the demo (no API keys needed)

```bash
make demo
```

This runs one full cycle in dry-run mode:
1. Loads and checks `config/budget.yaml`
2. Selects the toy expression dataset
3. Generates an analysis script (dry-run: uses a bundled script)
4. Executes in local sandbox (subprocess)
5. Runs self-critic checklist
6. Produces artifact bundle in `out/bundle_<timestamp>/`
7. Posts digest to stdout (local Discord test mode)
8. Simulates publish gate

### Run tests

```bash
make test
```

### Run with real API

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python run.py --question diff_expr --verbose
```

### Run with Docker sandbox

```bash
python run.py --dry-run --docker --question diff_expr
```

## Configuration

### config/budget.yaml

Controls spending limits and the kill switch. **The orchestrator will not run without this file.**

| Key | Description |
|-----|-------------|
| `daily_budget_usd` | Hard cap per nightly run |
| `monthly_budget_usd` | Hard cap per calendar month |
| `max_input_tokens` | Token limit for agent input |
| `max_output_tokens` | Token limit for agent output |
| `fallback_enabled` | Try Ollama if Claude exceeds budget |
| `kill_switch` | Set to `true` to halt all runs |

### config/allowlist.txt

Python packages allowed inside the sandbox. One per line.

### config/system_prompt.md

The system prompt sent to the agent. Defines rules for analysis quality, reproducibility, and artifact format.

### config/critic_checklist.md

Self-critic checklist run after every analysis. Covers statistical rigour, reproducibility, data integrity, claim quality, and artifact completeness.

## Artifact Bundle

Each run produces a bundle in `out/bundle_<timestamp>/`:

| File | Description |
|------|-------------|
| `post.md` | Short write-up of the finding |
| `plot.png` | Publication-quality figure |
| `raw_results.csv` | Numerical results behind the claim |
| `run_log.txt` | Full stdout/stderr archive |
| `reproduce.sh` | Script to regenerate results |

## Discord Integration

### Local test mode (default)

Prints the digest to stdout and simulates the publish gate. No credentials needed.

### Production mode

Set `DISCORD_BOT_TOKEN` and `DISCORD_CHANNEL_ID` environment variables. The bot posts an embed with three buttons:

- **Publish** – moves the bundle to `out/published/` (explicit human approval required)
- **Kill** – marks the run as killed, bundle is not published
- **Rerun** – requests the next nightly cycle to re-process the dataset

**There is no auto-publish. A human must click Publish.**

## Limitations

- GEO and GTEx dataset downloads are stubbed (only the toy dataset works locally)
- The Discord bot in local mode simulates a publish click automatically for testing; in production it waits for a real button press
- Sandbox mode requires Docker to be installed and running
- The critic pass checks basic artifact presence and finding validity, not deep statistical review
