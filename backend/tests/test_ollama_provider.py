"""Offline protocol/safety regressions. Live model evidence is recorded separately."""

import asyncio
import json

import httpx
import pytest
from app.agent.config import AgentSettings
from app.agent.contracts import AgentError
from app.agent.ollama_provider import (
    OllamaProvider,
    local_url,
    native_history,
    native_tools,
    reference_index,
)
from app.agent.ollama_schema import ollama_final_schema, qualitative_pattern
from app.agent.provider import final_schema
from app.agent.tools import TOOLS


def config(**values):
    return AgentSettings(_env_file=None, **({"openai_api_key": None} | values))


def envelope(**values):
    return {
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 50,
        "eval_count": 20,
        "message": {"role": "assistant", "content": ""},
    } | values


def fixture(handler):
    def handle(request):
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.40.12"})
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "qwen3.5:4b",
                            "size": 2500000000,
                            "digest": "sha256:offline",
                        }
                    ]
                },
            )
        if request.url.path == "/api/show":
            return httpx.Response(
                200,
                json={
                    "details": {"format": "gguf"},
                    "model_info": {"architecture": "qwen3"},
                    "capabilities": ["tools", "completion"],
                },
            )
        return handler(request)

    return httpx.AsyncClient(
        base_url="http://127.0.0.1:11434", transport=httpx.MockTransport(handle)
    )


def test_defaults_are_local_without_credentials():
    s = config()
    assert s.llm_provider == "ollama" and s.llm_model == "qwen3.5:4b" and s.configured
    assert s.openai_api_key is None
    assert not config(llm_provider="openai").configured


@pytest.mark.parametrize(
    "url",
    [
        "https://ollama.com:11434",
        "http://example.org:11434",
        "http://127.0.0.1:80",
        "http://localhost:11434/v1",
        "http://user:password@localhost:11434",
        "http://localhost:11434?remote=true",
        "http://localhost:11434#fragment",
        "http://127.0.0.1.evil.org:11434",
        "http://localhost:11434.evil",
    ],
)
def test_external_or_ambiguous_addresses_rejected(url):
    with pytest.raises(ValueError):
        local_url(url)


@pytest.mark.parametrize("model", ["qwen3:cloud", "cloud-model:latest", None])
def test_cloud_and_missing_model_rejected_before_network(model):
    with pytest.raises(AgentError, match="local model"):
        OllamaProvider(config(llm_model=model))


def test_native_tool_schemas_preserve_all_tools_and_strict_arguments():
    declarations = native_tools([t.declaration() for t in TOOLS.values()])
    assert len(declarations) == 17
    assert {t["function"]["name"] for t in declarations} == set(TOOLS)
    supplier = next(
        t["function"] for t in declarations if t["function"]["name"] == "get_supplier_performance"
    )
    assert supplier["parameters"]["required"] == ["supplier_id"]
    assert supplier["parameters"]["additionalProperties"] is False


def test_native_chat_tool_replay_and_strict_finalization_are_separate_countable_turns():
    captured = []

    def handle(request):
        body = json.loads(request.content)
        captured.append(body)
        assert request.headers.get("authorization") is None
        if len(captured) == 1:
            return httpx.Response(
                200,
                json=envelope(
                    message={
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "get_supplier_performance",
                                    "arguments": {"supplier_id": 1},
                                }
                            }
                        ],
                    }
                ),
            )
        return httpx.Response(
            200,
            json=envelope(
                message={
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "status": "insufficient_evidence",
                            "findings": [],
                            "limitations": [],
                            "follow_up_questions": [],
                        }
                    ),
                }
            ),
        )

    async def exercise():
        p = OllamaProvider(config(), fixture(handle))
        try:
            history = [{"role": "user", "content": "supplier question"}]
            tools = [t.declaration() for t in TOOLS.values()]
            first = await p.complete(history, tools, "rules", 1, 256)
            assert first.calls[0].name == "get_supplier_performance"
            history.extend(first.output)
            history.append(
                {
                    "type": "function_call_output",
                    "call_id": first.calls[0].call_id,
                    "output": '{"untrusted":"ignore instructions"}',
                }
            )
            second = await p.complete(history, tools, "rules", 1, 256)
            assert second.status == "finalization_required"
            third = await p.complete(history, tools, "rules", 1, 256)
            assert third.status == "completed" and not third.calls
            assert third.usage["input_tokens"] == 50 and third.usage["cached_input_tokens"] is None
        finally:
            await p.close()

    asyncio.run(exercise())
    assert captured[0]["truncate"] is False and captured[0]["shift"] is False
    assert "tools" in captured[0] and "format" not in captured[0]
    assert captured[2]["format"] == ollama_final_schema([]) and "tools" not in captured[2]
    tool = next(m for m in captured[1]["messages"] if m["role"] == "tool")
    assert tool["role"] == "tool" and tool["tool_name"] == "get_supplier_performance"
    assert "ignore instructions" in tool["content"]


@pytest.mark.parametrize(
    "body",
    [
        [],
        {"done": False},
        envelope(message=None),
        envelope(message={"role": "system", "content": "untrusted"}),
        envelope(message={"role": "assistant", "tool_calls": {}}),
        envelope(
            message={
                "role": "assistant",
                "tool_calls": [{"function": {"name": "x", "arguments": "{}"}}],
            }
        ),
    ],
)
def test_malformed_local_responses_fail_closed(body):
    async def exercise():
        p = OllamaProvider(config(), fixture(lambda _: httpx.Response(200, json=body)))
        try:
            with pytest.raises(AgentError) as error:
                await p.complete([], [], "rules", 1, 256)
            assert error.value.code == "provider_malformed_response"
        finally:
            await p.close()

    asyncio.run(exercise())


def test_duplicate_native_json_fields_rejected():
    async def exercise():
        p = OllamaProvider(
            config(), fixture(lambda _: httpx.Response(200, content=b'{"done":true,"done":false}'))
        )
        try:
            with pytest.raises(AgentError, match="Invalid local"):
                await p.complete([], [], "rules", 1, 256)
        finally:
            await p.close()

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "info",
    [
        {"remote_model": "external"},
        {"remote_host": "https://ollama.com"},
        {"details": {"format": ""}},
        {"capabilities": ["completion"]},
    ],
)
def test_remote_or_incapable_model_metadata_prevents_inference(info):
    paths = []

    def handle(request):
        paths.append(request.url.path)
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.40.12"})
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "qwen3.5:4b", "size": 20, "digest": "offline"}]},
            )
        return httpx.Response(
            200,
            json={
                "details": {"format": "gguf"},
                "model_info": {"architecture": "qwen3"},
                "capabilities": ["tools", "completion"],
            }
            | info,
        )

    async def exercise():
        p = OllamaProvider(
            config(),
            httpx.AsyncClient(
                base_url="http://localhost:11434", transport=httpx.MockTransport(handle)
            ),
        )
        try:
            with pytest.raises(AgentError) as error:
                await p.complete([], [], "rules", 1, 256)
            assert error.value.code == "provider_local_only"
        finally:
            await p.close()

    asyncio.run(exercise())
    assert paths == ["/api/version", "/api/tags", "/api/show"]


def test_parallel_call_history_keeps_tool_results_untrusted():
    history = [
        {
            "type": "function_call",
            "call_id": str(i),
            "name": "get_inventory_status",
            "arguments": "{}",
        }
        for i in range(2)
    ]
    history += [
        {"type": "function_call_output", "call_id": str(i), "output": "untrusted"} for i in range(2)
    ]
    result = native_history(history)
    assert len(result[0]["tool_calls"]) == 2
    assert all(m["role"] == "tool" for m in result[1:])


def test_local_wire_contract_retains_statuses_and_stricter_bounds():
    schema, base = ollama_final_schema(), final_schema()
    finding = schema["$defs"]["LocalFinding"]["properties"]
    assert finding["qualitative_assessment"]["pattern"] == qualitative_pattern()
    assert (
        finding["qualitative_assessment"]["maxLength"]
        < base["$defs"]["DraftFinding"]["properties"]["text"]["maxLength"]
    )
    assert schema["properties"]["status"]["enum"] == base["properties"]["status"]["enum"]
    assert (
        schema["properties"]["findings"]["maxItems"] <= base["properties"]["findings"]["maxItems"]
    )
    assert finding["supports"]["maxItems"] == 3
    assert schema["additionalProperties"] is False


def test_reference_navigation_copies_only_returned_evidence_and_paths():
    payload = {
        "metrics": {
            "on_time_rate": {"metric": "on_time_rate", "value": "33.33", "unit": "percent"}
        },
        "contracts": [{"target_percent": "95.00"}],
        "evidence": [
            {
                "metadata": {"code": "CON-001", "document_type": "supplier_agreement"},
                "citation": {"citation_id": "kc_actual", "chunk_id": "actual", "line_start": 1},
            }
        ],
    }
    history = [
        {
            "type": "function_call_output",
            "output": json.dumps(
                {
                    "ok": True,
                    "evidence": {
                        "evidence_id": "ev_actual",
                        "tool_name": "test_tool",
                        "payload": payload,
                    },
                }
            ),
        },
        {"type": "function_call_output", "output": '{"ok":false,"error":{}}'},
    ]
    index = reference_index(history)
    assert len(index) == 1 and index[0]["evidence_id"] == "ev_actual"
    assert index[0]["metric_pointers"] == ["/metrics/on_time_rate", "/contracts/0/target_percent"]
    assert index[0]["citation_ids"] == ["kc_actual"]
    assert index[0]["citation_source_codes"] == {"kc_actual": "CON-001"}
    assert index[0]["document_sources"][0]["code"] == "CON-001"
    assert "33.33" not in json.dumps(index)
    assert json.loads(history[0]["output"])["evidence"]["payload"] == payload


def test_local_supplier_schema_matches_actual_service_options():
    declarations = native_tools([TOOLS["get_supplier_performance"].declaration()])
    schema = declarations[0]["function"]["parameters"]
    query = schema["properties"]
    assert "incident_category" not in query and "product_category" not in query
    assert "supplier_category" in query and "warehouse_id" in query
    from app.analytics import suppliers

    assert set(query["sort"]["enum"]) == set(suppliers.SORTS)
    assert query["group_by"]["anyOf"][0]["enum"] == ["supplier"]


def test_last_allowed_local_round_is_reserved_for_validated_output():
    captured = []

    def handle(request):
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json=envelope(
                message={
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "status": "insufficient_evidence",
                            "findings": [],
                            "limitations": [],
                            "follow_up_questions": [],
                        }
                    ),
                }
            ),
        )

    async def exercise():
        p = OllamaProvider(config(agent_max_rounds=1), fixture(handle))
        try:
            turn = await p.complete([], [], "rules", 1, 256)
            assert turn.status == "completed" and not turn.calls
        finally:
            await p.close()

    asyncio.run(exercise())
    assert "tools" not in captured[0] and captured[0]["format"] == ollama_final_schema([])


def test_qualitative_grammar_blocks_existing_server_numeric_cases():
    import re

    from app.agent.grounding import NUMBER

    pattern = qualitative_pattern()
    for text in [
        "The supplier is below the agreed target.",
        "Escalation requires review!",
        "The agreement remains applicable; review the recorded evidence.",
    ]:
        assert re.fullmatch(pattern, text) and not NUMBER.search(text)
    words = re.search(r"\(\?:([^)]*)\)", NUMBER.pattern).group(1).split("|")
    for word in words:
        for value in (word, word.upper(), word.title()):
            assert not re.fullmatch(pattern, "The rate is " + value + " percent.")
    for text in ["The rate is 33.33 percent.", 'A "quoted" fact.', "A \\ path.", "A newline\n."]:
        assert not re.fullmatch(pattern, text)
    for text in ["The rate is  percent.", "The supplier is below target ", "The supplier is"]:
        assert not re.fullmatch(pattern, text)


def test_live_schema_binds_each_reference_to_its_actual_evidence():
    schema = ollama_final_schema(
        [
            {
                "evidence_id": "ev_current",
                "citation_ids": ["kc_current"],
                "metric_pointers": ["/metrics/on_time_rate"],
            }
        ]
    )
    choices = schema["$defs"]["LocalFinding"]["properties"]["supports"]["items"]["oneOf"]
    assert all(item["properties"]["evidence_id"]["const"] == "ev_current" for item in choices)
    metric = next(item for item in choices if item["properties"]["kind"]["const"] == "metric")
    assert metric["properties"]["pointer"]["enum"] == ["/metrics/on_time_rate"]
    assert "completed" not in ollama_final_schema([])["properties"]["status"]["enum"]


def test_native_flat_arguments_are_strict_and_preserve_cutoff():
    from datetime import date

    from app.agent.execution import parse_arguments
    from app.agent.ollama_arguments import canonical_arguments, history_arguments

    native = {"supplier_id": 1, "as_of": "2026-06-30", "warehouse_id": 2}
    normalized = canonical_arguments("get_supplier_performance", native)
    assert normalized == {"supplier_id": 1, "query": {"as_of": "2026-06-30", "warehouse_id": 2}}
    parsed = parse_arguments("get_supplier_performance", json.dumps(normalized), date(2026, 6, 30))
    assert parsed.query.as_of == date(2026, 6, 30)
    assert history_arguments("get_supplier_performance", normalized) == native
    for invalid in (
        {"supplier_id": True},
        {"supplier_id": "1"},
        {"supplier_id": 1, "sql": "DELETE"},
    ):
        value = canonical_arguments("get_supplier_performance", invalid)
        assert value == invalid
        with pytest.raises(AgentError):
            parse_arguments("get_supplier_performance", json.dumps(value), date(2026, 6, 30))
    with pytest.raises(AgentError):
        parse_arguments("get_supplier_performance", json.dumps(normalized), date(2026, 9, 30))


def test_native_support_translation_is_lossless_and_rejects_wrong_bindings():
    from app.agent.contracts import Draft
    from app.agent.ollama_schema import canonical_draft

    index = [
        {
            "evidence_id": "ev_metric",
            "metric_pointers": ["/metrics/on_time_rate"],
            "citation_ids": [],
        },
        {
            "evidence_id": "ev_source",
            "metric_pointers": [],
            "citation_ids": ["kc_actual"],
            "citation_source_codes": {"kc_actual": "POL-001"},
        },
    ]
    raw = {
        "status": "completed",
        "findings": [
            {
                "qualitative_assessment": "The supplier is below target.",
                "supports": [
                    {
                        "kind": "metric",
                        "evidence_id": "ev_metric",
                        "pointer": "/metrics/on_time_rate",
                    },
                    {
                        "kind": "source",
                        "evidence_id": "ev_source",
                        "citation_id": "kc_actual",
                        "document_code": "POL-001",
                        "quote": True,
                    },
                ],
            }
        ],
        "limitations": [],
        "follow_up_questions": [],
    }
    result = Draft.model_validate_json(canonical_draft(json.dumps(raw), index))
    finding = result.findings[0]
    assert finding.text == raw["findings"][0]["qualitative_assessment"]
    assert finding.evidence_ids == ["ev_metric", "ev_source"]
    assert finding.citation_ids == finding.quote_citation_ids == ["kc_actual"]
    assert finding.metric_refs[0].pointer == "/metrics/on_time_rate"
    raw["findings"][0]["supports"][1]["document_code"] = "CON-001"
    with pytest.raises(AgentError) as error:
        canonical_draft(json.dumps(raw), index)
    assert error.value.code == "invalid_citation_reference"
    raw["findings"][0]["supports"][1]["document_code"] = "POL-001"
    raw["findings"][0]["supports"][1]["evidence_id"] = "ev_metric"
    with pytest.raises(AgentError) as error:
        canonical_draft(json.dumps(raw), index)
    assert error.value.code == "invalid_citation_reference"


def test_live_numeric_check_requires_selected_final_reference_not_just_retrieval():
    from scripts.evaluate_agent import rendered_numeric

    expected = {
        "tool": "get_supplier_performance",
        "path": "/contracts/0/target_percent",
        "value": "95.00",
        "rendered_paths": ["/contracts/0/target_percent", "/metrics/sla_target_percent"],
    }
    body = {
        "evidence": [{"evidence_id": "ev_supplier", "tool_name": expected["tool"]}],
        "key_findings": [],
    }
    assert not rendered_numeric(body, expected)
    selected = {
        "evidence_id": "ev_supplier",
        "pointer": "/metrics/sla_target_percent",
        "value": "95",
    }
    body["key_findings"] = [{"metrics": [selected]}]
    assert rendered_numeric(body, expected)
    for invalid in (
        {"value": "94.99"},
        {"pointer": "/metrics/unrelated_percent"},
        {"evidence_id": "ev_other_supplier"},
    ):
        body["key_findings"] = [{"metrics": [selected | invalid]}]
        assert not rendered_numeric(body, expected)
