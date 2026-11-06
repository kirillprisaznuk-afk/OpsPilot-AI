# Stage 6 files

Starting checkpoint: `68a76ec2189a554819730235540aac45d8fa5815`. Local branch: `codex/stage6-frontend`.

- `frontend/`: package lock and strict TypeScript/Next/Tailwind configuration, production Dockerfile, app routes and browser gateway, typed API library, encrypted frontend session store, domain modules, visual tokens, unit and Playwright tests.
- `backend/app/api/workspace.py`: authenticated and scope-checked read projections. `backend/app/main.py`: router registration. `backend/app/workflow/http.py`: apply protected response boundary to projections.
- `backend/app/api/workflow.py`, `backend/app/workflow/queries.py`: additive search/priority/audit read filters. No executor, approval rules, migrations, grants or source calculations changed.
- `backend/tests/test_workspace.py`: actual restricted-login PostgreSQL read projection tests.
- `docker-compose.yml`, `.dockerignore`, `.gitignore`: one loopback frontend service, a scoped session volume and safe build/working-tree exclusions.
- `scripts/start_frontend.ps1`: project-only Windows launcher with explicit readiness checks.
- `scripts/validate_frontend.py`: original source, existing workflow/auth/audit rows, index and Docker resource preservation proof.
- `docs/FRONTEND_*`, `docs/DESIGN_SYSTEM.md`, `docs/STAGE6_*`: implementation, user instructions, visual review, measured acceptance.
- `reports/stage6-*`: preserved results and selected rendered screenshots. Local session storage, database backups, private credentials, model weights and temporary browser/build artifacts are excluded.
