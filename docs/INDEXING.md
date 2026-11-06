# Local model and index maintenance

Run from the repository root with `uv sync --frozen` and:

```powershell
$env:PYTHONPATH = 'backend;.'
uv run python -m scripts.knowledge download-model
docker compose up -d db
uv run alembic upgrade head
uv run python -m scripts.knowledge verify-sources
uv run python -m scripts.knowledge index
docker compose up -d --build api
uv run python -m scripts.knowledge status
uv run python -m scripts.knowledge verify-citations
uv run python -m scripts.evaluate_retrieval
```

An existing Stage 1–2 installation must keep `.env` and the database volume and
must not reseed. Review [image compatibility and backup/rollback](STAGE3_DATABASE_CHANGE.md)
before first moving that database to the pinned pgvector image. A clean setup
must seed the migrated empty database before indexing, as shown in README.

Before the first image/migration change, capture the accepted running installation:

```powershell
uv run python -m scripts.prepare_knowledge_upgrade
```

This writes a custom-format PostgreSQL backup and business/analytics/resource
baseline inside ignored `.local-tools`. It refuses to overwrite an existing
preserved baseline or backup. A fresh `--output-dir .local-tools/new-checkpoint`
can record a later snapshot without changing the original. Validate restoration
in isolated infrastructure before applying a database image change.

`download-model` fetches only the pinned ONNX weights, tokenizer, model config
and model card to `.models/minilm` and validates their checksums. The first run
requires internet and about 91 MB disk space plus library/cache overhead; no paid
key is required. Subsequent normal requests never download anything. Docker mounts
this directory read-only at `/home/opspilot/models/minilm`. Host development defaults
to `.models/minilm`; `EMBEDDING_CACHE` can select a prepared compatible cache.

`index` acquires an application-specific advisory lock, validates all registered
versions/hashes/metadata and compares the manifest. Unchanged versions retain their
chunks and embeddings. Changed/new versions alone are generated and replaced.
Unregistered index rows are removed only during this explicit maintenance operation.
The summary includes examined/indexed/unchanged versions, chunk and embedding counts,
model configuration, source validation, chunk generation, embedding and total times.
An exception fails the command and rolls back its transaction; a previously committed
index remains visible. There is no partial publication or automatic startup rebuild.

```powershell
uv run python -m scripts.knowledge index --rebuild
```

Explicit rebuild atomically regenerates the derived index and is required for an
incompatible embedding/chunking configuration. It never regenerates business facts,
changes a contract or resets a database. Missing/changed files must be corrected or
registered deliberately; a hash mismatch is an error, not permission to overwrite
the authoritative hash. Incomplete stored version coverage requires explicit repair.

```powershell
uv run pytest -q --basetemp=.local-tools/pytest-stage3
uv run ruff check .
uv run ruff format --check .
uv run python -m scripts.validate_knowledge --restart
```

Tests create UUID-named isolated PostgreSQL databases, use rollback fixtures and
temporary documents, and drop only their test databases. The project-local pytest
temporary directory avoids this host's inaccessible system pytest temp directory.
The full suite includes all 149 Stage 1–2 cases; the schema/head assertions now
include migration 0003 and its tables. The guarded explicit reset command includes
both known retrieval tables in the same TRUNCATE list and still uses no CASCADE.
No reset/reseed is part of the Stage 3 demo upgrade or acceptance.

`validate_knowledge --restart` deliberately reindexes, checks idempotency, exercises
actual Docker HTTP endpoints, resolves all citations, compares the stored Stage 3
preflight business/analytics baseline, restarts only OpsPilot db/api, then checks
unchanged index publication/vectors, business records and unrelated resources.
Its environment-specific preflight and backup live in ignored `.local-tools`.
Normal indexing/status/search do not require that acceptance baseline. The script
writes separate Stage 3 evidence and does not overwrite Stage 1–2 reports.
