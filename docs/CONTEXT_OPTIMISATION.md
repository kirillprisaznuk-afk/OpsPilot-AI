# Local agent context optimisation — Stage 4B

Status: implemented and regression-tested; final live acceptance is blocked by
resource pressure. Smaller payloads are not, by themselves, proof of better answers.

## Transport and retained authority

The gateway still validates full typed service results. For local Ollama only,
`views.py` factors identical metric definitions (`time_basis`, `grain`,
`limitations`) into content-addressed entries. A reverse transformation must equal
the original payload. Exact values, units, denominators, dates, nulls, status,
relationships and source passages remain intact. The original evidence is retained
server-side and returned through the API. The existing 48000-byte result ceiling is
applied to the actual projected model transport; requests remain bounded by the
existing 120000-byte context ceiling. There is no silent truncation.

With candidate capability selection enabled, the model can choose up to eight
registered metric columns. This **focused view is intentionally not lossless**:
omitted column names are explicitly disclosed, canonical evidence remains complete,
and one expansion can expose additional columns. Entity identity, observation
periods, selected metric definitions and source qualifications are not shortened.
The ordinary lossless codec refuses to pretend it can restore a focused view.

Repeated successful calls reuse verified evidence. Repeated failed calls are
suppressed, with one corrected argument attempt per tool. Small standard schemas
keep the caller's established cutoff; advanced options require explicit model
selection/expansion. No date is fabricated to make a call fit.

## Candidate selection and final output

The initial selector receives all seventeen capability descriptions and required
arguments. It chooses at most six for detailed schema exposure. Selection and the
single optional expansion consume ordinary model rounds. The selector is the local
model, not a question-specific dispatcher. The server allowlist is unchanged.

Short-reference finalization receives the original question, server validation
feedback and a ledger of selected evidence. It does not replay the entire duplicate
tool transcript. The ledger retains scope/period/limitations, selected metric
metadata, actual subject identities, complete selected source text and typed links.
The original canonical evidence independently validates every selected reference.
There are no tools in this final request. Invalid findings can receive one model
correction within the existing time/token/round budget; application code never
repairs the model's prose or inserts guessed business facts.

Conversation memory retains selected verified metrics, subjects and validated
ranking order from completed responses. It does not promote previous model prose
or failed rankings into evidence. Follow-ups must obtain fresh current-run sources.

## Measurements and fallback

| Actual experiment | Observed result | Interpretation |
|---|---|---|
| Fresh original A02 | 27007 observed tokens, 20.772 s; four result-limit errors | Available data was inaccessible through repeated oversized results. |
| Projection-only A01 | 89700 tokens, 69.737 s; completed | Worse than previous 80979 / 62.640 s; no speed improvement claimed. |
| Projection-only A02 | First comparison succeeded; later timeout | Transport defect fixed; complete answer still failed. |
| Earlier selected-catalogue A23 | 4869 tokens, 44.130 s; correct absence, no invalid arguments | Fewer tokens/errors than prior 28131 / 13.797 s / three errors; slower under shared load. |
| Final candidate, 23 cases | NOT_RUN; memory admission blocked | Final end-to-end token reduction and semantic accuracy remain unmeasured. |

Historical traces show 20144 bytes for the full tool schemas and 37986 bytes for
the old final schema. New per-round diagnostics record actual input/output counts,
request/message/schema bytes, cache counters when provided, load/prompt/generation
durations and wall time. A timeout has incomplete usage: known counts are not the
whole failed request's token total. No missing count is replaced by an estimate.

`OLLAMA_COMPACT_TRANSPORT=false` restores the old transport. Candidate
`OLLAMA_TOOL_SELECTION` and `OLLAMA_REFERENCE_OUTPUT` default to **false** in code
and Compose; this local evaluation explicitly enables both in ignored `.env`.
Setting them false restores full catalogue/legacy finalization. OpenAI transport
is unchanged. The final Stage 4B report distinguishes implemented mechanisms from
measured live benefits.

## Autonomous measured extension

The short final ledger now factors identical metric definitions through the same
lossless codec, keeping canonical entries for independent resolution. Original
source text, qualifiers, periods, values/units/denominators and scope round-trip
exactly. Captured A01 ledger bytes fell 65034 to 55976 (13.93%); A02 fell 94295 to
79941 (15.22%). The final actual A01 used 25636 known tokens but failed missing
policy coverage. It is not a successful-answer efficiency gain. A02 was interrupted
by the RAM guard with incomplete usage. Raw evidence is in
`reports/stage4b-final-ledger-compaction.json` and the compact-ledger live report.

8K requests of 9963–29181 tokens failed explicitly; 32K trials did not prove stable
RAM or model quality. No silent truncation or dropped contractual qualification
was used. Parent evaluator imports are now lean, oracle embedding sessions exit
before inference, and prepared oracle reuse is explicit and provenance-hashed.
An oracle snapshot is valid only against its independently verified dataset/corpus.
