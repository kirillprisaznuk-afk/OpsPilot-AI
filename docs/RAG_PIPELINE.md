# Retrieval and context pipeline

## Parsing and chunks

Sources must resolve inside the registered synthetic Markdown directory, decode
as UTF-8 and match their stored SHA-256. Parsed title, ID, type, version, effective
date, department and contract reference must match registered metadata. LF and CRLF
are supported without changing the original bytes used by source citations.

The inspected corpus contains one `Instructions and terms` section per document.
All 44 clauses fit intact: current embedding inputs contain 36–129 WordPiece
tokens including title and section context. For these concise sources a single
section per chunk preserves every qualifier and costs less context than artificial
overlap. There is no padding to a nominal 200–450-token target.

For longer sections, packing splits only between complete paragraphs near a
240-token target, with an absolute 256-token model limit. An oversized standalone
paragraph is rejected for source review rather than cut through an obligation.
Nested headings, stable order and exact contiguous line ranges are retained.
Chunks do not overlap. Their SHA-256 identity includes version ID, ordinal, text
checksum and embedding/chunking configuration. No Markdown page numbers are invented.

## Embeddings

The real [all-MiniLM-L6-v2 model](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
is Apache-2.0 licensed and produces 384 dimensions. Revision is pinned to
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. The unquantized ONNX weights are
90,405,214 bytes, about 90.4 MB, for a 22.7-million-parameter model. Runtime
resident memory is measured separately in the acceptance report; file size is
not a memory guarantee.

ONNX Runtime CPU inference uses two intra-op threads, attention-mask mean pooling
and L2 normalization. Query and document embeddings share the same provider and
configuration; cosine distance is PostgreSQL `<=>`. Pinned file checksums cover
weights, tokenizer and model configuration. Exact dependency versions are locked
in `uv.lock` and saved in the acceptance report. This direct ONNX implementation
uses the model's documented pooling method without installing PyTorch.

Tokenizer truncation is disabled explicitly. Oversized embedding input fails
instead of dropping qualifiers. Reproducibility tests use a numerical tolerance,
not a cross-platform binary vector hash. Configuration changes require explicit
reindexing; incompatible model vectors are never merged. Model files download only
through `download-model`; they are ignored by Git and Docker build context.

## Search, applicability and fusion

Every request selects at most one effective version per document: the latest
effective date/version whose publication and effective dates are no later than
`as_of`. Only then are whitelisted filters applied. Explicit older version filters
cannot silently insert a superseded version into current context. Preview routes
can inspect an explicit older version with its effective metadata.

Default `as_of` is 2026-09-30, independent of the computer clock. All 44 real
versions became effective 2025-10-01. Historical multi-version behavior is tested
with temporary revisions in isolated databases; additional production revisions
are not invented. Master titles/assignments have no independent revision history.

Keyword mode uses English generated `tsvector`, `websearch_to_tsquery` and
`ts_rank_cd`. Search text includes the real code, contract reference, title,
supplier name and section. Natural-language keyword queries use PostgreSQL's AND
semantics; quoted phrases and `OR` support exact identifiers and cross-document
requests. SQL data is bound, including vectors, terms and eligible version IDs.

Vector mode performs exact cosine search. Hybrid mode retrieves at most 100
candidates from each engine, deduplicates chunk IDs and sums `1/(60+rank)`.
Ties use stable chunk IDs. Raw lexical and cosine scores remain separate; they
are not added together. A lexical match qualifies as evidence; vector-only
candidates need cosine similarity >=0.45. This is a cautious heuristic, not a
calibrated probability or a guarantee of answer completeness. It has observed
false negatives, reported in the evaluation. Hybrid is the default because the
shared evaluation measured the best recall/MRR for that configuration.

## API and evidence boundaries

GET routes under `/api/v1/knowledge`: `documents`, `documents/{id}`,
`documents/{id}/versions/{version_id}`, `citations/{citation_id}`, `status`.
Read-only POST routes: `search` and `context`. There is no public indexing/upload.

Search body: `query` (2–512 characters), `mode` (`keyword|vector|hybrid`), `top_k`
(1–20), `as_of` and `filters`. Filters: supplier ID, policy/supplier-agreement type,
department ID, document ID, version ID, contract ID and exact contract reference.
Positive IDs are PostgreSQL-int bounded; unknown structured request fields and
invalid dates fail 422. Source IDs must belong together. Lists use limit 1–100
and bounded offset.
Missing/inapplicable sources return structured 404; corrupt/unavailable sources
or an incompatible index return structured 503. No paths or SQL stack traces are
returned. Nonmatching filters yield an empty applicable population.

Search distinguishes evidence found, no lexical matches, low semantic relevance
and no effective documents. `insufficient_evidence` marks absence of qualified
evidence; a false value does not establish that every requested fact is answered.
Sources describe scope and version explicitly. Different suppliers, general
policies and contractual terms are never merged into a fabricated common policy.
There is no legal conflict adjudication or inference of absent penalties.

Context accepts the same fields plus optional business-context metadata and a
128–8192-token budget. Business context is preserved as caller data and cannot
alter filters. Complete passages are selected, deduplicated and ordered by source.
The full serialized envelope, evidence metadata, citations and trust boundary are
counted using the real MiniLM WordPiece tokenizer. This is not a future LLM's token
count. Over-budget chunks are omitted whole and counted; a budget too small even
for the envelope returns 422. Coverage explicitly remains completeness-unverified.

All passages carry `untrusted_source_data`. Independent trust metadata says source
text cannot authorize actions, change filters, override instructions or request
secrets. A diagnostic pattern flag can surface some suspicious passages; it is
not a complete injection detector. Every passage remains untrusted regardless
of that flag. No component executes source text or calls tools/LLMs. Tests index
malicious temporary passages in isolated PostgreSQL, preserve the requested scope
and return the attack as quoted data. Future Stage 4 must enforce these boundaries
when constructing model messages; Stage 3 does not claim agent-level protection.
