# Stage 5 evaluation

Acceptance combines actual restricted-login PostgreSQL API tests, real Docker HTTP demonstrations, the complete retained regression suite and unchanged-source checks. No mocked successful executor or model response can establish acceptance.

Commands from repository root (PowerShell):

```powershell
$env:PYTHONPATH='backend;.'
.venv/Scripts/python.exe -m pytest backend/tests -q --junitxml=reports/stage5-pytest.xml
.venv/Scripts/ruff.exe check backend scripts
.venv/Scripts/ruff.exe format --check backend scripts
.venv/Scripts/python.exe -m alembic current
.venv/Scripts/python.exe -m alembic check
.venv/Scripts/python.exe -m scripts.validate_workflow --restart
.venv/Scripts/python.exe -m scripts.validate_agent --expected-migration 0004 --baseline .local-tools/stage5-baseline/stage3-baseline.json --output reports/stage5-regression.json --retrieval-output reports/stage5-retrieval.json
.venv/Scripts/python.exe -m scripts.evaluate_hybrid --mode DETERMINISTIC --output reports/stage5-deterministic-evaluation.json
```

Run restart acceptance after tests finish: they share the same project database container even though each suite uses separate disposable databases. The validator refuses to restart while test database sessions are active. It does not stop unrelated containers. Its only persisted live effects are documented demo workflow proposals/tasks/escalations/audits/sessions. It is not a read-only benchmark; reruns add new demo records. No reset/prune occurs.

The pre-migration backup and source baseline are ignored local artifacts under .local-tools/stage5-baseline. Business verification independently reloads original Base tables and registered source files, validates integrity/cross-domain scenarios and computes the accepted logical fingerprint. Workflow tables are a separate metadata scope and do not change that fingerprint. Knowledge index identity and embeddings are compared independently. New task/escalation totals never substitute for source counts.

Tests cover authentication, scopes, self-approval, immutability/revisions, exact hashes, expiry/revocation/policy changes, all actions/lifecycles, real evidence and forged references, direct database privileges/triggers, idempotency/replays, actual concurrent requests and real transaction failure/rollback. Controlled clocks are used only for approval expiry; successful action writes and failure-trigger rollbacks use actual PostgreSQL. Expiry cases also use real elapsed time. Demo reviews use distinct authenticated synthetic human accounts with explicit HTTP decisions, not a model approval.

Reports preserve actual first failures and final measurements. The first combined run revealed a readiness migration constant and was also interrupted by an early scoped restart; these are not counted as passing. Final acceptance must rerun the whole suite with no concurrent restart. Latency categories cover login, draft, detail/review, approve, execute, lists/audit and the measured workflow transaction wall time. The hardware/model resource admission policy is irrelevant to zero-inference Stage 5; Stage 4C LLM status remains separately BLOCKED.
