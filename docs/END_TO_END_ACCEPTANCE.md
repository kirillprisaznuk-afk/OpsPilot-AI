# Stage 7 acceptance matrix

The production Compose application was tested in Microsoft Edge with the real PostgreSQL database. Workflow mutation and outage tests use synthetic acceptance records. Destructive fault injection uses separate disposable databases. The real browser execution transport test discards the response only after the genuine backend commits.

| Journey | Expected product behavior and authority | Authorization and failure evidence | Outcome |
|---|---|---|---|
| A. Overview, supplier, contract, investigation | Stage 2 analytics supplies the KPI and supplier figures. Open the registered supplier agreement and run the grounded SLA/policy comparison. | Authenticated analyst sees the actual supplier and four tool results. Observed SLA and contractual target stay distinct. | PASS |
| B. Historical procurement, warehouse, fulfilment | The same August selection survives navigation. Original purchase orders, warehouse stock and customer promises use their own source populations. | Read-only authenticated gateway. SQL agrees for August and the full window. Invalid or out-of-window dates return 422 and an empty denominator is undefined. | PASS |
| C. Finance, exposure, supplier | Open exact GBP segment values and follow the supplier record without losing the selected period. | Real finance report groups by supplier. Unattributed segments remain plain text. Outstanding amounts, payments and recorded costs remain separate. | PASS |
| D. Knowledge and verified citation | Search real corpus text, see the excerpt and resolve its citation and exact document version. | Registered provenance, effective date and content hash are verified by the knowledge backend. No result is a distinct state. | PASS |
| E. Copilot and supporting evidence | Rank suppliers, compare the first two with their actual contracts, inspect supporting evidence and reset the conversation. | Exact-session binding at browser and API boundaries. Another browser session and direct anonymous reuse are rejected. Output records zero LLM calls. | PASS |
| F. Investigation to task, receipt and audit | Run an investigation, prepare the suggested internal task, save, submit, approve separately and execute. | Distinct authenticated approver, stable digest and operation key. Browser sees unknown outcome when response is lost, reads the real committed receipt and replays without a duplicate. | PASS |
| G. Internal escalation | Create an evidence-bound internal escalation, then prepare, approve and execute a distinct closure proposal. | Versioned state and actual PostgreSQL effect. Rejected, expired and stale changes stay blocked. Revisions require new approval. | PASS |
| H. Unauthorized action | Viewer cannot execute, and the outsider receives the actual scope denial. | Real BFF and direct workflow endpoint checks. Forged actor, missing identity, CSRF and origin failures covered by actual and isolated tests. | PASS |
| Audit | Inspect real committed execution event and scoped pagination. | PostgreSQL rejects update/delete of historical audit rows. Retry, failure and successful completion are separately attributed. | PASS |
| Responsive and accessibility | Main views load and workflow can be reviewed via keyboard. | No page-wide overflow at 1440, 1280, 1024, 768 or 390 px. Axe and keyboard test scope are described in the visual review. | PASS |
| Model interpretation | Optional local Qwen when resource admission and independent model quality pass. | Verified Intelligence has no model dependency. The current model could not be safely admitted. | BLOCKED |

The [browser evidence](../reports/stage7-browser.json) records exact test names and timings, operation and receipt IDs, the restart and recovery observations, and screenshot names. The [SQL cross-check](../reports/stage7-business-metrics.json) and [test results](../reports/stage7-backend-pytest.xml) provide separate evidence for the business and database boundaries.

Run these commands from the repository root after the normal local setup. The legacy runtime validator uses the accepted pre-frontend source and Docker reference, with Stage 7 preservation checked against its own fresh baseline.

```powershell
$env:PYTHONPATH = 'backend;.'
$env:OPSPILOT_BROWSER_EVIDENCE_DIR = '../.local-tools/stage7-browser'
./scripts/start_frontend.ps1 -Build -Open
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/python.exe -m alembic current
.venv/Scripts/python.exe -m alembic check
pnpm --dir frontend typecheck
pnpm --dir frontend lint
pnpm --dir frontend test
pnpm --dir frontend exec playwright test
.venv/Scripts/python.exe -m scripts.audit_business_metrics --output reports/stage7-business-metrics.json
.venv/Scripts/python.exe -m scripts.validate_analytics --live-url http://127.0.0.1:8001 --output .local-tools/stage7-analytics.json
.venv/Scripts/python.exe -m scripts.validate_agent --expected-migration 0004 --baseline .local-tools/stage6-baseline/legacy-validator.json --output .local-tools/stage7-prior-regression.json --retrieval-output reports/stage7-retrieval.json
.venv/Scripts/python.exe -m scripts.evaluate_hybrid --mode DETERMINISTIC --output .local-tools/stage7-deterministic.json
```
