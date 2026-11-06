from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, SecretStr, StringConstraints, field_validator

from app.agent.contracts import Strict as AgentStrict
from data.generator.company import END, START


class Strict(AgentStrict):
    @field_validator("title", "description", "text", "resolution", check_fields=False)
    @classmethod
    def nonblank_text(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Text must contain non-whitespace characters")
        return value.strip() if value is not None else value


Role = Literal[
    "VIEWER", "OPERATIONS_ANALYST", "WORKFLOW_OPERATOR", "WORKFLOW_APPROVER", "WORKFLOW_ADMIN"
]
Priority = Literal["low", "normal", "high", "urgent"]
TaskStatus = Literal["open", "active", "blocked", "completed", "cancelled"]
Source = Literal["HUMAN", "DETERMINISTIC_RECOMMENDATION", "AI_DRAFT"]
SubjectKind = Literal[
    "supplier", "purchase_order", "sales_order", "warehouse", "product", "incident", "department"
]
Nonempty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
Hash = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
FactId = Annotated[str, StringConstraints(pattern=r"^fact_[a-f0-9]{16}$")]


class Login(Strict):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9_.-]+$")
    password: SecretStr = Field(min_length=12, max_length=200)


class Token(Strict):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: AwareDatetime


class Principal(Strict):
    id: UUID
    username: str
    active: bool
    is_human: bool
    authz_version: int
    employee_id: int | None
    created_at: AwareDatetime
    roles: list[dict]


class RoleChange(Strict):
    role: Role
    department_id: int | None = Field(None, gt=0)
    active: bool
    reason: Nonempty


class PolicyChange(Strict):
    expected_version: int = Field(gt=0)
    max_validity_hours: int = Field(ge=1, le=168)
    approval_validity_minutes: int = Field(ge=5, le=1440)
    reason: Nonempty


class Subject(Strict):
    kind: SubjectKind
    entity_id: int = Field(gt=0, le=2147483647)


class CreateTask(Strict):
    type: Literal["CREATE_WORKFLOW_TASK"]
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    priority: Priority
    due_at: AwareDatetime
    employee_id: int | None = Field(None, gt=0)
    subject: Subject


class TaskTarget(Strict):
    task_id: UUID
    expected_version: int = Field(gt=0)


class AssignTask(TaskTarget):
    type: Literal["ASSIGN_WORKFLOW_TASK"]
    employee_id: int | None = Field(None, gt=0)
    department_id: int | None = Field(None, gt=0)


class SetStatus(TaskTarget):
    type: Literal["UPDATE_WORKFLOW_TASK_STATUS"]
    status: TaskStatus


class SetPriority(TaskTarget):
    type: Literal["UPDATE_WORKFLOW_TASK_PRIORITY"]
    priority: Priority


class SetDue(TaskTarget):
    type: Literal["UPDATE_WORKFLOW_TASK_DUE_DATE"]
    due_at: AwareDatetime


class AddNote(TaskTarget):
    type: Literal["ADD_WORKFLOW_TASK_NOTE"]
    text: str = Field(min_length=1, max_length=4000)


class CreateEscalation(Strict):
    type: Literal["CREATE_INTERNAL_ESCALATION"]
    title: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=4000)
    priority: Priority
    due_at: AwareDatetime
    subject: Subject
    task_id: UUID | None = None


class CloseEscalation(Strict):
    type: Literal["CLOSE_INTERNAL_ESCALATION"]
    escalation_id: UUID
    expected_version: int = Field(gt=0)
    resolution: str = Field(min_length=1, max_length=4000)


Action = Annotated[
    CreateTask
    | AssignTask
    | SetStatus
    | SetPriority
    | SetDue
    | AddNote
    | CreateEscalation
    | CloseEscalation,
    Field(discriminator="type"),
]


class ProposalInput(Strict):
    department_id: int = Field(gt=0)
    action: Action
    source_type: Source = "HUMAN"
    evidence_id: UUID | None = None
    fact_ids: list[FactId] = Field(default_factory=list, max_length=16)
    reason: Nonempty
    business_context: str | None = Field(None, max_length=2000)
    expires_at: AwareDatetime | None = None


class Review(Strict):
    proposal_version: int = Field(gt=0)
    digest: Hash
    reason: str | None = Field(None, max_length=1000)


class Revision(Review):
    proposal: ProposalInput


class EvidenceRequest(Strict):
    department_id: int = Field(gt=0)
    subject: Subject
    question: str = Field(min_length=2, max_length=2000)
    as_of: date = Field(END, ge=START, le=END)


class EvidenceOut(Strict):
    id: UUID
    created_by: UUID
    subject_id: UUID
    department_id: int
    payload: dict
    digest: Hash
    created_at: AwareDatetime
    expires_at: AwareDatetime


class ProposalOut(Strict):
    id: UUID
    proposer_id: UUID
    department_id: int
    subject_id: UUID
    evidence_id: UUID | None
    previous_id: UUID | None
    version: int
    action_type: str
    source_type: Source
    material: dict
    digest: Hash
    status: str
    effective_status: str
    stale: bool
    approval_policy_current: bool
    created_at: AwareDatetime
    updated_at: AwareDatetime
    expires_at: AwareDatetime
    approvals: list[dict]
    executions: list[dict]
    limitations: list[str]


class TaskOut(Strict):
    id: UUID
    title: str
    description: str
    status: TaskStatus
    priority: Priority
    department_id: int
    employee_id: int | None
    subject_id: UUID
    created_by: UUID
    proposal_id: UUID
    execution_id: UUID
    version: int
    created_at: AwareDatetime
    updated_at: AwareDatetime
    due_at: AwareDatetime
    completed_at: AwareDatetime | None
    subject: Subject
    source_type: Source
    evidence_id: UUID | None


class EscalationOut(Strict):
    id: UUID
    title: str
    reason: str
    status: Literal["open", "closed"]
    priority: Priority
    department_id: int
    subject_id: UUID
    task_id: UUID | None
    created_by: UUID
    proposal_id: UUID
    execution_id: UUID
    version: int
    created_at: AwareDatetime
    updated_at: AwareDatetime
    due_at: AwareDatetime
    closed_at: AwareDatetime | None
    resolution: str | None
    subject: Subject
    source_type: Source
    evidence_id: UUID | None


class ExecutionOut(Strict):
    id: UUID
    proposal_id: UUID
    actor_id: UUID
    approver_id: UUID
    status: Literal["EXECUTING", "COMPLETED", "FAILED"]
    result: dict
    error_code: str | None
    created_at: AwareDatetime
    finished_at: AwareDatetime | None


class AuditOut(Strict):
    id: UUID
    sequence: int
    actor_id: UUID | None
    department_id: int | None
    action: str
    object_type: str
    object_id: UUID | None
    proposal_id: UUID | None
    execution_id: UUID | None
    before_state: dict
    after_state: dict
    reason: str | None
    result: Literal["SUCCESS", "DENIED", "FAILED"]
    request_id: UUID
    created_at: AwareDatetime


class Page[T](Strict):
    items: list[T]
    total: int
    limit: int
    offset: int


class Recommendation(Strict):
    evidence_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    priority: Priority
    due_at: AwareDatetime
    employee_id: int | None = Field(None, gt=0)


class NoteOut(Strict):
    id: UUID
    task_id: UUID
    actor_id: UUID
    execution_id: UUID
    text: str
    created_at: AwareDatetime


class AssignmentOut(Strict):
    id: UUID
    task_id: UUID
    department_id: int
    employee_id: int | None
    actor_id: UUID
    execution_id: UUID
    created_at: AwareDatetime


class SummaryOut(Strict):
    source: Literal["stage5_workflow_state"] = "stage5_workflow_state"
    as_of: AwareDatetime
    open_tasks: int
    overdue_tasks: int
    open_escalations: int
    pending_proposals: int
    rejected_proposals: int
    completed_actions_this_month: int
    limitations: list[str]


class RecommendationOut(Strict):
    proposal: ProposalInput
    persisted: Literal[False]
    approval_granted: Literal[False]
    llm_calls: Literal[0]
    limitations: list[str]


class RegisteredAction(Strict):
    type: str
    target: str
    risk: str
    required_approvals: Literal[1]
    distinct_reviewer: Literal[True]
    input_schema: dict = Field(alias="schema")


class ActionRegistry(Strict):
    actions: list[RegisteredAction]
    external_side_effects: Literal[False]
    llm_required: Literal[False]


class PolicyState(Strict):
    id: int
    max_validity_hours: int
    approval_validity_minutes: int
    created_by: UUID | None
    created_at: AwareDatetime


class PolicyOut(PolicyState):
    required_approvals: Literal[1]
    separation_of_duties: Literal[True]
    origin: str
