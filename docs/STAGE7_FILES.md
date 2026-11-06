# Stage 7 file inventory

Stage 7 continues from `8d366c6e91af521d8020655dad748792f09ef58e` on `codex/stage7-quality`.

- `backend/app/api/hybrid.py`, `backend/app/hybrid/engine.py`, `backend/app/agent/conversation.py` bind conversation state to the authenticated server session while preserving direct local deterministic requests.
- `backend/tests/test_workflows.py` adds real PostgreSQL completion, concurrency, lock timeout and connection interruption checks in disposable databases.
- `frontend/src/lib/server-session.ts` enforces the exact JSON media type. `frontend/src/lib/api.ts` explains expired Copilot context without inventing an answer.
- `frontend/src/components/analytics.tsx` and `charts.tsx` connect real financial comparison rows to supplier detail and add navigation between pages of supplier exposure.
- `frontend/tests/live.spec.ts`, `restart.accept.ts`, `recovery.accept.ts` and the Playwright configurations retain the previous browser tests and add session, finance, outage and lost-response cases. An output directory can be selected per stage.
- `scripts/audit_business_metrics.py`, `scripts/benchmark_local.py` provide reproducible SQL cross-checks and bounded Windows HTTP measurements. Existing validators accept isolated evidence output and baseline paths.
- `docs/STAGE7_REPORT.md`, `SECURITY_AUDIT.md`, `RELIABILITY_EVALUATION.md`, `PERFORMANCE_BENCHMARK.md`, `END_TO_END_ACCEPTANCE.md`, `VISUAL_QA_REPORT.md`, and `RELEASE_READINESS.md` record the measured scope and outcome.
- `reports/stage7-*` holds acceptance measurements and selected real browser evidence. Private passwords, bearer sessions, raw browser traces, model files and disposable database contents remain in ignored local storage or in the local runtime.
