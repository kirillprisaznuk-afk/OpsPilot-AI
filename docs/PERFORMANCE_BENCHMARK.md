# Stage 7 local performance benchmark

Windows and Docker Desktop ran the production Next.js frontend, FastAPI and PostgreSQL on the user's laptop with 15.26 GiB usable physical memory and an RTX 4050 Laptop GPU. The benchmark uses real loopback requests. Analytics and deterministic intelligence are CPU and PostgreSQL workloads. The model is outside this benchmark.

The repeatable HTTP test opens one real operator session and performs 20 timed samples per operation after one warm-up. Requests are grouped into waves of at most four, reduced to two when available RAM starts below 1.5 GiB. The runner checks available RAM and system commit before each wave. It records success counts and errors, median, p95 when there are at least 20 successful samples, and maximum. Browser timings are single interactive observations. Chromium JavaScript heap is scoped to one test page.

```powershell
$env:PYTHONPATH = 'backend;.'
.venv/Scripts/python.exe -m scripts.benchmark_local --output reports/stage7-performance.json
.venv/Scripts/python.exe -m scripts.validate_workflow --output .local-tools/stage7-workflow-live.json
```

The live workflow validator uses existing demo identities and appends synthetic records. It measures real login, draft creation, submission, approval, execution and audit reads. Cold project startup means all three project containers were stopped before timing. Warm startup means the existing healthy containers were already running. The Docker Desktop engine stays running during both samples.

| Authenticated HTTP operation | Samples | Failures | Median ms | p95 ms | Max ms |
|---|---:|---:|---:|---:|---:|
| Dashboard overview | 20 | 0 | 349.4 | 409.6 | 425.8 |
| Supplier detail | 20 | 0 | 188.9 | 203.1 | 217.5 |
| Warehouse analytics | 20 | 0 | 204.2 | 253.9 | 257.5 |
| Hybrid keyword/vector knowledge search | 20 | 0 | 193.5 | 212.4 | 215.6 |
| Deterministic investigation | 20 | 0 | 522.4 | 764.3 | 770.6 |
| Scoped task list | 20 | 0 | 204.5 | 210.1 | 210.4 |
| Scoped paginated audit | 20 | 0 | 202.9 | 219.4 | 219.5 |

All 140 samples succeeded with up to four requests in flight. Available physical memory was 1.642 GiB before and 1.698 GiB after. One gateway login took 242.8 ms. Separate direct workflow API medians were 112.72 ms login (6), 45.92 ms draft creation (9), 45.78 ms submit (10), 47.55 ms approve (9), and 208.79 ms execute/replay (14). The direct audit read took 30.37 ms (one sample). All 72 checks matched their expected HTTP result, including expected denials. Maxima and individual requests are in the evidence. [Concurrent samples](../reports/stage7-performance.json) · [Workflow timings](../reports/stage7-workflow-live.json)

The stopped-project launch took 18.08 s and the already-running launch took 2.41 s. The final Edge run measured 405 ms for the initial document, 1.96 s from sign-in to the loaded dashboard, 936 ms for supplier navigation, 119 ms for supplier table search, 173 ms for knowledge search, and 386 ms for investigation. After the test interactions the page used 17.3 MiB of JavaScript heap with 36.6 MiB allocated. Browser and startup measurements are one sample each and carry no percentile or throughput claim. [Browser measurements](../reports/stage7-browser.json) · [Startup measurements](../reports/stage7-startup.json)
