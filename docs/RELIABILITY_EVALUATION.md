# Stage 7 reliability evaluation

The audit ranked cross-scope access, unsafe approval or execution, partial database commits, and source corruption ahead of view correctness, accessibility, startup, and performance. Tests reused the running OpsPilot stack for non-destructive reads and synthetic workflow actions. Database faults targeted disposable databases. Docker commands selected only the OpsPilot Compose services.

| Failure | Injection and verified outcome |
|---|---|
| Receipt update fails | A real PostgreSQL trigger rejects completion. The savepoint rolls back the task and success events, and a failed receipt records the outcome. |
| Success audit insert fails | A separate trigger rejects the completion event. Task and success events roll back together. |
| Commit fails | A deferred PostgreSQL trigger fails at transaction commit. No task, receipt or idempotency record survives. The approved proposal accepts the same key after the fault is removed. |
| Database lock timeout | A held advisory lock delays the task insert. The failed receipt is stable on retry. A new HTTP correlation ID still identifies each attempt. |
| Database connection loss during execution | A separate connection identifies and terminates only the waiting backend in the disposable database. The API returns a sanitized error, nothing is committed, and the same key succeeds after recovery. |
| Two approvals race | Two independently authorized reviewers race. One decision is stored and the accepted proposal executes. |
| Six executions race | Same-key and different-key PostgreSQL tests each produce one task, one receipt and one completion event. |
| Browser loses an execution response | The route sends the real request and discards the response only after the backend confirms commit. The UI reports an unknown outcome, reads the authoritative receipt, and verifies the same receipt with the same operation key. |
| Stale and revoked authority | The original Stage 5 and new browser coverage enforce session and approval expiry, role change, target version and policy revision. Old approval does not carry to a new proposal. |

The browser also separately exercises a scoped restart and temporary API and database outages. During an API outage, an established Copilot result and the typed follow-up remain visible. Its ephemeral server context disappears on API restart. OpsPilot directs the user to start a new conversation, while persisted authentication, tasks and knowledge remain available after recovery. The fault run checks that PostgreSQL-dependent endpoints fail visibly while the database is stopped and that the same signed-in session works when it is back.

Run from the repository root in PowerShell. Start the outage tests only after disposable PostgreSQL tests finish.

```powershell
$env:PYTHONPATH = 'backend;.'
$env:OPSPILOT_BROWSER_EVIDENCE_DIR = '../.local-tools/stage7-browser'
.venv/Scripts/python.exe -m pytest backend/tests -q --basetemp .local-tools/pytest-stage7-final --junitxml=reports/stage7-backend-pytest.xml
pnpm --dir frontend exec playwright test
pnpm --dir frontend exec playwright test --config playwright.restart.config.ts
.venv/Scripts/python.exe -m scripts.validate_frontend --baseline .local-tools/stage7-baseline --output reports/stage7-preservation.json
```

Take a fresh preservation baseline with the same validator and `--capture` before a future change. It refuses to overwrite an existing baseline. The verifier compares the accepted source fingerprint, knowledge index, preexisting auth/workflow/audit row digests, and Docker resource state.
