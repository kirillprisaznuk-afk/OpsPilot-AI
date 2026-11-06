# Citation and source model

Citation IDs are `kc_` followed by the 64-character chunk identity. That identity
binds document version, chunk ordinal, exact text hash and index configuration.
Unchanged indexing/rebuilds retain IDs. A source or configuration change can retire
old chunk IDs; resolving one then returns explicit 404 rather than another passage.

Every evidence item exposes document/version/chunk IDs, title, section path,
1-based inclusive source line range, effective date, supplier/department/contract
metadata, whole-source SHA-256, passage SHA-256, rank and retrieval method. The
source reference is a registered version API URL, never an arbitrary local path.
Markdown has no page numbers. The current terms sections begin at line 12.

`GET /api/v1/knowledge/citations/{citation_id}` finds the active registered chunk,
re-reads its registered source safely, checks the full file hash and requires the
exact original line range and passage hash to match the indexed text. It returns
`verified: true` only after those checks. Missing, altered or mismatched content
returns an error. Source verification is also performed before emitting search
evidence, so a stale excerpt cannot be presented as a verified quotation.

Document preview selects the latest effective version for `as_of`. The explicit
version route validates document ownership and rejects versions not yet effective
or published at that date. It allows deliberate inspection of an older version
without making it the active version in retrieval. Preview preserves original text,
registered metadata and actual line count. No route accepts a filesystem path.

Corpus resolution canonicalizes paths and symlinks, requires `.md` inside the
registered synthetic corpus and validates UTF-8/hash/size. Path traversal, malformed
IDs and unrelated version/document pairs are rejected. This protects file access;
it does not implement authentication or document-level RBAC.
