"""Render the centrally registered metric contracts into inspectable Markdown."""

from pathlib import Path

from app.analytics.registry import REGISTRY


def main():
    lines = [
        "# Metric registry\n",
        "Percentages use **0–100**. Money is exact **GBP net of VAT**.\n",
        "Every metric below inherits these defaults unless its definition narrows the scope:\n",
        "- Inclusion: persisted synthetic records visible by UTC end of as_of.\n",
        "- Exclusion: future events and records outside the metric's population.\n",
        "- Empty behavior: additive metrics are zero; empty averages and ratios are null.\n",
        (
            "- Limitations: no unrecorded losses, capacity denominators, employee "
            "scores or legal findings.\n"
        ),
        (
            "- Entity labels and assignment dimensions have no revision history; "
            "historical reassignment is unavailable.\n"
        ),
        "\nOrder promises mature at UTC end of their promised date. "
        "Full completion requires every original line. "
        "Product filters select line values/units but never redefine "
        "full-order service completion. "
        "Incidence flows and all-history snapshot prevalence are labelled separately.\n",
        "\nInvoice exposure and payments must not be added as two costs. "
        "Shortage units are remaining sales demand, not the initial missing-quantity snapshot. "
        "Reservations and carrier arrival are unavailable.\n",
    ]
    domain = None
    for definition in REGISTRY.values():
        current = definition.name.split(".")[0]
        if domain != current:
            domain = current
            lines += [
                f"\n## {domain.title()}\n",
                "| Metric | Unit | Definition | Numerator / denominator | Time basis | Grain |\n",
                "|---|---|---|---|---|---|\n",
            ]
        ratio = (
            f"{definition.numerator} / {definition.denominator}"
            if definition.denominator
            else "Not a ratio"
        )
        lines.append(
            f"| `{definition.name}` | {definition.unit} | {definition.definition} | "
            f"{ratio} | {definition.time_basis} | {definition.grain} |\n"
        )
    lines += [
        "\n## Comparisons and limitations\n",
        "Previous periods have the same number of calendar days and "
        "the same post-period observation lag. "
        "A previous window crossing 1 October 2025 is unavailable, not shortened. "
        "Relative change is null at a zero baseline; absolute change remains available. "
        "Rate differences additionally report percentage points.\n",
        "\nEarlier escalation counts are unavailable because "
        "incident status history does not exist. "
        "Task state uses the latest history entry before the exclusive next-day UTC cutoff. "
        "Missing task history makes open/overdue results unavailable, "
        "never inferred from final status.\n",
        "\nMonthly order trends use the report's as_of for outcomes "
        "and disclose mature denominators. "
        "Inventory trend snapshots use each month's end. "
        "The selected current period can be partial; "
        "comparisons preserve its actual length. A below-target supplier result is an operational "
        "concern, not a legally established contract violation.\n",
    ]
    Path("docs/METRICS.md").write_text("".join(lines), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
