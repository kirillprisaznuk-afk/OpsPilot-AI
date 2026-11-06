# Local authentication and RBAC

Argon2id hashes passwords with the library defaults (64 MiB memory); only hashes are stored. Generated demo passwords are random and saved under ignored .local-tools/stage5-demo/accounts.json. No credentials or bearer tokens belong in reports, Git, logs or prompts. There are no default known passwords, public registration or automatic privileged user creation by inference.

POST /api/v1/auth/login returns a random 256-bit opaque bearer token. PostgreSQL stores only its SHA-256 digest, principal/version, creation/expiry and revocation. Sessions default to four hours (bounded configuration 1–12). Every request rechecks session expiry/revocation and current active/human principal/version; every privileged mutation rechecks current role/scope. Logout persists revocation. Role changes advance authz_version, invalidating old sessions and approvals.

Authentication uses persistent account and client-origin failure buckets: eight failed attempts per 15-minute window trigger throttling. Unknown-user authentication follows a dummy Argon2 path. Password verification concurrency is bounded. Forwarded client headers are not trusted. Cookie-only authentication is refused; no browser auto-attached credential or cookie CSRF path is introduced. Bearer holders must still guard against XSS/token theft in a future frontend.

| Role | Permissions |
|---|---|
| VIEWER | Read permitted workflow records |
| OPERATIONS_ANALYST | Read, capture evidence, prepare/revise/cancel own proposals |
| WORKFLOW_OPERATOR | Analyst functions plus submit and execute own approved proposals |
| WORKFLOW_APPROVER | Read and review another principal's proposals |
| WORKFLOW_ADMIN | Scoped administration and operational permissions, still no self-approval |

Assignments may cover one department or globally (NULL). Transfer requires permission for both departments. Detail reads enforce object scope; lists and aggregates filter scope before pagination/counting. Only proposer or scoped administrator submits/executes/revises/cancels a proposal. Administrative policy changes require global administration. No client-supplied actor identifier can impersonate a principal.

Bootstrap for an existing accepted Stage 4C database, PowerShell from repository root:

```powershell
uv sync --frozen
$env:PYTHONPATH='backend;.'
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m scripts.bootstrap_workflow
docker compose config --quiet
docker compose build api
docker compose up -d db api
```

Keep the existing .env, original volume, models and index. Do not reseed, reset or prune. Bootstrap provisions one restricted runtime login and six separate demo accounts, writes only ignored local configuration, refuses to overwrite existing identities, and prints no secrets. WORKFLOW_DATABASE_URL must use the non-owner login; there is no owner fallback. Compose uses WORKFLOW_DB_USER/PASSWORD with container port 5432; native uses host port 55432. API stays at 127.0.0.1:8001. This path requires no Ollama/model process or paid key.

For routine later startup use `docker compose up -d db api`. Retrieve only the needed local demo credential privately, log in, and keep the bearer in memory. OpenAPI /docs provides exact schemas. Trusted account recovery/provisioning remains a maintenance function; public password reset, enterprise SSO and MFA are not implemented.

References: [argon2-cffi password hashing](https://argon2-cffi.readthedocs.io/en/stable/howto.html), [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
