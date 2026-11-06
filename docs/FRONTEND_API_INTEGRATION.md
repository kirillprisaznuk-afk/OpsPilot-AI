# Frontend API inventory

The same-origin browser gateway uses explicit method/path matching. Each allowed request verifies the browser session with the real FastAPI `/api/v1/auth/me`. The gateway does not accept arbitrary upstream hosts, credentials, headers or URLs. Backend objects enforce their original scopes; only browser mutations with same-origin intent and a matching CSRF token are forwarded.

| Product surface | Actual API families |
|---|---|
| Observation context / dashboard | `/demo/summary`, `/analytics/overview`, procurement trends, warehouse segments, supplier rank, workflow summary/audit |
| Analytical tabs | `/analytics/{procurement,inventory,warehouses,fulfilment,finance,workforce,incidents}` with supported filters |
| Supplier profile | `/analytics/suppliers/{id}`, registered knowledge metadata, purchase-order selector |
| Knowledge | `/knowledge/documents`, `/knowledge/search`, `/knowledge/citations/{id}` |
| Investigations / Copilot | `/hybrid/query` explicitly `DETERMINISTIC`; usage, graph and citations displayed |
| Tasks and escalations | `/workflows/tasks`, `/workflows/escalations`, task notes/assignments and scoped audit |
| Proposals and decisions | `/workflows/proposals`, evidence, approve/reject/submit/cancel/revoke/revise/execute |
| Access and status | `/auth/me`, role assignment only for authorised admins, readiness/knowledge/hybrid/provider metadata |

New read projections at `/api/v1/workspace`: `subjects` searches genuine catalog/source identities with bounded pages and recorded-date filters; `people` returns only scoped employee IDs/names/departments; `actor-labels` returns names for referenced visible actors or the caller; `principals` requires global administration and omits authentication fields; `status` exposes the actual backend version. Task/escalation search and priority filters and audit search/type/object/order filters retain the previous scope predicates. No new write route or arbitrary SQL is added.

`src/lib/generated.ts` comes from `app.openapi()`. The frontend uses strict TypeScript types plus runtime checks at the session, analytical report, proposal and deterministic investigation boundaries. Error pages distinguish backend rejection and unavailable services. Requests cancel on abandoned queries; protected responses use `no-store`. Mutations preserve their browser intent key across an uncertain retry. The key is derived from authenticated principal + path + exact body and is sent to the real Stage 5 idempotency ledger. No frontend retry silently executes with a new identity.

Historical analytical defaults come from the observed backend period; current workflow times are UTC and independently labelled. Source order rows retain stored record state while cohort filters affect recorded order dates; no final stored status is presented as a reconstructed historical status. Document passages and task notes are escaped text; citation navigation uses validated internal identifiers, never returned arbitrary URLs.
