# Stage 5 — final implementation and acceptance report

Verified 2026-11-05. Backend only; all enterprise data and identities are synthetic.

## STAGE 5 IMPLEMENTATION STATUS

PASS. Implemented and verified the backend workflow boundary on the existing repository. Acceptance uses actual PostgreSQL writes, authenticated HTTP requests and Docker persistence, not mocked model responses. No paid service, inference key, model installation, publication, frontend or Stage 6 implementation was used.

## EXACT STARTING CHECKPOINT

Clean commit `3ba176eb7cb41e12b8db0a9e86a32ff9519fc800` (Stage 4C validated checkpoint and blocked local-model acceptance). Work is on `codex/stage5-workflow`. The pre-migration source snapshot and 740,472-byte PG backup were captured under ignored `.local-tools/stage5-baseline` before live DDL.

## ARCHITECTURE BEFORE / AFTER

Before: Stage 4C typed deterministic read-only analytics/RAG, 14 capabilities, 17 tools and experimental optional local language interpretation. After: a separate authenticated proposal/review/execution service and independent workflow metadata. Original Base tables, analytics, corpus, embeddings and agent write permissions remain unchanged. See [architecture](WORKFLOW_ARCHITECTURE.md).

## WORKFLOW DOMAIN MODEL

18 tables: principals, roles, scoped role assignments, sessions, login buckets; policies/control, typed subjects, evidence, proposals, decisions, executions, tasks, assignments, notes, escalations, audit and idempotency. Seven supported subjects use real typed foreign keys and exactly-one checks. Workflow tasks remain separate from seeded tasks.

## DATABASE MIGRATIONS

Additive 0004 on the existing PostgreSQL 17/pgvector volume. Frozen migration and invoker SQL guards were tested by isolated upgrade, schema/check validation and full downgrade/upgrade roundtrip in disposable databases. Live downgrade was not run. `alembic current` = `0004 (head)`; `alembic check` = no new upgrade operations. Live source reset is now explicitly refused; only disposable test reset includes dependent workflow tables.

## AUTHENTICATION

Argon2id password hashes, six generated local demo principals, no hardcoded password, no public privileged signup. Trusted bootstrap uses maintenance credentials and writes private generated credentials only under ignored local storage. No credential is committed or printed. [Setup and RBAC](AUTHENTICATION_AND_RBAC.md).

## SESSION SECURITY

Random 256-bit opaque bearer; only SHA-256 digest persisted. Four-hour default expiry, durable logout/revocation and authorization-version invalidation. No cookie authentication. Persistent account/origin throttle after eight failed attempts per 15 minutes, bounded Argon2 concurrency and secret-safe errors. Real expired/revoked/disabled/nonhuman session tests passed.

## ROLE-BASED ACCESS CONTROL

Five persisted roles: VIEWER, OPERATIONS_ANALYST, WORKFLOW_OPERATOR, WORKFLOW_APPROVER, WORKFLOW_ADMIN. Scope may be departmental or global. All new endpoints authenticate and enforce applicable role/scope; lists/counts filter before pagination. Cross-department transfers require both scopes. Detail/aggregate and forged-role tests passed.

## SEPARATION OF DUTIES

Every action requires one distinct current human reviewer. Proposer/admin self-approval is denied. Actor identity comes only from the bearer session. Tests and demonstrations use separate synthetic human accounts making explicit authenticated HTTP decisions; this is not proof of a physical person clicking or enterprise identity assurance.

## ACTION PROPOSALS

Strict tagged inputs for action/subject/parameters/reason/source/evidence/expiry. Recommendations return a candidate without persisting a proposal or granting approval. Humans separately create and submit drafts. Proposer/scoped admin owns submit/revise/cancel/execute operations.

## PROPOSAL IMMUTABILITY

Material and digest are immutable from creation in API and PostgreSQL triggers. Review/transition requests bind exact version and digest. Revision creates a fresh UUID/version/digest, supersedes a live predecessor and carries no old approvals. PATCH/direct digest edits and old-approval execution were denied.

## APPROVAL STATE MACHINE

DRAFT -> PENDING_REVIEW -> APPROVED -> EXECUTING -> COMPLETED/FAILED, with reject/cancel/expire/revoke paths. Terminal records cannot silently reopen. Expiry is checked on access/operation; no expiry worker is claimed. Real elapsed proposal-expiry and controlled-clock approval-expiry tests passed.

## APPROVAL POLICY ENGINE

Versioned local-demo governance requires one distinct approver for all eight actions; it is explicitly not corporate contract law. Initial proposal maximum 24 hours, approval 60 minutes, default proposal two hours. Current policy, roles, authorization versions and validity are rechecked before execution. Policy changes serialize with execution and invalidate old proposal snapshots.

## WORKFLOW ACTION REGISTRY

All eight actions ran successfully: create task, assign task, update status, priority, due date, add note, create internal escalation, close internal escalation. Unknown money/email/stock/SQL/deletion actions are rejected. No write tools were added to the agent. [Registry](WORKFLOW_ACTION_REGISTRY.md).

## TRUSTED EXECUTION ENGINE

Typed registered executor rechecks approval, proposer/executor/reviewer scope, session, immutable material, current policy, source/evidence, target version/lifecycle, assignee and due date. Actual affected IDs and audit references come from database results. No evidence text, model recommendation or client-supplied approved_by field can authorize execution.

## POSTGRESQL PRIVILEGE SEPARATION

New `opspilot_wf_app` login is NOINHERIT, non-owner, nonsuperuser, NOCREATEDB/NOCREATEROLE/NOBYPASSRLS. Fixed nonlogin auth/read/review/executor/admin groups use SET LOCAL ROLE. 130 actual source-table DML privilege checks denied writes across all five groups; audit rewrite and all reader workflow writes denied. No SECURITY DEFINER. Historical read-only API connection behavior remains as before; all new workflow writes use the restricted login. [Privilege evidence](../reports/stage5-privileges.json).

## TASK MANAGEMENT

Task creation, scoped assignment/history, priority/date/status updates and inert notes persist. Every update binds/increments version. Completion/cancellation are terminal; no reopening. Employee must belong to department. Completed task means recorded internal workflow completion, not proven supplier remediation.

## INTERNAL ESCALATIONS

Verified evidence required for creation. Optional related task must share subject/department. Close requires exact current version and resolution. Both operations ran through distinct approval and real executor. No external messages, supplier contacts or financial commitments occur.

## BUSINESS ENTITY INTEGRATION

Suppliers, purchase/sales orders, warehouses, products, incidents and departments are linked through typed source FKs. Source rows are never workflow mutation targets. Target source hash and workflow target version are captured and rechecked; stale proposals fail safely.

## DETERMINISTIC AI RECOMMENDATIONS

Actual Supplier 1 investigation used four real read-only analytics/knowledge tools: observed 24/72=33.33%, own 95% agreement and procurement escalation policy. Verified primary-subject negative gap supports an unpersisted internal-review candidate. Priority, deadline and assignment are explicit proposed settings, not inferred contractual obligations.

## OPTIONAL LLM DRAFT SUPPORT

AI_DRAFT is a strict untrusted provenance label requiring real server-created evidence and known facts. It has no special privilege and uses the same human approval pipeline. Stage 5 never invokes a provider or grants a model an approval credential. Stage 4C experimental local LLM acceptance remains BLOCKED; no new inference was attempted.

## EVIDENCE VALIDATION

Server captures real deterministic verified graph facts/citations/cutoff/limitations, immutable digest and source-state checksum. Binding checks subject, department, expiry, actual fact IDs and unchanged historical source state. Citations must still resolve exactly and be effective at the historical cutoff. A demonstrated source-row change invalidated the snapshot; forged/wrong-subject references were rejected.

## TRANSACTIONAL EXECUTION

PostgreSQL execution savepoint atomically includes business effects, success audit and completed receipt. An actual test trigger rejecting the completed receipt proved task/success-audit rollback and durable FAILED receipt/proposal/failure event. Nothing is claimed committed before the outer transaction commits. Connection loss can require querying/retrying a receipt.

## IDEMPOTENCY

Durable UUID keys bind authenticated actor, operation and canonical body hash. Identical authorized retries return the original serialized response; conflicting body/actor/operation returns 409. Cached reads recheck current scope/ownership and append replay audit. Failed keys remain bound; an intentional new attempt uses a new key.

## CONCURRENT EXECUTION SAFETY

Six simultaneous actual Docker HTTP requests with different keys returned one execution ID and produced exactly one task/receipt. Isolated PostgreSQL API tests also covered same-key and different-key races. Proposal row lock, idempotency advisory locks and unique proposal execution constrain effects; this is not exactly-once network delivery.

## STALE STATE HANDLING

Expected versions, current role/policy/approval versions, validity, source-state checksum and current typed references are rechecked. Two approved edits of version 1 produced one success and one FAILED stale_target receipt with no overwrite. Revoked approver/policy revisions block old approvals. Views expose stale authorization/target flags and effective expiry.

## AUDIT TRAIL

Append-only actor/time/request/object/proposal/execution/reason/result and before/after state, plus role/policy/login/denial/replay events. Both restricted-role and owner UPDATE/DELETE attempts hit tested protection. The owner can still disable triggers/schema; no external WORM guarantee is claimed. No passwords, bearer tokens or private model reasoning are logged.

## EXECUTION RECEIPTS

Happy proposal `79433474-e9e3-4a4e-9559-4e40ceea7dc6` produced receipt `34aaa7d8-60c9-4322-9e9f-46a063c8e87c` and task `3003ead9-dd59-43c7-b725-06b2909a1e4e` with three real linked audit events, proposal digest, approver and actual before/after state. See [live evidence](../reports/stage5-live-validation.json).

## SECURITY THREAT MODEL

Documented and tested spoofing, self-approval, cross-scope access, stale roles/policy/payload, replay/concurrency, partial failure, audit edits, malicious text and forbidden actions. [Threat model and explicit limits](STAGE5_SECURITY.md). Host/owner/service-code compromise, SSO/MFA, internet deployment and external audit anchoring remain outside local-demo assurances.

## END-TO-END APPROVAL DEMONSTRATION

Real deterministic evidence -> unpersisted recommendation -> explicit analyst/operator draft -> submission -> distinct reviewer approval -> separate execute -> task/receipt/audit -> all remaining registered actions. 73 final HTTP checks passed, including six real logins. No successful executor/model mock was used.

## END-TO-END REJECTION DEMONSTRATION

Proposal `920cd9ed-6f93-4c39-8456-bba85ce76cf9` was explicitly rejected by the distinct reviewer; execution returned 409 and produced no task. Additional isolated actual-PG tests covered cancellation, revocation and expiry.

## UNAUTHORIZED EXECUTION TESTS

Anonymous 401; viewer write 403; proposer self-review 403; wrong-scope review/detail 403; unapproved/rejected execute 409; immutable edit 409; forged fact 422. Forged actor/role/body fields, owner runtime connections, cookie-only auth and forbidden action tags were denied in real API/PG tests.

## PROMPT-INJECTION TESTS

A live note containing an instruction to ignore restrictions and approve was stored only as inert text through its own approval. It granted no permission. Existing read-only task/file/invoice execution requests remain refused in the 38-case regression. AI_DRAFT without verified facts cannot enter the approved executor.

## REAL POSTGRESQL INTEGRATION

Full suite uses actual PostgreSQL, migrations, source seed/index, a real restricted runtime LOGIN, authenticated TestClient traffic and concurrent requests. Disposable databases are created/dropped by their exact test identities. No SQLite replacement or mocked successful mutation is used.

## RESTART PERSISTENCE

Only OpsPilot Compose db/api were restarted after tests finished. Before/after equality held for original fingerprint/integrity/scenarios, knowledge index and every workflow core-table count/digest; all 158 audit rows at restart had identical digest `c1cdcbd853151b758e34daa1143314a4664b363d08451118e7a47d8d5c49f03a`. Session remained valid. Later login/logout appended events; the 158-row prefix was independently reverified. Snapshot totals include both initial and final demos: 22 proposals, 18 executions, 4 tasks, 2 escalations, 2 evidence snapshots, 6 assignment-history rows, 2 notes, 100 idempotency records.

## API CONTRACTS

Versioned Pydantic auth/proposal/action/evidence/task/escalation/receipt/audit/summary contracts, strict action tags, bounded input, no-store and secret-safe errors, request IDs, limit<=100 and scoped pagination. OpenAPI API version 0.5.0. [Endpoint reference](WORKFLOW_API.md).

## PERFORMANCE MEASUREMENTS

Measured local API latencies, not promises. Successful execute samples include the six concurrent requests/replays.

| Operation | Samples | Median ms | Max ms |
|---|---:|---:|---:|
| authentication | 6 | 136.91 | 684.02 |
| create | 9 | 50.09 | 413.74 |
| submit | 10 | 47.96 | 451.83 |
| approve | 9 | 52.17 | 60.77 |
| execute | 14 | 219.21 | 417.80 |
| list_proposals | 1 | 128.42 | 128.42 |
| list_tasks | 1 | 33.84 | 33.84 |
| list_audit | 1 | 31.98 | 31.98 |
| real_supplier_contract_policy_investigation | 1 | 3824.43 | 3824.43 |
| proposal_review_detail | 5 | 28.03 | 36.32 |
| workflow_execution_transaction | 14 | 135.68 | 398.91 |

Workflow transaction timing includes connection/role setup, lock waits and commit, and excludes the separate authentication dependency. [Raw measurements](../reports/stage5-performance.json).

## ALL AUTOMATED TEST RESULTS

Final full run: **460 passed, 0 failed**, 224.74 seconds. All 401 prior tests retained plus 59 Stage 5 tests. One existing Starlette/httpx deprecation warning. [Final JUnit](../reports/stage5-pytest.xml). The first security run found retry timestamp serialization and stale-approval display errors; fixed and retested. First combined run had the stale 0003 readiness constant plus an accidental overlapping restart (2 failures, 4 teardown/connection errors); those failures are preserved in stage5-pytest-initial.xml. Readiness was fixed; exact own leftover disposable databases/role were removed; final suite/restart ran sequentially. Initial Docker action checks passed but readiness after restart failed; stage5-live-initial.json is preserved, not counted as acceptance.

## STAGE 1 BASELINE

PASS. Original fingerprint remains `7ed73422d07ddb0528f0ce5641e1767cdef95aa698dfcddf8dc26aad68dae0b7`. All 25 source-table counts, one seed run, integrity and five cross-domain scenarios preserved. Source seeding/reset/reproducibility remains tested in disposable PostgreSQL. No live reseed, source reset, volume replacement or prune.

## STAGE 2 ANALYTICS REGRESSION

PASS. Retained analytics tests, fresh-oracle comparisons and real runtime checks passed. Procurement->customer, warehouse capacity, contract concern, invoice review and overdue-workload scenarios match the accepted source. Stage 5 operational counts are labelled separately and do not change old denominators.

## STAGE 3 RETRIEVAL REGRESSION

PASS. All 44 documents/versions/chunks and 44 citations resolve; index/embeddings identical. 42-query evaluation quality unchanged: keyword/vector/hybrid recall@5 0.6000/0.8714/0.9429; citation resolution and no-answer accuracy 1.0 in each mode. Current medians 11.14/22.51/25.99 ms. [Retrieval evidence](../reports/stage5-retrieval.json).

## STAGE 4 READ-ONLY REGRESSION

PASS. Exactly 17 read-only tools preserved; real source/workflow write privilege probes denied. Old provider architecture/security remains intact. No model key or provider was invoked for acceptance.

## STAGE 4C DETERMINISTIC REGRESSION

PASS. 38/38 real HTTP scenarios (8 original + 15 Stage 4B + 15 Stage 4C), 14 capabilities, zero model calls/interpretations. Median HTTP 117.45 ms, maximum 1586.47 ms. Metrics checked against fresh canonical tool oracles; unsupported/ambiguous requests retain refusal/clarification/insufficient-evidence boundaries. [Actual evaluation](../reports/stage5-deterministic-evaluation.json), [agent review scope](../reports/stage5-semantic-review.json). Deterministic prose remains a verbose evidence ledger with limited executive narrative. The old read-only validator retains historical `ready_for_stage5:false` and `live_llm_acceptance:NOT_RUN`; these are its old LLM gate, not the new Stage 5 acceptance verdict.

## DOCKER HEALTH

PASS. Docker Desktop engine 29.8.1 was safely started from its stopped state; no destructive recovery. Final PostgreSQL and API containers are running/healthy. API rebuilt and runs at 127.0.0.1:8001; DB remains 127.0.0.1:55432. Original volume preserved. All 10 unrelated containers retained IDs/images/status/start/finish state; unrelated volumes/networks preserved. No unrelated process/container terminated, no prune/reset/uninstall.

## RUFF AND FORMAT

PASS. `ruff check .` and `ruff format --check .` succeeded; 232 files already formatted. Git whitespace check succeeded (only trailing whitespace in preserved first-failure XML was normalized).

## ALEMBIC HEAD

0004 (head); no new upgrade operations detected, both isolated schema regression and final live check.

## FILES CREATED AND MODIFIED

[Complete file inventory](STAGE5_FILES.md). The only original application changes are router/boundary wiring, readiness for 0004 and refusing source reset once live workflows exist. Existing migration/schema assertions were updated to the additive head; tests were retained. One expected-migration argument supports historic validator reuse.

## GIT COMMIT HASH

Implementation and validated evidence checkpoint: `2b9dc00d5fb70b246f6bb8bbed57248de1323497`. This report and explicit final gate metadata are committed in the subsequent documentation closure on the same branch. The final closure hash is the branch HEAD (`git log -1`) and is reported in the handoff. No push/publication.

## GIT STATUS

Local branch `codex/stage5-workflow`; validated implementation checkpoint committed locally. The final documentation closure is a separate local commit; the handoff verifies its HEAD and clean working tree. No remote push or publication.

## KNOWN LIMITATIONS

Local demo credential possession identifies a human-class principal; it does not prove liveness or enterprise IAM. No SSO/MFA/password-recovery UI, internet ingress, frontend, background expiry/retention job, external WORM or RLS claim. A trusted service login can SET its fixed role groups; application/host compromise is outside per-endpoint RBAC. Historical read APIs retain prior access behavior. Source checksum validation adds read work and conservative invalidation; global source changes require recapture. Proposal lists decorate bounded pages with current state and may require optimization at production volumes. Current latency is a local observation, not an SLA. Experimental LLM remains blocked and deterministic prose remains limited.

## REMAINING BLOCKERS

None for the accepted deterministic Stage 5 local backend. Stage 4C real local-model acceptance remains BLOCKED from the previous resource/model gate and was not retried or reclassified. Production IAM/security/deployment work remains separate future scope.

## NEXT RECOMMENDATIONS

Keep this local checkpoint and generated credentials private. Use existing documented startup and explicit review workflow. Stage 6 may be planned after user authorization; no Stage 6/frontend work has begun. Treat any optional future model draft as untrusted and require the same human review/execution boundary.

## FINAL VERDICT

STAGE 5 WORKFLOW ENGINE: **PASS**

STAGE 5 HUMAN APPROVALS: **PASS**

STAGE 5 AUTHENTICATION AND RBAC: **PASS**

STAGE 5 AUDIT AND IDEMPOTENCY: **PASS**

STAGE 1–4 REGRESSION: **PASS**

STAGE 4C LOCAL LLM: **BLOCKED**

STAGE 5 ACCEPTED: **YES**

READY FOR STAGE 6: **YES**

Readiness is a verdict only. No Stage 6 implementation or publication has occurred. The user explicitly accepts deterministic Stage 5 independently of the experimental LLM gate.
