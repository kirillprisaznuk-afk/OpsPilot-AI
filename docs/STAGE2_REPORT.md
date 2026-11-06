# OpsPilot AI — Stage 2 acceptance report

**Stage 2: COMPLETE. READY FOR STAGE 3: YES.** Stage 3 has not been started.
All reported gates have executed evidence against actual PostgreSQL and the
existing local Docker Compose application. No public push or remote was created.

## Architecture, SQL-first verification and metric definitions

The accepted Stage 1 monolith now has a dedicated `backend/app/analytics` layer:
central registry/contracts/common period utilities; shared full-order and historical
facts; separate procurement, supplier, inventory, warehouse, fulfilment, finance,
workforce and incident services; bounded relationships; overview composition; and
deterministic insights. Thin FastAPI routes expose typed contracts.

PostgreSQL performs aggregation using line/event CTEs, conditional aggregates,
DISTINCT ON, window counts, date truncation, grouped joins and percentiles.
Python formats aggregate results and applies transparent insight thresholds.
There is no pandas company aggregation, per-entity SQL loop, KPI result constant,
opaque score, analytics cache, materialized view or additional infrastructure.

`registry.py` supplies [METRICS.md](METRICS.md), including definition, units,
numerator/denominator, grain, time basis, inclusion/exclusion, null behavior and
limitations. [ANALYTICS.md](ANALYTICS.md) specifies domain filters and methods;
[WORKED_EXAMPLES.md](WORKED_EXAMPLES.md) supplies independent arithmetic.

## Time window / as-of semantics and period comparisons

Defaults are 1 October 2025–30 September 2026, as-of 30 September 2026, with UTC
end-of-day censoring. Current-clock dates are never an implicit business cutoff.
Only dates within observed history are accepted. Order-date cohorts, event flows
and all-history snapshot prevalence are explicitly distinguished.

Historical receipts, dispatches, payments, task history and incident closures are
censored at the requested cutoff. Earlier escalation counts are unavailable, not
zero or copied from the final incident status. Missing task history makes relevant
workload metrics unavailable. Metadata reassignment/due-date revisions are not
reconstructible; the unchanged Stage 1 static assignments/due dates remain the basis.

Comparisons preserve equal day counts and post-period observation lag. Previous
windows before the observation history are unavailable. Zero baselines retain
absolute change but have null relative change. Rate differences identify percentage
points. Current and previous values use identical precision, including averages.

## Enterprise overview and business domains

Default-cutoff results below are queried from persisted data; they are not API
constants or expectations forced into the generator.

| Domain | Implemented behavior and default evidence |
|---|---|
| Enterprise overview | 19 contextual headline metrics composed from the same domain services; acceptance checks require exact equality with detailed metrics. |
| Procurement | 2,400 orders; GBP 26,050,601.09 selected-line value; 2,386 completed; 14 overdue outstanding; GBP 141,686.31 unreceived commitment. Cohort completion and period completion-event throughput remain distinct. |
| Supplier performance | 1,678 due orders completed on time, 708 completed late, 14 still overdue; full-order on-time rate 69.92%. Split receipts do not independently complete an order. Mean/median completed lateness and overdue-open age are separate. |
| Contractual SLA | Contract-effective order cohorts and actual targets; supplier 1 has 24/72 due orders on time (33.33%) against 95%. Below-target concern is operational, never an established legal breach. Different contract targets are not blended. |
| Inventory | Physical stock 99,213 units; 320,740 received less 221,527 dispatched from zero opening stock. Open shortage records 34; remaining shortage-associated demand 543 units. Historical occurrence count is separately 1,144. |
| Warehouses | Bounded warehouse comparisons of physical stock, receipt/dispatch flows, shortage occurrences, explicit incidents, customer service and recorded additional costs. Selected warehouse inventory trends reconstruct monthly balances. No capacity denominator or utilization percent is invented. |
| Customer fulfilment | 1,800 customer orders, 222,070 ordered units, 221,527 dispatched and 543 outstanding. 1,766 fully dispatched, 34 partial; on-time full dispatch rate 54.83%. This is not carrier arrival performance. |
| Finance / costs | Invoice-cohort value GBP 25,910,489.78 = paid GBP 22,849,059.09 + outstanding GBP 3,061,430.69. Operating expense events total GBP 244,555; additional costs GBP 16,555 = expediting GBP 8,755 + overtime GBP 7,800. |
| Cost attribution | Expense/incident/order identifiers, exact amount, cost category and recorded basis are exposed. Invoice discrepancies are separate signed exposure; no penalty or lost-sale estimate is manufactured. |
| Workforce / tasks | 1,793 tasks: 1,618 completed and 175 unfinished overdue. Completed late 989 is distinct from 175 still overdue. Operations owns 123 unfinished overdue tasks. Assignment/priority/employee groups measure workload, not employee value. |
| Incidents / risk | 1,793 incidents, 1,618 resolved and 175 unresolved at cutoff; 65 final-cutoff escalated. Opening incidence, unresolved prevalence, closure time and distinct linked tasks remain separate. Historical escalation is unavailable. |

## Cross-domain investigations and deterministic insights

Ten supported roots—supplier, purchase order, sales order, shortage, warehouse,
incident, invoice, department, task and product—return bounded typed source evidence.
No relationship is inferred solely from coincident timestamps. Exact entity types,
IDs, event times, relationship labels, quantity/GBP and source references are returned.

The full supplier→purchase→receipt→stock→shortage→sales→dispatch→incident→task
case is reproduced, including a stronger simulated causal label only when the
late receipt is the sole recorded positive replenishment source. General shortage,
supplier-delay and capacity connections remain explicitly labelled associations.

Narrow investigation modes return task records with owner/status/title/due date,
open/overdue filters, explicit costs with recorded basis, exact shortage replenishment
receipts or deduplicated incidents. Complete pagination of Operations' 123 overdue
tasks and supplier task/workforce count consistency pass. Incident 1729 yields its
single actual GBP 120 overtime event; shortage 16 yields receipt 185.

The final supplier-cost reconciliation exposed an indirect warehouse overtime
association in the broad relationship graph. Focused supplier cost evidence now
uses the shared direct-attribution facts: supplier 1 reconciles to GBP 1,275.00.
The additional GBP 120 remains a labelled indirect association in the broad graph;
it is not silently assigned to that supplier's cost total.

The insight layer uses documented count/GBP/target-gap thresholds and stable severity
ordering. It returns real evidence for supplier target concerns, shortages, severe
open incidents, overdue corrective work, invoice reviews, overdue purchase exposure
and eligible period cost increases. It creates no generic advice, statistical
significance assertion, intelligence score or automatic corrective action.

## API, contracts and segmentation

Read-only paths under `/api/v1/analytics`: overview; procurement; suppliers and
supplier detail; inventory; warehouses; fulfilment; finance; workforce; incidents;
insights; and typed investigations. The local API remains on **127.0.0.1:8001**.

Dates, positive integer IDs, group/sort/direction whitelists, domain-appropriate
filters, offset and 1–100 pagination are validated. Invalid parameters return 422,
missing entities structured 404, unsupported writes 405 and database failures
sanitized 503. All API transactions use a PostgreSQL **repeatable-read, read-only**
snapshot. Financial values remain Decimal/NUMERIC and explicitly GBP; rates use
0–100; undefined/unavailable values are null with distinct status/context.

## Reconciliation and independent numerical fixtures

Purchase line values are counted once despite multiple receipts. Invoice values
reconcile to paid plus outstanding within the same cohort. Inventory reconciles
opening + receipts - dispatches + adjustments = closing. Sales units reconcile
ordered = dispatched + outstanding. Incident/task counts do not multiply through
child records. Supplier/overview/domain and investigation source consistency pass.

Legitimate scope differences remain visible. The procurement total differs from
invoice total because unreceived commercial commitments and explicit disputed
surcharges have different bases; invoices and payments are not two separate costs.
Cash paid in a period can concern invoices issued before it.

Hand-authored fixtures verify 8/10 due supplier orders on time, a separate immature
order, early partial/late final receipts, stock 20+15-25=10, invoice
1,000-400-350=250, two on-time/one late/one overdue task, same-SKU price variation,
separate completion-event throughput and exact UTC boundaries. They are independent
of the generated company's distributions and execute only in isolated test databases.

## Query performance and EXPLAIN review

Full JSON PostgreSQL `EXPLAIN ANALYZE, BUFFERS` plans and three-sample live HTTP
medians are in `reports/stage2-validation.json`; the reviewed tables and rationale
are in [SQL_PERFORMANCE.md](SQL_PERFORMANCE.md). Query counts are fixed by endpoint,
not supplier/order/employee population: the default overview uses six SELECTs;
domain reports use 3–9, and insights ten. A supplier page of one and 100 entries
uses the same number of SQL round trips.

Full-period sequential/hash/group scans are appropriate at this data size. Existing
lookup indexes support bounded investigation joins. No measured need justified
new indexes, tables or a migration. Alembic stays at **0002** with no model drift.

## Dataset preservation and Stage 1 regression

The generator, seed, models, migrations, 44 corporate documents and persisted demo
were not rewritten. The original logical fingerprint before and after Stage 2 is:

```text
7ed73422d07ddb0528f0ce5641e1767cdef95aa698dfcddf8dc26aad68dae0b7
```

All five Stage 1 scenarios remain valid: delayed supply/customer chain, warehouse
overtime, contractual concern, finance discrepancy and Operations backlog. The
original 51-test suite is included in the complete Stage 2 regression run. Stage 1
acceptance artifacts remain preserved; Stage 2 writes separate reports.

## PostgreSQL, Docker and tests

**149 passed, zero failures/errors/skips**, including 98 added analytical cases,
in the complete final run. Tests use actual PostgreSQL with UUID-isolated databases,
rollback mutations and exact cleanup; the demo database is never their writable
target. Runtime acceptance also uses actual HTTP requests to the rebuilt Linux
API container, independently of in-process API tests. One existing upstream
Starlette/httpx deprecation warning remains; it does not skip execution.

Only the OpsPilot API image/service was rebuilt/recreated. Its source hashes match
the final local application, and runtime transactions confirm read-only/repeatable
read. PostgreSQL remains healthy on 127.0.0.1:55432 with its original container,
volume, migration head, seed run and dataset. The prior Desktop issue did not recur
and was not reopened. Unrelated container/resource baselines are checked separately.
Ruff lint and formatting pass. No orphaned test database/process is required.

## Documentation, limitations and stage boundaries

New documents: ANALYTICS, METRICS, SQL_PERFORMANCE, WORKED_EXAMPLES, STAGE2_FILES
and this report.
README and ARCHITECTURE describe actual setup and analytics behavior. Metric docs
are regenerated from the registry, not maintained as a second formula source.

Limitations are explicit: no historical incident escalation transitions; no assignment,
priority, due-date or master-label revision history; no reservations or carrier arrival;
no capacity utilization; invoice/expense data is not a full P&L; recorded costs do not
quantify every commercial consequence. Insights use transparent demonstration
thresholds and bounded non-exhaustive signals, not calibrated probability scores.
Comparison rows describe the current period; summary metrics carry optional period
comparisons. Large investigation scopes require pagination.

Authentication/RBAC, workflow execution, approvals, LLMs, agents, frontend, retrieval,
embeddings, vector search and production deployment remain outside Stage 2.

## Final quality gates

| Gate | Evidence / result |
|---|---|
| Stage 1 regression and scenarios | PASS — complete original suite and five SQL traces |
| Dataset fingerprint unchanged | PASS — persisted tables and document hashes |
| SQL-first architecture and metric definitions | PASS — source inspection, central registry and query plans |
| Supplier / SLA / procurement | PASS — independent due/partial/late/immature and amount tests |
| Inventory / warehouse / fulfilment | PASS — historical ledger, segmentation, unit/service reconciliation |
| Finance / costs | PASS — exact cohorts/payments, partial exposure and source expense evidence |
| Workforce / incidents | PASS — historical status, UTC boundaries, incidence/prevalence and unknown-state tests |
| Investigations / deterministic insights | PASS — ten roots, bounded operational selectors and actual scenario sources |
| Period comparisons / numerical fixtures | PASS — equal lag, zeros/nulls, precision, independent examples |
| API contracts / pagination / validation | PASS — typed responses, whitelists, 404/422/405/503 behavior |
| PostgreSQL isolation / read-only / cleanup | PASS — actual PostgreSQL, separate temporary databases, runtime transaction checks |
| Performance / EXPLAIN | PASS — saved plans, real HTTP timings and constant query-count tests |
| Ruff / formatting / Docker health | PASS — actual commands and both healthy services |
| Unrelated resources / secrets | PASS — recorded resource comparison and deliverable secret scan |
| Documentation / scope | PASS — implemented semantics and explicit limitations; no Stage 3 work |

## Files and Git checkpoint

The complete created/modified inventory is in `STAGE2_FILES.md`. Stage 1 history
at `a03bd05` is preserved. The local Stage 2 checkpoint message is **Implement
OpsPilot enterprise operations analytics engine**; the actual hash is reported in
the final handoff rather than embedded in the commit that it would identify.
No public remote or push is created. **Remaining Stage 2 blockers: none.**
