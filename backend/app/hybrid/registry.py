"""Reusable capability semantics. No question strings, source IDs or business values."""

from dataclasses import asdict, dataclass

from app.agent.tools import TOOLS


@dataclass(frozen=True)
class Capability:
    capability_id: str
    domain: str
    objectives: tuple[str, ...]
    entity_types: tuple[str, ...]
    tools: tuple[str, ...]
    required_evidence: tuple[str, ...]
    metrics: tuple[str, ...] = ()
    semantics: str = "Observed records only; no unsupported causal or legal conclusion."
    unsupported: tuple[str, ...] = ("writes", "unrecorded losses", "automatic penalties")
    optional_parameters: tuple[str, ...] = ("as_of", "start_date", "end_date", "limit")
    required_parameters: tuple[str, ...] = ("validated_observation_scope",)
    output_types: tuple[str, ...] = ("verified_facts", "limitations")
    permission: str = "read_business_and_synthetic_knowledge"
    resource_cost: str = "one bounded read-only SQL/RAG tool per resolved subject"


def cap(name, domain, entities, tools, required, metrics=(), semantics=None):
    return Capability(
        name,
        domain,
        (name,),
        tuple(entities),
        tuple(tools),
        tuple(required),
        tuple(metrics),
        semantics or Capability.__dataclass_fields__["semantics"].default,
    )


REGISTRY = {
    c.capability_id: c
    for c in [
        cap(
            "supplier_performance",
            "procurement",
            ["supplier"],
            ["get_supplier_performance"],
            ["metrics"],
            ["on_time_rate", "due_orders", "on_time_orders", "overdue_outstanding_orders"],
        ),
        cap(
            "supplier_ranking",
            "procurement",
            [],
            ["compare_suppliers"],
            ["ranked_population"],
            [
                "on_time_rate",
                "overdue_outstanding_orders",
                "overdue_commitment",
                "open_commitment",
                "sla_gap",
            ],
        ),
        cap(
            "supplier_sla",
            "procurement",
            ["supplier"],
            ["get_supplier_performance", "search_corporate_knowledge"],
            ["metrics", "supplier_agreement"],
            ["on_time_rate", "due_orders", "on_time_orders"],
            "Compare supplier punctuality to its own effective target; "
            "not a customer promise or legal breach.",
        ),
        cap(
            "contract_lookup",
            "procurement",
            ["supplier"],
            ["get_supplier_performance", "search_corporate_knowledge"],
            ["supplier_agreement"],
        ),
        cap("policy_lookup", "knowledge", [], ["search_corporate_knowledge"], ["policy"]),
        cap(
            "inventory",
            "inventory",
            [],
            ["get_inventory_status"],
            ["metrics"],
            ["stock_on_hand", "outstanding_shortage_units"],
        ),
        cap(
            "warehouse",
            "warehousing",
            [],
            ["get_warehouse_performance"],
            ["metrics"],
            ["stock_on_hand", "outstanding_shortage_units"],
        ),
        cap(
            "fulfilment",
            "sales",
            [],
            ["get_customer_fulfilment"],
            ["metrics"],
            ["partial_orders", "overdue_outstanding_orders", "on_time_rate", "outstanding_units"],
            "Customer sales dispatch promises are separate from supplier purchasing agreements.",
        ),
        cap(
            "recorded_costs",
            "finance",
            [],
            ["get_operational_costs"],
            ["metrics"],
            ["additional_costs", "outstanding_amount", "overdue_amount"],
            "Recorded costs and exposure are not inferred lost profit or recoverable penalties.",
        ),
        cap(
            "workforce",
            "workforce",
            [],
            ["get_workforce_tasks"],
            ["metrics"],
            ["overdue_tasks", "open_tasks", "completed_tasks"],
        ),
        cap(
            "incidents",
            "operations",
            [],
            ["get_operational_incidents"],
            ["metrics"],
            ["open_incidents", "incidents", "escalated_incidents"],
        ),
        cap(
            "procurement",
            "procurement",
            [],
            ["get_procurement_performance"],
            ["metrics"],
            ["on_time_rate", "overdue_outstanding_orders", "overdue_commitment"],
        ),
        cap(
            "investigation",
            "cross_domain",
            [],
            ["investigate_business_entity"],
            ["relationships"],
            (),
            "Explicit links establish association. "
            "Only labelled simulated chains support modelled causality.",
        ),
        cap("overview", "enterprise", [], ["get_enterprise_overview"], ["metrics"]),
    ]
}

RELATIONSHIPS = (
    ("supplier", "purchase_order", "supplies"),
    ("purchase_order", "receipt", "received_against"),
    ("receipt", "stock_movement", "records_inventory"),
    ("stock_movement", "product", "concerns"),
    ("sales_order", "customer", "ordered_by"),
    ("fulfilment", "sales_order", "dispatches_against"),
    ("supplier_contract", "supplier", "defines_supplier_obligations"),
    ("policy", "procedure", "governs"),
    ("incident", "task", "linked_corrective_work"),
    ("recorded_cost", "invoice", "recorded_financial_basis"),
)


def describe():
    return [asdict(c) for c in REGISTRY.values()]


def validate_registry():
    for capability in REGISTRY.values():
        assert all(tool in TOOLS for tool in capability.tools)
        assert capability.permission == "read_business_and_synthetic_knowledge"
