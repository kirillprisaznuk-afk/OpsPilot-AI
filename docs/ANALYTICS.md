# Enterprise operations analytics

Stage 2 adds a read-only SQL analytics layer to the accepted Stage 1 modular
monolith. No schema migration, regenerated demo data, frontend, model integration,
retrieval pipeline or workflow executor is required.

## Responsibilities

`backend/app/analytics/registry.py` is the metric-definition source. Run
`python -m scripts.write_metrics` to reproduce [METRICS.md](METRICS.md).
`contracts.py` defines query validation and Pydantic responses. `common.py` owns
bounded SQL execution, numeric conventions, segmentation checks and comparisons.
`order_queries.py` centralizes full-quantity order completion. `facts.py` provides
one-row-per-entity historical facts. Separate domain services construct reports;
`api/analytics.py` only validates transport input and delegates.

All transactional filtering, grouping, sums, counts, percentiles and event joins
run in PostgreSQL through SQLAlchemy bound statements. Python converts aggregate
rows to typed contracts and evaluates documented threshold rules. It never loads
the company into pandas to calculate endpoint KPIs. The validation script loads
records solely to run the existing Stage 1 integrity/fingerprint checks.

Receipts and dispatches aggregate by line before joining order headers. Payments
aggregate by invoice before invoice totals. Corrective actions aggregate by incident
before incident counts. Independent warehouse/expense aggregates are joined only
at their aggregate grain. This prevents many-to-many multiplication.

Every API database session now uses a **REPEATABLE READ, READ ONLY** PostgreSQL
transaction, giving multi-query reports a consistent snapshot. Maintenance and
isolated test seeding use their existing separate writable sessions.

## Time and populations

The supported observation window is **2025-10-01 through 2026-09-30**. Default
`as_of` is 2026-09-30, independent of the machine clock. Defaults are
`start_date=2025-10-01` and `end_date=as_of`. Require
`start_date <= end_date <= as_of`, all within observed history. Dates are inclusive;
timestamp events use the exclusive UTC midnight following `as_of`.

- Procurement and fulfilment service metrics use **order-date cohorts**; receipts
  and dispatches are observed through `as_of`. A due promise matures at that UTC
  day's end. Full completion requires **all original lines**, including when a
  product filter selects only some commercial values/units. Overdue incomplete
  orders are explicit; immature promises are excluded from the rate denominator.
- Procurement `completed_in_period` is a separate **completion-event flow**,
  including orders placed before the selected period.
- Inventory opening/closing balances concern `start_date`/`end_date`;
  `stock_on_hand`, remaining demand and open shortages concern **as_of snapshots**.
  Receipt/issue/adjustment flows and shortage detections concern the selected period.
- Finance exposure uses the **invoice-issue cohort**, paid by `as_of`. Cash payments
  and operating expenses are independent **event flows** within the period.
- Workforce and incident headline backlogs are **all-history prevalence** at
  `as_of`; creation/completion/closure-in-period fields are separate incidence flows.

Monthly order trends retain the report's outcome cutoff and expose mature
denominators. Monthly stock snapshots use each bucket's end, including partial
months. Workforce/incident trends show creation/completion/closure flows. Select
`warehouse_id` or `supplier_id` to obtain that entity's applicable monthly series.

Previous periods have equal calendar-day length and the same post-period observation
lag. A previous period extending before 1 October 2025 is unavailable, never silently
shortened. Relative change divides by the absolute previous value; a zero baseline
produces null relative change while retaining absolute change. Rate differences
also identify percentage points. Both periods use identical numeric precision.

## Endpoints and dimensions

All paths below are under `/api/v1/analytics` on `http://127.0.0.1:8001`.

| Path | Supported filters | Groups |
|---|---|---|
| `/overview` | Date window / as_of only | Domain headline metrics |
| `/procurement` | supplier_id, warehouse_id, product_id, product_category, supplier_category | warehouse, supplier |
| `/suppliers`, `/suppliers/{supplier_id}` | supplier_id, warehouse_id, supplier_category | supplier |
| `/inventory` | warehouse_id, product_id, product_category | product, warehouse |
| `/warehouses` | warehouse_id, product_id, product_category | warehouse |
| `/fulfilment` | warehouse_id, product_id, product_category | warehouse |
| `/finance` | supplier_id, warehouse_id | supplier, warehouse; separate cost_categories |
| `/workforce` | department_id, employee_id, priority, incident_category, supplier_id, warehouse_id | department, employee, priority, incident_category |
| `/incidents` | department_id, incident_category, supplier_id, warehouse_id | category, severity, department, warehouse |
| `/insights` | Date window / as_of only | Bounded severity-prioritized rules |
| `/investigations/{entity_type}/{entity_id}` | Root entity and date window / as_of | Bounded linked evidence |

Task supplier/warehouse filters follow the linked incident's actual supply/location
references; they do not imply an employee's physical location. Product-specific
warehouse reporting omits unallocatable warehouse-wide incident/expense metrics
instead of inventing a product allocation. Unsupported dimensions return 422.

Lists use `limit` 1–100 and `offset` 0–1,000,000. Entity IDs are positive PostgreSQL
integers. Group, sort and direction expressions come from internal whitelists.
Default order is ID, then label; nulls sort last. Domain sorts additionally expose
supported value/rate/backlog fields documented by 422 errors and OpenAPI. Financial
cost categories are a separate bounded list, not extra rows appended to a paginated
supplier page. SKU price bands page independently using the same limit/offset.
Contract assessments are limited to 100 on the selected supplier page.

```powershell
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/analytics/overview'
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/analytics/suppliers/1?as_of=2026-09-30'
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/analytics/inventory?warehouse_id=1&as_of=2025-10-20'
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/analytics/finance?start_date=2026-09-01&end_date=2026-09-30'
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/analytics/investigations/shortage/16?limit=100'
```

Each metric identifies name, unit, value, numerator/denominator where relevant,
time basis, grain, status, limitations and optional comparison. The enclosing report
and trend point identify their window/as_of. Discrete counts/units are JSON integers;
Decimal money/rates/days serialize as strings. Rates use **0–100 percent**. Empty
additive populations yield zero; undefined rates/averages and unavailable history
yield null with different status values. Segment metrics describe the current
period; summary metrics optionally include previous-period comparisons.

## Supplier methodology and financial boundaries

Supplier reliability is full-order on-time receipt divided by mature due orders.
Incomplete overdue orders stay in that denominator; future commitments do not.
Positive completed-order lateness and overdue-open age remain separate. Individual
receipt punctuality is a different event-grain metric. Median positive lateness uses
PostgreSQL's interpolated percentile; monetary arithmetic never uses floating point.

SLA assessments use each actual contract's target and order-date effective interval.
Below-target observations identify an operational review concern, never an automatic
legal breach. Contracts with different targets stay separate; a common comparison
target is null/unavailable when no single effective target can be identified.
Same-product price bands avoid pooling unlike SKU prices into a misleading index.

Invoice value equals its payments plus remaining amount within the same invoice
cohort. Period cash flows can legitimately differ. Explicit expediting/overtime
expenses are additional recorded costs; outstanding invoice liability and signed
invoice discrepancies are separate exposure. Supplier-unattributable costs remain
in an explicit unattributed segment. There is no revenue, P&L, EBITDA, estimated
penalty, inferred lost sale or general-ledger calculation.

## Historical limitations and investigations

Task state follows history and observed completion timestamps. Missing history
makes open/overdue/completion-rate metrics unavailable. Incident opening and closure
timestamps reconstruct unresolved/resolved prevalence, but escalation/investigation
status has no transition history. Earlier escalation counts are unavailable.
Assignment, priority, severity and master-data labels have no revision history;
historical reassignment cannot be reconstructed. The Stage 1 single-completion /
single-closure lifecycle is retained.

Investigations support supplier, purchase_order, sales_order, shortage, warehouse,
incident, invoice, department, task and product. Each evidence edge has typed IDs,
event timestamp, relationship, source table/ID, optional units/GBP, and evidence class.
The graph follows actual keys, including earlier linked events through `as_of`,
not mere time overlap. Returned evidence is paginated with a total count. Root
metrics retain their documented cohort/snapshot basis; order roots describe the
whole identified order.

Use `evidence_kind=tasks|costs|receipts|incidents` for a narrower bounded operation
(default `all`). Task evidence identifies the task itself, employee owner, title,
priority, recorded due date and observed historical status. `open_tasks_only=true`
or `overdue_tasks_only=true` requires `evidence_kind=tasks`; overdue also requires
unfinished state and a due timestamp before the exclusive cutoff. Unknown task
history is not imputed as open. Supplier/department/warehouse task scope matches
the corresponding workforce filter. Due-date revisions are not recorded; these
queries use the original static Stage 1 due dates.

For an incident root, cost evidence contains only expenses explicitly linked to
that incident, including the recorded cost category and basis. For a shortage root,
receipt evidence follows its exact expected
purchase line, not other products delivered on the same commercial order.
Narrowed receipt/incident lists deduplicate entity IDs before pagination.
Supplier and warehouse cost selectors use the same explicit attribution facts as
financial analytics. The full relationship graph can also contain indirect
associations; those must not be summed as directly attributable supplier costs.

```powershell
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/analytics/investigations/supplier/1?evidence_kind=tasks&open_tasks_only=true'
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/analytics/investigations/department/1?evidence_kind=tasks&overdue_tasks_only=true&limit=100'
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/analytics/investigations/incident/1729?evidence_kind=costs'
```

Most evidence is an explicit association. The stronger `simulated_causal_chain`
label requires late inbound receipt, a prior linked shortage, delayed matching
dispatch at the same product/location, and no other recorded positive stock source
before that dispatch. It supports the generated causal case without generalizing
all customer delay to supplier fault. Unknown financial consequences remain unknown.

## Deterministic insight rules

No model or statistical-significance claim is involved. Rules use SQL aggregate
outputs and return their evidence/source references. Priority order is critical,
warning, opportunity, information, then stable rule/ID ordering.

| Rule | Condition / classification |
|---|---|
| Supplier below target | At least five due orders; below actual contract target. Gap at most -10 pp is warning, smaller negative gap information; up to three displayed concerns. |
| Warehouse shortage | Highest observed positive outstanding shortage demand, warning; ties by ID. |
| Corrective backlog | Positive overdue department workload; at least 20 is warning, otherwise information. |
| Severe open incidents | Critical unresolved incidents are critical; high unresolved incidents warning. |
| Invoice review | Positive explicitly evidenced discrepancy count, warning. |
| Purchase exposure | At least GBP 1,000 overdue unreceived cohort commitment, warning. |
| Expediting increase | Explicit period expediting cost exceeds an eligible equal-length previous period, warning. |

These are transparent demonstration thresholds, not calibrated risk scores or
employee productivity rankings. Insights are bounded, deterministic, non-exhaustive
signals; no corrective action is executed.

## Verification

See [WORKED_EXAMPLES.md](WORKED_EXAMPLES.md) for independent numbers and original
scenario evidence, [SQL_PERFORMANCE.md](SQL_PERFORMANCE.md) for actual plans, and
[STAGE2_REPORT.md](STAGE2_REPORT.md) for acceptance gates. Run the complete pytest
suite and `python -m scripts.validate_analytics --live-url http://127.0.0.1:8001`.
No Stage 3 retrieval or AI features are implemented.
