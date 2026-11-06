import asyncio
import hashlib
import json
import time
import uuid

from app.agent.contracts import AgentError, AgentResponse, Evidence, ToolTrace
from app.agent.database import agent_session, verify_reader
from app.agent.execution import parse_arguments
from app.agent.grounding import verify_final
from app.agent.prompts import SYSTEM
from app.agent.provider import final_schema
from app.agent.tools import TOOLS
from app.knowledge.embeddings import KnowledgeError
from sqlalchemy.exc import SQLAlchemyError


def render(status, findings):
    if not findings:
        return {
            "clarification_required": (
                "Clarification is required before selecting a business entity."
            ),
            "refused": "The requested action is outside the approved read-only capabilities.",
            "insufficient_evidence": (
                "The available evidence is insufficient to establish the requested facts."
            ),
        }.get(
            status,
            "Analysis is incomplete; see the validated partial evidence and termination reason.",
        )
    parts = []
    for finding in findings:
        for entity in finding.entities:
            label = (
                entity.get("label") or entity.get("name") or entity["entity_type"].replace("_", " ")
            )
            parts.append(
                (f"Rank {entity['rank']} — " if entity.get("rank") else "")
                + f"{entity['entity_type'].replace('_', ' ').title()}: {label} "
                f"(ID {entity['entity_id']})"
            )
        parts.append(finding.text + " [" + ", ".join(finding.evidence_ids) + "]")
        for metric in finding.metrics:
            window = metric.get("window")
            period = (
                (
                    f" (period {window['observation_start']} to {window['observation_end']}; "
                    f"as of {window['as_of']})"
                )
                if window
                else ""
            )
            value = metric["value"] if metric["value"] is not None else "unavailable"
            parts.append(
                f"{metric['metric']}: {value} {metric['unit']}{period}"
                + (
                    f"; numerator {metric['numerator']}, denominator {metric['denominator']}"
                    if metric.get("denominator") is not None
                    else ""
                )
                + f" [{metric['evidence_id']}]"
            )
        for relationship in finding.relationships:
            parts.append(
                f"Linked record ({relationship['evidence_class']}): "
                f"{relationship['entity_type']} {relationship['entity_id']} → "
                f"{relationship['related_entity_type']} {relationship['related_entity_id']}; "
                f"{relationship['relationship_type']}; source {relationship['source_reference']}"
            )
        if finding.citation_ids:
            parts.append("Sources: " + ", ".join(finding.citation_ids))
        for quote in finding.quotations:
            parts.append(
                "Verified source excerpt ["
                + quote["citation_id"]
                + "]: "
                + json.dumps(quote["text"], ensure_ascii=False)
            )
    return "\n".join(parts)


async def run_agent(request, provider, executor, settings, history=None, conversation_id=None):
    start = time.monotonic()
    deadline = start + settings.agent_timeout_seconds
    request_id = uuid.uuid4().hex
    response = AgentResponse(
        request_id=request_id,
        conversation_id=conversation_id,
        question=request.question,
        as_of=request.as_of,
        status="incomplete",
        answer="",
        termination_reason="not_finished",
        model=settings.llm_model,
        execution_mode=provider.execution_mode,
    )
    usage = response.usage
    evidence = []
    cache = {}
    failed_calls = set()
    failed_tools = {}
    final_repairs = 0
    seen_calls = set()
    messages = [
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": request.question,
                    "as_of": str(request.as_of),
                    "caller_context_untrusted": request.business_context,
                    "prior_context_untrusted": history or [],
                }
            ),
        }
    ]
    declarations = [t.declaration() for t in TOOLS.values()]
    instructions = SYSTEM + "\nEstablished business cutoff: " + str(request.as_of)
    rounds = min(
        settings.agent_max_rounds, request.constraints.max_rounds or settings.agent_max_rounds
    )
    tool_limit = min(
        settings.agent_max_tools, request.constraints.max_tool_calls or settings.agent_max_tools
    )
    prices = (settings.llm_input_usd_per_million, settings.llm_output_usd_per_million)
    local = settings.llm_provider == "ollama"
    priced = (
        not local
        and settings.llm_price_model == settings.llm_model
        and all(p is not None for p in prices)
    )

    def cost():
        if not usage.provider_usage_complete:
            usage.estimated_cost_usd = None
            usage.cost_basis = "Unavailable: a provider attempt did not supply usage."
            return
        if local:
            usage.estimated_cost_usd = 0
            usage.cost_basis = (
                "Local inference: no external API charges; hardware/electricity excluded."
            )
        if priced and usage.input_tokens is not None:
            usage.estimated_cost_usd = round(
                (usage.input_tokens * prices[0] + usage.output_tokens * prices[1]) / 1_000_000, 8
            )
            usage.cost_basis = (
                "Configured matching-model USD rates; all input charged at the "
                "uncached rate, an upper estimate."
            )

    def verify(raw):
        with agent_session(
            min(settings.agent_tool_timeout_seconds, max(0.1, deadline - time.monotonic())),
            bind=executor.bind,
        ) as db:
            verify_reader(db)
            try:
                return verify_final(raw, evidence, db, request.as_of)
            except (KnowledgeError, SQLAlchemyError) as exc:
                raise AgentError(
                    "source_verification_failed",
                    "Final source verification failed; no unverified answer was returned.",
                ) from exc

    def request_final_correction(error):
        nonlocal final_repairs
        if (
            not local
            or not settings.ollama_reference_output
            or not usage.provider_rounds
            or usage.provider_rounds[-1].get("phase") != "final"
            or final_repairs >= 1
            or usage.llm_calls >= rounds
        ):
            return False
        final_repairs += 1
        provider.finalizing = True
        if usage.provider_rounds:
            usage.provider_rounds[-1]["validation_error"] = error.code
        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "server_final_validation_feedback": {
                            "code": error.code,
                            "correction": str(error),
                        },
                        "remaining_final_corrections": 0,
                    }
                ),
            }
        )
        return True

    try:
        if request.constraints.max_cost_usd and not (priced or local):
            raise AgentError(
                "cost_configuration_required",
                "A cost ceiling requires explicit matching-model input/output price configuration.",
            )
        async with asyncio.timeout(max(0.01, deadline - time.monotonic())):
            for _ in range(rounds):
                context_size = len(
                    json.dumps(
                        [messages, declarations, instructions, final_schema()], ensure_ascii=False
                    ).encode()
                )
                # Native Ollama checks the actual projected wire request, including schemas.
                # Its canonical evidence remains available here for independent verification.
                if not local and context_size > settings.agent_context_bytes:
                    raise AgentError(
                        "context_limit",
                        "Context byte budget reached; no tool result was silently truncated.",
                    )
                if (
                    usage.total_tokens is not None
                    and usage.total_tokens >= settings.agent_usage_tokens
                ):
                    raise AgentError("token_budget", "Observed provider token budget reached.")
                if request.constraints.max_cost_usd and not local:
                    projected = (
                        (usage.estimated_cost_usd or 0)
                        + (context_size + 4096) * prices[0] / 1e6
                        + settings.agent_output_tokens * prices[1] / 1e6
                    )
                    if projected > request.constraints.max_cost_usd:
                        raise AgentError(
                            "cost_budget",
                            (
                                "Conservative text-byte admission bound exceeds the configured "
                                "cost ceiling."
                            ),
                        )
                turn = None
                for attempt in range(settings.agent_retries + 1):
                    if usage.llm_calls >= rounds:
                        raise AgentError(
                            "round_limit", "LLM call budget reached, including retries."
                        )
                    usage.llm_calls += 1
                    begin = time.monotonic()
                    try:
                        turn = await asyncio.wait_for(
                            provider.complete(
                                messages,
                                declarations,
                                instructions,
                                min(
                                    settings.agent_provider_timeout_seconds,
                                    max(0.01, deadline - time.monotonic()),
                                ),
                                settings.agent_output_tokens,
                            ),
                            min(
                                settings.agent_provider_timeout_seconds,
                                max(0.01, deadline - time.monotonic()),
                            ),
                        )
                        break
                    except TimeoutError as exc:
                        usage.provider_usage_complete = False
                        raise AgentError(
                            "provider_timeout", "Provider round exceeded its deadline."
                        ) from exc
                    except AgentError as exc:
                        usage.provider_usage_complete = False
                        if (
                            not exc.retryable
                            or attempt == settings.agent_retries
                            or request.constraints.max_cost_usd
                        ):
                            raise
                        await asyncio.sleep(min(0.25, max(0, deadline - time.monotonic())))
                usage.provider_round_ms.append(round(1000 * (time.monotonic() - begin), 3))
                if turn.diagnostics:
                    usage.provider_rounds.append(turn.diagnostics)
                if turn.usage:
                    for field in [
                        "input_tokens",
                        "output_tokens",
                        "total_tokens",
                        "cached_input_tokens",
                    ]:
                        amount = turn.usage.get(field)
                        if field == "cached_input_tokens" and amount is None and local:
                            continue
                        if not isinstance(amount, int) or amount < 0:
                            raise AgentError("invalid_usage", "Provider usage metadata is invalid.")
                        setattr(usage, field, (getattr(usage, field) or 0) + amount)
                    cost()
                    if usage.total_tokens > settings.agent_usage_tokens:
                        raise AgentError(
                            "token_budget",
                            "Observed provider token budget exceeded; "
                            "no further calls are allowed.",
                        )
                else:
                    usage.provider_usage_complete = False
                    raise AgentError(
                        "usage_unavailable",
                        (
                            "Provider usage was unavailable; execution stopped without "
                            "inventing token counts."
                        ),
                    )
                if turn.error:
                    error = AgentError(*turn.error)
                    if request_final_correction(error):
                        continue
                    raise error
                if local and turn.status in {"finalization_required", "capability_selection"}:
                    messages.extend(turn.output)
                    continue
                if turn.status != "completed":
                    raise AgentError(
                        "provider_" + turn.status, "Provider did not complete a usable response."
                    )
                if (
                    request.constraints.max_cost_usd
                    and usage.estimated_cost_usd > request.constraints.max_cost_usd
                ):
                    raise AgentError(
                        "cost_budget", "Observed estimated cost reached the request ceiling."
                    )
                messages.extend(
                    turn.output
                )  # Preserve function calls and encrypted reasoning, never promote to instructions.
                if not turn.calls:
                    try:
                        draft, findings, citations = await asyncio.to_thread(verify, turn.text)
                    except AgentError as exc:
                        if request_final_correction(exc):
                            continue
                        raise
                    if (
                        draft.status == "insufficient_evidence"
                        and not evidence
                        and any(t.status == "error" for t in response.tool_trace)
                    ):
                        raise AgentError(
                            "tool_execution_failed",
                            "Retrieval failed; this is not "
                            "evidence that the requested data does not exist.",
                        )
                    response.status = draft.status
                    response.termination_reason = "final_response_verified"
                    response.key_findings = findings
                    response.citations = citations
                    response.limitations.extend(draft.limitations)
                    response.follow_up_questions = draft.follow_up_questions
                    break
                for call in turn.calls:
                    if usage.tool_calls >= tool_limit:
                        raise AgentError(
                            "tool_call_limit",
                            "Tool call budget reached; investigation remains incomplete.",
                        )
                    usage.tool_calls += 1
                    begin = time.monotonic()
                    args = None
                    raw_key = call.name + hashlib.sha256(call.arguments.encode()).hexdigest()
                    key = raw_key
                    trace = ToolTrace(
                        call_id=call.call_id, tool=call.name, status="error", elapsed_ms=0
                    )
                    try:
                        if call.call_id in seen_calls:
                            raise AgentError("duplicate_call_id", "Provider repeated a call ID.")
                        seen_calls.add(call.call_id)
                        if local and raw_key in failed_calls:
                            trace.duplicate = True
                            raise AgentError(
                                "duplicate_failed_call",
                                "Do not repeat failed arguments; "
                                "use a corrected call or report the execution failure.",
                            )
                        if local and failed_tools.get(call.name, 0) >= 2:
                            raise AgentError(
                                "tool_retry_exhausted",
                                "The single argument correction "
                                "attempt is exhausted for this tool.",
                            )
                        if call.argument_error:
                            raise AgentError(
                                "invalid_arguments",
                                "Native arguments violate the advertised standard-mode schema.",
                                details=call.argument_error,
                            )
                        args = parse_arguments(call.name, call.arguments, request.as_of)
                        trace.arguments = args.model_dump(mode="json")
                        key = call.name + json.dumps(trace.arguments, sort_keys=True)
                        if local and key in failed_calls:
                            trace.duplicate = True
                            raise AgentError(
                                "duplicate_failed_call",
                                "This validated call already failed; do not repeat it.",
                            )
                        if key in cache:
                            item = cache[key]
                            trace.duplicate = True
                        else:
                            payload, _ = await executor.run(
                                call.name,
                                args,
                                max(0.01, deadline - time.monotonic()),
                                request.as_of,
                            )
                            item = Evidence(
                                evidence_id=f"ev_{request_id[:10]}_{len(evidence) + 1}",
                                tool_name=call.name,
                                arguments=trace.arguments,
                                as_of=request.as_of,
                                payload=payload,
                            )
                            evidence.append(item)
                            cache[key] = item
                        trace.status = "success"
                        trace.evidence_id = item.evidence_id
                        output = {"ok": True, "evidence": item.model_dump(mode="json")}
                    except AgentError as exc:
                        trace.error_code = exc.code
                        trace.error_details = exc.details
                        if local and exc.code not in {
                            "duplicate_failed_call",
                            "tool_retry_exhausted",
                        }:
                            failed_tools[call.name] = failed_tools.get(call.name, 0) + 1
                            failed_calls.update((key, raw_key))
                        output = {
                            "ok": False,
                            "error": {
                                "code": exc.code,
                                "message": str(exc),
                                "details": exc.details,
                                "corrections_remaining": max(0, 2 - failed_tools.get(call.name, 0)),
                            },
                        }
                    trace.elapsed_ms = round(1000 * (time.monotonic() - begin), 3)
                    response.tool_trace.append(trace)
                    messages.append(
                        {
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": json.dumps(output, ensure_ascii=False),
                        }
                    )
                    if call.name == "resolve_business_entity" and output.get("ok"):
                        state = output["evidence"]["payload"]["status"]
                        if state == "ambiguous":
                            raise AgentError(
                                "entity_ambiguous",
                                "Multiple recorded entities match; clarify before continuing.",
                            )
                        if state == "not_found":
                            raise AgentError(
                                "entity_not_found", "No matching recorded entity exists."
                            )
                    if output.get("error", {}).get("code") == "entity_not_found":
                        raise AgentError("entity_not_found", "No matching recorded entity exists.")
            else:
                raise AgentError(
                    "round_limit", "Maximum LLM rounds reached before a verified final answer."
                )
    except TimeoutError:
        response.status = "limited"
        response.termination_reason = "request_timeout"
        usage.provider_usage_complete = False
    except AgentError as exc:
        response.status = (
            "clarification_required"
            if exc.code == "entity_ambiguous"
            else "insufficient_evidence"
            if exc.code == "entity_not_found"
            else "provider_not_configured"
            if exc.code == "provider_not_configured"
            else "refused"
            if exc.code == "provider_refused"
            else "provider_error"
            if exc.code.startswith(("provider_", "invalid_credentials", "model_unavailable"))
            else "limited"
            if exc.code
            in {"round_limit", "tool_call_limit", "context_limit", "token_budget", "cost_budget"}
            else "validation_failed"
        )
        response.termination_reason = exc.code
        response.limitations.append(str(exc))
    except asyncio.CancelledError:
        raise
    response.evidence = evidence
    response.answer = render(response.status, response.key_findings)
    response.limitations.append(
        "Source verification proves provenance and numeric projection, not"
        " complete semantic entailment. Interpretations require review."
    )
    usage.elapsed_ms = round(1000 * (time.monotonic() - start), 3)
    cost()
    return response
