import uuid

from app.agent.contracts import AgentError
from app.agent.database import agent_session
from app.agent.tools import TOOLS
from app.analytics import (
    finance,
    fulfilment,
    incidents,
    inventory,
    procurement,
    suppliers,
    warehouses,
    workforce,
)
from app.hybrid.contracts import Binding, Plan, PlanStep
from app.hybrid.registry import REGISTRY
from app.knowledge.contracts import SearchRequest
from app.knowledge.search import eligible_documents

SERVICES = {
    "get_supplier_performance": suppliers,
    "compare_suppliers": suppliers,
    "get_procurement_performance": procurement,
    "get_inventory_status": inventory,
    "get_warehouse_performance": warehouses,
    "get_customer_fulfilment": fulfilment,
    "get_operational_costs": finance,
    "get_workforce_tasks": workforce,
    "get_operational_incidents": incidents,
}


def policy_filter(topic, cutoff, bind=None):
    if not topic:
        return {"document_type": "policy"}
    words = set(topic.casefold().split())
    with agent_session(bind=bind) as db:
        candidates = eligible_documents(
            db, SearchRequest(query=topic, as_of=cutoff, filters={"document_type": "policy"})
        )
        matches = [m for m in candidates if words <= set(m["title"].casefold().split())]
    return {
        "document_type": "policy",
        **({"document_id": matches[0]["document_id"]} if len(matches) == 1 else {}),
    }


def build_plan(intent, subjects, question, max_tools=12, bind=None):
    steps = []
    supplier_subjects = [s for s in subjects if s.entity_type == "supplier"]
    rank_step = None
    objectives = sorted(
        intent.objectives,
        key=lambda o: (
            o.capability != "supplier_ranking",
            o.capability not in {"supplier_sla", "contract_lookup"},
        ),
    )

    def add(capability, tool, arguments, *, binding=None, dependencies=()):
        existing = next(
            (
                s
                for s in steps
                if s.tool == tool and s.arguments == arguments and s.binding == binding
            ),
            None,
        )
        if existing:
            return existing.step_id
        step_id = f"step_{len(steps) + 1}"
        steps.append(
            PlanStep(
                step_id=step_id,
                capability=capability,
                tool=tool,
                arguments=arguments,
                binding=binding,
                depends_on=list(dependencies),
                expected_evidence=list(REGISTRY[capability].required_evidence),
            )
        )
        return step_id

    def query(tool, subject=None):
        values = {
            "as_of": str(intent.as_of),
            "limit": 5,
            "include_trends": False,
            "include_comparison": False,
        }
        if intent.start_date:
            values["start_date"] = str(intent.start_date)
        if intent.end_date:
            values["end_date"] = str(intent.end_date)
        allowed = SERVICES[tool].ALLOWED if tool in SERVICES else set()
        for s in subjects:
            if (
                subject
                and s.entity_type == subject.entity_type
                and s.entity_id != subject.entity_id
            ):
                continue
            key = s.entity_type + "_id"
            if key in allowed:
                if key in values and values[key] != s.entity_id:
                    if subject is None or subject.entity_type != s.entity_type:
                        raise AgentError(
                            "scope_ambiguous", "This aggregate accepts one value per entity filter."
                        )
                else:
                    values[key] = s.entity_id
        if subject and tool == "get_supplier_performance":
            values.pop("supplier_id", None)
        return values

    for objective in objectives:
        capability = REGISTRY[objective.capability]
        if objective.capability == "supplier_ranking":
            if len(supplier_subjects) > 1:
                raise AgentError(
                    "scope_ambiguous",
                    "Use a complete supplier ranking or one supported population filter.",
                )
            values = {
                **query("compare_suppliers"),
                "sort": objective.metric,
                "direction": objective.direction,
                "limit": objective.count,
            }
            rank_step = add(objective.capability, "compare_suppliers", values)
        elif objective.capability in {"supplier_performance", "supplier_sla", "contract_lookup"}:
            if not supplier_subjects:
                if rank_step and intent.reference == "rank_extreme":
                    # Expansion uses actual ranked records at execution, not an invented ID.
                    detail = add(
                        objective.capability,
                        "get_supplier_performance",
                        {"query": query("get_supplier_performance")},
                        binding=Binding(step_id=rank_step, kind="ranked_subjects"),
                        dependencies=[rank_step],
                    )
                    if objective.capability != "supplier_performance":
                        add(
                            objective.capability,
                            "search_corporate_knowledge",
                            {"as_of": str(intent.as_of), "top_k": 2},
                            binding=Binding(step_id=detail, kind="effective_contract"),
                            dependencies=[detail],
                        )
                    continue
                raise AgentError(
                    "subject_required",
                    "Specify a supplier name/ID or a verified ranking reference.",
                )
            for subject in supplier_subjects:
                detail = add(
                    objective.capability,
                    "get_supplier_performance",
                    {
                        "supplier_id": subject.entity_id,
                        "query": query("get_supplier_performance", subject),
                    },
                )
                if objective.capability != "supplier_performance":
                    add(
                        objective.capability,
                        "search_corporate_knowledge",
                        {"as_of": str(intent.as_of), "top_k": 2},
                        binding=Binding(
                            step_id=detail, kind="effective_contract", entity_id=subject.entity_id
                        ),
                        dependencies=[detail],
                    )
        elif objective.capability == "policy_lookup":
            topic = objective.topic
            add(
                objective.capability,
                "search_corporate_knowledge",
                {
                    "query": (topic + " procedure escalation") if topic else question[:512],
                    "as_of": str(intent.as_of),
                    "top_k": 2,
                    "filters": policy_filter(topic, intent.as_of, bind),
                },
            )
        elif objective.capability == "investigation":
            roots = [s for s in subjects if s.entity_type not in {"employee", "customer"}]
            if not roots:
                raise AgentError(
                    "subject_required",
                    "Specify an existing order, supplier, warehouse or incident to investigate.",
                )
            if len(roots) > 2:
                raise AgentError("scope_ambiguous", "Select at most two investigation roots.")
            for subject in roots:
                add(
                    objective.capability,
                    "investigate_business_entity",
                    {
                        "entity_type": subject.entity_type,
                        "entity_id": subject.entity_id,
                        "query": {**query("investigate_business_entity"), "limit": 20},
                    },
                )
        else:
            tool = capability.tools[0]
            if any(s.entity_type == "customer" for s in subjects):
                raise AgentError(
                    "unsupported_scope",
                    "Customer-level aggregate filters are unavailable; specify a sales order.",
                )
            allowed = SERVICES[tool].ALLOWED if tool in SERVICES else set()
            groups = {}
            for subject in subjects:
                if subject.entity_type + "_id" in allowed:
                    groups.setdefault(subject.entity_type, []).append(subject)
            repeated = [values for values in groups.values() if len(values) > 1]
            if len(repeated) > 1:
                raise AgentError(
                    "scope_ambiguous", "Narrow the comparison to one entity dimension."
                )
            if repeated:
                for subject in repeated[0]:
                    add(objective.capability, tool, query(tool, subject))
            else:
                add(objective.capability, tool, query(tool))
    if len(steps) > max_tools:
        raise AgentError(
            "tool_call_limit", "Narrow the request; its validated plan exceeds the tool budget."
        )
    for step in steps:
        if step.tool not in TOOLS or step.tool not in REGISTRY[step.capability].tools:
            raise AgentError(
                "invalid_plan", "Plan requested an unregistered capability/tool binding."
            )
    return Plan(
        plan_id=uuid.uuid4().hex,
        intent=intent,
        subjects=subjects,
        steps=steps,
        completion_conditions=[f"{s.step_id}: {', '.join(s.expected_evidence)}" for s in steps],
        constraints={"read_only": True, "max_tools": max_tools, "as_of": str(intent.as_of)},
        estimated_cost={"tool_steps": len(steps), "model_calls": 0, "parallelism": 1},
    )
