# Retrieval evaluation

The committed `data/evaluation/retrieval.json` contains 42 manually curated cases
grounded in the unchanged corpus: 35 answerable cases and seven negative cases
(including a historical request before any document became effective). Labels
identify actual document codes, section names and source start lines. Cases cover
all eight policies, supplier names and identifiers, metadata-filtered contract
questions, paraphrases, four cross-document requests and unsupported topics.

The production retrieval modules never read evaluation labels or recognise these
questions. `app/knowledge/evaluation.py` runs the same search service for keyword,
vector and hybrid modes. The threshold and RRF configuration are shared across
the modes where applicable; results are not query-specific overrides. Cross-document
cases use explicit quoted phrase/OR syntax and retain separate source citations.
This measures that supported query form; it does not claim arbitrary multi-hop
question decomposition.

## Quality results

| Mode | Recall@1 | Recall@3 | Recall@5 | MRR@5 | Precision@5 | nDCG@5 | Citation accuracy | Negative accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| keyword | 0.5429 | 0.6000 | 0.6000 | 0.6000 | 0.1429 | 0.6000 | 1.0000 | 1.0000 |
| vector | 0.8143 | 0.8714 | 0.8714 | 0.8714 | 0.1886 | 0.8641 | 1.0000 | 1.0000 |
| hybrid | 0.8857 | 0.9429 | 0.9429 | 0.9429 | 0.2114 | 0.9429 | 1.0000 | 1.0000 |


## Metric definitions

Recall@k is the number of distinct relevant document/section labels retrieved in
the first k results divided by all relevant labels for that question. It therefore
credits cross-document coverage proportionally. MRR@5 uses the reciprocal rank of
the first relevant result, zero if none is present in the five returned results;
it is explicitly bounded rather than an unlimited-candidate MRR. nDCG@5 uses binary
relevance with logarithmic discount. Precision@5 divides relevant results by five
even when fewer than five passages are returned. Macro averages include only the
35 answerable cases. Negative accuracy is empty-evidence handling on seven cases;
negatives are not assigned perfect recall or mixed into MRR.

Citation resolution accuracy requires every returned citation to resolve to the
same original text with valid hashes and line positions. It measures provenance,
not whether a passage answers every part of a question. Labels are intentionally
conservative; another document may have partial related content without receiving
a relevance label for this test.

## Misses, ranking choice and limitations

Hybrid had the best measured recall/MRR on this set and remains the default.
It missed the labelled inventory-control policy for “How are backorders and
outstanding quantities recorded?” (returned the receiving policy instead), and
returned no evidence for the filtered supplier question “How many days from invoice
issue until payment?” The latter fell below the semantic gate and had no lexical
match. These are recorded false negatives, not suppressed cases. Explicit source
terms or identifiers and source preview remain useful for those questions.

Vector-only retrieval confuses similarly templated supplier agreements and exact
contract identifiers. Hybrid's lexical branch improves those cases. English AND
full-text queries often miss natural paraphrases, explaining lexical-only gaps.
No inference of superiority beyond this evaluation is justified.

This is a small, synthetic development evaluation with highly repetitive contract
templates, one actual version and one terms section per source. It is not a held-out
benchmark, production calibration or statistical-significance test. The same
configuration was assessed across all cases; more independent queries, nuanced
negative clauses, future real revisions and larger corpora need separate evaluation.
The 0.45 semantic gate is a heuristic and cannot establish legal support or complete
answerability. False positives and false negatives remain possible beyond these cases.

## Timing and plans

| Mode | Evaluation median ms | Evaluation p95 ms | First query ms | Warm Docker HTTP median ms |
|---|---:|---:|---:|---:|
| keyword | 12.877 | 18.388 | 40.681 | 17.658 |
| vector | 26.240 | 39.970 | 527.620 | 23.031 |
| hybrid | 28.429 | 33.728 | 30.971 | 24.683 |

Measured model cold initialization: 0.717 s. Source validation: 0.081 s; chunk generation: 0.073 s; embeddings: 1.321 s; full explicit rebuild: 1.810 s. Idempotent pass: 0.077 s with zero embeddings.

Post-restart context HTTP median: 104.128 ms, using 5395 WordPiece tokens for separate contract/policy evidence. Derived chunk table plus indexes: 778,240 bytes. API container memory sample after model use: 213.9MiB / 7.391GiB (entire container, not isolated model allocation).


Timings are local observations, not performance guarantees. Evaluation reports
per-query durations, the mixed-query median and nearest-rank p95 over 42 sequential
requests per mode. The first vector query includes initialization of the cached
model; subsequent queries are warm. The actual Docker HTTP acceptance separately
records three-sample medians and context latency. No network model download occurs
in either measurement. Index time excludes the initial weight download.

Saved `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` plans cover real lexical and exact
vector queries. At 44 rows, sequential scans/sorts are appropriate; the existence
of a GIN index does not imply the planner should use it for this corpus. No ANN
index or materialized view is justified. Search issues a fixed set of SQL queries
for index validity, metadata and bounded candidates, rather than one query per
supplier/document. Source hash/line verification performs bounded corpus file reads.

Reproduce with `uv run python -m scripts.evaluate_retrieval`. Complete case-level
scores, missed queries and durations are in `reports/stage3-retrieval-evaluation.json`;
index timings, plans and actual Docker persistence checks are in
`reports/stage3-validation.json`. The exact pinned model/runtime is described in
[RAG_PIPELINE.md](RAG_PIPELINE.md).
