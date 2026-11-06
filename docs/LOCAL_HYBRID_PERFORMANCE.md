# Local hybrid runtime and measured performance

Measurement date: 2026-11-04. This is a shared Windows laptop; sampled host memory
includes other applications and test/oracle processes. It is not isolated model RAM.

## Configuration and real admission

Ryzen 7 8845HS; 16 GB installed, 15.265 GiB visible RAM;
RTX 4050 Laptop GPU, 6141 MiB VRAM. Approximately 148 GiB
free storage was observed during development. Existing Ollama 0.40.12 is project-owned,
loopback-only, with `OLLAMA_NO_CLOUD=true` confirmed in its startup log. Both existing
Qwen3.5 local GGUF models remain installed; no new model or provider was downloaded.

Hybrid candidate: `qwen3.5:2b-q4_K_M`, 8192 context, batch 128, no thinking, temperature
zero, output 256, at most two language calls, eight-second per-call timeout. The
existing 4B full-agent candidate remains experimental. No actual model inference
ran in Stage 4C: resource admission blocked cold load.

Final recorded admission: **1.178 GiB free RAM**, **5626
MiB free VRAM**, **13.009 GiB free commit**. Required RAM is
1.5 GiB; commit 2 GiB; cold-load free VRAM 4096 MiB. Per-request admission also requires
a fresh host heartbeat and the exact fully GPU-resident model/context with at least
512 MiB spare VRAM. No threshold was reduced. No unrelated application was closed.
Sampled evaluation free RAM ranged 0.366–1.065 GiB; minimum sampled free
VRAM 5626 MiB. Sampling is approximately every two seconds plus measurement
overhead. Maximum sampled total host RAM usage was 14.899 GiB and GPU usage
515 MiB, including unrelated applications. Sub-sample peaks and model
memory/throughput are **not measured**.

## Actual measurements

| Run | Model calls / observed tokens | Tool calls | Latency |
|---|---:|---:|---:|
| Previous real Stage 4 A01 | 5 / 80,979 | 7 successful | 62.640 s |
| Stage 4C A01 deterministic | 0 / 0 | 4 | 3.858 s server |
| Stage 4C A01 hybrid HTTP fallback | 0 / 0 | 4 | 0.238 s server |
| Stage 4C real local interpretation | NOT RUN | — | BLOCKED by RAM |

Deterministic 38-case HTTP median 110.14 ms, maximum
3879.43 ms. Hybrid/fallback 38-case median
118.12 ms, maximum 1460.41 ms.
A01 deterministic SQL tools 109.27 ms and RAG tools
3685.05 ms. Refusal HTTP timings, exact tool timings,
full responses and sampled resources are retained per case in the two evaluation
JSON files. Cold retrieval and host load affect these comparisons.

These results show that the deterministic architecture answers supported questions
without model consumption. They **do not measure a faster or more accurate LLM**.
Actual model calls, observed tokens and transmitted inference bytes are zero.
Prospective frame sizes, throughput and peak model residency remain unmeasured
because no inference ran. Local usage charges are zero; electricity/hardware costs are not
estimated. No missing provider token count is guessed.

## Free Windows startup

Use the existing accepted database/index and downloaded weights. No reseed, new
model, key or subscription is needed on this machine. From a PowerShell session:

```powershell
uv sync --frozen
$env:PYTHONPATH = 'backend;.'
./scripts/start_hybrid.ps1 -DeterministicOnly
# When actual RAM meets admission, in a fresh PowerShell session:
./scripts/start_hybrid.ps1
Invoke-RestMethod http://127.0.0.1:8001/api/v1/hybrid/status
```

The helper controls only the portable OpsPilot Ollama runtime and Compose API. Its
small host measurement watcher, used when admission permits model startup, publishes
actual Windows RAM/commit/GPU measurements to an ignored folder mounted read-only
into Docker. Missing/stale measurements disable inference; no model cold-load occurs
inside the API. The watcher requests unloading of the selected local model if RAM
falls below 512 MiB or commit below 2 GiB. This is a precaution, not evidence of
sustained model safety. `-DeterministicOnly` disables language inference for that
Compose invocation. The API can also explicitly request `mode=DETERMINISTIC`.

Once resources genuinely permit loading, rerun the same 38 cases in HYBRID_LOCAL
and require actual measured language calls, valid frames, supported interpretation
and sustained resource headroom. Do not force-close unrelated programs or lower
admission to produce a pass. Until then hybrid acceptance remains BLOCKED.

Official references: [native chat and usage fields](https://docs.ollama.com/api/chat),
[structured JSON schema output](https://docs.ollama.com/capabilities/structured-outputs),
[local runtime/GPU configuration](https://docs.ollama.com/faq).
