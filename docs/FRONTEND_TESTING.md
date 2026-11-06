# Stage 6 testing and reproduction

Backend checks use the existing actual PostgreSQL test fixtures and restricted workflow login. Frontend component-level contracts test formatting and gateway admission. Playwright drives the production Compose app in a real installed Edge instance, with independently authenticated synthetic demo identities and actual database effects. No browser backend is mocked. Traces, videos and failure screenshots are disabled for credential entry; deliberate screenshots are captured only after safe rendering.

```powershell
./scripts/start_frontend.ps1 -Build
$env:PYTHONPATH='backend;.'
.venv/Scripts/python.exe -m pytest backend/tests -q --junitxml=reports/stage6-backend-pytest.xml
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/python.exe -m alembic current
.venv/Scripts/python.exe -m alembic check
cd frontend
pnpm install --frozen-lockfile
pnpm typecheck
pnpm lint
pnpm test
pnpm test:e2e
# Explicit restart acceptance, after all database tests have finished:
pnpm exec playwright test --config playwright.restart.config.ts
```

Run the explicit restart acceptance only after the complete PostgreSQL suite has finished. It checks active disposable-test connections before restarting only project db/api/frontend. It reuses a real browser session and checks persisted workflow state; the source and existing-workflow fingerprints are checked separately. Do not reset volumes or add a model to reproduce results.

The browser suite exercises real historical KPI values, date changes, supplier details, a real knowledge citation, deterministic investigation/Copilot, an end-to-end proposal/approval/receipt with different identities, idempotent replay, adverse role and request cases, and responsive/axe checks. Results distinguish first failed attempts, fixes, and final runs. See [Playwright installation and use](https://playwright.dev/docs/intro). `OPSPILOT_BROWSER_CHANNEL` may select a locally supported browser channel for the suite.


The preservation verifier uses the pre-frontend Stage 6 snapshot in
`.local-tools/stage6-baseline`. `python -m scripts.validate_frontend --capture`
creates it once on a fresh run and refuses to overwrite an existing snapshot.
`python -m scripts.validate_frontend` verifies the original data and prior row
hashes without modifying PostgreSQL. Run from the repository root with `PYTHONPATH=backend;.`.
