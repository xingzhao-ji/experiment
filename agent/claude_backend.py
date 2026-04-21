"""Claude (Anthropic) backend for the Claw Engine agent."""

from __future__ import annotations

import json
import os

from agent.base import ModelBackend

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

# Default model to use for API calls.
DEFAULT_MODEL = "claude-sonnet-4-5-20250514"

# Pricing per million tokens (USD).
_INPUT_PRICE_PER_M = 3.0
_OUTPUT_PRICE_PER_M = 15.0

# Complete analysis script returned in dry-run mode.  This is a real Python
# script that reads the toy dataset, performs a t-test on gene_A, and
# produces all required artifacts so the full pipeline can be exercised
# without calling any external API.
_DRY_RUN_SCRIPT = '''\
import json, os, sys
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

data_dir = os.environ.get("SANDBOX_DATA_DIR", ".")
out_dir = os.environ.get("SANDBOX_OUTPUT_DIR", ".")

# SANDBOX_DATA_DIR may be a file path or a directory.
if os.path.isfile(data_dir):
    csv_path = data_dir
elif os.path.isfile(os.path.join(data_dir, "toy_expression.csv")):
    csv_path = os.path.join(data_dir, "toy_expression.csv")
else:
    # Check working directory as fallback
    for candidate in ["toy_expression.csv", "data/toy_expression.csv"]:
        if os.path.isfile(candidate):
            csv_path = candidate
            break
    else:
        print("ERROR: could not locate dataset CSV", file=sys.stderr)
        sys.exit(1)

df = pd.read_csv(csv_path)
control = df[df["group"] == "control"]["gene_A"]
treatment = df[df["group"] == "treatment"]["gene_A"]
stat, p = stats.ttest_ind(control, treatment, equal_var=False)
effect = (treatment.mean() - control.mean()) / df["gene_A"].std()

# post.md
post = f"""# Differential Expression of gene_A

gene_A is significantly differentially expressed between control
(mean={control.mean():.2f}) and treatment (mean={treatment.mean():.2f})
groups (Welch t-test, t={stat:.3f}, p={p:.2e}, Cohen d={effect:.2f}).

**Limitations:** This is a toy dataset for demo purposes.
"""
with open(os.path.join(out_dir, "post.md"), "w") as f:
    f.write(post)

# plot.png
fig, ax = plt.subplots(figsize=(6, 4))
ax.boxplot([control, treatment], labels=["Control", "Treatment"])
ax.set_ylabel("Expression level")
ax.set_title("gene_A expression by group")
fig.tight_layout()
fig.savefig(os.path.join(out_dir, "plot.png"), dpi=100)
plt.close(fig)

# raw_results.csv
res = pd.DataFrame({
    "gene": ["gene_A"],
    "control_mean": [control.mean()],
    "treatment_mean": [treatment.mean()],
    "t_statistic": [stat],
    "p_value": [p],
    "cohens_d": [effect],
})
res.to_csv(os.path.join(out_dir, "raw_results.csv"), index=False)

# reproduce.sh
with open(os.path.join(out_dir, "reproduce.sh"), "w") as f:
    f.write("#!/usr/bin/env bash\\nset -e\\npython3 analysis.py\\n")
os.chmod(os.path.join(out_dir, "reproduce.sh"), 0o755)

# JSON summary to stdout
print(json.dumps({
    "finding": f"gene_A is differentially expressed (p={p:.2e}, d={effect:.2f})",
    "p_value": round(p, 6),
    "effect_size": round(effect, 4),
    "test_used": "Welch t-test",
    "dataset": "toy_expression",
    "status": "success",
}))
'''


class ClaudeBackend(ModelBackend):
    """Anthropic Claude backend."""

    def __init__(self, config: dict) -> None:
        super().__init__(config)

        if anthropic is None:
            raise RuntimeError(
                "The 'anthropic' package is not installed. "
                "Install it with:  pip install anthropic"
            )

        self._model: str = config.get("model", DEFAULT_MODEL)
        self._dry_run: bool = config.get("dry_run", False)
        self._max_output_tokens: int = config.get("max_output_tokens", 8000)

        if not self._dry_run:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY environment variable is not set. "
                    "Export it before running the agent:  "
                    "export ANTHROPIC_API_KEY='sk-ant-...'"
                )
            self._client = anthropic.Anthropic(api_key=api_key)
        else:
            self._client = None

    # ------------------------------------------------------------------
    # ModelBackend interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "claude"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if self._dry_run:
            return _DRY_RUN_SCRIPT

        assert self._client is not None
        message = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_output_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
        )
        # The API returns a list of content blocks; concatenate all text blocks.
        return "".join(
            block.text for block in message.content if block.type == "text"
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_cost = (input_tokens / 1_000_000) * _INPUT_PRICE_PER_M
        output_cost = (output_tokens / 1_000_000) * _OUTPUT_PRICE_PER_M
        return input_cost + output_cost
