from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Constraints(Strict):
    max_rounds: int | None = Field(None, ge=1, le=6)
    max_tool_calls: int | None = Field(None, ge=1, le=12)
    max_cost_usd: float | None = Field(None, gt=0, le=10)


class AgentRequest(Strict):
    question: str = Field(min_length=2, max_length=2000)
    conversation_id: str | None = Field(None, pattern=r"^[a-f0-9]{32}$")
    as_of: date | None = None
    business_context: str | None = Field(None, max_length=1000)
    constraints: Constraints = Field(default_factory=Constraints)

    @field_validator("question")
    @classmethod
    def question_text(cls, value):
        if not value.strip() or "\x00" in value:
            raise ValueError("Question must contain text.")
        return value.strip()

    @field_validator("as_of")
    @classmethod
    def observed_cutoff(cls, value):
        if value is not None and not date(2025, 10, 1) <= value <= date(2026, 9, 30):
            raise ValueError("Agent business cutoff must be inside the observed Stage 2 period.")
        return value


class MetricRef(Strict):
    evidence_id: str
    pointer: str = Field(max_length=250, pattern=r"^/")


class EntityRef(Strict):
    evidence_id: str
    pointer: str = Field(max_length=250, pattern=r"^(?:/|$)")


class DraftFinding(Strict):
    quality_profile: Literal["legacy", "references"] = "legacy"
    claim_type: Literal[
        "interpretation",
        "observation",
        "comparison",
        "ranking",
        "policy_requirement",
        "association",
        "possible_explanation",
        "causal_chain",
        "suggestion",
        "unavailable",
    ] = "interpretation"
    entity_refs: list[EntityRef] = Field(default_factory=list, max_length=6)
    relationship_refs: list[MetricRef] = Field(default_factory=list, max_length=8)
    text: str = Field(
        min_length=1,
        max_length=600,
        description="Qualitative finding only. No digits, numeric entity IDs or number words. "
        "Use 'the supplier' rather than a numbered name. Put all quantities in metric_refs.",
    )
    evidence_ids: list[str] = Field(max_length=8)
    metric_refs: list[MetricRef] = Field(max_length=8)
    citation_ids: list[str] = Field(max_length=8)
    quote_citation_ids: list[str] = Field(default_factory=list, max_length=2)


class Draft(Strict):
    quality_profile: Literal["legacy", "references"] = "legacy"
    status: Literal[
        "completed", "partial", "insufficient_evidence", "clarification_required", "refused"
    ]
    findings: list[DraftFinding] = Field(max_length=8)
    limitations: list[str] = Field(
        max_length=8,
        description="Qualitative limitations only: no digits, dates, numeric IDs, "
        "document codes or spelled-out numbers. An empty list is allowed.",
    )
    follow_up_questions: list[str] = Field(
        max_length=3,
        description="Qualitative questions only: no digits, dates, numeric IDs, "
        "document codes or spelled-out numbers. An empty list is allowed.",
    )


class Evidence(Strict):
    evidence_id: str
    tool_name: str
    arguments: dict
    as_of: date
    payload: dict
    trust: Literal["untrusted_tool_data"] = "untrusted_tool_data"


class ToolTrace(Strict):
    call_id: str
    tool: str
    arguments: dict | None = None
    status: str
    elapsed_ms: float
    evidence_id: str | None = None
    error_code: str | None = None
    error_details: dict | None = None
    duplicate: bool = False


class Usage(Strict):
    provider_round_ms: list[float] = Field(default_factory=list)
    provider_rounds: list[dict] = Field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    llm_calls: int = 0
    tool_calls: int = 0
    provider_usage_complete: bool = True
    estimated_cost_usd: float | None = None
    cost_basis: str | None = None
    elapsed_ms: float = 0


class Finding(Strict):
    text: str
    entities: list[dict] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)
    claim_type: str = "interpretation"
    evidence_ids: list[str]
    metrics: list[dict]
    citation_ids: list[str]
    quotations: list[dict] = Field(default_factory=list)


class AgentResponse(Strict):
    request_id: str
    conversation_id: str | None
    question: str
    as_of: date
    status: str
    answer: str
    key_findings: list[Finding] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)
    tool_trace: list[ToolTrace] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    termination_reason: str
    model: str | None = None
    execution_mode: Literal["live", "offline_test"] = "live"


class AgentError(Exception):
    def __init__(self, code, message, retryable=False, details=None):
        super().__init__(message)
        self.code, self.retryable = code, retryable
        self.details = details
