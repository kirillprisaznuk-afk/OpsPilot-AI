# Free local LLM setup on Windows

Ollama is the default provider. No account, API key, subscription or inference
credits are required. The selected downloaded model is **Qwen3.5 4B, Q4_K_M**
(`qwen3.5:4b`, Apache-2.0). Downloads require internet once; inference, analytics
and retrieval run locally. OpenAI remains an explicitly selected optional adapter,
with no automatic fallback. Never select a cloud model.

## Setup and startup

From the repository root in PowerShell, with Docker Desktop running:

```powershell
# First time: official portable runtime (~1.6 GB) and local weights (~3.3 GB).
.\scripts\start_ollama.ps1 -Install -PullModel
# Subsequent sessions: starts/warm-ups the downloaded local model.
.\scripts\start_ollama.ps1
uv sync --frozen
$env:PYTHONPATH = 'backend;.'
docker compose up -d --build --wait
Invoke-RestMethod http://127.0.0.1:8001/api/v1/agent/status
uv run python -m scripts.evaluate_agent --live --limit 1 --output reports/local-evaluation.json
```

Use `.env.example` for a fresh environment. Keep the accepted database/corpus;
do not reseed or rebuild the index for this migration. A fresh database follows the
main README migrations, deterministic seed, knowledge index and reader-role setup.
Runtime and weights stay inside ignored `.local-tools/ollama` and `.models/ollama`.
The helper verifies the pinned official Ollama **0.40.12** archive checksum before
extraction. It needs no Windows service, registry change or administrator install.
If script execution is restricted, use an already permitted PowerShell session;
do not change machine-wide policy. Re-run `-PullModel` to resume a failed download.

The helper binds `127.0.0.1:11434`, sets `OLLAMA_NO_CLOUD=1`, one parallel slot/loaded
model, Flash Attention and q8_0 KV cache in its child process only. Check
`.local-tools/ollama/server.stderr.log` for `Ollama cloud disabled: true`.
An already listening server is left intact; verify its settings separately.
Docker Desktop reaches this host through `host.docker.internal:11434`; OpsPilot
stays on loopback port **8001**. Warm-up performs a real short local completion
before bounded agent queries. A cold load can exceed the provider deadline.

```dotenv
LLM_PROVIDER=ollama
LLM_MODEL=qwen3.5:4b
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_CONTEXT_TOKENS=32768
AGENT_USAGE_TOKENS=100000
```

The tested machine has 15.26 GiB RAM and an RTX 4050 Laptop GPU with 6141 MiB VRAM.
An earlier loaded profile reported 3,725,884,128 bytes in VRAM at 32K context.
Severe available-RAM pressure makes a larger model inappropriate for this run.
Qwen3 4B Thinking and Instruct variants were actually tried; their failures are
retained in the reports. Qwen3.5 supports local tool calling and avoids their
observed context/offload problems. Model tags can change: the tested weight digest is
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`.
See the Stage 4 report for actual quality failures; fitting VRAM is not acceptance.

## Protocol and enforcement

The native `/api/chat` adapter exposes the existing seventeen allowlisted tools.
Schemas reflect each analytics service's actual filters, grouping and sort options.
Supplier-detail and investigation arguments use a strict flat native wire contract,
translated losslessly to the existing canonical nested query. Unknown or invalid
arguments still fail the unchanged server gateway. Full tool results remain
untrusted tool messages; no source instructions become system messages.

Planning uses non-thinking sampling (temperature .7, top-p .8, top-k 20).
Finalization uses temperature zero and a stricter local JSON schema: short English
qualitative findings (up to three) and explicit bound supports for evidence, metric
pointers and source citations. A source selection includes its exact registered
document code where supplied by tool metadata, bound to that evidence/citation
rather than a free label. Standalone citation-resolution results without metadata
use a null code; the original server still verifies their document identity. Those selections map to the original Draft contract; the original
server independently validates evidence scope, metric values, source hashes/lines,
effective dates and quotations. No JSON repair or inserted business facts are used.
The grammar excludes existing numeric-word patterns, digits, control characters,
blank word gaps and unfinished sentences. It cannot establish semantic entailment.
A copied navigation index contains actual reference IDs/paths, never computed facts.
Actual runs still produced unsupported quantitative paraphrases/misspellings and
wrong topic attribution. These limitations fail live quality acceptance despite
valid references; see the Stage 4 report before relying on a model answer.

Only local HTTP hosts on port 11434 are permitted; proxies and redirects are off.
Downloaded manifests, local GGUF metadata and tool capability are checked before
inference. Cloud tags and remote model metadata fail. Ollama 0.40.12 or newer is
required for `truncate=false` and `shift=false`; context overflow fails explicitly.

The existing hard ceilings remain six rounds, twelve tools, ninety seconds total
and one hundred thousand observed aggregate tokens. Local setup uses that existing
token maximum; the unset default remains 64000. Provider timeout is thirty seconds.
The adapter reserves structured finalization by the fifth turn, earlier for lower
caller limits. All planning/final calls consume the same budgets. Missing usage stops
execution. Actual prompt/evaluation counts are reported; absent cache counters stay
unknown. Zero external API charges exclude electricity and hardware costs.

## Responses compatibility and optional OpenAI

Ollama documents a stateless Responses compatibility subset. The actual local model
endpoint and existing Responses-shaped request both returned HTTP 200. The bounded
probe consumed its output in reasoning and returned empty final text; this is not
proof that Responses is wholly unsupported or that structured output works.
The existing adapter is fixed to OpenAI's official endpoint and requires its key,
so it cannot be reused unchanged. The separate native adapter supplies explicit
thinking/context/no-shift controls and local model verification without dummy keys.
Raw compatibility results are in `reports/stage4-local-responses-compatibility.json`.

Only explicitly setting `LLM_PROVIDER=openai`, an account-supported `LLM_MODEL` and
`OPENAI_API_KEY` enables the retained OpenAI adapter. The free default never invokes
it. Its SDK serialization/error regressions use offline transports.

## Official references

- [Windows portable runtime](https://docs.ollama.com/windows)
- [Local-only mode and cache settings](https://docs.ollama.com/faq)
- [Native tool calling](https://docs.ollama.com/capabilities/tool-calling)
- [Structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [OpenAI compatibility subset](https://docs.ollama.com/api/openai-compatibility)
- [Pinned chat controls](https://github.com/ollama/ollama/blob/v0.40.12/api/types.go)
- [Model and license](https://ollama.com/library/qwen3.5:4b)
- [Model card and sampling](https://huggingface.co/Qwen/Qwen3.5-4B)

## Stage 4B candidate profile and memory headroom

The grammar description above is the retained legacy finalization path.
`OLLAMA_REFERENCE_OUTPUT=true` selects the candidate short-reference format: natural
qualitative prose, explicit subjects/claim types and short metric/document/link
supports. Independent scope, prose and relationship checks remain server-side;
one bounded model correction is allowed, never silent application repair.
`OLLAMA_TOOL_SELECTION=true` selects a bounded model-chosen detailed catalogue.
Both flags default false pending live acceptance; compact transport defaults true.
Set flags in ignored `.env`, then rebuild/recreate only the API service.

The launcher now bounds its child checkpoints/prior-prompt RAM cache to one / zero.
An existing listener is left intact. The original FC26 load was historical;
later autonomous trials found sustained
RAM and business-quality failures. No routine application-closing task is assigned
to the user. `-NoWarmup` starts the server without loading model weights.
No additional installation/key is needed here.
See [Windows benchmark/reproduction](LOCAL_MODEL_BENCHMARK.md),
[context and fallback details](CONTEXT_OPTIMISATION.md) and the
[Stage 4B report](STAGE4B_REPORT.md) for actual failures and unexecuted live gates.

The supported optional `OLLAMA_BATCH_TOKENS=128` experimental profile must match
`start_ollama.ps1 -BatchTokens 128`; unset/default remains 512. Only native load
options change, never tool permissions or factual validation. Real latest results
and the retained 4B preference are in [STAGE4B_REPORT.md](STAGE4B_REPORT.md).
