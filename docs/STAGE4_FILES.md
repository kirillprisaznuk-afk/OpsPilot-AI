# Stage 4 file inventory

Paths are relative to the OpsPilot repository. Original implementation inventory
is retained below; local migration additions and actual live results are separate.
Credentials, model weights, caches and machine-specific baselines remain ignored.

## Files created (31)

- `backend/app/agent/config.py`
- `backend/app/agent/contracts.py`
- `backend/app/agent/conversation.py`
- `backend/app/agent/database.py`
- `backend/app/agent/execution.py`
- `backend/app/agent/grounding.py`
- `backend/app/agent/orchestrator.py`
- `backend/app/agent/prompts.py`
- `backend/app/agent/provider.py`
- `backend/app/agent/service.py`
- `backend/app/agent/tools.py`
- `backend/app/api/agent.py`
- `backend/tests/test_agent.py`
- `backend/tests/test_agent_provider.py`
- `data/evaluation/agent.json`
- `docs/AGENT_ARCHITECTURE.md`
- `docs/AGENT_EVALUATION.md`
- `docs/AGENT_GROUNDING.md`
- `docs/AGENT_SECURITY.md`
- `docs/LLM_INTEGRATION.md`
- `docs/STAGE4_FILES.md`
- `docs/STAGE4_REPORT.md`
- `docs/TOOL_REGISTRY.md`
- `reports/stage4-live-evaluation.json`
- `reports/stage4-offline-evaluation.json`
- `reports/stage4-pytest.xml`
- `reports/stage4-retrieval-regression.json`
- `reports/stage4-validation.json`
- `scripts/evaluate_agent.py`
- `scripts/prepare_agent_reader.py`
- `scripts/validate_agent.py`

## Files modified (7)

- `.env.example`
- `README.md`
- `backend/app/main.py`
- `docker-compose.yml`
- `docs/ARCHITECTURE.md`
- `pyproject.toml`
- `uv.lock`

Original domain models, migrations, generator, corpus, analytical/retrieval source,
all existing tests and prior acceptance artifacts remain unchanged. No business
records or retrieval data were regenerated. The new SDK and its dependencies are
locked; existing accepted package versions are retained.

## Local Ollama migration additions

- `backend/app/agent/ollama_provider.py`: local native API, metadata verification and protocol mapping.
- `backend/app/agent/ollama_arguments.py`: strict native/canonical argument translation.
- `backend/app/agent/ollama_schema.py`: stricter structured decoding and bound support translation.
- `backend/tests/test_ollama_provider.py`: offline protocol/safety and evaluator regression tests.
- `scripts/start_ollama.ps1`: project-local verified portable runtime, download and warm-up.
- `reports/stage4-local-*.json` and `stage4-local-pytest.xml`: actual successes, failures and regressions.

Configuration, agent provider selection/orchestration, prompt descriptions, direct
httpx dependency, evaluation/validation commands and associated docs were updated.
Original OpenAI tests now explicitly select their optional provider. The evaluation
fixture keeps its original plans/values and adds explicit equivalent final metric
paths for the single-supplier A01 assertions. No production routing uses the fixture.
Original business models/migrations, generator, analytics, grounding validator,
corpus and retrieval code remain unchanged. No remote publication was performed.
