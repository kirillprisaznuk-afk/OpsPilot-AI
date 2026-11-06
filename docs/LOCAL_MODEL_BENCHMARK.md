# Local model benchmark — Stage 4B

## Tested configuration

Windows; AMD Ryzen 7 8845HS; 16 GB installed / 15.265 GiB visible RAM;
NVIDIA RTX 4050 Laptop GPU, 6141 MiB reported VRAM. Approximately 149 GiB disk
space remained during the hardware inspection. The installed portable official
Ollama version remains 0.40.12. No new model was downloaded for Stage 4B.

Model: **qwen3.5:4b**, Q4_K_M, digest
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`.
Native `/api/chat`, local GGUF verification, no cloud, no keys, no external
inference. Context 32768; q8_0 KV; Flash Attention; one loaded model/parallel slot.
Tool planning uses the existing non-thinking sampling; final output temperature is
zero. Existing ceilings: six rounds, twelve tools, ninety seconds per question,
thirty seconds per provider request, up to 100000 observed tokens locally.

## Experiments and confounders

The portable server and weights were already present. Actual Stage 4B experiments
used this model with real Docker FastAPI, PostgreSQL analytics and local RAG.
See the report and raw `reports/stage4b-*-evaluation.json` artifacts for failures,
successful tools, actual findings and per-round usage. Test doubles are not included
as model successes.

A concurrent FC26 process occupied roughly 2.8 GB GPU memory at inspection and
later increased. Total driver-reported use approached 5.9 GB while inference was
loaded; free system RAM reached approximately 0.6 GB. Model allocation reported by
Ollama is not the same as free driver memory. No unrelated application was stopped.
The user was asked to free the game's resources; no response was assumed.

Forcing 99 GPU layers was tried: the model reported 3725884128 bytes in VRAM,
but loaded inference still timed out under the shared load. This change was reverted
to automatic allocation. It is not retained as a benchmark win. An orphan-runner
hypothesis was checked and not established.

The installed official `llama-server --help` documents inherited
`LLAMA_ARG_CTX_CHECKPOINTS` and `LLAMA_ARG_CACHE_RAM`. The project launcher now sets
four checkpoints / 256 MiB instead of defaults 32 / 8192 MiB, only for its process
tree. Logs confirm the settings and cloud-disabled mode. This bounds cache memory;
it does not prove cache defaults caused the shared hardware pressure.

A smaller free Qwen3.5 2B Q4_K_M tag was considered from the official model listing.
It was **not downloaded or benchmarked**: current RAM headroom did not justify
another heavy experiment, and no semantic-quality comparison is available. A larger
model is likewise not assumed to be better or suitable on this machine.

## Final admission measurement

`reports/stage4b-live-evaluation.json` records **0.547 GiB free RAM**, **2252 MiB free
VRAM**, model unloaded. The evaluation profile requires 1.5 GiB RAM and 4096 MiB
free VRAM before cold-loading this 4B model (512 MiB VRAM margin if already resident).
These are conservative benchmark admission margins, not a model vendor minimum or
proof that inference could never run with less memory. All final 23 cases are
explicitly NOT_RUN. Quality, final latency and final semantic error rate are unknown.

## Reproduce on this Windows machine

**2026-11-03 resume:** free VRAM improved to 5913 MiB, but free RAM was only
0.877 GiB against the unchanged 1.5 GiB margin. The existing model remains unloaded;
no live case ran. Free at least another approximately 638 MiB RAM before retrying,
preferably with additional headroom. See `reports/stage4b-resume-resource-check.json`
and the dated section in [STAGE4B_REPORT.md](STAGE4B_REPORT.md). No new model or
changed profile is required.

The commands below are historical reproduction notes. The later autonomous
workflow below performs permitted project recovery itself. Keep the accepted
database and document index; never terminate unrelated apps to force a test pass.

```powershell
$env:PYTHONPATH = 'backend;.'
uv run python -m scripts.evaluate_reliability --check-resources --output reports/stage4b-resource-check.json
# Only after admission succeeds: warms the already downloaded local model.
.\scripts\start_ollama.ps1
# In ignored .env: OLLAMA_TOOL_SELECTION=true and OLLAMA_REFERENCE_OUTPUT=true
docker compose up -d --no-deps --build --wait api
uv run python -m scripts.evaluate_reliability --output reports/stage4b-live-evaluation.json
```

Each of the original eight and fifteen unseen cases must run, followed by a manual
review of findings against the stored SQL/RAG oracles and verified quotations.
`completed` is not semantic acceptance. The follow-up runs only after its preceding
ranking is independently verified. If it fails, keep that dependency failure visible.

Official sources: [tool calling](https://docs.ollama.com/capabilities/tool-calling),
[structured outputs](https://docs.ollama.com/capabilities/structured-outputs),
[thinking](https://docs.ollama.com/capabilities/thinking),
[model tags](https://ollama.com/library/qwen3.5/tags), and the installed runtime's
own help for process-local llama-server cache settings. No external LLM judge is used.

## Autonomous recovery results — 2026-11-03

The current outcome is in the opening section of [STAGE4B_REPORT.md](STAGE4B_REPORT.md).
No routine environment work is assigned to the user. FC26 was absent; project-owned
API caches, evaluator lifetime, batch/context and local model residency were handled
automatically. No unrelated interactive application was closed.

Exactly one alternative was downloaded and verified: `qwen3.5:2b-q4_K_M`, digest
`1e2d21a4f03ab9e4a9c1976a4b7e88f21de61d65f2c5485d8fde8942be73f1e7`.
4B remained preferred. 2B/8K/batch128/cache0 scheduled the 23-case matrix but failed
business quality and initially exposed a now-fixed search-query ledger HTTP500.
2B/32K avoided specific 8K context overflows, then triggered the RAM guard. It is
not an accepted alternative. The original 4B was restored in `.env`; no model is
loaded at closure. Final free RAM/VRAM were 0.856 GiB / 5913 MiB.

The current launcher uses one checkpoint and zero prior-prompt RAM cache in its
own child process. Batch remains 512 by default for compatibility; the measured
low-memory experiment explicitly used `-BatchTokens 128` and matching
`OLLAMA_BATCH_TOKENS=128`. `-NoWarmup` verifies downloaded metadata without loading
weights. Context and batch parameters must match the API to avoid a runner reload.
The process-local settings do not alter an existing listener.

`python -m scripts.evaluate_monitored` is a reproducible Windows guard around the
existing evaluator, with physical/commit memory and paging counters. It verifies
ownership before stopping only its own Ollama tree on resource failure. Its paired
`.memory.json` is not a semantic score. Experimental 1 GiB resident admission failed
sustained trials and was reverted; the final guard/evaluator both require 1.5 GiB.
The 512 MiB observation floor is an emergency stop, not a safe steady-state claim.
