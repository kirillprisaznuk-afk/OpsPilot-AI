# Hybrid evaluation methodology

`scripts.evaluate_hybrid` sends only the actual question, mode, cutoff and verified
conversation ID to the running Docker API. Expected facts, case IDs and oracle
plans stay in evaluation code/data. It runs sequentially and preserves complete
responses, trace, findings, graph, citations, usage, HTTP timings and sampled host
resources. API readiness precedes measured requests. Existing Stage 4B SQL/RAG
oracle artifacts remain valid against the preserved accepted fingerprint; the
additional cases execute independent oracle tool queries in isolated processes.

The suite contains the original eight cases, all fifteen Stage 4B unseen cases,
and fifteen additional cases in `data/evaluation/hybrid.json`. The latter cover
supplier/contract identity, a critical impact investigation, different metric/date
rankings, invoice/employee/product scope, two-warehouse/two-supplier comparisons,
clarification and absent entities. Evaluation fixtures are never imported by
production modules.

Automatic checks inspect original expectations, source identity, real complete
rankings, required entity/tool selection, exact scoped oracle metrics, every graph
fact's verification, statuses and budgets. Independent oracle matching preserves
outer detail IDs instead of allowing a nested null filter to overwrite them.
Acceptance also requires reading actual prose, numerical denominators, full source
qualifications, refusals, customer/supplier distinctions and causal/legal limits;
completion status alone is not correctness.

Report each gate separately: deterministic capabilities, real local language
interpretation, experimental legacy, security, preservation and performance. Hybrid
HTTP fallback success is not a real-model pass. Zero calls/tokens mean no model
ran; missing provider counts remain unknown, with incomplete usage explicitly set.
Mocked semantic frames are negative unit tests only and never live acceptance.

Reproduction (existing configured Windows environment):

```powershell
$env:PYTHONPATH = 'backend;.'
uv run python -m scripts.evaluate_hybrid --output reports/stage4c-deterministic-evaluation.json
# Start the guarded local runtime as described in LOCAL_HYBRID_PERFORMANCE.md first.
uv run python -m scripts.evaluate_hybrid --mode HYBRID_LOCAL --output reports/stage4c-hybrid-evaluation.json
uv run pytest -q --basetemp .local-tools/pytest-stage4c-review --junitxml reports/stage4c-pytest.xml
uv run ruff check .
uv run ruff format --check .
```

Use a new ignored pytest temporary directory if the Windows global pytest directory
has restricted permissions. No integration test is skipped to bypass PostgreSQL.
Actual outcomes, encountered failures and their fixes are in STAGE4C_REPORT.md;
measured comparisons are in LOCAL_HYBRID_PERFORMANCE.md.
