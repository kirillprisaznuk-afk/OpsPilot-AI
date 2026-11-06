# OpsPilot AI Stage 7 quality and release audit

## Stage 7 implementation status

Stage 7 hardened the existing Next.js and FastAPI application, added failure coverage, and independently checked the local portfolio deployment against its real data. It introduced no migration, new workflow action or model dependency.

## Initial project health

The Stage 6 checkpoint had a clean working tree. Compose reported healthy PostgreSQL, API and frontend services. The real sign-in document returned 200. The starting preservation snapshot recorded the original business data, knowledge index, existing workflow/auth/audit row digests and ten unrelated Docker containers.

## Login credential handoff confirmation

The login form requires **Username**. Edge verified `stage5.operator` and the distinct `stage5.reviewer`, both scoped to department 1. It also verified `stage5.analyst`, `stage5.viewer` and `stage5.admin`. The two requested passwords were delivered through a private ignored local file. Existing identities and passwords were used.

## Exact starting checkpoint

`8d366c6e91af521d8020655dad748792f09ef58e`, the accepted Stage 6 closure. The local Stage 7 branch is `codex/stage7-quality`.

## Security threat model

Tested actors include anonymous clients, users with the wrong department or role, an expired or revoked session, an intercepted conversation reference and an authorized client retrying after a lost response. The accepted boundary is a synthetic Windows loopback deployment. Host ownership and service credentials remain trusted. [Security audit](SECURITY_AUDIT.md)

## Authentication audit

Real sign-in and logout succeeded for five distinct role-bearing users. The retained tests exercise unknown identity, wrong password, a disabled or non-human principal, and persistent failed-login throttling. No password was rotated or copied to tracked evidence.

## Session security

The frontend retains an opaque httpOnly, SameSite Strict host cookie and encrypts the backend bearer in the scoped session volume. The HTTPS Secure configuration was inspected in source, with browser verification performed over the documented loopback HTTP origin. Revocation, expiry, separate browser contexts, refresh and restart were exercised.

## Role-based access control

The backend denied viewer execution, wrong-department reads, forged identity and self-approval. Approval and scoped read tests use actual credentials and the restricted database login. Current membership is evaluated before replay, including after role changes.

## Frontend gateway security

The actual gateway refused missing credentials, revoked sessions, forged origin, missing CSRF, incompatible media type, a provider-mode request, arbitrary agent forwarding and a handle from another browser session. The direct API also refuses anonymous reuse of an owned conversation. Gateway success responses preserve their documented typed contracts.

## Approval security

Submission, rejection, cancellation, revocation, expiry, stale target and policy change are separate states. Approvals bind one authorized distinct person to the exact version and digest. Simultaneous eligible approvals produced one recorded decision. A revision required a new approval.

## Workflow transactions

Receipt and success-audit insert faults rolled back task changes. A deferred commit failure rolled back task, receipt and idempotency state. PostgreSQL lock timeout preserved a failed receipt. Terminating one waiting connection in a disposable database produced a sanitized 503 and allowed a safe retry of the same approved proposal. [Reliability evaluation](RELIABILITY_EVALUATION.md)

## Idempotency and concurrency

Same-key and different-key races each yielded one task, one receipt and one completion event. The real browser lost the first committed response, then read the authoritative receipt and retried with the same operation key. The replay returned the same receipt and one task remained.

## Audit integrity

The audit database tests cover attribution and ordering, immutable rows, completion/failure/replay events and scope-filtered reads. The browser followed the real task and audit links. The database owner remains within the documented trust boundary.

## Business data accuracy

Independent SQL matched two live reporting windows and six business domains. Full-period results included 1,678 on-time of 2,400 due purchase orders (69.92%), 708 late completed orders, £141,686.31 open procurement commitment, 99,213 units in stock and 543 outstanding customer units. Invoices totalled £25,910,489.78, with £22,849,059.09 paid and £3,061,430.69 outstanding. Recorded operating expenses were £244,555 and open historical tasks and incidents each numbered 175. Scoped workforce checks matched department and employee SQL. [Independent SQL evidence](../reports/stage7-business-metrics.json)

## Historical date handling

The UI retained the August scope across procurement, inventory, fulfilment, finance and supplier detail. A separate quarter selection changed the dashboard values to the authoritative API result. API validation rejected three invalid, reversed or out-of-window dates. An empty purchase-order population had zero orders and an undefined rate. Current workflow dates stay separate from original historical KPI scope.

## RAG and document citations

The 42-query retrieval regression matched the accepted quality metrics in keyword, vector and hybrid modes. Hybrid recall@3 was 94.29%. Citation resolution was 100% in each mode and all 44 registered citations resolved. The separate semantic review checked five citation uses against the actual agreement, procurement procedure and incident procedure. [Retrieval evaluation](../reports/stage7-retrieval.json) · [Source review](../reports/stage7-source-review.json)

## Deterministic intelligence

The live evaluator passed **38/38** automatic oracle checks, with 26 completed and three each of partial, clarification required, insufficient evidence and refused. Median direct HTTP latency was 91.1 ms, with a maximum of 1,517.5 ms. A representative review of 12 cases checked numerical grounding, operational versus legal conclusions, absence of policy, recorded costs versus unrecorded losses, customer versus supplier terms, and unsupported actions. [Evaluation](../reports/stage7-deterministic-summary.json) · [Semantic review](../reports/stage7-source-review.json)

## Local LLM status

**BLOCKED** for live inference. The final resource check measured 1.707 GiB available RAM and 27.09 GiB free commit. The local Ollama API was unavailable and the existing admission policy refused to load a model. One real hybrid fallback completed the supplier, agreement and policy question with four read-only tool calls, two citations, zero model calls and zero model request bytes. No paid key was set in the deployed API. [Model boundary evidence](../reports/stage7-local-model-boundary.json)

## Frontend functionality

Financial comparison now links actual supplier exposure rows to the underlying supplier in the same period and allows paging through the population. Knowledge, inspections, workflow creation, approvals, audit, account and system routes loaded real records or explicit empty states.

## Frontend design review

The rendered dashboard, supplier, procurement, fulfilment, finance, knowledge, investigations, Copilot, approval, receipt, governance and outage views were inspected. The existing design was retained. [Visual QA](VISUAL_QA_REPORT.md)

## Accessibility

Axe found zero violations in the loaded desktop dashboard, loaded mobile task list and loaded desktop admin settings. Keyboard approval entered the dialog, confirmed with Space and Enter, and left the modal. The scope of the automated scans is limited to those views.

## Responsiveness

Measured page width was within the viewport at 1440, 1280, 1024, 768 and 390 px. Mobile navigation and the loaded task list were exercised. Dense tables use an internal scroll region.

## End-to-end browser journeys

Eight acceptance tests and two restart/fault tests passed in real Edge. They cover the supplier agreement, historical operations, finance, knowledge, Copilot, governed tasks, escalation and access denials. [Acceptance matrix](END_TO_END_ACCEPTANCE.md)

## Fault injection

The real browser observed temporary API and PostgreSQL outages. Database trigger, lock, commit and connection faults used disposable PostgreSQL. The browser's lost-response exercise forwarded the actual write to the backend before interrupting the transport.

## Recovery behaviour

API stop to authenticated recovery took 13.9 seconds. The unsent question and prior finding remained visible. After API restart, the app explained the expired in-memory conversation, and the user could start again. PostgreSQL stop to authenticated recovery took 15.5 seconds. Workflow and knowledge returned with the original session expiry. The separate three-service restart preserved the exact workflow record and session in 9.9 seconds.

## Performance results

All 140 authenticated HTTP samples passed at up to four requests in flight. Median/p95 was 349/410 ms for the dashboard overview endpoint, 194/212 ms for knowledge search and 522/764 ms for a deterministic investigation. The real workflow validator passed 72 expected HTTP results and verified completed receipts from all eight action types. Six concurrent live attempts returned one receipt and created one task. [Benchmark](PERFORMANCE_BENCHMARK.md) · [Workflow evidence](../reports/stage7-workflow-live.json)

## Startup reliability

The existing launcher built the production app, started a stopped OpsPilot stack in 18.08 seconds, and confirmed the already-running stack in 2.41 seconds. The browser open option was exercised on the healthy stack. PostgreSQL was 17.11 and Docker Engine 29.8.1. Stage 7 measured project startup with Docker Engine running. Starting the engine itself was outside the Stage 7 restart exercise because other projects share it. [Startup observations](../reports/stage7-startup.json)

## Dependency security

The runtime npm audit and the locked Windows Python audit found zero known vulnerabilities. The full npm audit identified one moderate lint-time advisory. The current ESLint dependency still requires minimatch 10, so this audit kept the compatible toolchain and records the limitation. [Dependency advisory](https://github.com/advisories/GHSA-g3hv-75wg-m249)

## Defects identified

The browser-signed conversation handle exposed a backend identifier that the anonymous direct endpoint accepted. The media-type prefix check forwarded an invalid JSON-like type. Financial comparison rows had no drill-down or way to page through attributed suppliers. A stale Copilot context returned a generic browser error.

## Defects fixed

FastAPI scopes owned conversation context to a verified backend session. Next enforces the exact JSON media type. Finance links to real supplier records and preserves the selected reporting period. A stale conversation now tells the user how to recover. These fixes were exercised on the actual production build.

## Tests added

Five additional PostgreSQL cases cover audit insertion failure, deferred commit, simultaneous approvals, lock timeout and connection interruption. Browser coverage adds exact-session isolation, financial drill-down and loaded navigation, plus the separate outage test. The existing execution test now exercises a lost response after a real commit.

## Total backend tests

**471 passed in 244.44 seconds**, including all 466 original tests. One existing Starlette warning deprecates the httpx TestClient backend. Ruff lint and format passed, and Alembic reported `0004 (head)` with no migration drift. [Backend JUnit](../reports/stage7-backend-pytest.xml)

## Total frontend tests

Two frontend contract/unit tests passed. TypeScript strict checking, ESLint and the standalone production Next.js build passed.

## Real browser tests

Eight primary tests and two outage/restart tests passed. The browser evidence includes named durations, actual operation IDs, viewport measurements and observed recovery behavior. [Browser evidence](../reports/stage7-browser.json)

## Stage 1–6 regression

**PASS.** The original source integrity and five cross-domain source scenarios passed. Stage 2 live reconciliations and 11 investigation root types passed, Stage 3 retained retrieval quality, and the 17 tools retained read-only PostgreSQL access. Stage 4C deterministic, Stage 5 approval and Stage 6 browser checks passed within their accepted scopes. [Prior-stage evidence](../reports/stage7-prior-regression.json)

## PostgreSQL integrity

The final validation checked the original counts, 44 documents, unchanged index, original data integrity, migration 0004 and all project services healthy. It found zero remaining disposable PostgreSQL test databases. [Preservation evidence](../reports/stage7-preservation.json)

## Source data fingerprint

The original accepted fingerprint is `7ed73422d07ddb0528f0ce5641e1767cdef95aa698dfcddf8dc26aad68dae0b7`. The independent analytics validator and the final preservation comparison use this same scope.

## Workflow and audit persistence

The final verifier compared every pre-audit auth, workflow and audit row with its baseline digest. Existing data matched. Synthetic test operations appended records and sessions, including the committed task read by the same Edge session after restart.

## Docker resource preservation

All ten unrelated containers retained their recorded state, and existing networks and volumes matched the Stage 7 baseline. The three project ports were all loopback-bound. The final API and frontend ran as UID 1000. [Preservation evidence](../reports/stage7-preservation.json)

## Files modified

The scoped changes are documented by area. [File inventory](STAGE7_FILES.md)

## Git commit hash

The validated implementation and evidence are in local commit `93dc2356b6034c7fe112c8a0000a59512d2758af` on `codex/stage7-quality`. The following documentation-only commit records this closure. The staged changes passed whitespace and local credential checks. No remote publication was performed.

## Remaining risks

The moderate lint dependency advisory remains an engineering-tool issue. The application uses local sessions and loopback binding. The test evidence covers bounded local loads and one installed browser.

## Known limitations

Verified Intelligence is deterministic. Local Qwen remains an optional experimental path. The test boundary excludes internet deployment, TLS termination, enterprise SSO, external audit anchoring, and broad assistive-technology certification.

## Portfolio release recommendation

| Verdict | Result |
|---|---|
| SECURITY ACCEPTED | YES, within the local deployment scope |
| BUSINESS CORRECTNESS ACCEPTED | YES |
| WORKFLOW RELIABILITY ACCEPTED | YES |
| FRONTEND ACCEPTED | YES |
| BROWSER END-TO-END ACCEPTED | YES |
| PERFORMANCE MEASURED | YES |
| STAGE 1–6 REGRESSIONS | PASS |
| LOCAL LLM | BLOCKED |
| STAGE 7 ACCEPTED | YES |
| READY FOR STAGE 8 | YES |

Stage 8 remains a separate release task. [Release readiness matrix](RELEASE_READINESS.md)
