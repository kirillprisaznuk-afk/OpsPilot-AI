# Grounding and answer verification

Only validated successful tool results create `ev_<run>_<ordinal>` evidence IDs.
Each retains tool name, validated arguments, established cutoff, typed payload and
an explicit untrusted-data classification. Provider-selected references must exist
in the current run; even a real document citation from another run cannot substitute
for evidence that was actually retrieved now.

Final output is a typed draft of findings, limitations and follow-up questions.
Every finding cites supporting evidence IDs. Numerical facts use JSON pointers to
actual Stage 2 metric objects or specific returned contract-assessment fields.
The server resolves those pointers and renders the original value, unit, observation
window, denominator/status and supporting evidence. It never computes a new company
KPI from model prose or raw rows. Unknown pointers, unsupported values and model-written
digits/common number words in narrative fail validation. Undefined/unavailable
metrics retain null status rather than becoming zero.

Contract terms use the Stage 3 citation map. The server checks the citation was
returned by a supporting tool, resolves source text/hash/line range and requires
the applicable version at the same request cutoff. Altered, unavailable, superseded
or unrelated sources fail. For exact clauses with numerical terms, the model may
request `quote_citation_ids`: the server inserts the complete verified passage,
with its original qualifications, rather than accepting model-written quotations.
Quotations remain untrusted source data. Metadata-only previews remain typed
registered-source evidence; narrow clause citations are obtained through retrieval.

Analytics and document evidence remain distinct. Metrics carry actual units/windows;
documents carry document/version/section/line/hash metadata. Supplier performance
versus target is an operational assessment, not proof of legal liability. Direct
recorded cost attribution stays distinct from indirect relationship graphs. Incident
relationships retain their Stage 2 explicit-link/simulated-scenario labels; generic
causation is not inferred by the server.

Ambiguous/missing resolved entities, no relevant knowledge, unavailable history,
unsupported finance concepts, malformed output and limited execution have explicit
statuses. Completed responses require supported findings. Valid partial evidence
is returned after a limit or provider error, without presenting a truncated
investigation as complete. No generic recommendation is forced into every answer.

These checks establish provenance, scope and faithful numeric projection. They do
**not** prove full semantic entailment of unrestricted narrative, correct initial
entity interpretation, a complete answer or legal conclusions. Numerical-prose and
false-action phrase guards are conservative checks with possible false positives/
negatives. Real-model evaluations and human review remain necessary. No numerical
confidence percentage or overall AI accuracy is invented.

## Stage 4B typed-reference profile

Optional short supports resolve to actual subjects, metrics, documents and typed
links in canonical evidence. Row metrics need their own subject; an aggregate
cannot become one supplier's fact, nor another supplier's contract support it.
Observed/target comparisons need both metrics with compatible scope and direction.
Ranking requires actual comparison order and criterion; verified identities/ranks
are rendered server-side. Supplier agreements and customer promises stay distinct.

Association, possible explanation and simulation-supported causality are separate
claim types. A positive causal chain needs actual simulation-labelled records.
Policy timing cannot create a prohibition on other action or automatic penalties.
Complete verified source quotations retain numerical terms and qualifications.
Natural qualitative generation replaces the exclusion grammar in this candidate
profile only. Independent guards reject tested malformed prose, quantity paraphrases
and misspellings; conservative English checks still have false positives/negatives.
[Live semantic review remains required](STAGE4B_REPORT.md), beyond provenance.
