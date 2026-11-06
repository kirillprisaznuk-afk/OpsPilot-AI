import asyncio
import json
import re
import time
import uuid

from pydantic import ValidationError

from app.agent.config import agent_settings
from app.agent.contracts import AgentError, Evidence, ToolTrace, Usage
from app.agent.conversation import Conversations
from app.agent.database import agent_session
from app.agent.execution import ToolExecutor, parse_arguments
from app.agent.intent import prohibited_execution
from app.hybrid.composition import compose
from app.hybrid.contracts import Binding, HybridResponse, Objective, PlanStep, Subject
from app.hybrid.evidence import graph_from, grounded_findings
from app.hybrid.intent import interpret, validate_intent
from app.hybrid.planning import build_plan
from app.hybrid.registry import REGISTRY

conversations = Conversations()
ACTIVE = asyncio.Semaphore(1)


class Engine:
    def __init__(self, request, settings, response, bind=None):
        self.request, self.settings, self.response = request, settings, response
        self.executor = ToolExecutor(settings, bind)
        self.deadline = time.monotonic() + settings.agent_timeout_seconds
        self.limit = min(
            request.constraints.max_tool_calls or settings.agent_max_tools, settings.agent_max_tools
        )
        self.cache, self.results, self.capabilities = {}, {}, {}

    async def call(self, tool, arguments, capability):
        if capability != "entity_resolution" and (
            capability not in REGISTRY or tool not in REGISTRY[capability].tools
        ):
            raise AgentError("invalid_plan", "Tool is not authorized by its registered capability.")
        if capability == "entity_resolution" and tool != "resolve_business_entity":
            raise AgentError("invalid_plan", "Entity resolution cannot execute this tool.")
        args = parse_arguments(tool, json.dumps(arguments), self.response.as_of)
        key = tool + args.model_dump_json()
        if key in self.cache:
            self.response.execution.duplicates_avoided += 1
            return self.cache[key]
        if self.response.usage.tool_calls >= self.limit:
            raise AgentError("tool_call_limit", "Validated execution reached the tool budget.")
        self.response.usage.tool_calls += 1
        trace = ToolTrace(
            call_id=uuid.uuid4().hex,
            tool=tool,
            arguments=args.model_dump(mode="json"),
            status="error",
            elapsed_ms=0,
        )
        self.response.tool_trace.append(trace)
        started = time.perf_counter()
        try:
            payload, elapsed = await self.executor.run(
                tool, args, max(0.01, self.deadline - time.monotonic()), self.response.as_of
            )
            evidence = Evidence(
                evidence_id="ev_" + uuid.uuid4().hex[:16],
                tool_name=tool,
                arguments=trace.arguments,
                as_of=self.response.as_of,
                payload=payload,
            )
            self.response.evidence.append(evidence)
            trace.status, trace.evidence_id = "success", evidence.evidence_id
            self.cache[key] = evidence
            self.capabilities[evidence.evidence_id] = capability
            if "knowledge" in tool or "document" in tool:
                self.response.execution.rag_tool_ms += elapsed
            else:
                self.response.execution.sql_tool_ms += elapsed
            return evidence
        except AgentError as exc:
            trace.error_code = exc.code
            trace.error_details = exc.details
            raise
        finally:
            trace.elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

    async def execute(self, plan):
        missing = []
        for step in list(plan.steps):
            arguments = dict(step.arguments)
            try:
                if step.binding:
                    previous = self.results.get(step.binding.step_id)
                    if not previous:
                        missing.append(
                            f"{step.step_id}: required preceding evidence is unavailable."
                        )
                        continue
                    if step.binding.kind == "effective_contract":
                        sid = step.binding.entity_id or previous.arguments.get("supplier_id")
                        contracts = [
                            c
                            for c in previous.payload.get("contracts", [])
                            if c["supplier_id"] == sid
                        ]
                        if not contracts:
                            missing.append(
                                "No applicable supplier contract was returned at this scope."
                            )
                            continue
                        if len(contracts) != 1:
                            missing.append(
                                "Multiple contracts overlap the observation window; narrow the "
                                "period to retrieve one agreement without blending targets."
                            )
                            continue
                        contract = contracts[0]
                        arguments.update(
                            query=contract["reference"],
                            filters={
                                "document_type": "supplier_agreement",
                                "supplier_id": sid,
                                "contract_id": contract["contract_id"],
                            },
                        )
                    elif step.binding.kind == "ranked_subjects":
                        rows = previous.payload.get("breakdowns", [])
                        if not rows:
                            missing.append("The ranking returned no available subject.")
                            continue
                        row = rows[0]
                        arguments["supplier_id"] = row["entity_id"]
                        subject = Subject(
                            entity_type="supplier",
                            entity_id=row["entity_id"],
                            label=row["label"],
                            provenance="verified_ranking",
                        )
                        if subject not in plan.subjects:
                            plan.subjects.append(subject)
                result = await self.call(step.tool, arguments, step.capability)
                self.results[step.step_id] = result
                self.response.execution.executed_steps += 1
                if step.tool == "investigate_business_entity":
                    total = result.payload["total"]
                    size = result.payload["limit"]
                    for offset in range(size, min(total, 3 * size), size):
                        if self.response.usage.tool_calls >= self.limit or len(plan.steps) >= 12:
                            break
                        page_args = {
                            **arguments,
                            "query": {**arguments.get("query", {}), "offset": offset},
                        }
                        page_step = step.model_copy(
                            update={
                                "step_id": f"step_{len(plan.steps) + 1}",
                                "arguments": page_args,
                                "depends_on": [step.step_id],
                            }
                        )
                        plan.steps.append(page_step)
                        self.response.execution.planned_steps += 1
                        page = await self.call(step.tool, page_args, step.capability)
                        self.results[page_step.step_id] = page
                        self.response.execution.executed_steps += 1
                if step.tool == "search_corporate_knowledge" and result.payload.get(
                    "insufficient_evidence"
                ):
                    missing.append(f"{step.capability}: required source evidence was not found.")
            except AgentError as exc:
                missing.append(f"{step.capability}: {exc.code}.")
        # Conditional expansion is justified only by actual typed relationship records.
        # Never treat temporal coincidence or a model-selected ID as a foreign key.
        if plan.intent.causality != "none":
            coverage = {}
            for evidence in self.response.evidence:
                if evidence.tool_name == "investigate_business_entity":
                    key = (evidence.arguments["entity_type"], evidence.arguments["entity_id"])
                    count, total = coverage.get(key, (0, evidence.payload["total"]))
                    coverage[key] = (count + len(evidence.payload["evidence"]), total)
            roots = {
                (e.arguments["entity_type"], e.arguments["entity_id"])
                for e in self.response.evidence
                if e.tool_name == "investigate_business_entity"
            }
            candidates = {}
            for step in list(plan.steps):
                source = self.results.get(step.step_id)
                if not source or source.tool_name != "investigate_business_entity":
                    continue
                root = (source.arguments["entity_type"], source.arguments["entity_id"])
                if coverage[root][0] >= coverage[root][1]:
                    continue
                for row in source.payload.get("evidence", []):
                    for kind, identifier in (
                        (row["entity_type"], row["entity_id"]),
                        (row["related_entity_type"], row["related_entity_id"]),
                    ):
                        key = (kind, identifier)
                        if kind in {"shortage", "sales_order", "incident"} and key not in roots:
                            candidates.setdefault(key, step)
            ordered = sorted(
                candidates.items(),
                key=lambda item: (
                    {"shortage": 0, "sales_order": 1, "incident": 2}[item[0][0]],
                    item[0][1],
                ),
            )
            for (kind, identifier), parent in ordered[:2]:
                if self.response.usage.tool_calls >= self.limit or len(plan.steps) >= 12:
                    missing.append("Further linked-record investigation exceeds the tool budget.")
                    break
                arguments = {
                    "entity_type": kind,
                    "entity_id": identifier,
                    "query": {**parent.arguments.get("query", {}), "offset": 0, "limit": 20},
                }
                child = PlanStep(
                    step_id=f"step_{len(plan.steps) + 1}",
                    capability="investigation",
                    tool="investigate_business_entity",
                    arguments=arguments,
                    depends_on=[parent.step_id],
                    binding=Binding(
                        step_id=parent.step_id, kind="linked_entity", entity_id=identifier
                    ),
                    expected_evidence=["relationships"],
                )
                plan.steps.append(child)
                self.response.execution.planned_steps += 1
                try:
                    self.results[child.step_id] = await self.call(
                        child.tool, arguments, child.capability
                    )
                    self.response.execution.executed_steps += 1
                except AgentError as exc:
                    missing.append(f"Linked-record investigation: {exc.code}.")
        return missing


async def query_hybrid(
    request, *, settings=None, bind=None, language=None, conversation_owner=None
):
    from app.hybrid.resolution import resolve

    settings = settings or agent_settings()
    if request.constraints.max_rounds is not None:
        settings = settings.model_copy(
            update={
                "agent_max_rounds": min(settings.agent_max_rounds, request.constraints.max_rounds)
            }
        )
    start = time.monotonic()
    response = HybridResponse(
        request_id=uuid.uuid4().hex,
        conversation_id=None,
        question=request.question,
        as_of=request.as_of or __import__("datetime").date(2026, 9, 30),
        status="incomplete",
        answer="",
        termination_reason="not_finished",
        operating_mode=request.mode,
        response_origin="verified_structured_facts",
        model=None,
        usage=Usage(
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            estimated_cost_usd=0,
            cost_basis="No model inference.",
        ),
    )
    sql_execution = re.search(
        r"(?:^|\b(?:execute|run|issue)\s+)(?:the\s+)?(?:sql\s+)?"
        r"(?:drop|alter|truncate|insert|update|delete|grant|revoke|select)\b",
        request.question,
        re.I,
    )
    if prohibited_execution(request.question) or sql_execution:
        response.status, response.termination_reason = "refused", "unsupported_execution"
        response.answer = compose(response)
        response.usage.elapsed_ms = round((time.monotonic() - start) * 1000, 3)
        return response
    if request.mode == "LOCAL_FULL_AGENT":
        from app.agent.contracts import AgentRequest
        from app.agent.service import query_agent
        from app.hybrid.resources import HybridSettings, admission

        try:
            config = HybridSettings()
            if not config.allow_legacy or settings.llm_provider != "ollama":
                raise AgentError("legacy_disabled", "Experimental full-agent mode is disabled.")
            admission(config, model=settings.llm_model, context=settings.ollama_context_tokens)
            body = AgentRequest.model_validate(
                {k: v for k, v in request.model_dump().items() if k in AgentRequest.model_fields}
            )
            legacy = await query_agent(body)
            return HybridResponse(
                **legacy.model_dump(), operating_mode=request.mode, response_origin="legacy_agent"
            )
        except AgentError as exc:
            response.status, response.termination_reason = "limited", exc.code
            response.limitations = [str(exc)]
        response.answer = compose(response)
        response.usage.elapsed_ms = round((time.monotonic() - start) * 1000, 3)
        return response
    identifier, conversation = conversations.get(
        request.conversation_id, None, owner=conversation_owner
    )
    response.conversation_id = identifier
    engine = Engine(request, settings, response, bind)
    try:
        async with asyncio.timeout(settings.agent_timeout_seconds):
            async with ACTIVE, conversation.lock:
                intent = interpret(
                    request.question,
                    request.as_of or conversation.as_of or response.as_of,
                    explicit_cutoff=request.as_of,
                )
                if request.objectives:
                    intent.objectives = request.objectives
                    intent.source = "structured"
                    intent.clarification = None
                if request.entities is not None:
                    intent.mentions = request.entities
                if (
                    intent.reference == "previous"
                    and not intent.objectives
                    and not intent.unsupported_concept
                ):
                    previous = next(
                        (t for t in reversed(conversation.turns) if t["status"] == "completed"),
                        None,
                    )
                    prior_subjects = (
                        {(e["entity_type"], e["entity_id"]) for e in previous.get("entities", [])}
                        if previous
                        else set()
                    )
                    if (
                        previous
                        and len(prior_subjects) == 1
                        and previous.get("hybrid_objectives")
                        and not previous.get("ranking_validated")
                    ):
                        intent.objectives = [
                            Objective.model_validate(o) for o in previous["hybrid_objectives"]
                        ]
                        intent.clarification = None
                for name in ("start_date", "end_date"):
                    if getattr(request, name) is not None:
                        if getattr(intent, name) not in {None, getattr(request, name)}:
                            raise AgentError(
                                "scope_conflict", "Question and structured dates differ."
                            )
                        setattr(intent, name, getattr(request, name))
                if (
                    intent.clarification
                    and request.mode == "HYBRID_LOCAL"
                    and request.interpret
                    and not intent.unsupported_concept
                ):
                    from app.hybrid.language import LocalLanguage, fallback

                    try:
                        client = language or LocalLanguage(response, settings)
                        proposed = await client.interpret(request.question, intent)
                        validate_intent(proposed)
                        intent = proposed
                    except (AgentError, ValueError, KeyError, TypeError) as exc:
                        fallback(response, exc)
                validate_intent(intent)
                response.interpretation = intent
                response.as_of = intent.as_of
                if intent.clarification:
                    raise AgentError("intent_ambiguous", intent.clarification)
                subjects = await resolve(
                    intent, request.question, conversation.turns, engine.call, bind
                )
                response.resolved_entities = subjects
                plan = build_plan(
                    intent,
                    subjects,
                    request.question,
                    engine.limit - response.usage.tool_calls,
                    bind,
                )
                response.plan = plan
                response.execution.planned_steps = len(plan.steps)
                missing = await engine.execute(plan)
                response.resolved_entities = plan.subjects
                graph = graph_from(response.evidence, engine.capabilities, plan)
                graph.missing.extend(missing)
                response.evidence_graph = graph
                if graph.facts:
                    with agent_session(bind=bind) as db:
                        findings, citations = grounded_findings(graph, response.evidence, plan, db)
                    response.key_findings, response.citations = findings, citations
                identities = {(s.entity_type, s.entity_id) for s in response.resolved_entities}
                for fact in graph.facts:
                    if (
                        fact.subject
                        and (fact.subject.entity_type, fact.subject.entity_id) not in identities
                    ):
                        response.resolved_entities.append(fact.subject)
                        identities.add((fact.subject.entity_type, fact.subject.entity_id))
                if intent.unsupported_concept or intent.causality == "universal":
                    graph.missing.append(
                        "The requested unrecorded quantity, universal causal proof or automatic "
                        "legal conclusion is not established."
                    )
                graph.completeness = (
                    "partial"
                    if graph.facts and graph.missing
                    else "complete"
                    if graph.facts
                    else "insufficient"
                )
                response.status = {
                    "complete": "completed",
                    "partial": "partial",
                    "insufficient": "insufficient_evidence",
                }[graph.completeness]
                response.termination_reason = (
                    "verified_plan_completed"
                    if response.status == "completed"
                    else "required_evidence_incomplete"
                )
                response.limitations.extend(graph.missing)
                if request.mode == "HYBRID_LOCAL":
                    from app.hybrid.language import assist

                    await assist(request, response, settings, language)
                conversation.as_of = response.as_of
                conversations.save(conversation, response)
                if response.status == "completed":
                    conversation.turns[-1]["hybrid_objectives"] = [
                        o.model_dump() for o in intent.objectives
                    ]
    except (AgentError, ValidationError, TimeoutError) as exc:
        code = (
            exc.code
            if isinstance(exc, AgentError)
            else "request_timeout"
            if isinstance(exc, TimeoutError)
            else "invalid_interpretation"
        )
        response.status = (
            "insufficient_evidence"
            if code == "entity_not_found"
            else "clarification_required"
            if code
            in {
                "intent_ambiguous",
                "entity_ambiguous",
                "subject_required",
                "scope_ambiguous",
                "scope_conflict",
                "reference_unresolved",
                "ranking_reference_unverified",
                "unsupported_scope",
            }
            else "limited"
            if code in {"tool_call_limit", "request_timeout"}
            else "validation_failed"
        )
        response.termination_reason = code
        response.limitations.append(
            str(exc)
            if isinstance(exc, AgentError)
            else "The requested interpretation or execution could not be validated."
        )
        if response.status == "clarification_required":
            response.follow_up_questions.append(response.limitations[-1])
    response.answer = compose(response)
    response.usage.elapsed_ms = round((time.monotonic() - start) * 1000, 3)
    response.execution.sql_tool_ms = round(response.execution.sql_tool_ms, 3)
    response.execution.rag_tool_ms = round(response.execution.rag_tool_ms, 3)
    return response
