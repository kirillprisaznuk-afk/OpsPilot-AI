# Stage 2 file inventory

Relative paths are rooted at the OpsPilot repository. This inventory describes the
validated Stage 2 checkpoint; runtime caches, `.env` and local diagnostic helpers
are ignored and excluded.

## Files created (30)

- `backend/app/analytics/common.py`
- `backend/app/analytics/contracts.py`
- `backend/app/analytics/facts.py`
- `backend/app/analytics/finance.py`
- `backend/app/analytics/fulfilment.py`
- `backend/app/analytics/incidents.py`
- `backend/app/analytics/insights.py`
- `backend/app/analytics/inventory.py`
- `backend/app/analytics/order_queries.py`
- `backend/app/analytics/overview.py`
- `backend/app/analytics/procurement.py`
- `backend/app/analytics/registry.py`
- `backend/app/analytics/relationships.py`
- `backend/app/analytics/suppliers.py`
- `backend/app/analytics/warehouses.py`
- `backend/app/analytics/workforce.py`
- `backend/app/api/analytics.py`
- `backend/tests/analytics_fixtures.py`
- `backend/tests/test_analytics_api.py`
- `backend/tests/test_analytics_numerical.py`
- `docs/ANALYTICS.md`
- `docs/METRICS.md`
- `docs/SQL_PERFORMANCE.md`
- `docs/STAGE2_FILES.md`
- `docs/STAGE2_REPORT.md`
- `docs/WORKED_EXAMPLES.md`
- `reports/stage2-pytest.xml`
- `reports/stage2-validation.json`
- `scripts/validate_analytics.py`
- `scripts/write_metrics.py`

## Files modified (7)

- `README.md`
- `backend/app/db/session.py`
- `backend/app/main.py`
- `backend/tests/conftest.py`
- `docs/ARCHITECTURE.md`
- `pyproject.toml`
- `uv.lock`

Stage 1 models, migrations, generator, synthetic corpus, Compose configuration and
acceptance artifacts remain unchanged. No dependency versions were added or changed;
`uv.lock` changes only the root project version to 0.2.0.
