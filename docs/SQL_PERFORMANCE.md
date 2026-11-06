# SQL performance evidence

Acceptance uses PostgreSQL 17 in the existing OpsPilot Compose database and the actual API at http://127.0.0.1:8001. No demo reseed or schema migration was performed. Measurements are three-sample local medians on the persisted Stage 1 dataset; they are observations, not SLAs, p95 estimates or statistical-significance claims.

## PostgreSQL queries

Each query ran with bound parameters and `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`. Full plans are retained in `reports/stage2-validation.json`. PostgreSQL performs aggregation; Python receives aggregate or bounded evidence rows.

| Query | Round-trip median ms | EXPLAIN planning ms | EXPLAIN execution ms | Shared hits | Shared reads |
|---|---:|---:|---:|---:|---:|
| procurement | 35.927 | 1.739 | 32.209 | 176 | 0 |
| supplier_comparison_grain | 35.998 | 1.650 | 33.559 | 177 | 0 |
| inventory | 26.137 | 2.917 | 24.406 | 318 | 0 |
| finance | 23.984 | 3.769 | 24.512 | 237 | 0 |
| workforce | 12.952 | 1.937 | 8.974 | 167 | 0 |
| investigation | 67.804 | 16.359 | 69.115 | 1475 | 0 |

## Plan review

- Receipt/dispatch CTEs aggregate by line before order/header joins; full-order counts never multiply through event rows. Procurement completion-flow grouping is performed once per grouping key, including months with no new orders.
- Supplier cohort and completion-flow results join by one aggregate key. No per-supplier network loop exists; tests compare pages of one and 100 suppliers and require equal SQL round-trip counts.
- Invoice values and payment aggregates retain invoice grain; expense category and supplier groups are separate event aggregates. An explicit unattributed-supplier bucket preserves non-supplier expenses.
- Workforce latest history uses DISTINCT ON with ordered history; incident task counts are preaggregated. Neither task history nor incident children inflate entity counts.
- Full-year aggregate plans legitimately use sequential scans over most observed rows, hash/group aggregation and CTE scans. Existing lookup/index paths support narrow references and investigation joins. Extra indexes or materialized views were not justified by the measured dataset. Alembic remains at 0002.
- The investigation plan uses bounded indexed lookups inside one SQL statement; repeated nested-loop/index operations are visible in the saved plan. These are not one client query per supplier/incident. Returned evidence remains limited to 100 even when the relational scope is broader.

## Actual API container

HTTP timings below use the published Docker endpoint, including serialization, transport and complete default domain reports. SQL counts are independently captured in-process against the same real PostgreSQL database; defaults use the full-year window, so an unavailable previous year triggers no extra previous-period queries. Eligible comparison windows perform bounded additional domain queries.

| Endpoint suffix | HTTP median ms | SQL SELECT round trips |
|---|---:|---:|
| `/analytics/overview` | 252.609 | 6 |
| `/analytics/procurement` | 150.901 | 4 |
| `/analytics/suppliers` | 158.350 | 5 |
| `/analytics/inventory` | 167.813 | 3 |
| `/analytics/warehouses` | 366.431 | 9 |
| `/analytics/fulfilment` | 183.374 | 3 |
| `/analytics/finance` | 104.541 | 4 |
| `/analytics/workforce` | 98.376 | 3 |
| `/analytics/incidents` | 96.233 | 3 |
| `/analytics/insights` | 250.120 | 10 |

Overview executes six domain summary queries. Warehouse composition executes a fixed set of grouped domain queries, not one query per warehouse. Insights consume bounded SQL aggregates, not transaction records. An empty offset page may issue one additional count query to preserve an accurate total.

No Redis, external analytics service, extra database table, materialized view, new migration or cache was introduced. Reproduce with:

```powershell
$env:PYTHONPATH = 'backend;.'
uv run python -m scripts.validate_analytics --live-url http://127.0.0.1:8001
```

Queries use PostgreSQL [aggregate functions](https://www.postgresql.org/docs/17/functions-aggregate.html) and [CTEs](https://www.postgresql.org/docs/17/queries-with.html); the stored EXPLAIN output, not a claim that every scan needs an index, is the acceptance evidence.
