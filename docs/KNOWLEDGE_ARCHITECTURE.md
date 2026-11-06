# Enterprise knowledge architecture

Stage 3 adds retrieval inside the existing FastAPI modular monolith. It produces
source evidence and bounded context; there is no LLM, agent, answer generator,
workflow, frontend, upload API or document-level authorization.

The authoritative corpus is the existing 36 supplier agreements and eight policies
under `knowledge/synthetic_documents`. Document identity, owning department and
optional supplier contract come from the business tables. Supplier references are
joined through contracts. Version ID, effective date, path and SHA-256 come from
`document_versions`. Supplier master records are not copied into another master.

`app/knowledge` separates contracts, safe corpus access, section chunking, local
embeddings, transactional indexing, retrieval/ranking, citations, context assembly,
metadata services and offline evaluation. Thin routes live in `app/api/knowledge.py`.
There are two derived tables: `knowledge_indexes` records one active configuration,
version manifest and publication time; `knowledge_chunks` stores source ranges,
text hashes, vectors and generated English tsvectors. Separate SQLAlchemy metadata
keeps these tables outside the original business-data fingerprint. Alembic compares
both metadata collections. No domain table or earlier migration is rewritten.

PostgreSQL 17.11/Bookworm now runs the pinned pgvector 0.8.7 image on the original
volume. See [the backup, compatibility and rollback record](STAGE3_DATABASE_CHANGE.md).
Migration 0003 installs the extension and two tables; downgrade drops only those
tables and deliberately retains the potentially shared extension. A GIN text-search
index and version lookup index support lexical/filter operations. Vector retrieval
uses exact cosine search: 44 chunks do not justify an approximate-nearest-neighbor
index or another vector database.

API sessions remain repeatable-read/read-only, including structured search/context
POSTs. Writes occur only through explicit local maintenance commands. Indexing
locks its own transaction, validates sources and generates replacements before
publishing them atomically. Readers see one committed index snapshot. Startup does
not download weights, migrate, seed, rebuild or invoke a model. The first semantic
request initializes the already-cached CPU model once per process.

The Docker API mounts only the ignored model directory read-only; corpus sources
remain part of the application image. Routes resolve registered IDs, never supplied
filesystem paths. Missing/corrupt sources, incompatible embeddings and invalid
citations return explicit sanitized errors. Metadata filters select business scope;
they are not permissions. All listeners remain on localhost and the corpus synthetic.

See [pipeline semantics](RAG_PIPELINE.md), [citations](CITATION_MODEL.md),
[maintenance](INDEXING.md) and [measured evaluation](RETRIEVAL_EVALUATION.md).
