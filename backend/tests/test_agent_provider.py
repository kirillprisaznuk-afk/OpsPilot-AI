import asyncio
import json

import httpx
import pytest
from app.agent.config import AgentSettings
from app.agent.contracts import AgentError
from app.agent.provider import OpenAIProvider
from app.agent.tools import TOOLS
from openai import AsyncOpenAI
from pydantic import SecretStr


def response_data(output=None, status="completed"):
    return {
        "id": "resp_offline",
        "object": "response",
        "created_at": 1,
        "model": "offline-configured-model",
        "status": status,
        "output": output or [],
        "parallel_tool_calls": False,
        "tools": [],
        "tool_choice": "auto",
        "usage": {
            "input_tokens": 20,
            "output_tokens": 10,
            "total_tokens": 30,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


def fixture_client(handler):
    return AsyncOpenAI(
        api_key="offline-test-key",
        base_url="https://api.openai.com/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )


def test_official_sdk_request_and_response_protocol():
    captured = []

    def handle(request):
        captured.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": "offline-configured-model",
                    "object": "model",
                    "created": 1,
                    "owned_by": "test",
                },
            )
        return httpx.Response(
            200,
            json=response_data(
                [
                    {
                        "type": "reasoning",
                        "id": "rs_test",
                        "summary": [],
                        "encrypted_content": "encrypted-test-only",
                    },
                    {
                        "type": "function_call",
                        "call_id": "call_test",
                        "name": "get_inventory_status",
                        "arguments": "{}",
                        "id": "fc_test",
                        "status": "completed",
                    },
                ]
            ),
        )

    async def exercise():
        s = AgentSettings(
            llm_provider="openai",
            _env_file=None,
            llm_model="offline-configured-model",
            openai_api_key=SecretStr("offline-test-key"),
        )
        p = OpenAIProvider(s, fixture_client(handle))
        try:
            return await p.complete(
                [{"role": "user", "content": "test"}],
                [TOOLS["get_inventory_status"].declaration()],
                "read only",
                3,
                1000,
            )
        finally:
            await p.close()

    turn = asyncio.run(exercise())
    assert turn.calls[0].name == "get_inventory_status"
    assert turn.output[0]["encrypted_content"] == "encrypted-test-only"
    assert turn.usage["total_tokens"] == 30
    body = json.loads(captured[-1].content)
    assert body["store"] is False and body["parallel_tool_calls"] is False
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["tools"][0]["strict"] is True
    assert "temperature" not in body and "top_p" not in body


@pytest.mark.parametrize(
    "code,expected",
    [
        (401, "invalid_credentials"),
        (403, "model_unavailable"),
        (404, "model_unavailable"),
        (429, "provider_rate_limited"),
        (500, "provider_error"),
        (400, "provider_request_rejected"),
    ],
)
def test_sdk_failures_are_sanitized_without_hidden_retries(code, expected):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            code, json={"error": {"message": "sensitive raw provider error", "type": "test_error"}}
        )

    async def exercise():
        s = AgentSettings(
            llm_provider="openai",
            _env_file=None,
            llm_model="offline-configured-model",
            openai_api_key=SecretStr("offline-test-key"),
        )
        p = OpenAIProvider(s, fixture_client(handle))
        try:
            with pytest.raises(AgentError) as error:
                await p.complete([], [], "test", 1, 256)
            assert error.value.code == expected and "sensitive" not in str(error.value)
        finally:
            await p.close()

    asyncio.run(exercise())
    assert len(requests) == 1


def test_missing_provider_never_creates_a_client():
    with pytest.raises(AgentError, match="Configure"):
        OpenAIProvider(
            AgentSettings(
                llm_provider="openai", _env_file=None, llm_model=None, openai_api_key=None
            )
        )


def test_malformed_sdk_function_call_is_a_structured_error():
    def handle(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": "offline-configured-model",
                    "object": "model",
                    "created": 1,
                    "owned_by": "test",
                },
            )
        return httpx.Response(
            200,
            json=response_data(
                [
                    {
                        "type": "function_call",
                        "id": "fc",
                        "call_id": "c",
                        "name": "get_inventory_status",
                        "arguments": None,
                    }
                ]
            ),
        )

    async def exercise():
        s = AgentSettings(
            llm_provider="openai",
            _env_file=None,
            llm_model="offline-configured-model",
            openai_api_key=SecretStr("offline-test-key"),
        )
        p = OpenAIProvider(s, fixture_client(handle))
        try:
            with pytest.raises(AgentError, match="function-call"):
                await p.complete([], [], "test", 1, 256)
        finally:
            await p.close()

    asyncio.run(exercise())
