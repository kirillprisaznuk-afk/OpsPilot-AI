# OpsPilot AI — Stage 1 report

Validation date: 27 October 2026 (Atlantic/Canary).

## Stage 1 status

**Stage 1 is complete. READY FOR STAGE 2: YES.** Docker Desktop recovery, the
existing image build, both Compose services, live API acceptance, database
integrity, reproducibility and service restart persistence have passed. The user
approved changing only OpsPilot's host API port to **8001**, with container port
8000 unchanged. The existing ProductPulse reservation on host port 8000 and all
other unrelated resources were preserved.

Actual PostgreSQL migrations, full seeding, database/API tests, scenario queries,
logical fingerprint reproduction and native database restart persistence pass.
No Stage 2 feature has been started.

## Final Docker acceptance — 27 October 2026

- **Desktop / engine:** Docker Desktop 4.93.0 (240920), Engine 29.8.1,
  Linux/amd64 are operational.
- **Observed root cause:** Desktop failed before starting its Linux engine while
  renaming its pre-existing zero-byte `engine.sock` reparse point. The socket was
  dated 2 October, before OpsPilot existed. This is an environmental runtime-endpoint
  failure, not an OpsPilot Compose failure. The event that originally stranded the
  socket is not established. The symptoms match [Docker issue 15064](https://github.com/docker/for-win/issues/15064).
- **Recovery:** graceful Desktop stop timed out. After confirming that the engine
  pipe was absent, only the failed Desktop/backend processes at verified Docker
  executable paths were stopped. The socket-only parent directory was preserved
  intact as `docker-secrets-engine.opspilot-preserved-20261027-a7534b0c` in the same
  per-user Local AppData folder. Desktop recreated the runtime directory and started.
  No reset, uninstall, deletion, prune, WSL shutdown, administrator elevation, or
  direct Docker settings edit was used. Desktop itself rewrote its settings file
  during normal startup (its SHA-256 changed); unchanged settings bytes are not claimed.
- **Build / necessary fix:** the existing API Dockerfile built successfully with
  locked dependencies and non-root user `opspilot`. `.dockerignore` now excludes
  `.local-tools`, `.local-pg` and `.local-pg-validated`, preventing local validation
  runtimes and database files entering the build context. Application code,
  Dockerfile and Compose topology are unchanged. The user-approved port mapping
  is now `127.0.0.1:8001:8000`; startup documentation uses the same host port.
- **Native conflicts:** only verified OpsPilot native API PID 24216 and its
  `.local-pg-validated` PostgreSQL cluster were stopped. Their data remains intact.
- **Database:** `opspilot-stage1-db-1` is healthy on 127.0.0.1:55432. It runs PostgreSQL
  17.11 Debian and uses `opspilot-stage1_opspilot_pgdata`.
- **Alembic / seed:** empty container database upgraded to `0002`; Alembic reports
  no model drift. Full deterministic seed succeeded in 11.201 seconds. All exact
  domain counts below match the native baseline; there is exactly one seed run.
- **Integrity / scenarios:** the PostgreSQL-loaded dataset and all five scenario
  traces pass; its full logical fingerprint matches the baseline below.
- **Persistence:** `docker compose restart db api` completed; both services became
  healthy again. Every domain count, one seed run, the persistent database volume
  and the full logical fingerprint remain unchanged afterward. No reseeding occurred.
- **Full tests:** 51 passed, zero failures/errors/skips in 58.32 seconds against
  temporary isolated databases on the Compose PostgreSQL container. One existing
  Starlette/httpx deprecation warning remains. Ruff lint and format both pass.
- **Other resources:** all 10 pre-existing unrelated containers retain their IDs,
  running/exited states and start/finish timestamps. Existing volumes and networks
  remain present; only the OpsPilot volume and network were added. Baseline capture
  occurred immediately after engine recovery; no pre-recovery engine inventory was
  available while Desktop was down.
- **Live API:** `opspilot-stage1-api-1` is healthy at `http://127.0.0.1:8001`.
  Thirteen actual HTTP checks passed both before and after restarting OpsPilot:
  liveness/readiness, summary with every domain count and fingerprint, all five
  paginated lists, both order timelines with independently expected quantities,
  and 422/404/405 behavior. These checks reached the Linux API container, separately
  from the in-process integration tests. Port 8000 was initially blocked; the
  approved OpsPilot-only host mapping to 8001 resolved it without touching ProductPulse.

Machine-readable facts are saved in `reports/docker-acceptance.json`; current
container-database validation/timings are in `reports/stage1-validation.json`.

## Architecture summary and project structure

Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, PostgreSQL 17, Alembic, pytest and
Ruff form a synchronous modular monolith. Exact resolved dependency versions are
committed in `uv.lock`; application and development dependencies are separate.

```text
backend/app/api/            versioned read-only routes
backend/app/core/           environment settings
backend/app/db/             engine/session lifecycle
backend/app/models/         seven domain model modules and shared base
backend/app/repositories/   pagination and order timeline queries
backend/app/schemas/        typed Pydantic response contracts
backend/app/services/       seed safety, integrity, scenarios and demo orchestration
backend/alembic/            frozen schema and PostgreSQL guard migrations
backend/tests/             unit, PostgreSQL and API verification
data/generator/             deterministic fictional company/event simulation
knowledge/synthetic_documents/  36 agreements and eight policies
scripts/                   environment setup, database maintenance and validation
docs/                      architecture, model, business, data and validation notes
reports/                   measured JSON evidence and pytest JUnit output
```

All source was created in the initially empty standalone OpsPilot directory.
No code was copied from another user project. A full created-file manifest is in
`FILES.md`; there were no pre-existing project files to modify.

## Business model and organisation domain

Fictional Northstar Supply operates UK B2B procurement/distribution in GBP. Six
departments, 48 synthetic employees, six descriptive roles and 48 responsibility
assignments provide task ownership. Emails use `.example`. There are no actual
personal records, sensitive employee profiles or login accounts.

## Procurement domain and supplier contracts

36 suppliers have 36 dated supplier contracts with service targets, escalation
intervals and payment terms. 2,400 purchase orders contain 4,799 product lines.
Original promises, partial receipts, open commitments and procurement statuses
remain separate from inventory events. There are no stored performance scores.

## Inventory domain

200 products and four warehouses use a signed stock ledger. 5,447 receipts and
4,768 dispatches post 10,215 source-linked movements. Opening stock is zero;
all historical balance prefixes are nonnegative. Closing stock is 99,213 units.
1,144 explicit shortages preserve sales demand and candidate replenishment links.
Database guards reject mismatched movements and over-receipts; deferred constraints
require exactly one ledger entry per receipt/dispatch. Adjustments are supported
with reasons; transfers and reservations are not generated.

## Sales and fulfilment domain

120 synthetic business customers place 1,800 sales orders with 3,599 sales lines.
Ordered, dispatched and outstanding quantities reconcile. Full and partial
dispatches consume actual inventory; unmet demand remains backordered. Customer
promises concern dispatch; carrier arrival tracking is not implemented.

## Finance and costs domain

2,386 supplier invoices, 2,210 payments and 216 explicit operating expenses use
exact GBP values, net of VAT. Partial/outstanding/disputed invoice states are
represented. Discrepancy cases add a declared unsupported GBP 25 surcharge.
Expediting and overtime costs have explicit scenario bases; no automatic losses
are inferred from lateness. This is not double-entry bookkeeping or a general ledger.

## Task management; incidents and risks

1,793 evidence-linked incidents have 1,793 owned corrective tasks and 3,527 task
status history rows. Shortages, supplier delays, warehouse pressure and invoice
discrepancies have actual operational links. Active, open, completed and escalated
tasks coexist; 123 unfinished overdue tasks belong to Operations at the cutoff.
Incident closure and task completion never precede creation.

## Corporate document foundation

44 concise local Markdown documents and 44 version records contain document IDs,
titles/types, effective dates, versions, departments and contract references.
Contract terms and agreement prose share one source. SHA-256 checks prevent corpus
drift during seeding. The corpus has no copied proprietary text, embeddings,
retrieval pipeline or model integration.

## Database schema and Alembic migrations

26 normalized relational tables use primary/foreign keys, unique constraints,
constrained statuses, integer stock units, NUMERIC money, UTC timestamps and
relationship/status/date indexes. See `DATA_MODEL.md` for the ER diagram.

Migration `0001` creates the frozen enterprise schema. Migration `0002` installs
aggregate quantity/payment checks, source/stock guards, immutable events, deferred
ledger completeness and the stock partition index. Empty-database migration and
head verification pass; metadata drift is checked using Alembic. A dedicated
temporary database tests upgrade/downgrade/reapply. Initial migration command
elapsed time was **2.663 seconds**, including Python/Alembic process startup.

## Synthetic dataset summary and exact entity counts

| Entity | Count | Entity | Count |
|---|---:|---|---:|
| departments | 6 | employees | 48 |
| business_roles | 6 | responsibilities | 48 |
| suppliers | 36 | supplier_contracts | 36 |
| warehouses | 4 | products | 200 |
| customers | 120 | purchase_orders | 2,400 |
| purchase_order_lines | 4,799 | goods_receipts | 5,447 |
| sales_orders | 1,800 | sales_order_lines | 3,599 |
| fulfilments | 4,768 | stock_movements | 10,215 |
| shortages | 1,144 | supplier_invoices | 2,386 |
| payments | 2,210 | operational_expenses | 216 |
| incidents | 1,793 | tasks | 1,793 |
| task_status_history | 3,527 | documents | 44 |
| document_versions | 44 | seed_runs | 1 |

## Demo historical period; behavioural patterns

**1 October 2025 through 30 September 2026**, inclusive. Fixed seed `20251001`,
generator `1.0`; actual events do not depend on today's clock. Supplier reliability,
commercial price premiums, seasonal demand and Midlands handling pressure vary
with declared probabilities, quantities and dates. Some promises/payments remain
outstanding at the cutoff. No canned analytical conclusions are returned by API routes.

## Cross-domain scenarios and validation

All five scenarios reproduce through PostgreSQL joins:

- Supplier 1 → purchase order 1 → receipt 185 → movement 332 → shortage 16 →
  sales order 1 → dispatch 149 → incident/task 16. Procurement is 12 days late;
  customer dispatch is 10 days late, supported by an isolated product supply chain.
- Warehouse 1 → sales order 822 → escalated incident/task 1729 → GBP 120 overtime.
- Contract 1 targets 95% on-time receipt; 24 of 72 due orders meet it (33.33%).
- Invoice 37 exceeds purchase-line value by GBP 25 → open incident/task 1153.
- Operations owns 123 unfinished overdue corrective tasks across eight employees.

See `SCENARIO_VALIDATION.md` and `reports/stage1-validation.json` for evidence.
The report contains query plans; scenarios are not supplied to an AI model.

## Data integrity, determinism and seed safety

Full generated and PostgreSQL-loaded validation checks all foreign keys, order
statuses/quantities, receipt/dispatch chronology, stock prefixes and sources,
invoice/payment reconciliation, incident evidence, employee ownership, task
histories and document hashes. Corruption tests require explicit failures.

Logical fingerprint before and after native PostgreSQL restart:

```text
7ed73422d07ddb0528f0ce5641e1767cdef95aa698dfcddf8dc26aad68dae0b7
```

Same-seed regeneration, database-loaded comparison, and explicit reset/reseed tests
reproduce this digest; a different seed changes it. Money is normalized to two
decimals, rows have deterministic IDs/timestamps, and seed provenance is excluded
from its own hash. Future generated IDs/metadata would need explicit normalization.

Repeated seed is rejected before inserting anything. Seed/reset acquire a database
transaction advisory lock. Reset requires the exact database-specific confirmation,
is restricted to OpsPilot database names, and truncates only known application
tables without CASCADE. Restarts preserve data. No Docker volume has been deleted.

## FastAPI endpoints and local startup

Liveness `/health`, readiness `/ready`, `/api/v1/demo/summary`, catalogue lists,
incidents/tasks and typed purchase/sales timelines are implemented. Every business
endpoint queries real PostgreSQL. Lists are paginated and filters validated.
Transactions are read-only; there are no write routes. Database errors are sanitized.

Follow `README.md` for uv/Windows/Docker commands. The native validation API and
PostgreSQL cluster are now stopped. The Compose database owns 127.0.0.1:55432.
The Compose API is healthy on 127.0.0.1:8001, with container port 8000 unchanged.
Native PostgreSQL stop/start commands in `TESTING.md` are retained as historical
fallback instructions; do not start that cluster while Compose owns its port.

## PostgreSQL / Docker

PostgreSQL **17.11** was downloaded from the official EDB binary distribution;
the archive matched the vendor SHA-256 manifest. It runs from ignored project-only
folders with random ignored credentials and a loopback listener. It is not installed
as a system service. Native stop/start persistence and post-restart API readiness pass.

Compose defines `opspilot-stage1`, persistent project storage, PostgreSQL/API health
checks, loopback ports and a non-root API container. `docker compose config --quiet`
passes. Desktop, image build, both container runtimes, live API readiness and
database-volume persistence after restarting both services are verified.
pgvector compatibility is documented; no extension or embedding pipeline is installed.

## Query performance

Initial native seed/validate/insert/commit command: **14.740 seconds**. Container
database seed: **11.201 seconds**. Latest post-restart generation: **1.282 seconds**;
five-sample cross-domain join median: **98.378 ms**. In-process HTTP medians with
container PostgreSQL: health 3.221 ms; readiness 21.534 ms; summary 56.726 ms;
suppliers 14.929 ms; purchase timeline 29.840 ms. These include client/framework
overhead and are not production guarantees or live API-container HTTP measurements.
The JSON report retains EXPLAIN ANALYZE/BUFFERS evidence.

## Tests, Ruff / format and documentation

Final pytest/JUnit evidence is in `reports/pytest.xml`: **51 passed, zero skipped
in 58.32 seconds**,
using the Compose PostgreSQL container after restarting both services. No integration tests
are hidden/skipped. One upstream
Starlette warning deprecates its `httpx` test client adapter; runtime/API tests still
execute. Ruff lint and format checks pass. Offline migration SQL renders successfully.

README and six focused design/test documents describe implemented behavior and
limitations. This report and `FILES.md` provide the checkpoint inventory.

## Security / privacy and known limitations

All business data/documents are synthetic. `.env`, virtual environments, downloaded
binaries and local clusters are ignored. No credentials are committed. No actual
company or employee data was used. Only the standalone OpsPilot repository and its
project-local validation resources were modified.

This is a local demo with no authentication, RBAC enforcement, approval workflow,
audit service, frontend, LLM, analytics product, vector retrieval, background job
engine, reservation/transfer simulation, carrier arrival tracking or complete
accounting. Those are deliberately outside Stage 1. Database-owner maintenance can
still bypass application-level cross-row validators; future write services must
enforce all domain contracts and use least-privilege roles.

## Files created / modified; Git status and commit

The initial implementation created all deliverable files; see `FILES.md`. The
repository is standalone. The foundation checkpoint is `8e6685e`, **Establish
OpsPilot AI enterprise data foundation**. Recovery evidence was checkpointed as
`8d18987`. Closure changes only the approved Compose host port, documentation and
validation evidence; application/model/generator code remains unchanged.
The final handoff gives the actual commit hash and verified working-tree status.
There is no remote publication or automatic push. The report does not embed its
own commit hash because that would change the commit being identified.

## Final quality gates

| Required quality gate | Result |
|---|---|
| 1. Migrations pass | PASS — empty upgrade, head, drift and rollback/reapply |
| 2. PostgreSQL starts | PASS — native baseline and healthy Compose PostgreSQL 17.11 |
| 3. Seed completes | PASS — full atomic seed |
| 4. All domains populated | PASS — exact counts above |
| 5. Foreign keys / constraints | PASS — schema, validator and rejection tests |
| 6. Procurement / receipts | PASS — aggregate quantities and chronology |
| 7. Sales / inventory | PASS — dispatch quantities and historical stock |
| 8. Finance | PASS — exact invoice, purchase-line and payment reconciliation |
| 9. Tasks / incidents | PASS — real evidence links and ownership |
| 10. Document metadata | PASS — 44 versioned, hashed documents |
| 11. Scenarios queryable | PASS — five independent workflows |
| 12. Reproducibility | PASS — same seed, database and reset fingerprints |
| 13. Unsafe reseed rejected | PASS — no records changed |
| 14. Real PostgreSQL API | PASS — integration and live HTTP smoke tests |
| 15. API tests | PASS |
| 16. Ruff | PASS |
| 17. Tests without skips | PASS — 51 passed, zero skipped |
| 18. Docker Compose runtime | PASS — image build and both healthy services |
| 19. Restart persistence | PASS — both services restarted; API and database fingerprint reverified |
| 20. Documentation | PASS — actual implementation and limitations |
| 21. No committed secrets | PASS — ignore rules and generated-password scan |
| 22. Other projects/resources unaffected | PASS — only standalone project resources used |

**Remaining Stage 1 blockers: none.** All acceptance gates have actual successful
evidence. The preserved Docker socket directory remains intact for recovery
traceability; Desktop-wide stop/start durability is not claimed by these
Compose-service restart tests. No reset, prune, global configuration edit or
unrelated container stop was required. Stage 2 has not been started.
