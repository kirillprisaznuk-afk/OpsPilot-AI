import asyncio
import json
import time
import uuid
from contextlib import AsyncExitStack
from datetime import date

from app.agent.config import agent_settings
from app.agent.contracts import AgentError, AgentResponse, Usage
from app.agent.conversation import conversations
from app.agent.execution import ToolExecutor
from app.agent.intent import prohibited_execution
from app.agent.ollama_provider import OllamaProvider
from app.agent.orchestrator import run_agent
from app.agent.provider import OpenAIProvider

ACTIVE = asyncio.Semaphore(2)


async def query_agent(request):
    settings = agent_settings()
    cutoff = request.as_of or date(2026, 9, 30)
    denied = prohibited_execution(request.question)
    if denied:
        return AgentResponse(
            request_id=uuid.uuid4().hex,
            conversation_id=None,
            question=request.question,
            as_of=cutoff,
            status="refused",
            answer="Stage 4 is read-only. It cannot change business records, send messages, "
            "execute code or access local secrets. It can explain procedures and analyse "
            "authorised business evidence.",
            termination_reason="unsupported_execution_" + denied,
            model=settings.llm_model,
            usage=Usage(
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                estimated_cost_usd=0,
                cost_basis="Preflight refusal; no inference or tools.",
            ),
        )
    if not settings.configured:
        return AgentResponse(
            request_id=uuid.uuid4().hex,
            conversation_id=None,
            question=request.question,
            as_of=cutoff,
            status="provider_not_configured",
            answer=(
                "The LLM provider is not configured. Existing analytics and "
                "knowledge endpoints remain available."
            ),
            limitations=[
                (
                    "Configure a downloaded local Ollama LLM_MODEL. OpenAI requires explicit"
                    " provider selection and local credentials."
                )
            ],
            termination_reason="provider_not_configured",
            model=settings.llm_model,
        )
    identifier, conversation = conversations.get(
        request.conversation_id, request.as_of if request.conversation_id else cutoff
    )
    started = time.monotonic()
    deadline = started + settings.agent_timeout_seconds
    try:
        async with AsyncExitStack() as stack:
            async with asyncio.timeout(settings.agent_timeout_seconds):
                await stack.enter_async_context(ACTIVE)
                await stack.enter_async_context(conversation.lock)
            remaining = max(0.001, deadline - time.monotonic())
            bounded_settings = settings.model_copy(update={"agent_timeout_seconds": remaining})
            request = request.model_copy(update={"as_of": conversation.as_of})
            provider = (
                OllamaProvider(
                    settings.model_copy(
                        update={
                            "agent_max_rounds": min(
                                settings.agent_max_rounds,
                                request.constraints.max_rounds or settings.agent_max_rounds,
                            )
                        }
                    )
                )
                if settings.llm_provider == "ollama"
                else OpenAIProvider(settings)
            )
            try:
                response = await run_agent(
                    request,
                    provider,
                    ToolExecutor(settings),
                    bounded_settings,
                    conversation.turns,
                    identifier,
                )
            finally:
                await provider.close()
            secret = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
            if secret:
                response = AgentResponse.model_validate_json(
                    json.dumps(response.model_dump(mode="json")).replace(secret, "[REDACTED]")
                )
            response.usage.elapsed_ms = round(1000 * (time.monotonic() - started), 3)
            conversations.save(conversation, response)
            return response
    except TimeoutError as exc:
        raise AgentError(
            "request_timeout", "Request deadline reached while waiting for execution capacity."
        ) from exc
