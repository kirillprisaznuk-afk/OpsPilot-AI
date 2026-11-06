# Stage 8 release file manifest

The [release report](STAGE8_REPORT.md) records what actually ran. This manifest lists the files added or changed for release and how to find the evidence.

| Files | Purpose |
| --- | --- |
| [README](../README.md), [architecture](ARCHITECTURE.md) | Product entry point, system boundaries, and two renderable Mermaid data-flow diagrams. |
| [Quick start](QUICK_START.md), [demo guide](DEMO_GUIDE.md) | Windows setup and recovery, an independent clean demo, and five- and ten-minute walkthroughs. |
| [Case study](CASE_STUDY.md), [portfolio copy](PORTFOLIO_COPY.md) | Technical decisions and tradeoffs, plus LinkedIn, résumé and interview copy. |
| [Release notes](RELEASE_NOTES.md), [publication checklist](PUBLICATION_CHECKLIST.md), [Stage 8 report](STAGE8_REPORT.md) | Release scope, limits, publication procedure, and the acceptance matrix. |
| [Screenshot gallery](../assets/screenshots/README.md) | Twelve unretouched 1440 × 980 PNGs of real analytics, citation search, Copilot, task, approval, receipt and audit screens. |
| [Evidence index](../reports/README.md) | Release checks and preserved earlier-stage reports. |
| [Windows launcher](../scripts/opspilot.ps1), [compatibility wrapper](../scripts/start_frontend.ps1), [workflow status](../scripts/workflow_status.py) | Guarded bootstrap, normal launch, stop and status with a restricted database probe. |
| [Compose](../docker-compose.yml), [environment example](../.env.example) | Loopback ports, named volumes and a public-safe configuration template. |
| [CI workflow](../.github/workflows/ci.yml), [pnpm override](../frontend/pnpm-workspace.yaml), [pnpm lock](../frontend/pnpm-lock.yaml) | Pinned CI and scoped dependency advisory remediation. |
| [Global styles](../frontend/src/app/globals.css), [live browser tests](../frontend/tests/live.spec.ts), [recovery tests](../frontend/tests/recovery.accept.ts), [browser configuration](../frontend/playwright.config.ts) | Layout polish, real showcase captures, outage tests and browser test targeting. |
| [Deterministic evaluator](../scripts/evaluate_hybrid.py), [benchmark](../scripts/benchmark_local.py) | Release measurements against an explicit local origin. |
| [Hybrid regressions](../backend/tests/test_hybrid.py), [testing guide](TESTING.md) | Model safety tests with explicit test mode and an isolated Windows temporary directory option. |

Seven historical evidence files retain their results with machine-specific paths replaced by portable labels: `reports/stage4b-autonomous-runtime-checks.json`, `reports/stage4b-lean-working-set-recovery.json`, `reports/stage4b-postfix-working-set-recovery.json`, `reports/stage4b-project-working-set-recovery.json`, `reports/stage4b-resume-verification.json`, `reports/stage4b-runtime-checks.json`, and `reports/stage5-pytest-initial.xml`.

Twelve historical JUnit reports under `reports` have a portable test-host label. Test outcomes, durations and failure text were preserved except for the local paths listed above. [Testing guide](TESTING.md)

Private dotenv files, generated account passwords, model downloads, database and session volumes, raw browser traces and local working scripts are outside the distributable tree. The public snapshot is separate from the historical development branch.
