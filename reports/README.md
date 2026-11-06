# Evidence index

The current release summary lives in [the Stage 8 report](../docs/STAGE8_REPORT.md). Files prefixed `stage8-` contain release measurements. Earlier stage reports document how the product was built and validated.

- [Analytics and source integrity](stage8-analytics.json) records the fingerprint, original scenarios, SQL reconciliations and typed investigations.
- [Retrieval](stage8-retrieval.json), [deterministic investigations](stage8-deterministic.json) and [optional model fallback](stage8-optional-model.json) separate retrieval quality and verified answers from experimental inference.
- [Live workflow](stage8-workflow-live.json) records all eight approved action types, timing and concurrent replay. [Responsive coverage](stage8-responsive.json) records the measured route and viewport pairs.
- [Backend JUnit](stage8-backend-pytest.xml) and [browser acceptance](stage8-browser.json) contain the regression and recovery results.
- [Windows startup](stage8-startup.json) records readiness, launcher guards and scoped container memory.
- [Gateway benchmark](stage8-performance.json) and [primary preservation](stage8-preservation.json) record the launched release's measurements and the comparison with the pre-release database and Docker baseline.
- [Dependencies](stage8-dependencies.json), [source audit](stage8-public-audit.json), and [documentation checks](stage8-documentation.json) describe the release review.

- [Stage 7](../docs/STAGE7_REPORT.md) covers the original acceptance and hardening checks, including workflow recovery and concurrency.
- [Stage 6](../docs/STAGE6_REPORT.md) records the first browser and design acceptance.
- [Stage 5](../docs/STAGE5_REPORT.md) records transactional workflow and approval verification.
- [Stage 4C](../docs/STAGE4C_REPORT.md) separates accepted deterministic capabilities from experimental local language interpretation. The older `stage4-` and `stage4b-` files are retained engineering research, including failed model runs.
- [Stage 3](../docs/STAGE3_REPORT.md), [Stage 2](../docs/STAGE2_REPORT.md) and [Stage 1](../docs/STAGE1_REPORT.md) record the retrieval, analytics and synthetic source baselines.

The portfolio screenshots are in [the release gallery](../assets/screenshots/README.md). Raw environment logs, account files, models, databases and browser traces are not release artifacts.
