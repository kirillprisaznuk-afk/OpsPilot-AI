from datetime import date
from typing import Literal

from pydantic import Field

from app.agent.contracts import AgentRequest, AgentResponse, Strict

Mode = Literal["HYBRID_LOCAL", "DETERMINISTIC", "LOCAL_FULL_AGENT"]
EntityKind = Literal[
    "supplier",
    "warehouse",
    "product",
    "department",
    "employee",
    "customer",
    "purchase_order",
    "sales_order",
    "invoice",
    "incident",
    "task",
    "shortage",
]


class Mention(Strict):
    entity_type: EntityKind
    term: str = Field(min_length=1, max_length=150)


class Subject(Strict):
    entity_type: EntityKind
    entity_id: int = Field(gt=0)
    label: str
    provenance: Literal["database_lookup", "verified_conversation", "verified_ranking"]


class Objective(Strict):
    capability: str = Field(max_length=60)
    metric: str | None = Field(None, max_length=80)
    direction: Literal["asc", "desc"] | None = None
    count: int = Field(3, ge=1, le=10)
    topic: str | None = Field(None, max_length=180)


class Intent(Strict):
    objectives: list[Objective] = Field(default_factory=list, max_length=8)
    mentions: list[Mention] = Field(default_factory=list, max_length=8)
    as_of: date
    start_date: date | None = None
    end_date: date | None = None
    reference: Literal["none", "previous", "first_two", "rank_extreme"] = "none"
    unsupported_concept: str | None = None
    causality: Literal["none", "association", "universal"] = "none"
    clarification: str | None = None
    source: Literal["grammar", "local_model", "structured"] = "grammar"


class HybridRequest(AgentRequest):
    mode: Mode = "HYBRID_LOCAL"
    objectives: list[Objective] | None = Field(None, min_length=1, max_length=8)
    entities: list[Mention] | None = Field(None, max_length=8)
    start_date: date | None = None
    end_date: date | None = None
    interpret: bool = True


class Binding(Strict):
    step_id: str
    kind: Literal["effective_contract", "ranked_subjects", "linked_entity"]
    entity_id: int | None = None


class PlanStep(Strict):
    step_id: str
    capability: str
    tool: str
    arguments: dict
    required: bool = True
    depends_on: list[str] = Field(default_factory=list)
    binding: Binding | None = None
    expected_evidence: list[str] = Field(default_factory=list)


class Plan(Strict):
    plan_id: str
    intent: Intent
    subjects: list[Subject]
    steps: list[PlanStep] = Field(max_length=12)
    completion_conditions: list[str]
    constraints: dict
    estimated_cost: dict


class Fact(Strict):
    fact_id: str
    evidence_id: str
    pointer: str
    source_tool: str
    scope: dict
    kind: Literal["metric", "document", "relationship"]
    subject: Subject | None = None
    subject_evidence_id: str | None = None
    subject_pointer: str | None = None
    window: dict | None = None
    value: dict
    verified: bool


class Graph(Strict):
    facts: list[Fact] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    completeness: Literal["complete", "partial", "insufficient"] = "insufficient"


class Execution(Strict):
    planned_steps: int = 0
    executed_steps: int = 0
    duplicates_avoided: int = 0
    sql_tool_ms: float = 0
    rag_tool_ms: float = 0
    model_role: str = "none"
    model_state: str = "not_requested"
    model_error: str | None = None
    model_request_bytes: int = 0
    fallback_used: bool = False


class HybridResponse(AgentResponse):
    operating_mode: Mode
    interpretation: Intent | None = None
    resolved_entities: list[Subject] = Field(default_factory=list)
    plan: Plan | None = None
    evidence_graph: Graph = Field(default_factory=Graph)
    execution: Execution = Field(default_factory=Execution)
    language_interpretation: dict | None = None
    response_origin: Literal["verified_structured_facts", "local_interpretation", "legacy_agent"]
