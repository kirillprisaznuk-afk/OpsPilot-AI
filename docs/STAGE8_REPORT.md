# OpsPilot AI Stage 8 release report

## Implementation status and starting checkpoint

Stage 8 began from the clean Stage 7 closure `c3f98892da0215d5debedd8254a62a74149d8756` on `codex/stage7-quality`. The release work is on `codex/stage8-release`. The source generator, PostgreSQL business semantics, analytics tool catalogue, RAG corpus and workflow policy were carried forward.

The implementation and regression checkpoint is `eb9a948408dce9446549b6bc2ee0ed4bc41d10ad`. The closure commit includes the release evidence. The intended public tree is the identical, separately audited standalone `codex/public-v1.0.0-local`, locally tagged `v1.0.0-local`. Use Git to resolve the exact closure and publication candidate commit IDs.

## Initial release audit and product positioning

The starting local stack had three healthy services and no Git remote. Initial release blockers were a bootstrap that assumed existing private accounts and a populated volume, historical machine paths in seven reports, and the absence of CI and a reviewed public branch. The product is a local operations intelligence and governed action demonstration for a synthetic distributor. The accepted deterministic interpretation and read-only tools are separate from optional experimental model inference.

## Frontend quality and visual refinement

The release keeps the Stage 6 workspace and design tokens. The chart panels now use shrinkable grid tracks and stop stretching their neighbors when a table of exact values is expanded. The browser exercises actual analytics, source links, session boundaries, task/escalation forms, independent review and audit. Stage 8 retains the small-screen internal scroll region for dense tables.

Microsoft Edge loaded 18 authenticated routes at widths of 390, 768, 1024, 1280 and 1440 pixels. None of the 90 rendered combinations overflowed the page; mobile navigation also worked with reduced motion enabled. This is a targeted responsive and accessibility check. [Responsive measurements](../reports/stage8-responsive.json)

## Screenshot collection and authenticity

The gallery uses live Edge captures from the separate Northstar Supply installation and lists each route and scope. The pending proposal, task, execution receipt and audit views were captured at their actual workflow states. Screens were reviewed for loading states and sensitive material. [Screenshot gallery](../assets/screenshots/README.md)

The gallery is the release's visual walkthrough. No optional video is included.

## README, architecture and data flow

The README opens with the actual dashboard and a short example connecting supplier delivery, contractual evidence and human approval. Two source-controlled diagrams document the logical read path and write path, including session and role checks, verified citations, transaction boundaries and retries. [README](../README.md) · [Architecture](ARCHITECTURE.md)

## Fresh setup and clean installation

The initial independent setup ran in a new Git clone with no local dotenv, environment, encoder cache, workflow identities or volumes. It used project `opspilot-release-test`, loopback ports 3118/8018/55448 and separate database and frontend session volumes. It downloaded and verified the pinned CPU MiniLM files, applied Alembic 0004, generated the accepted source fingerprint, indexed all 44 documents and generated six independent demo accounts. The production API and frontend were built and started against that isolated database. The code under test was then fast-forwarded to the reviewed candidate before the final CI-equivalent checks.

## Windows launcher and credential provisioning

`opspilot.ps1` offers `Setup`, `Start`, `Stop` and `Status`. Setup refuses existing configuration, named database/session volumes, existing project containers or occupied ports. It writes private random credentials under ignored paths. The old `start_frontend.ps1` delegates to Start. The independent operator and reviewer still use the existing username-based login. Existing installations reuse the same files and database. [Quick start and recovery](QUICK_START.md)

On PowerShell 7.6.5, a start of the stopped, built stack took 23.05 s, with the API first ready at 13.52 s and the frontend login first responding at 18.01 s. Running Start on the already healthy stack took 3.62 s. Each is one sample. Stop left no running services in the isolated project, the configuration and generated accounts were byte-identical after restart, and repeat Setup refused. Status verified all three service health checks and the restricted workflow database access. At idle, a single Docker sample showed 124.9 MiB for the API, 25.14 MiB for PostgreSQL and 48.83 MiB for the frontend. [Startup measurements](../reports/stage8-startup.json)

## Demonstration and technical case study

The five-minute walkthrough follows a supplier from observed performance through the applicable agreement and procedure to an internal task that requires a second authorized person. A deeper engineering walkthrough explains how the evidence and receipt can be verified. [Demo guide](DEMO_GUIDE.md) · [Case study](CASE_STUDY.md)

## Publication security, Git history and repository hygiene

The audit examined all reachable local blobs and scanned the candidate against known current local passwords and token, key, URI and artifact patterns. It found seven reports with absolute Windows paths and twelve JUnit reports with a local test hostname, with one report in both sets. It found no current credentials or high-confidence token or key patterns. The distributable copies use portable labels. The public ref uses a standalone commit of the reviewed tree, leaving the original machine identifiers and historic author metadata outside the public ref. The accepted local engineering history remains intact. [Publication checklist](PUBLICATION_CHECKLIST.md) · [Source audit evidence](../reports/stage8-public-audit.json)

## Dependency and license review

A scoped lockfile override updated the lint-only minimatch chain to 11.0.1. The resulting npm audit returned zero advisories. The locked Windows Python audit returned zero findings across 49 distributions. Third-party package metadata and license files were reviewed. The MiniLM model card reports Apache-2.0 and the model is fetched separately by digest; no downloaded model is distributed. No license was assigned to the OpsPilot source on the owner’s behalf. [Dependency evidence](../reports/stage8-dependencies.json) · [Minimatch advisory](https://github.com/advisories/GHSA-g3hv-75wg-m249) · [Upstream encoder model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)

## GitHub Actions and CI validation

The workflow uses a read-only job token, pinned action revisions, disabled credential persistence and a disposable digest-pinned PostgreSQL/pgvector service. It installs locked Python and Node dependencies and runs style, tests and a production frontend build. Actionlint 1.7.11 passed locally after the service port map key was quoted. Hosted CI is **NOT_RUN** because the repository has not been published.

The final Windows run of the locked backend suite passed **471 tests in 238.21 s** against real isolated PostgreSQL, with one existing Starlette TestClient deprecation warning. Ruff lint and format passed. Frozen frontend install, TypeScript, ESLint, two frontend unit tests, and the production image build passed. [Backend JUnit](../reports/stage8-backend-pytest.xml)

## Documentation and career copy

The package includes a concise README, installation and recovery, architecture, verified demo, security audit, case study, release notes, publication checklist and a separate LinkedIn/CV draft. Earlier evidence remains under the same paths, indexed by stage. [Portfolio copy](PORTFOLIO_COPY.md) · [Evidence index](../reports/README.md)

Both Mermaid diagrams rendered locally. The link check covered the README and all Markdown files under `docs`, `reports` and `assets`. The LinkedIn project description has 354 characters and the draft lists ten skills. [File manifest](STAGE8_FILES.md) · [Documentation checks](../reports/stage8-documentation.json)

## Known limits and publication

The connected GitHub account was verified as `kirillprisaznuk-afk`. The candidate destination `kirillprisaznuk-afk/OpsPilot-AI` returned 404 during the authenticated read-only check. Public creation and pushing require explicit authorization for that target. Local Qwen remains experimental. The tested application boundary is synthetic data on Windows loopback, with targeted accessibility and bounded performance checks.

## Business, retrieval and workflow checks

All eight regular browser scenarios passed against the independent production build. These covered live dashboard metrics and historical filters; supplier terms, evidence search and investigation; a verified proposal with a distinct reviewer, execution, receipt, audit and replay; task changes and escalation, including stale, rejected and expired attempts; session and origin checks; and responsive navigation. The synthetic supplier example showed 24 of 72 orders on time (33.33%) against a 95% target. The application treats that gap as an observation; it does not establish breach.

Both additional browser recovery scenarios passed. A restart of the three isolated Compose services preserved the exact task and version, the browser principal and the original session expiry. Temporary API and PostgreSQL outages recovered without changing that expiry. The browser retained the existing answer and unsent prompt during the API outage and required an explicit reset for an expired conversation. The restart scenario took 9.99 s from restart to verified response; API and database stop-to-authenticated timings were 14.56 s and 11.85 s. [Browser acceptance and persistence](../reports/stage8-browser.json)

All 42 retrieval evaluations matched the accepted Stage 7 metrics: recall at five was 60.00% for keyword, 87.14% for vector and 94.29% for hybrid search. All three modes achieved 100% citation resolution and no-answer accuracy on this fixed set. One real `HYBRID_LOCAL` request with inference disabled completed through the verified fallback, using zero model calls and zero model request bytes and returning two citations.

The SQL and HTTP checks verified five original cross-domain scenarios, ten typed investigations and the existing reconciliations against the accepted dataset. All 38 deterministic HTTP cases passed the automatic checks and performed 129 comparisons against the saved tool oracle. The outcomes included 26 completed, three partial, three refused, three requiring clarification, and three with insufficient evidence. Median HTTP time was 114.38 ms; the slowest was 1,598.79 ms, with zero language model calls. The supplier investigation and safe refusal boundaries were also exercised through the browser and workflow suite. Alembic was `0004 (head)` without migration drift; all 44 stored source citations resolved. [SQL and HTTP analytics](../reports/stage8-analytics.json) · [Retrieval](../reports/stage8-retrieval.json) · [Deterministic suite](../reports/stage8-deterministic.json) · [Optional model fallback](../reports/stage8-optional-model.json)

The workflow validator passed 72 real HTTP checks on the independent stack and committed all eight allowed action types. Six simultaneous attempts to execute one proposal returned a single receipt and created one task. Checks covered distinct users, anonymous and viewer denials, stale or rejected requests, forged evidence, scope restrictions and retry behavior. The median across all 72 requests was 57.53 ms (maximum 1,031.21 ms) on this laptop during the release checks. [Workflow evidence](../reports/stage8-workflow-live.json)

## Measured user interactions

The browser trace recorded a 223 ms initial document response, 1.83 s for the dashboard interaction, 0.94 s to navigate to the supplier, 133 ms to filter a table, 178 ms for knowledge search, and 2.97 s for the first browser investigation. These are individual Edge measurements on the clean stack; the 38-case HTTP median above is a separate measurement. The browser used about 16.3 MiB of JavaScript heap (34.8 MiB allocated), not the whole browser process.

The live workflow HTTP median was 117.55 ms for login (six samples), 62.14 ms for proposal creation (nine), 53.50 ms for approval (nine) and 222.59 ms for execution (14 successful responses, including retries). The single audit list sample was 35.71 ms. These are local synthetic workloads. They do not establish throughput for a production service.

The main Windows Compose gateway then completed 140 measured requests without failures (20 per operation, up to two concurrent, warmup excluded). Median / p95 were 280.5 / 317.1 ms for dashboard data, 103.6 / 121.1 ms for supplier detail, 129.1 / 266.0 ms for the warehouse query, 76.7 / 84.5 ms for hybrid knowledge search, 270.7 / 373.5 ms for deterministic investigation and 72.9 / 82.4 ms for paged audit. One gateway login took 318.8 ms. The bounded run remained above its 1 GiB free-RAM threshold and made no model calls. [Gateway benchmark](../reports/stage8-performance.json)

## Primary Docker release and data preservation

The isolated project containers, its network and its two verified named volumes were removed after acceptance. The primary release started at `http://127.0.0.1:3106`; PostgreSQL, the API and the frontend all reported healthy. Alembic is `0004`. The restricted workflow probe and sign-in endpoint passed. The existing primary PostgreSQL volume, local configuration and account file were reused.

The pre-release and post-release source fingerprint was `7ed73422d07ddb0528f0ce5641e1767cdef95aa698dfcddf8dc26aad68dae0b7`. The release matched the original corpus and vector index, 44 documents, 17 read-only tools, 14 deterministic capabilities and every original row digest in the auth and workflow tables. These include 82 proposals, 74 approvals, 60 execution records and 672 audit events. The read-only gateway benchmark added one attributable authentication session and two audit events; the original rows were unchanged. Ten unrelated containers and the unrelated networks and volumes were unchanged. No test database remained. [Primary preservation evidence](../reports/stage8-preservation.json)

## Issues found and resolved during release validation

- The initial local CI schema check rejected a numeric port map key. Actionlint passed after it was quoted.
- A TypeScript path variable shadowed a module import. The production frontend built after the variable was renamed.
- The first Windows status check looked up the wrong workflow field; it now uses the existing restricted policy reader. The first browser capture run also revealed an ambiguous task row selector; the final run verified the saved ID and title against the real API.
- An early Windows launcher run left empty database variables in the calling shell, overriding valid dotenv values. Start and Status now preserve set and unset caller values. The Windows regression uses a workspace temporary directory because the pre-existing global pytest directory denied access. Two model safety tests now set their intended test mode explicitly, so the fresh installation can keep real inference off without changing what the tests exercise.

## Release acceptance matrix

| Area | Status | Evidence |
| --- | --- | --- |
| Product functionality | PASS | Production build, real browser and API, original capabilities preserved. |
| Visual quality | PASS | Real Edge review of twelve frames; 90 loaded route and viewport combinations. |
| Business analytics | PASS | Original SQL reconciliations, ten typed investigations and five cross-domain scenarios. |
| RAG and citations | PASS | 42 retrieval cases, unchanged metrics, all 44 stored citations resolved. |
| Deterministic intelligence | PASS | 38 real HTTP cases, 129 saved-oracle comparisons and zero LLM calls. |
| Workflow execution | PASS | 72 checks, all eight action types and one effect from six concurrent retries. |
| Human approvals | PASS | Distinct principals; blocked self-approval, wrong scope and stale or changed proposals. |
| Security | PASS | Read-only agent tools, authenticated gateway, origin and CSRF checks, evidence and scope validation, controlled execution. |
| Database integrity | PASS | Accepted fingerprint, Alembic 0004 and every original primary workflow and audit row matched. |
| Windows launch | PASS | Start, Stop, Status and the compatibility entry point on PowerShell 7.6.5. |
| Fresh installation | PASS | New clone, model cache, database and account set with separate Compose ports and volumes. |
| Reproducible demo | PASS | Genuine browser journey; independently created task, receipt and audit. |
| Backend tests | PASS | 471 tests against real PostgreSQL; Ruff lint and format passed. |
| Frontend tests | PASS | Frozen install, TypeScript, ESLint, two unit tests and production build. |
| Browser end-to-end | PASS | Eight regular tests and two restart and outage tests. |
| CI local validation | PASS | Actionlint and local equivalent of locked backend/frontend steps. |
| CI remote validation | NOT_RUN | No GitHub repository or hosted run verified. |
| GitHub security audit | PASS | Exact standalone ref audited before tagging; local historical refs are excluded. |
| README and documentation | PASS | Checked relative paths, two rendered diagrams, demo and recovery. |
| Screenshots | PASS | Twelve reviewed real Edge frames, no sensitive screenshot metadata. |
| Portfolio materials | PASS | Case study, release notes, five-minute demo, LinkedIn and CV copy. |
| Optional local LLM | EXPERIMENTAL | No accepted Qwen inference; verified fallback with zero calls. |
| Publication | READY_TO_PUBLISH | Audited standalone ref and local tag. Explicit authorization for the exact public destination is pending. |

## Final assessment

- **STAGE 8 TECHNICAL ACCEPTANCE: YES.** The independent install and real runtime, regression, restart and primary data checks passed.
- **STAGE 8 PORTFOLIO ACCEPTANCE: YES.** The real screenshots, documentation, walkthrough, case study and career copy are complete and checked.
- **PUBLIC RELEASE SECURITY GATE: PASS.** This applies to the reviewed standalone candidate. The private engineering branch includes the earlier machine identifiers and is outside the approved public scope.
- **PUBLICATION AUTHORIZED: NO.** Explicit approval for a public `kirillprisaznuk-afk/OpsPilot-AI` is required under the Stage 8 publication gate.
- **GITHUB PUBLICATION: READY_TO_PUBLISH.** No repository creation or push occurred. No repository URL or remote CI outcome was verified.
- **COMPLETE PROJECT RELEASE STATUS: READY.** The local application and portfolio release are accepted. Ollama inference remains experimental and was unavailable in this acceptance run. The tested release operates on synthetic data and local Windows loopback.
