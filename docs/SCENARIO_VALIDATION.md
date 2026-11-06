# Cross-domain scenario verification

Run `uv run python -m scripts.manage verify` for integrity and five SQL evidence
traces, or `uv run python -m scripts.validate` for a saved report and timings.
Queries live in `backend/app/services/scenarios.py`. They join actual PostgreSQL
records; no scenario-name table or hardcoded answer endpoint is used.

| Case | Evidence in the default seed |
|---|---|
| A — procurement shortage | Supplier 1 → purchase order/line 1 → receipt 185 → stock movement 332 → shortage 16 → sales order/line 1 → dispatch 149 → incident 16 → task 16. Supplier promise 8 Oct 2025; receipt 20 Oct; customer promise 10 Oct; dispatch 20 Oct. Product 1 has no other supply, so the relationship supports the causal claim. |
| B — warehouse capacity | Midlands warehouse 1 → sales order 822 → escalated incident 1729 → overtime expense 104 (GBP 120) → task 1729. Dispatch occurs after the handling queue. The simulator checks stock availability when assigning this case. |
| C — supplier service terms | Contract/supplier 1 has a 95% on-time full-receipt target. Query finds 24 of 72 due orders on time (33.33%) at the cutoff. This is evidence for review, not an automatically assessed penalty. |
| D — finance review | Invoice 37 → purchase order 37 → line value GBP 9,028.43 versus invoice GBP 9,053.43 → open incident/task 1153. Explicit unsupported surcharge GBP 25; payment is held. |
| E — workload | Operations department 1 has 123 unfinished overdue corrective tasks across eight synthetic owners at the fixed cutoff, linked back to incident evidence. |

Tests independently assert A's exact quantities/dates and D's GBP 25 discrepancy.
Other cases assert grounded relationships, actual costs and below-target performance.
The generated JSON report contains exact IDs/counts and PostgreSQL EXPLAIN evidence.
Changing seed/configuration can change the selected query evidence; defaults above
describe only generator version 1.0 and seed 20251001.

These cases prepare later evaluation inputs; Stage 1 does not send answers to an
AI model, perform inference, or implement corrective execution/approval workflows.
