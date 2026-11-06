# OpsPilot AI — Stage 3 acceptance report

**STAGE 3: COMPLETE. READY FOR STAGE 4: YES.** Stage 4 has not started.
This checkpoint implements retrieval evidence and context, with no LLM, generated
answer, agent, workflow, frontend or public upload feature.

## Knowledge architecture, corpus and parsing

The FastAPI modular monolith now has a dedicated `app/knowledge` layer with typed
contracts, corpus validation, chunking, local embeddings, transactional indexing,
PostgreSQL search/fusion, citations, context assembly, source/status services and
offline evaluation. Business KPI computation remains in the existing SQL analytics
layer. See [KNOWLEDGE_ARCHITECTURE.md](KNOWLEDGE_ARCHITECTURE.md).

All **44 documents and 44 actual version records** are accounted for: **36 supplier
agreements and eight policies**. Original content, hashes, contract terms, generator
and document metadata were preserved. No alternate corpus or historical revisions
were manufactured. UTF-8 and LF/CRLF parsing preserves exact source bytes, titles,
section paths, version/effective dates and business entity references. Metadata
and whole-file hashes validate against their authoritative registrations.

## Chunking and total chunk count

The resulting index has **44 chunks**. Each short real terms/policy section stays
intact, with 36–129 model tokens including title/heading context. Section boundaries
and exact inclusive Markdown line offsets are retained; the terms section begins
at line 12. Stable IDs bind version, ordinal, passage hash and configuration.
Longer sections use whole-paragraph packing near 240 tokens; an oversized single
paragraph fails explicitly at the 256-token limit. No clause is silently truncated,
no page numbers are invented and no overlap duplicates are generated.

## PostgreSQL, pgvector and migrations

The downloaded, digest-pinned pgvector image was verified to run the **same
PostgreSQL 17.11/Bookworm Debian build** as the accepted database, with **pgvector
0.8.7**. The original named volume, database, credentials and loopback port remain.
A 627,190-byte custom-format pre-upgrade backup was restored into isolated temporary
infrastructure before changing the accepted container. Upgrade/downgrade/re-upgrade
passed there with preserved original business counts and fingerprint provenance.
The temporary validation container was subsequently removed; its original backup
is preserved locally and ignored by Git.

Alembic is now **0003 (head)**; schema drift check passes. Migration 0003 adds the
extension and **two derived tables**, without changing existing domain tables or
earlier migrations. Separate retrieval metadata preserves the original fingerprint
population. The database as a whole has changed: it now contains retrieval storage.
The guarded reset/seed compatibility list includes the new tables explicitly and
continues to use no CASCADE; no demo reset or reseed was performed.

The image digest, backup process, tested compatibility and rollback procedure are
documented in [STAGE3_DATABASE_CHANGE.md](STAGE3_DATABASE_CHANGE.md).

## Embedding model and consistency

Real CPU inference uses `sentence-transformers/all-MiniLM-L6-v2`, exact revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, **384 dimensions**, Apache-2.0,
unquantized ONNX, attention-mask mean pooling, L2 normalization and cosine distance.
Weights, tokenizer and model-config SHA-256 values are pinned and checked.
Tokenizer truncation is explicitly disabled; document and query inputs share the
same configuration and reject over-budget inputs. Real inference, normalization,
semantic similarity and numerical reproducibility execute in the tests.

Locked libraries: ONNX Runtime 1.31.1, tokenizers 0.23.3, NumPy 2.5.4, pgvector
Python 0.4.2 and huggingface-hub 1.33.0. Model download is explicit and public; no paid
API key is required. Cached weights are ignored and mounted read-only into Docker.
Startup and normal requests never download or automatically reindex. The first
semantic request initializes cached weights once per process. Incompatible model
configuration requires explicit rebuild rather than mixing vectors.

## Indexing pipeline and idempotency

Discovery, source/metadata validation, section parsing, embedding generation,
storage, provenance and count verification execute under one publication transaction
and an indexing-specific advisory lock. Replacements are generated before existing
rows are removed. Failure rolls back publication, preserving the committed index.
Changed versions alone are replaced where configuration remains compatible.

The explicit rebuild generated **44 real embeddings**. The following unchanged
pass examined 44 versions, retained all 44 and generated **zero embeddings**.
Rebuild IDs remained stable and stored vectors matched within the documented
numerical tolerance. Tests also cover incremental one-version replacement,
incompatible configuration, deliberate failure, empty/missing/malformed sources,
partial stored coverage and PostgreSQL rejection of incorrect vector dimensions.
Controlled maintenance commands and their measured summaries are described in
[INDEXING.md](INDEXING.md). The delivered backup command also executed successfully
in a fresh ignored directory and refused to overwrite its preserved output.

## Full-text, vector, hybrid and business metadata filtering

Keyword retrieval uses real English tsvector/websearch queries, ts_rank_cd and a
GIN index. Semantic retrieval uses real query embeddings and exact PostgreSQL
pgvector cosine ordering. Hybrid uses **Reciprocal Rank Fusion, k=60**, on up to
100 candidates per method, deduplicates chunk IDs and breaks ties stably. Raw
lexical/cosine scores remain visible separately. No query-to-document mapping or
evaluation-label lookup is used in production.

Supplier, document type, department, document/version ID, contract ID and contract
reference filters are controlled and parameterized. Latest effective/published
version is selected as-of the requested date before filtering. Default is
**2026-09-30**, independent of current clock time. A pre-2025-10-01 request returns
no effective documents. Temporary multi-version tests verify historical selection,
supersession and no leakage from backdated-but-not-yet-published versions.
Metadata filters do not constitute authentication or RBAC.

## Citations, source preview and context builder

Every result contains real document/version/chunk identity, heading path, inclusive
source lines, hashes, metadata, effective date, retrieval method and rank. Stable
`kc_<chunk-id>` citations resolve through a bounded registered-ID endpoint. All
**44 citations** resolved through actual Docker HTTP, with exact source text/hash
and line verification. Corrupt passage/scope and invalid-ID tests fail explicitly.
Source preview validates document/version ownership and date applicability, and
never accepts a path or exposes arbitrary application files. See
[CITATION_MODEL.md](CITATION_MODEL.md).

The context builder returns original question, optional caller context, separately
cited complete passages, metadata, provenance, coverage and trust instructions.
It counts the full serialized bundle with the actual WordPiece tokenizer, omits
over-budget passages whole, preserves source order and reports omissions. Its
tokenizer is identified explicitly rather than represented as a future LLM tokenizer.
The live multi-document bundle contains contract and procurement-policy evidence
with separate citations and fits the requested 8,192-token budget. No final answer
or fabricated merged policy is generated.

No-match, low-relevance and no-effective-document states are distinct. Source
unavailability, invalid input and incompatible index states return structured
errors. Evidence presence does not claim complete answerability. Explicit trust
metadata makes every passage untrusted data; it cannot change filters, request
secrets, authorize tools or trigger actions. Real isolated PostgreSQL tests index
malicious temporary passages and return their text without granting authority.
The diagnostic suspicious-text flag is limited; Stage 4 must enforce the boundary
when constructing model messages. This is not a claim of agent-level injection immunity.

## Retrieval evaluation and multi-document evidence

The independent evaluation has **42 cases**, 35 answerable and seven negative,
covering all eight policies, supplier terms/names/identifiers, semantic paraphrases,
historical applicability and four explicit cross-document requests. Labels identify
actual document/section/line evidence and remain separate from production search.

| Mode | Recall@1 | Recall@3 | Recall@5 | MRR@5 |
|---|---:|---:|---:|---:|
| Keyword | 0.5429 | 0.6000 | 0.6000 | 0.6000 |
| Vector | 0.8143 | 0.8714 | 0.8714 | 0.8714 |
| Hybrid | 0.8857 | 0.9429 | 0.9429 | 0.9429 |

Citation accuracy and no-answer accuracy were **1.0 for all three modes** on this
set. Hybrid is the evidence-supported default. Its two labelled misses remain
reported: the inventory backorder paraphrase retrieved the receiving policy, and
the filtered invoice-payment-period question returned insufficient evidence.
No cases were suppressed or special-cased. Cross-document OR/phrase requests
retrieve separate contractual and internal-policy sources. More general automatic
multi-hop question decomposition is not claimed.

Precision@5, nDCG@5, complete per-query results, metric denominators and limitations
are in [RETRIEVAL_EVALUATION.md](RETRIEVAL_EVALUATION.md) and its JSON artifact.
This small repetitive synthetic development set is not a held-out benchmark or
statistically significant proof of general retrieval quality.

## Index performance, search latency and plans

Final recorded cold model initialization was **0.717 s**; source validation
**0.081 s**, chunk generation **0.073 s**, embedding generation **1.321 s** and
explicit full rebuild **1.810 s**. Unchanged indexing took **0.077 s** with zero
embedding work. These exclude the first model download.

Post-restart three-sample Docker HTTP medians were **17.658 ms keyword**, **23.031 ms
vector**, **24.683 ms hybrid**, and **104.128 ms context**. The derived chunk table
plus indexes occupied **778,240 bytes** at measurement. Whole API-container memory
sample after model use was **213.9 MiB**. These are local observations, not SLAs.
Evaluation separately reports mixed-query median/p95 and first-query cold effects.

Actual EXPLAIN ANALYZE/BUFFERS JSON plans are retained. Exact sequential vector
search and small-table text scans/sorts are appropriate for 44 chunks; no ANN,
Redis, external vector database, materialized view or speculative optimization
was added. SQL round trips are fixed by operation, not one query per source.

## Persistence, business fingerprint and Stage 2 regression

Only OpsPilot db/api were restarted. Index publication timestamp, configuration,
44 IDs, stored vectors and counts stayed unchanged; no startup indexing or chunk
duplication occurred. Retrieval, context and citations worked after restart.
The original business/corpus fingerprint was independently recalculated before,
after and at final deployment:

```text
7ed73422d07ddb0528f0ce5641e1767cdef95aa698dfcddf8dc26aad68dae0b7
```

All five Stage 1 scenarios remain valid. All **ten complete live analytics response
bodies** matched the captured accepted Stage 2 baseline before/after restart and
at the final deployment, including numerical metric values and investigations
covered by the full regression suite. No operational records were regenerated.
Stage 1–2 source, corpus and acceptance artifacts remain preserved.

## PostgreSQL / Docker, tests and quality gates

Both final Docker services are healthy on the original localhost ports. The
original database volume is retained. All **ten unrelated containers** retain
identity, image, state and start/finish timestamps; pre-existing volume/network
names/IDs remain present. No global reset, prune, unrelated stop or deletion occurred.
The backup restore container created solely for this task was safely removed.

**182 tests passed, zero failures/errors/skips**, including all 149 prior cases
and **33 new knowledge cases**. Tests use real PostgreSQL, real model embeddings,
rollback mutations and UUID-isolated databases. Exact schema/head assertions were
updated for 0003 and its tables without weakening prior domain assertions. There
are no orphaned test databases. One existing Starlette/httpx deprecation warning
remains. Ruff lint and formatting pass; deployed Python source hashes match the
validated workspace; runtime transactions are read-only/repeatable-read.

All requested Stage 3 gates have executed evidence. Machine-readable runtime,
backup, source, persistence and test facts are in `reports/stage3-validation.json`;
pytest evidence is in `reports/stage3-pytest.xml`; retrieval scores/plans/timings
are recorded separately. Original Stage 1–2 reports were not overwritten.

## Documentation, limitations, files and Git

The five requested focused knowledge documents, database-change record, README
and general architecture describe implemented behavior. Sources remain synthetic;
credentials, `.env`, weights, backups and local caches are ignored. There is no
production authentication, document-level RBAC, public upload, legal interpretation,
answer generation or Stage 4 implementation. Version history exists only in tests
beyond the corpus's actual single revisions. Ranking/insufficient-evidence heuristics
have measured false negatives and cannot guarantee completeness or confidence.

Created/modified paths are listed in [STAGE3_FILES.md](STAGE3_FILES.md). Stage 1–2
history, including Stage 2 `81cff76`, is preserved. The local checkpoint message is
**Implement OpsPilot enterprise knowledge retrieval and RAG foundation**. Its actual
hash is reported in the handoff rather than embedded in the commit it identifies.
No remote or public push is created. **Remaining Stage 3 blockers: none.**
