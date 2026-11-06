# Agent evaluation and current acceptance state

The corpus/analytics retrieval benchmark is not an agent-answer benchmark. Stage 4
separates three kinds of evidence rather than reporting a single AI accuracy score.

## Offline orchestration and SDK tests

Deterministic providers in tests exercise multi-round selection/result submission,
structured final parsing, current-run evidence, exact numeric projection, citations,
entity ambiguity stops, follow-ups/date inheritance, retries, deadlines, cancellation,
limits, source injection and provider configuration failures. A MockTransport drives
the actual official OpenAI SDK to validate Responses wire fields, function calls,
encrypted output replay, structured output and sanitized HTTP errors. These are
explicit test doubles, not live inference or measured model tool-selection quality.

Real PostgreSQL tests use UUID-isolated databases, the actual SQL services and the
restricted role. Knowledge tests use real MiniLM/pgvector and registered temporary
Markdown for attacks, restoring fixture registrations afterward. Ordinary tests
never incur paid calls or mutate the demo corpus/business records.

## Curated evaluation set and offline tool results

`data/evaluation/agent.json` has **30 cases**, including all eight requested scenarios,
supplier/contract/policy synthesis, finance, inventory, warehouse, task/incidents,
historical scope, ambiguous/unknown entities, unsupported metrics, no-answer,
cross-document evidence and negative tool/schema attempts. Plans/known labels are
evaluation fixtures, never a production dispatcher for matching questions.

`uv run python -m scripts.evaluate_agent --offline` executes those declared plans
through the real read-only gateway, checks schemas/errors, exact previously accepted
numbers and required document codes, and records actual tool durations. These checks
passed. Known assertions include supplier on-time 33.33%, target 95.00%, inventory
99,213 units and Operations overdue workload 123. Cases requiring a final model
answer remain unscored offline. A scripted/requested plan succeeding does not prove
that a model would select it or explain it correctly.

## Live local evaluation

The default provider is local Ollama with Qwen3.5 4B Q4_K_M and 32K context,
without keys or cloud. Qwen3 4B Thinking/Instruct trials remain historical failure
evidence. Current runs are `stage4-local-live-evaluation.json` and
`stage4-local-multi-tool.json`; measured hardware is `stage4-local-final-hardware.json`.

```powershell
uv run python -m scripts.evaluate_agent --live --limit 1 --output reports/local-critical.json
uv run python -m scripts.evaluate_agent --live --cases A01,A02,A03,A06,A22,A23,A25,A27 --output reports/local-cases.json
```

Live reports include successful native tool selection, strict argument outcomes,
actual PostgreSQL evidence, required retrieved/cited document codes, exact known
numeric evidence and separately checked selected final metric references, citation
resolution, final status, actual usage and latency.
These indicators do not prove complete semantic correctness. Review the actual
findings and quotations: below-target performance is not automatic legal breach,
recorded costs differ from inferred losses, and unsupported calculations remain
unavailable. Cases with invalid output, fabricated references, truncation or exhausted
budgets fail explicitly. Offline plans/test transports never count as live successes.
The Stage 4 report records the final observed results and remaining limitations.

## Regression, performance and artifacts

The full regression includes the accepted **182 Stage 1–3 cases** plus agent tests.
Exact executed counts are in `reports/stage4-local-pytest.xml` and the Stage 4 report.
`scripts.validate_agent --restart` compares the independently recalculated business
fingerprint, all ten complete analytics responses, 44 documents/chunks, every citation,
the prior retrieval evaluation and index persistence after restarting only OpsPilot
db/api. It verifies provider status and the tool registry without invoking inference.

Offline tool timings are in `reports/stage4-offline-evaluation.json`; live-gate state
is in `reports/stage4-live-evaluation.json`; prior retrieval measurements are in
`reports/stage4-retrieval-regression.json`; runtime preservation evidence is in
`reports/stage4-validation.json`. They do not overwrite accepted Stage 1–3 artifacts.
Actual local usage and latency are measured in the local reports. Semantic accuracy
requires reviewing findings and source coverage; completed status alone is insufficient.

**Stage 4 cannot be declared complete; READY FOR STAGE 5: NO** until the real
multi-tool LLM acceptance gate succeeds and its actual trace/usage/evidence are reviewed.

The recorded offline tool-plan durations (nonempty plans only) had a median of 85.674 ms and maximum 1261.069 ms. These include real SQL/retrieval and cold local-model work where applicable; they are not LLM latency measurements.

Final numeric selection checks compare the actual selected reference, value and
supporting tool evidence. A01 explicitly accepts the supplier-detail top-level and
single-supplier breakdown paths for the same rate/target; merely retrieving correct
numbers does not pass a final-answer check. These assertions do not score semantic
entailment or entity substitution. Historical report schemas predate this check.

## Stage 4B independent matrix

`scripts.evaluate_reliability` combines the original eight critical cases with fifteen
unseen questions in `data/evaluation/agent_reliability.json`. SQL/RAG oracle plans
and expected results never enter production model code. Checks compare exact windows,
selected metric values/subjects, ranking, sources/citations and zero-inference refusal.
Human review of actual findings/quotations is still required. The follow-up is blocked
unless its preceding ranking independently verifies. Each case is saved immediately.

```powershell
$env:PYTHONPATH = 'backend;.'
uv run python -m scripts.evaluate_reliability --prepare-only --output reports/stage4b-oracles.json
uv run python -m scripts.evaluate_reliability --check-resources --output reports/stage4b-resource-check.json
uv run python -m scripts.evaluate_reliability --output reports/stage4b-live-evaluation.json
```

All 23 oracle plans prepared; final 23 model cases are memory-blocked, NOT_RUN.
These oracles are not inference. Intermediate actual model runs, including failures,
are separate artifacts. The 348-test suite adds 48 reliability checks; see the
[Stage 4B report](STAGE4B_REPORT.md) for actual coverage and remaining gates.

## Autonomous live evidence

The later 2026-11-03 runs did execute real local tools and model requests. See the
opening section of [STAGE4B_REPORT.md](STAGE4B_REPORT.md) and
`reports/stage4b-autonomous-semantic-review.json`. The 8K matrix issued 22 API
attempts (18 structured responses, four transport/HTTP errors, B15 blocked). The
32K matrix returned 16 structured responses, then later cases were NOT_RUN after
memory protection. These are not final 23/23 passes. B15 cannot be credited without
an independently verified ranking. Accepted model-output citations total zero,
so answer citation accuracy is N/A; 44 backend citation resolutions passed separately.

`--prepared-oracles` avoids a second embedding session during live inference,
records the oracle report SHA and requires the unchanged verified dataset/corpus.
Without it, oracle work runs in a short-lived process. `evaluate_monitored` samples
Windows RAM/commit/paging and stops only the verified project Ollama tree when the
emergency reserve fails. No lower resident admission is retained after failed
experiments. Full regression now has 352 passes; live Stage 4B acceptance is NO.
