# Local installation on Windows

Use PowerShell 7 on Windows, Docker Desktop with Compose v2, and uv. Allow internet access on first setup for locked Python/Node packages, the container images and the public pinned MiniLM embedding model. The app runs locally after setup. You do not need Ollama, an account with an AI provider, an API key, or a host Node installation for normal use.

## Fresh checkout

Run from the repository root. Leave `.env` absent so the launcher can create it.

```powershell
./scripts/opspilot.ps1 Setup -Open
```

The default UI is [127.0.0.1:3106](http://127.0.0.1:3106). The API and PostgreSQL are bound to loopback ports 8001 and 55432. Setup refuses existing local configuration, account files, named database/session volumes, existing project containers, or occupied ports. It migrates, seeds and indexes a new database, creates six synthetic accounts, and waits for the three services. Account passwords are in the ignored local file `.local-tools/stage5-demo/accounts.json`. Open that file in your editor and enter the exact account name in **Username**.

## Existing installation

```powershell
./scripts/opspilot.ps1 Start -Open
./scripts/opspilot.ps1 Status
./scripts/opspilot.ps1 Stop
```

Use `Start -Build` after a source change. The prior `./scripts/start_frontend.ps1 -Build -Open` entry point calls the same launcher. Stop retains the project volumes. Status checks the three services, sign-in, knowledge index, restricted workflow connection and optional Ollama reachability.

## Separate demo installation

Use a second checkout so model cache and credential files are separate. Choose a unique project and free loopback ports. An example:

```powershell
./scripts/opspilot.ps1 Setup -Project opspilot-demo -WebPort 3118 -ApiPort 8018 -DbPort 55448 -Open
```

Subsequent commands read that checkout’s configuration. For a demo you intend to discard, first inspect the exact project name and the two named volumes. Use `docker compose --project-name opspilot-demo down --volumes` from **that disposable checkout only**, after confirming those are the demo resources. Never use this command for the primary installation. [Demo journey](DEMO_GUIDE.md)

## Recovery and existing database upgrades

- If Docker or a port is unavailable, correct the reported problem before running Setup. If Setup already created `.env`, retain it. Do not recreate passwords or delete a populated volume.
- If downloading dependencies failed before initialization, rerun the failed maintenance step with the generated configuration. From the checkout set `$env:PYTHONPATH = 'backend;.'`, then run `uv sync --locked` and `uv run python -m scripts.knowledge download-model`. The cache uses the repository’s `.models/minilm` directory. Use `docker compose up -d --wait db` only for the configured project.
- For a verified new empty database, the remaining steps are `uv run alembic upgrade head`, `uv run python -m scripts.manage seed`, `uv run python -m scripts.knowledge index`, and `uv run python -m scripts.bootstrap_workflow`, followed by `Start -Build -Open`. The seeder refuses nonempty data and the bootstrap refuses to overwrite existing principals. If source data was already seeded, use `scripts.manage verify` and skip seeding. If the account file is missing from an established installation, recover it from your private backup rather than guessing or resetting credentials.
- For a planned existing schema upgrade, back up that installation first and inspect `uv run alembic current`. The release expects head 0004. Run only the documented required migrations and keep the original data, corpus and credentials. Normal Start does not migrate or seed.

If PowerShell blocks a script, inspect it and use the organization’s approved way to run it. The launcher does not modify execution policy or system-wide Docker configuration.
