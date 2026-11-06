# Stage 3 file inventory

Paths are relative to the repository root. Model weights, `.env`, backups,
machine-specific baselines and temporary test data remain ignored.

## Files created (30)

- `backend/alembic/versions/0003_knowledge.py`
- `backend/app/api/knowledge.py`
- `backend/app/knowledge/chunking.py`
- `backend/app/knowledge/citations.py`
- `backend/app/knowledge/context.py`
- `backend/app/knowledge/contracts.py`
- `backend/app/knowledge/corpus.py`
- `backend/app/knowledge/embeddings.py`
- `backend/app/knowledge/evaluation.py`
- `backend/app/knowledge/indexing.py`
- `backend/app/knowledge/schema.py`
- `backend/app/knowledge/search.py`
- `backend/app/knowledge/service.py`
- `backend/tests/test_knowledge.py`
- `data/evaluation/retrieval.json`
- `docs/CITATION_MODEL.md`
- `docs/INDEXING.md`
- `docs/KNOWLEDGE_ARCHITECTURE.md`
- `docs/RAG_PIPELINE.md`
- `docs/RETRIEVAL_EVALUATION.md`
- `docs/STAGE3_DATABASE_CHANGE.md`
- `docs/STAGE3_FILES.md`
- `docs/STAGE3_REPORT.md`
- `reports/stage3-pytest.xml`
- `reports/stage3-retrieval-evaluation.json`
- `reports/stage3-validation.json`
- `scripts/evaluate_retrieval.py`
- `scripts/knowledge.py`
- `scripts/prepare_knowledge_upgrade.py`
- `scripts/validate_knowledge.py`

## Files modified (13)

- `.dockerignore`
- `.gitignore`
- `README.md`
- `backend/alembic/env.py`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/services/demo.py`
- `backend/app/services/seeding.py`
- `backend/tests/test_postgres.py`
- `docker-compose.yml`
- `docs/ARCHITECTURE.md`
- `pyproject.toml`
- `uv.lock`

Original domain models, generator, corpus, analytics source and Stage 1–2 acceptance
artifacts are unchanged. Earlier migrations are unchanged. Modifications to existing
PostgreSQL tests update the exact head/table assertions for migration 0003; no prior
domain test is removed or weakened.
