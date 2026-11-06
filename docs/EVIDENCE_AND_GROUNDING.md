# Evidence and grounding

Canonical tool DTOs remain separately available in `evidence`. The graph contains
stable current-run fact IDs, canonical evidence IDs/pointers, source tools, argument
scope, subject provenance, metric metadata, observation windows and verification
state. Semantic duplicate selections are removed; exact source passages retain all
clauses. Graph edges distinguish subject scope, document scope and typed recorded
relationships. No LLM transcript is required to calculate a business answer.

Verification is independent of the language model:

1. Match every selected value, unit/metadata, source tool, scope and window to the
   canonical current-run result. Contract display objects copy the actual scalar
   fields and observed denominator; they do not recalculate KPIs.
2. Bind metrics to their actual supplier/entity or full scoped aggregate. Do not
   promote a supplier obligation to a customer dispatch promise.
3. Verify every selected metric/entity/relationship through the existing strict
   grounding validator, in bounded batches; no extra relationships are marked
   verified merely because the first page passed.
4. Resolve every document citation from the stored index and registered Markdown,
   independently checking source/text hashes, effective version, exact passage,
   displayed metadata and source identity. A forged retrieval payload cannot replace
   the registered text or its supplier/title/code.
5. Render only facts that passed verification. A failed graph never leaks its
   unverified numbers or quotes through the fallback composer.

Observed percentages preserve numerator/denominator and window; percentage-point
gaps remain distinct from percentages. Undefined/null values are explicitly
unavailable, never zero. Supplier assessments retain contract identity and targets;
multiple periods/targets are not blended. Financial outputs are recorded costs or
exposure, not inferred profit, EBITDA or recoverable penalties. Operational
below-target performance does not assert legal breach. Bounded relationship samples
are disclosed and cannot prove universal causation.

The model receives a bounded selection of verified facts and full selected passages,
not all raw tool payloads. No source clause is silently cut to fit context: if the
complete selected view exceeds the compact budget, language assistance is skipped.
Validated semantic selections cannot remove mandatory evidence from the response.
Untrusted source instructions are quoted as data and cannot change permissions.

Reader role, read-only repeatable-read transactions, statement/result deadlines,
allowlist, argument contracts, sanitized errors and disconnect cancellation are
reused. Direct writes, secret access, shell/SQL execution and outbound actions are
refused before tools. Logs contain request IDs/status/counts/timing, not secrets or
private model reasoning. This remains a local synthetic-data demonstration, without
production authentication or workflow writes.
