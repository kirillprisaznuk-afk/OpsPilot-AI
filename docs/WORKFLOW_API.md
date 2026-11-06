# Stage 5 API contracts

The existing read-only analytics, knowledge, agent and hybrid endpoints retain their contracts. New workflow/auth routes use explicit Pydantic response models, JSON errors, no-store responses and UUID request correlation IDs. Interactive exact field schemas are served by /docs and /openapi.json. HTTP bodies are bounded to 64 KiB and ten seconds; pages default to 25 with a maximum of 100 and bounded offsets.

| Endpoint | Purpose |
|---|---|
| POST /api/v1/auth/login | Username/password -> bearer, expiry |
| GET /api/v1/auth/me | Safe principal and current roles |
| POST /api/v1/auth/logout | Persist session revocation |
| POST /api/v1/auth/principals/{id}/roles | Scoped admin role change and version invalidation |
| GET /api/v1/workflows/actions | Exactly eight allowlisted schemas |
| GET/POST /api/v1/workflows/policy | Read or version demo governance |
| POST /api/v1/workflows/evidence | Capture a real deterministic historical investigation |
| GET /api/v1/workflows/evidence/{id} | Read scoped immutable evidence |
| POST /api/v1/workflows/recommendations | Return an unpersisted typed candidate; no approval |
| GET/POST /api/v1/workflows/proposals | Scoped listing or immutable draft creation |
| GET/PATCH /api/v1/workflows/proposals/{id} | Detail or explicit immutable-edit denial |
| POST /api/v1/workflows/proposals/{id}/revise | New draft/version; no inherited approval |
| POST /api/v1/workflows/proposals/{id}/submit | Explicit submission |
| POST /api/v1/workflows/proposals/{id}/approve | Distinct human approval |
| POST /api/v1/workflows/proposals/{id}/reject | Human rejection |
| POST /api/v1/workflows/proposals/{id}/revoke | Original reviewer/scoped admin revocation |
| POST /api/v1/workflows/proposals/{id}/cancel | Proposer/scoped admin cancellation |
| POST /api/v1/workflows/proposals/{id}/execute | Revalidated transactional internal effect |
| GET /api/v1/workflows/executions/{id} | Receipt and actual affected objects |
| GET /api/v1/workflows/tasks[/{id}] | Scoped list/detail with provenance |
| GET /api/v1/workflows/tasks/{id}/notes | Inert append-only notes |
| GET /api/v1/workflows/tasks/{id}/assignments | Assignment history |
| GET /api/v1/workflows/escalations[/{id}] | Scoped list/detail |
| GET /api/v1/workflows/audit | Bounded scoped audit query |
| GET /api/v1/workflows/summary | Workflow-only operational counts |

All workflow business mutations require Authorization: Bearer <session> and Idempotency-Key: <uuid>. Approval/transition requests contain proposal_version, digest, optional reason. Create uses department_id, tagged action, reason, optional business_context/source_type/evidence_id/fact_ids/expiry. Actors, approvals and execution outcomes are never accepted as client declarations. Revision wraps a new proposal input plus the reviewed predecessor version/digest.

List filters include proposal status/department/source; task status/department/supplier/employee/overdue; escalation status/department/supplier/overdue; audit action/proposal/execution. Exact currently supported filters are in OpenAPI. Receipts expose actual IDs, status, result and audit references. Error JSON has error.code/message/request_id/details; validation details exclude input values and secrets. Common statuses are 401 unauthenticated, 403 scope/role/self-approval, 404 missing object, 409 stale/state/idempotency conflict, 413 body limit, 422 schema/evidence mismatch, 503 database/runtime unavailable.

Server-Timing workflow_tx measures the workflow unit from pool/role setup through commit, including lock waits; authentication happens separately. It is not isolated SQL CPU time. HTTP latency measurements include serialization and auth. Responses contain no database URLs or credentials.
