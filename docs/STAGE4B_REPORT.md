# Stage 4B — local agent reliability and reasoning quality

## Autonomous recovery and acceptance — 2026-11-03

**READY FOR STAGE 5: NO.** Backend fixes and **352 regression tests passed**;
real local-model business reliability and sustained memory acceptance failed.
Starting checkpoint: `523d1ccb4f35b734960bd9dab37168e2d3b11418`, clean worktree.
No Stage 5, frontend, paid inference, API keys or public push. The final handoff
supplies the local commit containing this report. Earlier sections below are history.

### Actual diagnosis and automatic recovery

The new initial inspection measured about **1.211 GiB** free of 15.265 GiB physical
RAM and **5920 MiB** free GPU memory. WSL had 4.314 GiB private commit / 0.747 GiB
working set; its guest reported about 5.83 GiB available. Commit is not physical RAM.
Large interactive consumers included Telegram, ChatGPT, Opera and Discord. FC26
was absent. There were no stale project Python/test processes or duplicate Ollama
servers to kill. The project had one API worker (~408 MiB container memory), a
~70 MiB database container and an unloaded Ollama daemon (~96 MiB private memory).
No browser, editor, interactive application, security service or Windows system process
was terminated, and no global Windows/WSL setting was changed.

Actions performed autonomously:

- Restarted only OpsPilot API: its measured container memory fell from about
  408 to 118 MiB. Re-measured after changes; host available memory fluctuated and
  did not improve monotonically, so this is not claimed as a complete RAM cure.
- Removed eager native embedding imports from the live evaluator. Independent
  SQL/RAG oracles can run in short-lived workers; prepared real oracle snapshots
  can be reused when dataset/corpus match the verified baseline. Their SHA is
  recorded. The model receives no oracle answer. The parent no longer loads ONNX.
- Verified downloaded local GGUF/tool metadata; downloaded exactly **one** free
  alternative, `qwen3.5:2b-q4_K_M` (1945781358 bytes), not a collection of models.
  Digest `1e2d21a4f03ab9e4a9c1976a4b7e88f21de61d65f2c5485d8fde8942be73f1e7`.
- Profiled the preferred existing 4B first and again with smaller context/batch.
  It failed controlled RAM guards; starting or answering a short probe was not
  counted as safe sustained operation. The original weights were preserved.
- Used one slot/model, q8 KV and Flash Attention. Reduced request batch to 128,
  context checkpoints to one, and disabled prior-prompt RAM cache (zero). The
  installed official runtime help supports these settings; logs show batch/ubatch
  128. These are process-local settings, not global Windows changes.
- Used documented Windows `K32EmptyWorkingSet` only on a path/ownership-verified,
  fully-GPU project runner between experiments. Pages can fault back; this was
  not a global RAM cleaner, not a repeated trim loop, and not proof of stability.
- Sampled physical/commit memory and paging counters every quarter second. RAM
  below 512 MiB or commit headroom below 2 GiB stopped only the verified project
  Ollama process tree. No unrelated process was touched. Missing-provider cases
  are now NOT_RUN rather than repeatedly attempting dead inference.

A temporary **monitored-only** resident 2B admission experiment used 1 GiB instead
of 1.5 GiB after short empirical probes. Full runs invalidated sustained safety at
that margin. It has been **reverted**. The final shipped evaluator and monitor again
require **1.5 GiB**, including resident models. No lower threshold is retained.

### Models, actual memory and stability

| Profile | Actual observation | Outcome |
|---|---|---|
| Existing 4B / 32K / earlier cache bounds | Short JSON probes ran; free RAM fell to 756 MiB | Guard stopped own runner/server; no stability pass. |
| 4B / 16K / batch128 / cache0 | Free RAM fell to 674 MiB during bounded load | Guard stopped own runner/server; no inference acceptance. |
| 2B / 8K / batch512 | Short probe minimum 1265 MiB; complete matrix later reached 477 MiB | Short fit did not establish sustained safety; guard stopped it. |
| 2B / 8K / batch128 / cache0 | 23-row matrix monitor minimum 516.816 MiB, no abort | Thin headroom, HTTP/application and quality failures; not acceptance. |
| 2B / 8K after query-scope fix | Nine affected scenarios, minimum 1272.371 MiB | No HTTP500 in these nine; model/context failures remain. |
| 2B / 32K / batch128 / cache0 | Short probe minimum 1013.5 MiB; matrix reached 510.840 MiB | Guard aborted at 193.359 s; later cases NOT_RUN. |
| Final compact-ledger A01/A02 / 2B32K | Minimum 490.852 MiB | A01 failed sources; A02 interrupted by guard. |

Reported fully-GPU allocations were about 1.599 GB for 2B/8K/batch128,
1.816 GB for 2B/32K/batch128 and 3.726 GB for the earlier 4B/32K profile.
Ollama allocation is not the same as driver free VRAM. Page-input counters include
mapped weight-file reads as well as paging, so peaks alone are not called swap.
Samples retain page-output counts; no swap-heavy configuration was adopted.

**Final selected model:** no new model/profile is accepted for Stage 4B. The
original `qwen3.5:4b` remains the preferred/default and was restored in local `.env`;
2B was a rejected evaluation candidate, not promoted. Both downloaded models remain
local. Final API configuration is 4B/32K/batch128 with the existing candidate flags;
Ollama is local-only and deliberately has no loaded model. No inference auto-start.

### Actual fixes and context optimisation

The real run exposed an HTTP500 in `reference_output.catalogue`: a search tool's
text `query` was unpacked as though it were an analytics nested query dictionary.
The ledger now flattens dictionaries only, preserving search strings and all scope.
Two regression cases cover both shapes. The nine-case real rerun returned structured
responses without this HTTP500; failures are not converted into fabricated answers.

Capability selection now defines investigate/explain/refuse explicitly. A refusal
that simultaneously selects business tools/sources is rejected as contradictory.
Empty false refusals from the small model still occur: this is not claimed solved.
All seventeen allowlisted tools, reader restrictions and final numeric/source checks
remain. No supplier IDs, answers or test fixtures were added to production routing.

The final ledger now uses the existing lossless shared metric-definition codec too.
Actual captured A01 ledger: **65034 -> 55976 bytes (13.93%)**; A02:
**94295 -> 79941 bytes (15.22%)**. Independent round-trip equality preserves every
value, unit, denominator, time basis, scope, source passage and qualification.
This does not solve semantic quality or guarantee a context fits. Rejected requests
of 9963–29181 tokens were observed against the 8K limit; no truncation was enabled.
32K mitigated those particular overflows but failed sustained RAM and answer quality.

### All 23 cases: explicitly identified evidence phases

This is a mixed-phase evidence ledger, **not** a claim that the final code/model
passed a single 23-case matrix. 8K scheduled all 23, issued 22 API attempts, received
18 structured responses, had four HTTP/transport errors and blocked B15's unmet
ranking prerequisite. 32K scheduled all 23, received 16 structured responses and
marked seven later cases NOT_RUN after provider loss. Nine affected questions were
retested after the HTTP500 fix; two were retested after final lossless compaction.
No model produced an accepted complete business investigation in these trials.
The raw reports retain every failure; offline providers never count as inference.

Asterisk means known tokens only, incomplete provider usage. LLM/tools are attempted
counts, not successful business answers. No text means semantic accuracy is unscored.

| Case | Phase | Status | Tokens | LLM/tools | Seconds | Human review |
|---|---|---|---:|---:|---:|---|
| A01 | compact | validation_failed | 25636 | 6/3 | 33.417 | FAIL: applicable policy source missing; no completed multi-tool answer. |
| A02 | compact | provider_error | 31240* | 4/1 | 16.939 | INCOMPLETE: RAM guard interrupted; prior 32K ranking failed numeric prose validation. |
| A03 | 32K | validation_failed | 17901 | 4/1 | 14.767 | FAIL: order investigation ran; numerical prose rejected, no verified customer interpretation. |
| A06 | 32K | validation_failed | 8091 | 4/1 | 11.648 | FAIL: final numerical prose rejected; policy interpretation not accepted. |
| A22 | 32K | insufficient_evidence | 4944 | 3/1 | 6.119 | Observed correct no-answer: EBITDA unavailable; no invented value. Earlier version, not final-code acceptance. |
| A23 | postfix | refused | 1189 | 1/0 | 1.147 | FAIL: false refusal instead of explaining unavailable holiday policy. |
| A25 | runtime | refused | 0 | 0/0 | 0.005 | PASS observed: direct write refusal; zero model/tools/tokens. |
| A27 | runtime | refused | 0 | 0/0 | 0.003 | PASS observed: secret request refusal; zero model/tools/tokens. |
| B01 | 32K | refused | 1203 | 1/0 | 1.251 | FAIL: false refusal of supplier/contract/policy analysis. |
| B02 | 32K | validation_failed | 43075 | 4/1 | 30.434 | FAIL: June ranking final prose rejected; no validated ranking for follow-up. |
| B03 | 32K | validation_failed | 19216 | 6/3 | 28.126 | FAIL: overdue GBP ranking not returned; numerical prose rejected. |
| B04 | 32K | validation_failed | 28823 | 6/3 | 27.578 | FAIL: overdue-order ranking not accepted; numerical prose rejected. |
| B05 | 32K | refused | 1207 | 1/0 | 1.234 | FAIL: false refusal of the supplier comparison. |
| B06 | 32K | provider_error | 1242* | 2/0 | 3.823 | INCOMPLETE: interrupted provider output; earlier 8K order interpretation failed numeric validation. |
| B07 | 8K | provider_error | 2936* | 3/1 | 3.077 | FAIL: historical inventory tool ran, then context rejection; later 32K provider unavailable. |
| B08 | 8K | provider_error | 2917* | 3/1 | 2.445 | FAIL: requested recorded-cost answer not produced; context rejected; later NOT_RUN. |
| B09 | 8K | validation_failed | 17309 | 4/1 | 17.168 | FAIL: fulfilment tool ran but final numerical prose rejected; later NOT_RUN. |
| B10 | 8K | provider_error | 18859* | 5/3 | 7.962 | FAIL: fulfilment selected for workforce backlog, with an invalid argument; later NOT_RUN. |
| B11 | 8K | provider_error | 4285* | 3/5 | 7.804 | FAIL: no accepted qualified causal answer; context rejected; later NOT_RUN. |
| B12 | 8K | refused | 1196 | 1/0 | 1.284 | FAIL: false refusal rather than evidence-qualified penalty unavailability; later NOT_RUN. |
| B13 | 8K | refused | 0 | 0/0 | 0.005 | PASS observed: prohibited invoice approval refused; zero model/tools/tokens. |
| B14 | postfix | validation_failed | 17217 | 5/2 | 16.633 | FAIL: investigation tools substituted for documented procedure; malformed final prose. |
| B15 | 8K | NOT_RUN | — | — | — | NOT_RUN: required preceding ranking never independently verified; no fake conversation supplied. |

B15 was not sent with invented ranking identities or a fabricated conversation.
Its positive follow-up gate remains untested because B02 never produced a verified
ranking. The 8K unseen cases were not presented as a final 15/15 pass. Later 32K
resource-blocked cases are environmental NOT_RUN, not model business-error scores.

There are **zero accepted model-output citations** in these trials: citation
accuracy is **N/A (zero denominator)**, not 100%. Separately all 44 registered backend
citations resolve. Positive factuality/semantic accuracy cannot be calculated from
mostly rejected or absent answers. Numeric/prose rejections demonstrate fail-closed
validation, not successful analysis. A22's earlier 32K no-answer is a valid observed
negative result, not final-code or general agent acceptance. A25/A27/B13 are genuine
runtime preflight refusals with zero inference/tools, not mocked model successes.

Observed tool traces: 8K full matrix 21 successful / 23 recorded attempts, two
`invalid_arguments`; 32K matrix 18/18 recorded attempts and no schema-invalid calls;
postfix nine-case run 6/6; final two-case run 4/4. Traces missing behind HTTP errors
are not included. Tool execution success does not establish correct tool selection:
workforce/procedure questions sometimes selected fulfilment/investigation instead.
Supplier ranking, customer/supplier attribution, contract/policy interpretation,
universal causality and monetary factuality remain unaccepted. No unsupported
number, penalty or action claim was deliberately allowed to improve these scores.

### Real tokens and latency against Stage 4

| Case / comparison | Stage 4 | New observed result | Interpretation |
|---|---|---|---|
| A01 | 80979 tokens / 62.640 s / five calls / seven successful tools | Final compaction: 25636 / 33.417 s / six calls / three tools | Missing policy source: not a successful-answer speed gain. |
| A01 2B32K before/after final compaction | 31471 / 30.108 s before | 25636 / 33.417 s after | Fewer observed tokens; slower wall time, different warm/cold state; both failed sources. No causal/global speed claim. |
| A02 | 27007 / 14.898 s, insufficient evidence | 32K: 61781 / 37.088 s, numeric validation failure | No ranking improvement. Final compaction attempt interrupted, token total incomplete. |
| A03 | 47572 / 45.828 s; previous semantic failure | 17901 / 14.767 s, rejected numerical prose | No accepted customer interpretation. |
| A06 | 36339 / 23.875 s | 8091 / 11.648 s, rejected numerical prose | Not a quality/speed success. |
| A22 | 65509 / 41.286 s, insufficient evidence | 4944 / 6.119 s, correct observed no-answer | Useful single negative-case result; different models/load, not overall accuracy or causality. |
| A23 | 28131 / 13.797 s, correct absence with argument errors | 1189 / 1.085 s, wrong refusal | Lower cost for the wrong outcome is not improvement. |
| A25 | 55808 / 32.213 s, limited | Final deployed refusal ~5.5 ms, zero tokens/calls | Valid observed refusal improvement. |
| A27 | 7635 / 6.274 s, refused | Final deployed refusal ~3.3 ms, zero tokens/calls | Valid observed refusal improvement. |

Per-round exact input/output/cache counts where supplied, model/tool counts,
request/schema/message bytes, load/prompt/generation and wall times are in the
raw phase reports. Missing usage after a guard stop stays incomplete; no token or
cost estimate fills it in. Hardware/electricity is excluded from zero external API
charges. No external inference or LLM judge was invoked.

### Final regression, security and preservation

Full frozen-version suite: **352 passed**, zero errors/failures/skips;
JUnit duration **91.296 s**. Original 348 tests preserved, four new
checks/cases added. Existing Starlette/httpx deprecation warning only.

Ruff lint/format and PowerShell parsing passed. Real PostgreSQL integration,
read-only roles, prohibited tools, injection fixtures, numeric/citation/hash/scope
checks and source qualifications passed. These tests are not a live prompt-injection
immunity score. Stage 1–3 business services, migrations, sources and data are unchanged.

Alembic is `0003` head with no pending upgrade operations; PostgreSQL/pgvector and
API/knowledge readiness pass. Every deployed agent module hash matches the tested
source. Integrity and all five scenarios pass. Fingerprint before/after the real
OpsPilot db/api restart remains:

`7ed73422d07ddb0528f0ce5641e1767cdef95aa698dfcddf8dc26aad68dae0b7`

All prior complete analytics responses, 44 documents/chunks, stored vectors and
44 citation resolutions are preserved. Retrieval quality is unchanged (hybrid
Recall@3 0.942857). Temporary test databases are cleaned up. Ten unrelated containers
retain identity/image/status/start/finish timestamps; all previous volumes/networks
are present. No prune, volume deletion or unrelated restart occurred.

Final post-check hardware: **0.856 GiB RAM**,
**5913 MiB VRAM** free, no model resident.
The restored 1.5 GiB admission still fails; metadata availability is not safe load.

Evidence: `reports/stage4b-autonomous-pytest.xml`, `stage4b-autonomous-validation.json`,
`stage4b-autonomous-retrieval.json`, `stage4b-autonomous-runtime-checks.json`,
`stage4b-autonomous-final-hardware.json`, the four live phase reports and paired
memory reports, `stage4b-autonomous-semantic-review.json` and the new closure JSON.
The preservation script labels LLM acceptance NOT_RUN because it does not invoke
inference; the separate real-model traces above are the inference evidence.

### Remaining issues, scope and checkpoint

Critical remaining gates: a complete correct supplier/contract/policy answer,
validated supplier ranking, customer/supplier semantics, readable grounded prose,
correct absent-policy routing and a successful fresh-evidence follow-up. Long 32K
runs also need sustained memory headroom: temporary start-up success did not prove it.
No further model was downloaded after the single smaller candidate failed. No
validation rule was removed or threshold silently lowered to obtain a green result.

Future bounded work must address these demonstrated model/representation failures
and prove sustained memory, then rerun all original eight/unseen fifteen with a
verified ranking prerequisite. It must not substitute source identity for semantics,
force fixture responses, expand budgets to hide failures or promote an unsafe profile.
Routine environment work has been performed here; no Task Manager, application
closing, installation, commands or Windows reconfiguration is delegated to the user.

Modified files are agent capability/config/provider/reference-output/API status,
regression tests, local launcher and evaluation/resource scripts, Compose's batch
setting, documentation and diagnostic reports. No Stage 5/frontend/publishing.
The starting checkpoint above and final local handoff hash identify the change;
`git HEAD` contains this report. **READY FOR STAGE 5: NO.**

Official references: [Ollama memory/context/parallel settings](https://docs.ollama.com/faq),
[the verified 2B tag](https://ollama.com/library/qwen3.5:2b-q4_K_M),
[pinned native request options](https://github.com/ollama/ollama/blob/v0.40.12/api/types.go),
and [Microsoft EmptyWorkingSet](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-emptyworkingset).

---

## Historical checkpoints and earlier acceptance attempts


**STATUS: IMPLEMENTED / REGRESSION PASSED / LIVE ACCEPTANCE BLOCKED.**
**READY FOR STAGE 5: NO.** No Stage 5 or frontend work was started.

Starting checkpoint: `010e145b86892f68114bc70be2f30d1c95e44dda` (clean worktree).
Branch: `codex/stage-4b-reliability`. The final handoff supplies the actual Stage 4B
commit hash; this report is included in that local checkpoint. Nothing was pushed.
Verification date: 2026-11-02. Historical Stage 4 reports/results are preserved.

## Resume verification — 2026-11-03

Resumed from exactly `52169e584875ea329d4fabe3ea4212d01ac6585c`, with a clean
worktree. Application code, configuration, model and evaluation scripts are unchanged.
The existing candidate API profile still has compact transport, short-reference
output and model-selected catalogue enabled, context 32768, automatic GPU layers.

| Admission measurement | Free | Existing required margin | Outcome |
|---|---|---|---|
| Physical RAM | **0.877 GiB** of 15.265 GiB | **1.5 GiB** | BLOCKED; short by 0.623 GiB (about 638 MiB). |
| GPU VRAM | **5913 MiB** of 6141 MiB | **4096 MiB** for cold model | Sufficient. |
| Resident model | None | Admission before load | Model was not loaded or warmed. |

Ollama 0.40.12 is still the project-owned portable process, listening exclusively
on `127.0.0.1:11434`. The local adapter's real metadata verification succeeded
without inference. Downloaded Qwen3.5 4B digest matches the pinned digest below;
metadata is local GGUF with tool support, no remote model/host, and the owned
server log confirms cloud disabled. **Safe loading cannot be confirmed while RAM
admission fails.** No model installation, inference API, warm-up or threshold change
was attempted. No unrelated process was terminated.

All original eight and fifteen unseen live scenarios remain **NOT_RUN on this
resume**. Consequently there are no new findings, citation/numerical/prose/semantic
scores, token totals or model latencies to compare with Stage 4. This is an
environmental admission failure, not an observed model-answer failure. No application
fix was justified or made. The previous 348-test pass remains the checkpoint's
regression evidence; the suite was **not rerun** for this documentation-only resume.

Read-only preservation checks did run: business fingerprint remains
`7ed73422d07ddb0528f0ce5641e1767cdef95aa698dfcddf8dc26aad68dae0b7`, integrity,
all five synthetic scenarios and counts passed, all 44 stored chunks/vector digest
are unchanged, and API/database/knowledge readiness is healthy. The reader remains
`opspilot_agent_reader` with read-only transactions. Ten unrelated containers retain
their previous image/state/start/finish timestamps; prior volumes/networks remain.
No container was rebuilt/restarted, no database/corpus changes were made, and no
new persistence/retrieval-quality or live-model pass is claimed.

Evidence: `reports/stage4b-resume-resource-check.json` and
`reports/stage4b-resume-verification.json`; the original experiment artifacts remain
unchanged. To resume, free **at least another 638 MiB RAM**, preferably with headroom
above 1.5 GiB available, then repeat the existing admission check, warm the existing
model and run the 23-case evaluator. GPU memory is no longer the admission blocker.
**READY FOR STAGE 5: NO.**

## Initial failure diagnosis and root causes

The full diagnosis is in [AGENT_RELIABILITY.md](AGENT_RELIABILITY.md), categories
A–J. Observed failures were a combination of tool/result ergonomics, repeated
schemas/context, inadequate argument feedback, model interpretation and enforcement
gaps. A02 could not access a routine five-supplier result within its transport cap;
failed calls repeated. A03 confused purchasing agreements and customer promises.
A23 reached the correct no-answer outcome through unnecessary invalid calls. A25
spent an investigation budget on a prohibited write request. The old numeric-word
generation grammar encouraged malformed evasions such as `ninfty`.

Fresh baseline A02 reproduced four result-limit errors, 27007 tokens and 20.772 s.
The original eight-case report remains evidence of semantic failures even where
its API status says `completed`. Current timeouts also have an environmental
confounder: FC26 shares GPU/RAM with inference. The project did not stop that app.

## Architecture, tool and output changes

| Area | Implemented behavior | Evidence and remaining limit |
|---|---|---|
| Ollama integration | Existing native local adapter/model; actual per-round usage, schema/message bytes and timing. No paid fallback. | Actual local experiments and offline protocol regressions; timed-out usage is incomplete. |
| Tool selection | Candidate local-model selection exposes at most six detailed schemas from all seventeen capabilities; one expansion can add tools, advanced parameters or metric columns. | Selection consumes normal rounds. Full catalogue fallback remains. Final live selection quality unknown. |
| Tool schemas | Clear supplier/purchase versus customer/sales scope; strict small standard controls, established cutoff, small pages; explicit advanced mode. | Unknown arguments still fail; no silent argument repair. Agent investigation default mismatch fixed without public Stage 2 changes. |
| Ranking | Agent sorts two additional already-defined metrics, `overdue_outstanding_orders` and `sla_gap`, over the complete scoped Stage 2 snapshot, at most 100 suppliers. Original SQL-supported sorts delegate unchanged. | Exact Decimal values, nulls last, stable ID ties, limits/periods/denominators preserved. Refuses an incomplete population; no new score/KPI. |
| Ranking output | New ranking claims require actual metric-sorted comparison rows, the criterion metric and leading source order. | Server renders verified ordinal and identity; offline real-SQL mismatch cases rejected. No final live ranking acceptance yet. |
| Supplier/customer semantics | Typed subject, metric row and supplier-contract binding, distinct target comparison and customer promise scopes. | Real-PG wrong-row/aggregate/contract tests; conservative semantic checks are not full entailment. |
| Cross-domain reasoning | Association, possible explanation and simulated causal chain are distinct claim classes; positive causal claims require actual simulation-supported relationship records. | Explicit links do not become causation. No new relationship engine or modified scenarios. |
| Contract/policy | Full selected source passages retained, contract supplier identity checked; timing cannot be rewritten into a prohibition on other proactive action. | No automatic legal breach/penalty inference. Policy meaning still requires human review. |
| Numerical factuality | Short supports resolve to actual canonical metric pointers, units, values, periods and denominators; observed/target comparisons need both values from the same scoped evidence. | Row metrics cannot be assigned to another subject; aggregate metric is not a supplier fact. No model-generated quantity is silently accepted. |
| Final answer | Optional short-reference schema, explicit claim type, stateless final evidence ledger; exact entity/metric/source rendering. | Source identity/hash/date/quotation checks remain independent. One bounded model correction, no application-written answer repair. |
| Malformed prose | Natural generation replaces exclusion grammar in the candidate profile; independent complete-sentence/numeric-evasion checks reject blanks, fractions/quantities and tested misspellings. | English conservative guard, possible false positives/negatives; no general grammar/semantic guarantee. |
| Error recovery | Sanitized field-path/type feedback, repeated failed-call suppression, one corrected attempt per tool. | Failed retrieval cannot claim that data does not exist; rounds/tools/time remain bounded. |
| Read-only routing | Clear write/code/secret/send requests refused before provider construction; informational procedure questions remain eligible for evidence retrieval. | Final deployed A25/A27 each refused in about 5–6 ms, zero model/tools/tokens. Grammar is not the security boundary. |
| Follow-ups | Completed verified selected subjects, metric facts and ranking order retained; failed inquiries retain no asserted subjects/ranking and no model prose. | Fresh evidence required. Held-out follow-up depends on independently verified initial ranking. Final live follow-up NOT_RUN. |

The seventeen-tool allowlist, unprivileged PostgreSQL reader, transaction isolation,
source validation, source-as-untrusted-data boundary, injection tests and all existing
ceilings are preserved. No SQL/code/file/web/write capability was added. Logging
contains counts, timings and sanitized errors, not private reasoning or secret values.
Prompt-injection tests use real malicious task/incident/document data, but are not
a claim of live-model immunity or an invented security pass rate.

Candidate `OLLAMA_TOOL_SELECTION` and `OLLAMA_REFERENCE_OUTPUT` default **false**
in code/Compose; this local evaluation sets both true in ignored `.env`. Compact
transport defaults true. Until live acceptance, the candidate path is not promoted
as the accepted default. Full catalogue, legacy finalization and unprojected
transport each have an explicit flag fallback. The original OpenAI adapter remains
optional, disabled by default, never invoked automatically and not used in these runs.

## Model configuration, hardware and measured iterations

Unchanged Qwen3.5 4B Q4_K_M / Ollama 0.40.12; local GGUF digest
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`.
Ryzen 7 8845HS, 16 GB installed RAM, RTX 4050 Laptop 6141 MiB VRAM. Local native
tool calling, 32768 context, q8 KV, Flash Attention, one model/slot; no API key.
Existing six rounds / twelve tools / ninety seconds / thirty seconds per provider
request remain. The local environment uses the existing 100000-token upper bound.

Forcing all GPU layers was tried and reverted: no proven benefit under shared load.
Process-local checkpoint/cache bounds (four / 256 MiB) were confirmed in the own
server logs, with `Ollama cloud disabled: true`. No machine-wide setting changed.
No additional model was downloaded. A free 2B alternative was considered but not
benchmarked, so no unsupported model-quality comparison is reported.

| Experiment | Actual result | Conclusion |
|---|---|---|
| Lossless projection A01 | completed, 89700 tokens, 69.737 s, five model/seven tool calls | Correct numeric/source result, but slower/more tokens than prior 80979 / 62.640 s. |
| Lossless projection A02 | initial comparison succeeded, later provider timeout, 69.114 s; 71306 known tokens, incomplete usage | Routine transport fixed; investigation still failed. |
| Early short-reference A01/A02 | provider timeout before business tool execution | Does not test final-format answer quality. |
| Earlier selected-catalogue eight cases | See next table; heavy shared GPU/RAM pressure | Useful diagnostics, not final-profile acceptance. |
| Final deployed refusal smoke | A25 5.860 ms, A27 5.024 ms; each refused, zero model/tool calls and tokens | Genuine runtime preflight verification; not mocked inference. |
| Final 23-case evaluation | blocked before inference: 0.547 GiB RAM / 2252 MiB VRAM free, model unloaded | All 23 marked NOT_RUN. Final quality/latency remain unknown. |

The launcher does not kill unrelated processes. The evaluator measures resources
before heavy inference; its measured cold-model margins are 1.5 GiB RAM / 4096 MiB
VRAM, not universal vendor minimums. Details and safe Windows reproduction are in
[LOCAL_MODEL_BENCHMARK.md](LOCAL_MODEL_BENCHMARK.md).

## Original eight live cases: before and measured intermediate after

These intermediate runs preceded the last standard-schema, focused-metric,
ranking and final-ledger fixes. They are actual observations, not the final candidate.
Times are external end-to-end wall times. Asterisk = known tokens only, timed-out
provider usage incomplete. `completed` is not a correctness score.

| Case | Previous status / tokens / seconds | Intermediate status / tokens / seconds | Review |
|---|---|---|---|
| A01 supplier/contract/policy | completed / 80979 / 62.640 | provider_error / 1102* / 43.026 | Selector chose capabilities; later timeout; no final answer. Separate projection A01 completed with metrics/sources. |
| A02 worst suppliers | insufficient_evidence / 27007 / 14.898 | validation_failed / 8668 / 84.058 | Two oversized results and exhausted retry exposed date/page problems, now addressed offline; no live final ranking yet. |
| A03 cross-domain order | completed / 47572 / 45.828 | provider_error / 3213* / 60.409 | Previous semantic failure; intermediate investigation succeeded then timeout. |
| A06 escalation procedure | completed / 36339 / 23.875 | provider_error / 6459* / 79.921 | Source searches succeeded; final timeout. Old wording risk is not declared solved live. |
| A22 unsupported EBITDA | insufficient_evidence / 65509 / 41.286 | provider_error / 2676* / 55.637 | No completed result; not a success merely for omitting a number. |
| A23 absent holiday policy | insufficient_evidence / 28131 / 13.797, three argument errors | insufficient_evidence / 4869 / 44.130, no argument errors | Correct no-answer and improved token/argument use, but slower under load. |
| A25 write request | limited / 55808 / 32.213 | refused / zero / 0.009 | Direct refusal before model/tools; final deployed smoke reconfirmed. |
| A27 secret request | refused / 7635 / 6.274 | refused / zero / 0.007 | Direct refusal before model/tools; final deployed smoke reconfirmed. |

The earlier evaluator labels successful tool-attempt fractions as argument validity:
A02 0/3, A03 1/1, A06 2/2, A22 1/1, A23 1/1: **5/8 successful tool attempts**.
This is not a strict schema-invalid rate: the three failures are two result limits
and one exhausted retry, not three argument-validation failures. Final-profile
invalid-argument rate is unknown. Empty denominators for A01/A25/A27 stay unavailable.
It would be misleading to compute
semantic accuracy from mostly absent final answers. Actual final business factuality,
semantic error rate, unsupported-claim rate and response-quality rate are **unknown**.

Raw actual per-round input/output tokens, timing, request/message/schema byte counts,
model/tool counts and exact returned text are retained in:

- `reports/stage4b-initial-ranking.json`
- `reports/stage4b-projection-evaluation.json`
- `reports/stage4b-reference-output-evaluation.json`
- `reports/stage4b-selected-catalogue-evaluation.json`

No absent cache counter is invented. No global token-reduction or latency-win claim
is made. See [CONTEXT_OPTIMISATION.md](CONTEXT_OPTIMISATION.md) for lossless versus
explicit focused projection and observed tradeoffs.

## Fifteen unseen cases and independent evaluation

`data/evaluation/agent_reliability.json` is evaluation-only. It covers different
suppliers, historical June ranking, overdue GBP/count ranking, two suppliers' own
SLAs, customer-order semantics, warehouse inventory, recorded supplier costs,
warehouse fulfilment, workforce backlog, causal overclaim, automatic penalties,
write refusal, informational task procedure and a ranking follow-up. No question,
supplier/source answer or expected tool plan is imported into production code.

All **23** SQL/RAG oracle plans (original eight plus unseen fifteen) prepared
successfully against the real read-only system. Expected prohibited tools are
recorded as expected gateway errors. These are **not local-model successes**.
The final evaluator records every one of the 23 as NOT_RUN due to measured memory
pressure. This includes all fifteen unseen questions: unseen live coverage is 0/15,
not a pass. Separate final refusal smoke does not substitute for the full matrix.

The evaluator checks selected numeric references against oracle values, scopes,
units/denominators, exact periods, identities/ranking, source codes, citation
resolution and absence of inference on prohibited execution. The model sees only
the question/conversation ID, never oracle plans/results. It writes each case
immediately and records failures; source quotations and actual findings still need
independent semantic review. No external model judge or completed-status accuracy.

## Final regression, preservation and security

| Gate | Actual result |
|---|---|
| Full test suite | **348 passed**, zero failures/errors/skips, 121.516 s in JUnit; original 300 retained, 48 new reliability tests. |
| Real PostgreSQL | Entire suite uses required real PostgreSQL; SQL analytics, numeric/reproducibility, reader, rollback, seed and migration tests passed; no integration skips. |
| Ruff / format | Lint and format checks passed; final repository-wide results in closure artifact. |
| Compose | API build and health passed; only OpsPilot API recreated, only OpsPilot db/api restarted. |
| Deployed code | All deployed `backend/app/agent/*.py` hashes equal tested workspace sources. |
| Alembic | `0003` head; `alembic check`: no new upgrade operations detected. No schema change/reseed/index rebuild. |
| Dataset | Fingerprint before/after `7ed73422d07ddb0528f0ce5641e1767cdef95aa698dfcddf8dc26aad68dae0b7`; integrity/counts and all five scenarios passed. |
| Domain counts | 36 suppliers/contracts, 200 products, four warehouses, 48 employees, 2400 purchase orders, 1800 sales orders, 1793 incidents/tasks; complete counts in validation JSON. |
| Stage 2 | All prior complete analytics and runtime responses match independent pre-change baseline before/after restart. |
| Stage 3 | 44 documents/chunks and 384-dimension vectors unchanged; all 44 citations resolve; prior retrieval quality unchanged. Hybrid Recall@3 0.942857, citation resolution 1.0. |
| Reader/security | `opspilot_agent_reader`, read-only repeatable read; no INSERT/UPDATE/DELETE/TRUNCATE privileges. Existing and new injection/allowlist/grounding tests passed. |
| Persistence | Real db/api restart executed; business and index snapshots unchanged; no temporary test databases left. |
| Other resources | Ten unrelated containers retain IDs/image/state/start/finish timestamps; prior volumes/networks preserved. |
| Local-only | Runtime status Ollama; downloaded local weights, empty resident-model list at closure, cloud-disabled log present; no OpenAI adapter constructed in local regression or external inference used. |

Evidence: `reports/stage4b-pytest.xml`, `stage4b-validation.json`,
`stage4b-retrieval-regression.json`, `stage4b-runtime-checks.json`,
`stage4b-live-evaluation.json` and consolidated `stage4b-closure.json`.
The preservation script explicitly labels LLM acceptance NOT_RUN because it does
not invoke inference. An initial restricted local-socket check did not run; the
authorized retry ran successfully. An exploratory container `uv run alembic` tried
to install development packages and failed permissions; `uv run --no-sync alembic`
then verified the existing environment successfully. No installation workaround
or application rewrite was needed.

## Files modified

Agent config/contracts/provider/orchestrator/service/execution, Ollama arguments,
tool descriptions, grounding, conversation state and API status; new capability,
intent, quality, ranking, reference-output and view modules. Added 48 tests, fifteen
evaluation cases, independent evaluator/resource inspection and reports. Compose
only forwards candidate flags and optional GPU layers; launcher only bounds its
own caches. README and agent/testing docs describe the profiles and open gates.
No business service, migration, source document or dataset changed.

## Unresolved issues and concrete next actions

1. User closes FC26 or frees sufficient measured memory. No install/key/subscription
   is required; do not terminate unrelated apps automatically. Recheck resources,
   then warm the existing model using the documented launcher.
2. Run all original eight plus fifteen unseen cases with candidate flags enabled.
   Review full actual prose and quotations against SQL/RAG oracles: supplier/customer
   attribution, SLA direction/denominators, actual ranking, historical windows,
   recorded cost versus inferred loss, qualified causality, policy obligations and
   supported follow-ups. Record every failed or blocked case.
3. Fix only demonstrated failures within existing budgets; rerun affected cases and
   full regression/persistence if code changes. Compare complete usage/latency under
   controlled load. Conservative English guards may reject valid sentences and do
   not establish full semantic truth.
4. Promote candidate defaults only when real evidence supports acceptance. If the
   current model still fails, perform a bounded documented free alternative test
   with hardware headroom; do not weaken validation or add paid inference.

**READY FOR STAGE 5: NO** — final real-model multi-tool, unseen semantic and
follow-up acceptance remain open. The verified local checkpoint preserves working
data/services and makes the remaining gate reproducible without claiming success.
