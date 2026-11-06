# Stage 6 — enterprise frontend acceptance

## Implementation status and exact starting checkpoint

Stage 6 adds an authenticated enterprise operations workspace to the existing local FastAPI/PostgreSQL application. Work started from Stage 5 checkpoint `68a76ec2189a554819730235540aac45d8fa5815` on local branch `codex/stage6-frontend`. There are no changes to the existing write engine, source calculations, migrations, database grants or model configuration. No Stage 7 or Stage 8 work is included.

## Frontend technology, design and navigation

| Area | Implementation |
|---|---|
| Frontend technology stack | Next App Router, React 19.3.1, Tailwind CSS 4.3.4, TanStack Query, Recharts 3.10.1, Radix and Lucide 1.69.0. The standalone production image runs on Node 24 as a non-root user. |
| Next.js version and TypeScript configuration | Next.js 16.4.5 and TypeScript 5.9.3 with strict checking and generated OpenAPI types. The pnpm lockfile pins dependencies. |
| Design system and visual identity | Shared indigo mark, cool canvas, white working panels, reusable statuses, forms, charts, tables, loading states and evidence panels. |
| Typography and colour system | Local system font stack, tabular numerals, visible focus, indigo actions, named teal/amber/red status and measured contrast refinements. See the [design system](DESIGN_SYSTEM.md). |
| Application shell and navigation | Authenticated workspace with grouped desktop navigation and a mobile drawer, visible page/section context, skip link, account controls and readiness. |

## Business and evidence views

| Area | Implementation and observed behaviour |
|---|---|
| Dashboard and KPI visualisations | Actual historical dates, delivery, inventory, finance and exception measurements. At the accepted default range the browser checked 69.92% supplier on-time delivery; charts use the same real series and expose exact data. |
| Supplier intelligence and procurement | Ranking, period-aware supplier profile and related purchase orders, performance, SLA and contract evidence. The investigation found Supplier 1 delivery at 33.33% and retrieved the applicable contract and escalation policy. |
| Inventory and warehouses | Stock and fulfilment risk, actual product/warehouse selectors and exact record details. The browser opened product 44 at warehouse 3. |
| Customer fulfilment | Historical service and customer promise analysis, selected orders and scoped exception details. |
| Financial intelligence | GBP exposure, ageing and scoped records, displayed using real units and currency. |
| Workforce and incidents | Separate historical workforce/incident views and current workflow queue; source period is not a filter for current operations. |
| Knowledge Base | Keyword, vector and hybrid search, excerpts and citations linked to the registered document and exact source version. |
| Investigations | Deterministic structured findings and separately registered evidence, with read-only tool counts visible. |
| AI Copilot and local LLM status | Verified deterministic mode, signed follow-up context and an explicit new conversation. Browser inference count is zero. The optional local LLM remains **BLOCKED** at the inherited Stage 4C live acceptance boundary; Stage 6 neither enabled nor retested it. |
| Historical data handling | Source metadata controls the reporting window. Dates, units, provenance and denominators are shown where relevant; seeded historical KPIs and present workflow state remain separate. |
| API integration | Explicit, typed Next gateway for approved paths. Additional FastAPI endpoints provide authenticated read projections and existing workflow filter extensions. See [API integration](FRONTEND_API_INTEGRATION.md). |
| Error and loading states | A load in progress, a genuinely empty result, unavailable service, forbidden action and stale workflow state have distinct UI states. |

## Workflow, approval and audit

| Area | Implementation |
|---|---|
| Workflow tasks and internal escalations | Scoped, searchable queue and record details, priority and assignment context, visible version and related work. |
| Proposal creation | Eight supported action-specific forms, trusted target selectors, captured evidence, draft, explicit submit and revision. |
| Approval inbox and human review | Actual role/scope decisions are made by Stage 5. A distinct reviewer sees the proposed operation and captured evidence and can approve or reject. |
| Workflow execution and execution receipts | An explicit authorized execution request produces a server receipt. Stable operation identity allows safe replay. The workflow record, receipt and event are read back from PostgreSQL through the real API. |
| Audit trail | Scoped and paginated history with actor labels, filters, event/target context and links. Audit and execution are produced by the existing workflow engine. |

## Authentication, session security, role control and validation

Stage 5 verifies every browser identity and role. The browser holds an opaque, httpOnly SameSite Strict cookie; server-only bearer material is encrypted at rest in the scoped Compose volume. HTTPS deployments require Secure cookies and the documented origin and TLS boundary. The gateway validates origin, CSRF, method, route, body bounds and mode. Logout revokes access and clears the browser cache. Protected business requests cannot bypass the server check by changing UI state. The Copilot gateway admits only `DETERMINISTIC` and validates zero inference; a conversation handle is bound to the authenticated frontend session.

Actual browser tests cover missing and revoked identity, missing CSRF, a forged origin, denied roles, cross-scope access, injected text rendered inertly, disallowed provider mode, an unregistered agent route and fabricated conversation handles. The existing direct FastAPI read-only endpoints are separate, loopback demo surfaces governed by the previous-stage policy; the frontend is not a production IAM layer. See [authentication boundaries](FRONTEND_AUTHENTICATION.md).

## Browser acceptance, responsive design and visual review

Playwright uses installed Microsoft Edge against the production Compose service. The user-facing sign-in and actual rendered screenshots were opened and inspected. [The design review](STAGE6_VISUAL_REVIEW.md) records observations across 15 categories. First attempts exposed low contrast, a mismatched account control name and a false empty evidence state; these were corrected. A later desktop scan found three amber values below 4.5:1 and led to a darker token. Test harness fixes narrowed a locator matching the Next route announcer, used the actual combobox role, and waited for the Copilot route to mount before filling its input.

The final six-case run passed, as did a separate real restart test. [Browser evidence](../reports/stage6-browser.json) records test durations, viewport measurements and the persisted proposal, receipt and record identifiers.

| Browser gate | Observed result |
|---|---|
| A — Dashboard | **PASS** — the real dashboard and chart loaded, KPI values matched, and date changes updated the view. |
| B — Supplier | **PASS** — supplier selection, period-aware performance, applicable contract and related data were inspected. |
| C — Knowledge | **PASS** — the real procurement procedure was found and its verified citation opened the exact registered version. |
| D — Investigation | **PASS** — comparing delivery with the SLA and escalation policy returned 33.33%, registered evidence and four read-only tool calls. |
| E — Proposal | **PASS** — an authenticated operator attached verified evidence, saved a draft and submitted it. |
| F — Human approval | **PASS** — an independently authenticated, distinct reviewer examined and approved that proposal. |
| G — Execution | **PASS** — the operator executed the approved change; the task was read back and a same-key replay returned the original receipt with one committed effect. |
| H — Audit | **PASS** — the workflow event and receipt appeared with the persisted proposal and task. |
| I — Authorization | **PASS** — viewer, outsider and unauthorized request attempts were denied; stale, rejected and expired proposals did not execute. A revision did not inherit the stale proposal's approval. |
| J — Copilot | **PASS** — an actual deterministic ranking, a contract comparison follow-up and conversation reset worked with zero LLM calls. |
| K — Responsive | **PASS** — measured no page-wide overflow at 1440, 1280, 1024, 768 and 390 px; checked a loaded mobile task list and keyboard operation of decision controls. Axe found zero violations in the loaded desktop dashboard and mobile task-list scans. |
| L — Restart | **PASS** — only OpsPilot db, API and frontend were restarted. The pre-restart browser session retained the same principal and expiry and read back the identical committed task and version after restart. |

Additional real browser cases applied a task priority change, created and closed an evidence-bound escalation, and checked inventory, financial, customer and workforce scope. The security assertions verified inert display of injected text and blocked unsafe requests without editing the application database directly.

### Frontend performance and screenshots

These are single local browser observations, not capacity targets: initial login document 285 ms; sign-in plus loaded dashboard/chart 2,308 ms; supplier navigation 939 ms; table search 139 ms; knowledge search 164 ms; deterministic investigation 556 ms. The scoped restart and browser persistence sequence took 11.9 s. The actual captures are in [the screenshot directory](../reports/stage6-screenshots/), including [desktop overview](../reports/stage6-screenshots/dashboard-1440.png), [mobile task list](../reports/stage6-screenshots/tasks-390.png), [approval review](../reports/stage6-screenshots/approval-1440.png), [receipt](../reports/stage6-screenshots/receipt-1440.png) and [source citation](../reports/stage6-screenshots/citation-1440.png).

## Full backend regression and frontend build

- The complete actual PostgreSQL suite passed **466/466** in 233.30 seconds, including the 460 prior tests and six new workspace projection tests. There was one existing Starlette/httpx deprecation warning. [Backend JUnit](../reports/stage6-backend-pytest.xml).
- Ruff lint and format passed; the final format check found 245 files already formatted. Alembic was at `0004 (head)` and found no new upgrade operations.
- The production Docker build, strict TypeScript check, ESLint and both frontend unit checks passed. The browser results are separate from the build.

## Stage 4C intelligence and Stage 5 approval regression

The [runtime validator](../reports/stage6-prior-regression.json) passed against the already-restarted stack. It checked unchanged prior-stage analytics, the original index, the PostgreSQL read-only role and all 44 citations. The [42-query retrieval evaluation](../reports/stage6-retrieval.json) matched accepted quality metrics for keyword, vector and hybrid retrieval; all three had 100% citation-resolution and negative-query accuracy. Hybrid recall@3 was 94.29%. PostgreSQL pgvector was 0.8.7.

The [deterministic live HTTP evaluator](../reports/stage6-deterministic-summary.json) passed all **38/38** automatic oracle checks: eight original, fifteen unseen and fifteen additional scenarios. Median HTTP latency was 111.3 ms and maximum 1,420.6 ms. It recorded zero LLM calls, zero tokens and zero model interpretations. This is a deterministic regression, including expected refusals, partial outcomes and clarifications; it is not a fresh full qualitative review of model prose.

The six browser scenarios and the full PostgreSQL suite retained Stage 5 approval, rejected and expired state, stale protection, revision, replay, access, and audit behaviour. The restart test used the persisted real task and authenticated session. The legacy runtime validator did not itself restart anything and did not run model acceptance. Its inherited `ready_for_stage5` field is a legacy model gate, not the Stage 6 verdict.

## Database integrity, fingerprint and Docker health

The [post-restart preservation verifier](../reports/stage6-preservation.json) recorded the exact original business fingerprint `7ed73422d07ddb0528f0ce5641e1767cdef95aa698dfcddf8dc26aad68dae0b7`. It verified five original source scenarios, all original source counts and the original knowledge index, the 17 read-only tools and 14 deterministic capabilities, and every preexisting auth, workflow and audit row against its own digest. The new synthetic browser activity added workflow records and sessions; it did not alter accepted business data. The three OpsPilot services were healthy and no disposable PostgreSQL test databases remained.

Docker Desktop was stopped at the start of Stage 6. Starting the installed engine was sufficient; no reset or global configuration change was needed. Two existing ProductPulse containers resumed during engine recovery under Docker's own configuration, so their start/finish timestamps differed from the older Stage 5 Docker snapshot, with the same container IDs. The Stage 6 pre-frontend snapshot was taken after engine recovery and before frontend or browser integration. From that snapshot through the OpsPilot-only restart, all ten unrelated container states, mounts and restart counts matched, and the existing networks and volumes matched. No command explicitly stopped, recreated or modified another project's containers. The only new volume was the OpsPilot frontend session volume.

## Windows local launch, file manifest and evidence

From the repository root run `./scripts/start_frontend.ps1 -Build -Open` with the existing local Stage 5 account and database setup. Open [OpsPilot](http://127.0.0.1:3106). The launcher starts only the Compose project services and checks readiness; it does not generate credentials, reseed, or start a model. After the initial build, omit `-Build` for regular startup. The [user guide](FRONTEND_USER_GUIDE.md), [testing instructions](FRONTEND_TESTING.md) and [file manifest](STAGE6_FILES.md) describe the setup, procedures and changed files.

## Git checkpoint

The validated implementation and evidence are in local commit `33f5be478ffee2d0a7c0f4bb2f27d5723bf9a7c4` (`Build professional OpsPilot enterprise frontend`). The following report-only commit records closure. The staged files passed the whitespace and local credential checks. Neither commit was published.

## Remaining limitations and next recommendations

The accepted deployment boundary is one local synthetic enterprise workspace. The app does not implement a production SSO provider, internet-facing deployment, centralized session fleet, or global search. Dense tables scroll within their region on small screens. The design review and axe scans do not certify WCAG conformance. Verified Copilot uses deterministic structured prose. Treat any future model evaluation and production IAM work as separate acceptance tasks.

## Acceptance states

| Gate | Result |
|---|---|
| Frontend application | PASS |
| Design system | PASS |
| Business dashboard | PASS |
| Analytics integration | PASS |
| Knowledge Base | PASS |
| Investigations | PASS |
| Workflow tasks | PASS |
| Human approval UI | PASS |
| Audit view | PASS |
| Authentication and RBAC | PASS |
| Copilot deterministic | PASS |
| Local LLM | BLOCKED — inherited optional gate; no model run |
| Responsive design | PASS |
| Accessibility | PASS — measured scope above |
| Real browser end-to-end | PASS |
| Stage 1–5 regression | PASS |

- **STAGE 6 FRONTEND FUNCTIONALITY: PASS**
- **STAGE 6 VISUAL QUALITY: PASS**
- **STAGE 6 SECURITY: PASS** within the documented local deployment boundary
- **STAGE 6 BROWSER ACCEPTANCE: PASS**
- **STAGE 1–5 REGRESSION: PASS**
- **STAGE 6 ACCEPTED: YES**
- **READY FOR STAGE 7: YES** — Stage 7 was not started
