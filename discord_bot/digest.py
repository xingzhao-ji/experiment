"""Format run results into a Discord-ready digest message."""

from __future__ import annotations

from pathlib import Path


def format_digest(run_result) -> str:
    """Create a digest message from a RunResult."""
    lines = [
        f"**Claw Engine Run Report** – `{run_result.run_id}`",
        "",
    ]

    if run_result.success:
        lines.append(":white_check_mark: **Status: SUCCESS**")
    else:
        lines.append(":x: **Status: FAILED**")

    if run_result.finding:
        f = run_result.finding
        lines.extend([
            "",
            f"**Finding:** {f.get('finding', 'N/A')}",
            f"**Dataset:** {f.get('dataset', 'N/A')}",
            f"**Test:** {f.get('test_used', 'N/A')}",
            f"**p-value:** {f.get('p_value', 'N/A')}",
            f"**Effect size:** {f.get('effect_size', 'N/A')}",
        ])

    lines.extend([
        "",
        f"**Critic pass:** {'Yes' if run_result.critic_pass else 'No'}",
    ])

    if run_result.bundle_dir:
        lines.append(f"**Bundle:** `{run_result.bundle_dir}`")

    return "\n".join(lines)


def format_digest_embed(run_result) -> dict:
    """Create a Discord embed dict from a RunResult."""
    color = 0x2ECC71 if run_result.success else 0xE74C3C

    fields = []
    if run_result.finding:
        f = run_result.finding
        fields.extend([
            {"name": "Finding", "value": f.get("finding", "N/A"), "inline": False},
            {"name": "Dataset", "value": f.get("dataset", "N/A"), "inline": True},
            {"name": "Test", "value": f.get("test_used", "N/A"), "inline": True},
            {"name": "p-value", "value": str(f.get("p_value", "N/A")), "inline": True},
            {"name": "Effect size", "value": str(f.get("effect_size", "N/A")), "inline": True},
        ])

    fields.append(
        {"name": "Critic", "value": "PASS" if run_result.critic_pass else "FAIL", "inline": True}
    )

    return {
        "title": f"Claw Run {run_result.run_id}",
        "description": "Automated re-analysis result",
        "color": color,
        "fields": fields,
    }
