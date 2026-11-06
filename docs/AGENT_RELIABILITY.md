# Stage 4B reliability diagnosis and measured iterations

Starting checkpoint: `010e145b86892f68114bc70be2f30d1c95e44dda`.
The worktree was clean. The existing local model remains Qwen3.5 4B Q4_K_M,
Ollama 0.40.12. No cloud, paid inference or new business architecture is introduced.
The pre-change backup/fingerprint is in ignored `.local-tools/stage4b-baseline`.

## Initial actionable diagnosis

| Category | Observed cause | Action |
|---|---|---|
| A Model capability | Small model changes entities, invents proportions and conflates domains. | Improve input/typed output; retain independent semantic review. |
| B Descriptions | Overlapping procurement, supplier and fulfilment descriptions. | Give explicit business scope and exclusions. |
| C Selection | Wrong fallback domains; unknown FINALIZE function. | Bounded model-selected capabilities with full-catalogue fallback; explicit finalization. |
| D Arguments | Invalid fields/enum attempts lack field-level feedback; failed calls repeat. | Sanitized structured field feedback and bounded correction/duplicate suppression. |
| E Context | All native schemas alone are 20144 serialized bytes each tool round. | Benchmark model-selected schema exposure; measure every real round. |
| F Tool presentation | A02's five-row supplier report exceeds 48000-byte transport limit. A01 repeats metric definitions across aggregate and supplier rows. | Lossless shared metric definitions in model transport; preserve canonical evidence. |
| G Semantics | Supplier agreement used to explain customer dispatch promise. | Typed domain/relationship labels and explicit limits on causal claims. |
| H Final generation | Numeric-word exclusion grammar forces evasive misspellings such as ninfty. | Separate concise interpretation from exact reference selection; validate and allow one bounded model correction. |
| I Enforcement | Clear write/secret requests enter costly investigation; absent semantic checks. | Conservative grammatical preflight plus unchanged server allowlist/reader role; typed claim checks. |
| J Instrumentation | Only aggregate tokens retained; completed status mistaken for quality. | Per-round actual token/byte/timing records; independent semantic case reviews and held-out questions. |

The fresh baseline A02 again made four unsuccessful comparison attempts (five/ten
rows), all `tool_result_limit`, and returned insufficient evidence despite available
data: 27007 observed tokens, 20.772 seconds. Artifact:
`reports/stage4b-initial-ranking.json`. The prior successful A01 used 80979 tokens,
five model calls and 62.640 seconds; prior quality failures remain unchanged evidence.

## Iteration 1: lossless transport projection

Hypothesis: factor repeated metric definitions to make ordinary supplier comparison
fit the existing wire limit and reduce repeated context without omitting any fact.
The server keeps the full typed canonical payload for verification and API evidence.
Only model transport shares identical time basis, grain and limitations through
content-addressed definitions. Values, units, denominators, dates, nulls, source
passages, qualifiers and relationship classes are retained exactly. A reverse codec
is tested for equality, including real PostgreSQL supplier results. Duplicate tool
results refer to the original evidence rather than repeat it. The actual native
request still obeys the existing byte ceiling; OpenAI transport stays unchanged.
Fallback: `OLLAMA_COMPACT_TRANSPORT=false` restores original transport/admission.

Affected offline/PostgreSQL checks: 39 passed. Original schema/grounding is unchanged
in this iteration. Actual A01/A02 model results are recorded separately before the
next significant change, in `reports/stage4b-projection-evaluation.json`.

Official protocol references: [tool calling](https://docs.ollama.com/capabilities/tool-calling),
[structured output](https://docs.ollama.com/capabilities/structured-outputs),
[thinking controls](https://docs.ollama.com/capabilities/thinking). The runtime's
actual metadata/settings are checked rather than assuming all documented options
exist in this installed version. No private reasoning is included in diagnostics.

## Observed iteration outcomes and environment

Projection-only live run: A01 completed with both exact metrics and sources, but used
89700 tokens / 69.737 seconds; this did not improve the previous efficient baseline.
A02's initial comparison succeeded, proving the transport limit fix, but additional
lookups and finalization timed out. Do not count that failed answer as a speed gain.
Per-round instrumentation identified the old final schema at 37986 bytes and repeated
schema/context input. Artifact: `stage4b-projection-evaluation.json`.

The short-reference format removes the number-excluding generation grammar. The model
selects short subject/metric/document/relationship references; the original server
resolves actual identities/values/citations. Additional independent checks bind row
metrics to row subjects, contract metrics to their supplier, source scope, typed
causality and complete prose. One model correction is allowed inside existing budgets.
No numeric/identity/source value is repaired or synthesized in application code.

The first short-format probe timed out before business tool selection, so it does
not measure final-format quality. Clear write/secret requests did verify preflight
refusals: approximately 21/8 ms, zero inference/tools. The next selected-catalogue run
correctly handled absent holiday policy without argument errors (4869 tokens versus
28131 previously), but elapsed time worsened under shared hardware load. It also
correctly distinguished ranking query failure from absence of supplier data.

Actual hardware investigation found a concurrent FC26 process consuming approximately
2794 MiB of dedicated GPU memory, in addition to the project runner's 2992 MiB;
free physical RAM reached about 0.6 GiB. Driver-reported VRAM use approached 5900 MiB,
despite Ollama reporting a smaller model allocation. FC26 was not stopped or changed.
A question was sent to the user about freeing those resources while implementation
continued. Timeouts in that state do not establish intrinsic model-quality failure.
Forcing all layers onto GPU was not proven beneficial and was reverted to automatic
allocation. The existing model and its downloaded files remain the default.

The installed official llama-server help documents process-local
`LLAMA_ARG_CTX_CHECKPOINTS` and `LLAMA_ARG_CACHE_RAM`. The project helper now limits
these to four / 256 MiB instead of 32 / 8192 MiB. Only the verified project-owned
Ollama process was restarted; logs confirm those bounds and cloud-disabled mode.
This is a bounded-memory mitigation, not proof that caches caused all VRAM pressure.

Selected schema exposure has an explicit full-catalogue fallback. Initial selection
uses the same real local model and consumes a round. A single bounded expansion can
expose additional registered tools, advanced parameters or extra metric columns.
Standard parameters hide unrequested dates/advanced options, cap ordinary pages at
five (investigation event pages at 25), and reject undeclared arguments. The caller's
established cutoff still enters the unchanged gateway. Advanced mode preserves all
original supported options. Investigation arguments also fix an actual agent-default
bug: injecting a query previously selected Stage 2's trend/comparison defaults rather
than the intended agent defaults. Stage 2 public contracts remain unchanged.

Focused model views contain only the metric columns selected by the model, plus
unchanged entity/period/source/contract/relationship data. Omitted columns are named
explicitly and remain in full canonical API evidence; an expansion can display them.
No document qualifications or selected metric denominators/units/nulls are omitted.
Conversation state keeps verified metric selections and successful entity order,
not model narrative or entities from failed investigations. Fresh evidence is still
required for follow-ups. Fifteen held-out questions are in an evaluation-only fixture;
none enter production routing or prompts.

## Autonomous recovery: demonstrated defects and limits

The 2026-11-03 guarded runs exposed a concrete ledger TypeError: knowledge `query`
is text, while analytics `query` may be a nested mapping. The final ledger now
flattens mappings only and retains search text. Affected live reruns had structured
responses instead of that HTTP500. Contradictory refusal plus selected capabilities
is now rejected; the small model still produces empty false refusals, so intent
quality is not declared solved.

The independent evaluator no longer imports/holds a second native embedding runtime
throughout inference. Fresh oracle work exits a subprocess; independently prepared
SQL/RAG snapshots can be reused against the unchanged verified dataset/corpus.
Missing providers stop further inference attempts rather than creating a cascade of
business-error scores. Strict argument failures and tool execution failures now
have separate counters. Lossless final-ledger metadata factoring reduced actual
A01/A02 ledger bytes by 13.93%/15.22%, with exact round-trip equality. It did not
produce an accepted final investigation or a global speed win.

The 4B and sole smaller 2B trials, actual 23-row schedules, environmental NOT_RUN
cases, guard stops, false refusals, numeric/prose errors and all token/latency limits
are documented in [STAGE4B_REPORT.md](STAGE4B_REPORT.md). The 352-test suite passes;
real answer acceptance remains NO. No automatic response repair, fake ranking,
weakened grounding or fixture-based production routing was introduced.
