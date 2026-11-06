# Approved agent tools

Every tool is a fixed registered function with a Pydantic argument contract, response
contract, read-only classification, output byte limit and future permission label
`read_business_and_synthetic_knowledge`. Public introspection is available at
`GET /api/v1/agent/tools`. Provider declarations use strict function schemas derived
from those models. No arbitrary method discovery, SQL, Python, shell, URL, file path
or write capability is exposed.

| Tool | Existing authority |
|---|---|
| resolve_business_entity | Bound SQL lookups of actual names/numeric IDs |
| get_enterprise_overview | Stage 2 overview composition |
| get_procurement_performance | Stage 2 procurement |
| compare_suppliers | Stage 2 supplier comparison |
| get_supplier_performance | Stage 2 supplier detail and contractual SLA assessments |
| get_inventory_status | Stage 2 stock ledger and shortages |
| get_warehouse_performance | Stage 2 warehouse grouping |
| get_customer_fulfilment | Stage 2 dispatch commitments |
| get_operational_costs | Stage 2 exact GBP exposure and recorded cost attribution |
| get_workforce_tasks | Stage 2 task status/history and workload |
| get_operational_incidents | Stage 2 incident incidence/prevalence |
| get_deterministic_insights | Stage 2 transparent threshold signals |
| investigate_business_entity | Stage 2 explicit relationships and narrow evidence selectors |
| search_corporate_knowledge | Stage 3 lexical/vector/hybrid retrieval |
| build_knowledge_context | Stage 3 bounded context assembly |
| get_document_details | Stage 3 registered document/version preview |
| resolve_source_citation | Stage 3 source hash/line verification |

Supplier SLA is included in supplier detail rather than duplicated in another SQL
tool. Likewise, recorded costs and knowledge evidence reuse existing services.
Analytics responses preserve their metric definitions, units, nulls, denominators,
scope and limitations. Common defaults suppress trends/comparisons and use a small
page; the original controlled options remain available where the service supports
them. Invalid sort/group/filter combinations are rejected by that service.

Tool arguments use strict JSON validation: malformed JSON, duplicate fields,
NaN/infinity, unknown fields, boolean/string coercion into IDs/counts, invalid dates,
unsupported enums, excessive pages and unknown tools fail with structured codes.
The server supplies only an omitted as-of from the established request cutoff;
an explicit conflicting or null cutoff is rejected. IDs must exist and have been
created within the observation scope. A nonexistent product cannot become a
misleading zero-stock result.

Entity resolution covers supplier/warehouse/department names, product names, task
titles and numeric incident/order IDs. The schema contains no invented order or
incident reference-code column. Partial names can return ambiguity; the server
stops for clarification after an ambiguous resolution. A missing entity stops
analysis without substituting another identifier. Interpretation of an arbitrary
name in the original question still depends on the model; live correctness must
be evaluated separately from these deterministic checks.

Successful outputs are validated against the existing response models, bounded to
48,000 bytes by default and attached to a per-run evidence ID. Oversized output
returns `tool_result_limit` and asks for narrower scope; it is not silently sliced.
Pages are limited to 100 records, entity lookup candidates to 20, retrieval passages
to eight and knowledge context to the existing 8,192-token maximum. Identical
validated calls reuse evidence within a run; attempts still count toward the cap.

Errors include unknown/invalid arguments, missing entity, source inapplicability,
database/source unavailability, invalid output, timeout and result limits. Raw SQL,
credentials and provider traces are excluded. One tool failure can be returned to
the model for correction; unknown/ambiguous entity resolution stops safely.

## Stage 4B local presentation

There are still seventeen tools. Candidate selection exposes small standard schemas
and allows one bounded expansion of tools/advanced parameters/metric columns.
No question-specific dispatcher or fixture answer enters production. Sanitized field
feedback and duplicate-failure suppression preserve validation and budgets.

Agent comparison can additionally order the existing Stage 2 `overdue_outstanding_orders`
and `sla_gap` metrics over a complete scoped snapshot, at most 100 suppliers. Exact
values/periods/denominators and nulls are retained, ties use ID order, and incomplete
population rankings are refused. Public Stage 2 contracts and SQL sorts are unchanged;
there is no new composite score. For local compact transport, the byte ceiling
measures actual projected payload after canonical validation. Full server evidence
stays intact. Focused metric omissions are disclosed/expandable; source qualifications
are not truncated. See [context details](CONTEXT_OPTIMISATION.md).
