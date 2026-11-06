# Validation and testing

Run from the repository root with `PYTHONPATH=backend;.` and configured ignored
`.env`. Use `uv sync --frozen` first. PostgreSQL must be reachable; the test role
must be able to create databases. Tests fail explicitly when PostgreSQL is absent.
There are no SQLite substitutes or integration-test skips.

```powershell
uv run pytest -q --junitxml=reports/pytest.xml
uv run ruff check .
uv run ruff format --check .
uv run alembic check
uv run python -m scripts.validate
```

If pytest cannot open the shared Windows temporary directory, add
`--basetemp .local-tools/pytest-local` from the repository root. Use a different
unused directory for each parallel run.

The session fixture creates a UUID-named `opspilot_test_*` database, applies
migrations from empty, seeds and commits the full dataset. Test transactions
rollback individual mutations. Finalization drops only the fixture's exact database.
A separate isolated database exercises upgrade → downgrade to base → upgrade.

Coverage includes generated and PostgreSQL-loaded foreign keys, exact Decimal
finance, commercial/date/status relationships, full stock prefixes, source movement
reconciliation, payments, incidents, ownership, task history, document hashes,
same/different seed fingerprints, reseed rejection, explicit reset/reseed and
independent scenario values. Deliberately corrupted datasets must fail loudly.
Database tests exercise FK/check/trigger failures and deferred ledger completeness.
API tests verify exact entity values, filter counts, non-overlapping pagination,
timeline quantities, 404/422/503/405 behavior, readiness and read-only transactions.

`scripts.validate` compares the database against a freshly generated logical
fingerprint, verifies document bytes, prints concise scenario traces and measures
five samples of representative SQL/API calls. It saves medians and EXPLAIN ANALYZE
in `reports/stage1-validation.json`. API timings use in-process HTTP routing with
real PostgreSQL, not internet/network latency. Local timings are observations,
not service-level guarantees.

Initial validation used an official EDB PostgreSQL 17.11 portable runtime because
Docker Desktop failed on an inaccessible secrets-engine runtime socket. The native
runtime remains in ignored `.local-tools`, with its preserved project-only cluster
in ignored `.local-pg-validated`. Both the native cluster and native API are now
stopped. Random credentials remain only in ignored `.env`.

Docker Desktop has since recovered after its socket-only parent directory was
preserved intact under a backup name. Current tests run against temporary databases
on the healthy **Compose PostgreSQL container** at 127.0.0.1:55432: 51 passed, zero
skipped. Container database restart persistence and fingerprint checks pass.
The user-approved host API port is **8001**, mapped to container port 8000, preserving
the unrelated container's reservation on host 8000. Both Compose services are
healthy. Thirteen live HTTP checks passed before and after restarting both services,
including readiness, all domain counts/fingerprint, pagination, order timelines and
error/write rejection behavior. See `STAGE1_REPORT.md`
and `reports/docker-acceptance.json` for exact recovery actions and current gates.

The native fallback is historical validation infrastructure, not a new startup
architecture or required dependency. Its downloaded ZIP matched the vendor checksum.
Do not start it while Compose owns port 55432.

To stop the validation fallback before starting Compose on the same port:

```powershell
./.local-tools/pgsql/bin/pg_ctl.exe -D .local-pg-validated -w stop
```

To restart that existing local fallback without reseeding:

```powershell
./.local-tools/pgsql/bin/pg_ctl.exe -D .local-pg-validated -l .local-tools/postgres.log -o '-p 55432 -h 127.0.0.1' -w start
```

Do not share/commit these ignored runtime/data folders. Native PostgreSQL and Docker
database restart checks are reported separately. Docker API-service readiness and
restart also pass. Full final gate results are in `STAGE1_REPORT.md`.

## Local LLM migration regression

The default agent uses Ollama and requires no key. Offline pytest never downloads
or invokes a model. Protocol tests use explicit MockTransport fixtures; these do
not count as live model acceptance. Run actual model evaluation separately:

```powershell
uv run python -m scripts.evaluate_agent --live --limit 1 --output reports/local-agent-evaluation.json
uv run python -m scripts.evaluate_agent --offline --output reports/local-tool-evaluation.json
uv run python -m scripts.validate_agent --restart --baseline .local-tools/ollama-baseline/stage3-baseline.json --output reports/local-validation.json --retrieval-output reports/local-retrieval-regression.json
```

Capture a fresh read-only baseline/backup with `scripts.prepare_knowledge_upgrade`
using a new ignored output directory before a migration. The restart check touches
only OpsPilot db/api, compares fingerprints and stored vectors, verifies all prior
analytics/RAG responses and citations, and checks unrelated Docker resources.
The validation script does not infer agent-answer success from these regressions.

## Stage 4B closure commands

```powershell
$env:PYTHONPATH = 'backend;.'
uv run pytest -q --basetemp=.local-tools/pytest-stage4b-closure --junitxml=reports/stage4b-pytest.xml
uv run ruff check .
uv run ruff format --check .
uv run python -m scripts.evaluate_reliability --prepare-only --output reports/stage4b-oracles.json
uv run python -m scripts.evaluate_reliability --output reports/stage4b-live-evaluation.json
uv run python -m scripts.validate_agent --restart --baseline .local-tools/stage4b-baseline/stage3-baseline.json --output reports/stage4b-validation.json --retrieval-output reports/stage4b-retrieval-regression.json
# No package installation inside the production container:
docker compose exec -T api uv run --no-sync alembic current
docker compose exec -T api uv run --no-sync alembic check
```

Capture a fresh baseline/backup in a new ignored directory before modification;
do not manufacture a pre-change baseline from changed results. Stage 4B has 348
tests passing with real PostgreSQL and no integration skips. The evaluator measures
memory and labels unexecuted cases NOT_RUN. Follow [Windows instructions](LOCAL_MODEL_BENCHMARK.md)
for resources, candidate flags and warm-up. Oracle preparation/refusal routing do
not establish a successful model investigation. See [report](STAGE4B_REPORT.md).

## Autonomous acceptance follow-up

The frozen autonomous checkpoint ran **352 tests**, no errors/failures/skips, with
real PostgreSQL. Read `reports/stage4b-autonomous-pytest.xml` for exact timing.
Actual model trials are separate from these tests; the Stage 4B report records
critical failures, 23-row schedules and conditional follow-up NOT_RUN.

For reproducible guarded Windows evaluation, after independent baseline/oracle
verification, the repository now provides:

```powershell
uv run python -m scripts.evaluate_monitored --prepared-oracles reports/stage4b-oracles.json --output reports/guarded-live.json
```

This wraps the existing sequential evaluator; it is not a new startup architecture.
Standard 1.5 GiB RAM admission remains. Guard stops, incomplete usage and provider
loss never count as business correctness. There is no extra model installation,
paid API, mocked inference or completed-status quality score in this command.

## Stage 4C hybrid acceptance

Stage 4C preserves the original 352 tests and adds PostgreSQL/RAG hybrid regressions.
See [hybrid evaluation](HYBRID_AGENT_EVALUATION.md) for all eight original, fifteen
unseen and fifteen additional questions and the separate real-model gate.

```powershell
$env:PYTHONPATH = 'backend;.'
uv run pytest -q --basetemp .local-tools/pytest-stage4c-review --junitxml reports/stage4c-pytest.xml
uv run ruff check .
uv run ruff format --check .
uv run python -m scripts.evaluate_hybrid --output reports/stage4c-deterministic-evaluation.json
uv run python -m scripts.evaluate_hybrid --mode HYBRID_LOCAL --output reports/stage4c-hybrid-evaluation.json
uv run python -m scripts.validate_agent --restart --baseline .local-tools/stage4c-baseline/stage3-baseline.json --output reports/stage4c-validation.json --retrieval-output reports/stage4c-retrieval.json
docker compose exec -T api uv run --no-sync alembic current
docker compose exec -T api uv run --no-sync alembic check
```

Use the fresh pre-change baseline already captured for this checkpoint; on a future
change capture a new baseline/backup before editing. Runtime validation does not
reseed, reset the volume or imply successful LLM acceptance. Model mocking occurs
only in explicit unit tests; real HTTP fallback is labelled separately from model
interpretation. Safety admission requires actual host RAM/commit/VRAM and exact
GPU residency. Do not lower thresholds to make a benchmark run.


## Stage 5 workflow acceptance

Use [Stage 5 evaluation](STAGE5_EVALUATION.md) for restricted-login PG tests,
all eight real internal actions, adversarial approval/auth/RBAC cases and the
complete retained regression. Finish tests before running the explicit scoped
restart validator. Migration head is now 0004; historic Stage 4 validation uses
`--expected-migration 0004` when run on this upgraded database. A workflow
transaction never changes the accepted source fingerprint. Stage 5 requires no
model process, API key or inference. The blocked Stage 4C model gate remains
separately reported.

## Stage 6 browser acceptance

Follow [frontend testing](FRONTEND_TESTING.md) for the production Compose
build, actual Edge tests and the separate OpsPilot-only restart. The
[Stage 6 report](STAGE6_REPORT.md) links the browser evidence, screenshots,
PostgreSQL regression and preservation proof.
