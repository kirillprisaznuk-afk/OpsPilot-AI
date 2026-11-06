# Stage 5 files

Starting checkpoint: 3ba176eb7cb41e12b8db0a9e86a32ff9519fc800, clean tree. Branch: codex/stage5-workflow.

## New implementation

- `backend/app/workflow/__init__.py`
- `backend/app/workflow/actions.py`
- `backend/app/workflow/audit.py`
- `backend/app/workflow/auth.py`
- `backend/app/workflow/common.py`
- `backend/app/workflow/contracts.py`
- `backend/app/workflow/evidence.py`
- `backend/app/workflow/http.py`
- `backend/app/workflow/permissions.py`
- `backend/app/workflow/policy.py`
- `backend/app/workflow/queries.py`
- `backend/app/workflow/schema.py`
- `backend/app/workflow/service.py`
- `backend/app/workflow/unit.py`

- `backend/app/api/workflow.py`: authenticated API contracts and operation endpoints.
- `backend/alembic/versions/0004_workflow_governance.py`: frozen additive schema, default roles/policy.
- `backend/alembic/versions/0004_workflow_guards.sql`: invoker guards, lifecycle/immutability/execution restrictions.
- `backend/tests/test_workflows.py`: actual PostgreSQL/restricted-login API and security tests.
- `scripts/prepare_workflow_runtime.py`: explicit least-privilege PG provisioning.
- `scripts/bootstrap_workflow.py`: trusted generated local demo identities/configuration.
- `scripts/validate_workflow.py`: actual Docker HTTP workflow/rejection/concurrency/restart acceptance.

## Narrow existing changes

- `backend/alembic/env.py`: include independent workflow metadata.
- `backend/app/main.py`: new routers/middleware/safe errors, API version 0.5.0.
- `backend/app/services/demo.py`: readiness expects current head 0004.
- `backend/app/services/seeding.py`: refuse live Stage 5 reset; allow explicit disposable test reset with dependencies.
- `backend/tests/test_postgres.py`: retain checks, update expected head/schema metadata for additive 0004.
- `scripts/validate_agent.py`: explicit expected-migration option, default historic 0003.
- `docker-compose.yml`, `.env.example`: restricted workflow runtime configuration.
- `pyproject.toml`, `uv.lock`: Argon2id maintained hashing dependency only.
- `README.md`, `docs/ARCHITECTURE.md`, `docs/TESTING.md`: current stage/startup/acceptance links.

## Documentation and evidence

WORKFLOW_ARCHITECTURE.md, WORKFLOW_ACTION_REGISTRY.md, APPROVAL_ENGINE.md,
AUTHENTICATION_AND_RBAC.md, AUDIT_AND_EXECUTION.md, WORKFLOW_API.md,
STAGE5_SECURITY.md, STAGE5_EVALUATION.md, STAGE5_REPORT.md and this file.

Committed reports under reports/stage5-* preserve final test/live/regression results
and actual first-run failures. Ignored local files retain the pre-migration backup,
raw logs and generated credentials. No password, bearer, environment secret or model
weights are committed. No historical reports are rewritten. No model/provider,
original analytics/corpus, frontend or Stage 6 implementation is changed.
