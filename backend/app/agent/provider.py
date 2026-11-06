"""Official SDK Responses adapter. No provider executes application functions."""

from dataclasses import dataclass, field

import openai
from app.agent.contracts import AgentError, Draft
from openai import AsyncOpenAI, pydantic_function_tool


@dataclass
class Call:
    call_id: str
    name: str
    arguments: str
    argument_error: dict | None = None


@dataclass
class Turn:
    output: list[dict] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    text: str = ""
    status: str = "completed"
    usage: dict | None = None
    error: tuple[str, str] | None = None
    diagnostics: dict | None = None


def final_schema():
    schema = pydantic_function_tool(Draft)["function"]["parameters"]

    def clean(value):
        if isinstance(value, dict):
            value.pop("default", None)
            for child in value.values():
                clean(child)
        elif isinstance(value, list):
            for child in value:
                clean(child)

    clean(schema)
    return schema


class OpenAIProvider:
    execution_mode = "live"

    def __init__(self, settings, client=None):
        if not (
            settings.llm_model
            and settings.openai_api_key
            and settings.openai_api_key.get_secret_value().strip()
        ):
            raise AgentError(
                "provider_not_configured",
                (
                    "Configure OPENAI_API_KEY and LLM_MODEL only in the local "
                    "environment or ignored .env."
                ),
            )
        self.settings = settings
        self.client = client or AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            base_url="https://api.openai.com/v1",
            max_retries=0,
            timeout=settings.agent_provider_timeout_seconds,
        )
        self.verified = False

    async def complete(self, history, tools, instructions, timeout, output_tokens):
        try:
            options = self.client.with_options(timeout=timeout, max_retries=0)
            if not self.verified:
                await options.models.retrieve(self.settings.llm_model)
                self.verified = True
            result = await options.responses.create(
                model=self.settings.llm_model,
                input=history,
                instructions=instructions,
                tools=tools,
                store=False,
                parallel_tool_calls=False,
                truncation="disabled",
                max_output_tokens=output_tokens,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "opspilot_grounded_answer",
                        "strict": True,
                        "schema": final_schema(),
                    }
                },
            )
        except openai.AuthenticationError as exc:
            raise AgentError(
                "invalid_credentials", "OpenAI authentication failed; check local credentials."
            ) from exc
        except (openai.NotFoundError, openai.PermissionDeniedError) as exc:
            raise AgentError(
                "model_unavailable", "The configured model is not available to this API account."
            ) from exc
        except openai.RateLimitError as exc:
            raise AgentError(
                "provider_rate_limited", "OpenAI rate or account quota limit reached.", True
            ) from exc
        except (openai.APITimeoutError, openai.APIConnectionError) as exc:
            raise AgentError(
                "provider_connection_error",
                (
                    "OpenAI connection failed or timed out; automatic replay is "
                    "disabled to avoid duplicate charges."
                ),
            ) from exc
        except openai.BadRequestError as exc:
            raise AgentError(
                "provider_request_rejected",
                (
                    "Model rejected the request, context or tool/output schema; verify"
                    " model capabilities."
                ),
            ) from exc
        except openai.APIStatusError as exc:
            raise AgentError(
                "provider_error", "OpenAI service request failed.", exc.status_code >= 500
            ) from exc
        if not isinstance(result.output, list) or not isinstance(result.status, str):
            raise AgentError(
                "provider_malformed_response", "OpenAI returned an invalid response envelope."
            )
        output = [item.model_dump(mode="json", exclude_none=True) for item in result.output]
        for item in output:
            if item.get("type") == "function_call" and not all(
                isinstance(item.get(field), str) and item.get(field)
                for field in ["call_id", "name", "arguments"]
            ):
                raise AgentError(
                    "provider_malformed_response",
                    "OpenAI returned an invalid function-call envelope.",
                )
        calls = [
            Call(i["call_id"], i["name"], i["arguments"])
            for i in output
            if i["type"] == "function_call"
        ]
        refused = any(
            c.get("type") == "refusal"
            for i in output
            if i["type"] == "message"
            for c in i.get("content", [])
        )
        usage = None
        if result.usage:
            usage = {
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "total_tokens": result.usage.total_tokens,
                "cached_input_tokens": getattr(
                    result.usage.input_tokens_details, "cached_tokens", 0
                ),
            }
        return Turn(
            output, calls, result.output_text, "refused" if refused else result.status, usage
        )

    async def close(self):
        await self.client.close()
