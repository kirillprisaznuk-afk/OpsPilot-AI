# Stage 5 threat model

The trust boundary is authenticated human request -> strict allowlisted action -> immutable reviewed digest -> revalidated executor. Local models, deterministic recommendations, retrieved documents, free text, notes and external input are untrusted proposals/evidence, never authorities. No inference process receives a human bearer or workflow service credential. Stage 5 itself calls no model.

| Threat | Enforcement and real tests |
|---|---|
| Claimed administrator/approver in input | Strict extra-forbid, bearer-derived principal; forged headers/body refused |
| Self-approval, including admin | Distinct human identity required in service and DB approval guard |
| Cross-department access or transfer | Current role/scope checks and scoped list predicates |
| Stolen/revoked/expired session | Opaque token hashes; persisted expiry/revocation and authz_version |
| Credential guessing | Persistent per-account/origin throttle; Argon2id; bounded hash concurrency |
| Mutable approved payload | Immutable material/digest; new revision requires new approval |
| Stale role/policy/evidence/target | Final checks, principal/policy locks, current source checksum, optimistic versions |
| Replay or simultaneous execution | Durable actor/op/body idempotency, unique receipt and proposal lock |
| Partial mutation/forged success | Actual PG savepoint rollback test with rejecting receipt trigger |
| Audit rewrite | Runtime no DML permission; owner-level UPDATE/DELETE trigger denial demonstrated |
| SQL/shell/external action injection | Eight typed actions only, bound query values, no arbitrary execution tool |
| Prompt injection in note/evidence | Inert stored text; no identity/approval semantics; real note exercise |
| Compromised reader | SELECT-only historical data, no workflow writes |

Evidence capture runs the real Stage 4C deterministic engine against PostgreSQL analytics/RAG, checks verified facts, resolved subject and zero model calls, persists source-state checksum, citations, cutoff and limitations. Proposal binding verifies the immutable digest, subject/department, actual fact IDs, expiry and source-state checksum. Registered citations must still resolve exactly and match the effective version at the historical cutoff. A source change requires recapture. Recommendations use only the primary subject's verified negative target gap or positive overdue condition; proposed priority/date/assignee remain explicit human settings. No penalty/legal breach inference is introduced.

Limits: local demo authentication is not enterprise IAM, MFA, human liveness or a production internet deployment. Host/DB owner credentials and arbitrary native code execution remain trusted. SQL privilege separation limits mistakes and untrusted read tools; one service login can SET its fixed internal groups, so service compromise is outside per-endpoint RBAC protection. No RLS or external immutable audit store is claimed. Bearer theft allows credential impersonation until expiry/revocation. Authentication buckets have no scheduled retention job. Restarted sessions persist by design until their original expiry. Credentials are stored in ignored local development files and need host access protection.

Existing historical APIs retain their local read-only exposure. No frontend, internet ingress, email integration, task worker, payment connector or Stage 6 work is included. Production hardening should separately address TLS/SSO/MFA, secret management, account recovery, retention, external audit anchoring and access control for historical reads.
