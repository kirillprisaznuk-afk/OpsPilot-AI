import uuid
from typing import Annotated
from uuid import UUID

from app.workflow import actions, auth, evidence, policy, queries, service
from app.workflow import contracts as c
from app.workflow import schema as s
from app.workflow.audit import event
from app.workflow.common import (
    Actor,
    WorkflowError,
    lock,
    principal_locks,
    transaction,
    workflow_engine,
)
from app.workflow.permissions import require
from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

auth_router = APIRouter(prefix="/api/v1/auth", tags=["local authentication"])
router = APIRouter(prefix="/api/v1/workflows", tags=["human-governed workflows"])
bearer = HTTPBearer(auto_error=False)


def runtime():
    return workflow_engine()


RUNTIME_DEPENDENCY = Depends(runtime)


def request_id(request: Request):
    if not hasattr(request.state, "correlation_id"):
        supplied = request.headers.get("X-Request-ID")
        try:
            request.state.correlation_id = uuid.UUID(supplied) if supplied else uuid.uuid4()
        except ValueError:
            raise WorkflowError(
                "invalid_request_id", "Request correlation ID must be a UUID.", 422
            ) from None
    return request.state.correlation_id


def principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    bind=RUNTIME_DEPENDENCY,
):
    token = (
        credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else None
    )
    actor = auth.authenticate(token, request_id(request), bind)
    request.state.workflow_actor = actor
    request.state.workflow_bind = bind
    return actor


ActorDep = Annotated[Actor, Depends(principal)]
Key = Annotated[UUID, Header(alias="Idempotency-Key")]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=1000000)]


def deliver(result, response):
    response.status_code = result.status
    if result.transaction_ms is not None:
        response.headers["Server-Timing"] = f"workflow_tx;dur={result.transaction_ms:.3f}"
    return result.unwrap()


@auth_router.post("/login", response_model=c.Token)
def login(body: c.Login, request: Request, bind=RUNTIME_DEPENDENCY):
    return auth.login(
        body, request.client.host if request.client else "local", request_id(request), bind
    )


@auth_router.get("/me", response_model=c.Principal)
def me(actor: ActorDep, bind=RUNTIME_DEPENDENCY):
    return auth.me(actor, bind)


@auth_router.post("/logout", response_model=dict[str, bool])
def logout(actor: ActorDep, request: Request, bind=RUNTIME_DEPENDENCY):
    return auth.logout(actor, request_id(request), bind)


@auth_router.post("/principals/{identifier}/roles", response_model=dict[str, bool])
def role_change(
    identifier: UUID, body: c.RoleChange, actor: ActorDep, request: Request, bind=RUNTIME_DEPENDENCY
):
    return auth.change_role(actor, identifier, body, request_id(request), bind)


@router.get("/actions", response_model=c.ActionRegistry)
def registry(actor: ActorDep, bind=RUNTIME_DEPENDENCY):
    with transaction("read", bind) as db:
        from app.workflow.permissions import memberships

        if not memberships(db, actor.id):
            raise WorkflowError("permission_denied", "No workflow role is assigned.", 403)
    return {
        "actions": [
            {
                "type": key,
                "target": spec.target,
                "risk": spec.risk,
                "required_approvals": 1,
                "distinct_reviewer": True,
                "schema": spec.model.model_json_schema(),
            }
            for key, spec in actions.REGISTRY.items()
        ],
        "external_side_effects": False,
        "llm_required": False,
    }


@router.get("/policy", response_model=c.PolicyOut)
def get_policy(actor: ActorDep, bind=RUNTIME_DEPENDENCY):
    with transaction("read", bind) as db:
        from app.workflow.permissions import memberships

        if not memberships(db, actor.id):
            raise WorkflowError("permission_denied", "No workflow role is assigned.", 403)
        return {
            **policy.current(db),
            "required_approvals": 1,
            "separation_of_duties": True,
            "origin": "Stage 5 local-demo application security policy",
        }


@router.post("/policy", response_model=c.PolicyState)
def change_policy(body: c.PolicyChange, actor: ActorDep, request: Request, bind=RUNTIME_DEPENDENCY):
    from sqlalchemy import insert, select, update

    failure = None
    result = None
    with transaction("admin", bind) as db:
        try:
            lock(db, "workflow-policy", 1)
            principal_locks(db, [actor.id])
            require(db, actor, "admin", [None])
            db.execute(select(s.policy_control).where(s.policy_control.c.id == 1).with_for_update())
            previous = policy.current(db)
            if previous["id"] != body.expected_version:
                raise WorkflowError("policy_version_conflict", "Governance policy changed.")
            result = dict(
                db.execute(
                    insert(s.policies)
                    .values(
                        max_validity_hours=body.max_validity_hours,
                        approval_validity_minutes=body.approval_validity_minutes,
                        created_by=actor.id,
                    )
                    .returning(s.policies)
                )
                .mappings()
                .one()
            )
            db.execute(
                update(s.policy_control)
                .where(s.policy_control.c.id == 1)
                .values(policy_id=result["id"])
            )
            event(
                db,
                actor,
                "policy.changed",
                request_id=request_id(request),
                object_type="policy",
                before={"version": previous["id"]},
                after={"version": result["id"]},
                reason=body.reason,
            )
        except WorkflowError as exc:
            failure = exc
            event(
                db,
                actor,
                "policy.denied",
                request_id=request_id(request),
                result="DENIED",
                after={"code": exc.code},
            )
    if failure:
        raise failure
    return result


@router.post("/evidence", response_model=c.EvidenceOut)
async def capture_evidence(
    body: c.EvidenceRequest,
    key: Key,
    actor: ActorDep,
    request: Request,
    response: Response,
    bind=RUNTIME_DEPENDENCY,
):
    return deliver(await evidence.capture(actor, body, key, request_id(request), bind), response)


@router.get("/evidence/{identifier}", response_model=c.EvidenceOut)
def get_evidence(identifier: UUID, actor: ActorDep, bind=RUNTIME_DEPENDENCY):
    return queries.captured_evidence(actor, identifier, bind)


@router.post("/recommendations", response_model=c.RecommendationOut)
def recommend(body: c.Recommendation, actor: ActorDep, bind=RUNTIME_DEPENDENCY):
    return evidence.recommendation(actor, body, bind)


@router.post("/proposals", response_model=c.ProposalOut)
def create(
    body: c.ProposalInput,
    key: Key,
    actor: ActorDep,
    request: Request,
    response: Response,
    bind=RUNTIME_DEPENDENCY,
):
    return deliver(service.create(actor, body, key, request_id(request), bind), response)


@router.get("/proposals", response_model=c.Page[c.ProposalOut])
def proposals(
    actor: ActorDep,
    limit: Limit = 25,
    offset: Offset = 0,
    status: str | None = None,
    department_id: int | None = Query(None, gt=0),
    source_type: c.Source | None = None,
    bind=RUNTIME_DEPENDENCY,
):
    return queries.proposals(actor, limit, offset, status, department_id, source_type, bind)


@router.get("/proposals/{identifier}", response_model=c.ProposalOut)
def get_proposal(identifier: UUID, actor: ActorDep, bind=RUNTIME_DEPENDENCY):
    return queries.proposal(actor, identifier, bind)


@router.patch("/proposals/{identifier}", response_model=c.ProposalOut)
def edit_proposal(
    identifier: UUID,
    key: Key,
    actor: ActorDep,
    request: Request,
    response: Response,
    bind=RUNTIME_DEPENDENCY,
):
    # No body is interpreted or mass-assigned, even for a draft.
    return deliver(service.deny_edit(actor, identifier, key, request_id(request), bind), response)


@router.post("/proposals/{identifier}/revise", response_model=c.ProposalOut)
def revise(
    identifier: UUID,
    body: c.Revision,
    key: Key,
    actor: ActorDep,
    request: Request,
    response: Response,
    bind=RUNTIME_DEPENDENCY,
):
    return deliver(
        service.revise(actor, identifier, body, key, request_id(request), bind), response
    )


@router.post("/proposals/{identifier}/submit", response_model=c.ProposalOut)
def submit(
    identifier: UUID,
    body: c.Review,
    key: Key,
    actor: ActorDep,
    request: Request,
    response: Response,
    bind=RUNTIME_DEPENDENCY,
):
    return deliver(
        service.submit(actor, identifier, body, key, request_id(request), bind), response
    )


@router.post("/proposals/{identifier}/approve", response_model=c.ProposalOut)
def approve(
    identifier: UUID,
    body: c.Review,
    key: Key,
    actor: ActorDep,
    request: Request,
    response: Response,
    bind=RUNTIME_DEPENDENCY,
):
    return deliver(
        service.review(actor, identifier, body, key, request_id(request), "APPROVE", bind), response
    )


@router.post("/proposals/{identifier}/reject", response_model=c.ProposalOut)
def reject(
    identifier: UUID,
    body: c.Review,
    key: Key,
    actor: ActorDep,
    request: Request,
    response: Response,
    bind=RUNTIME_DEPENDENCY,
):
    return deliver(
        service.review(actor, identifier, body, key, request_id(request), "REJECT", bind), response
    )


@router.post("/proposals/{identifier}/revoke", response_model=c.ProposalOut)
def revoke(
    identifier: UUID,
    body: c.Review,
    key: Key,
    actor: ActorDep,
    request: Request,
    response: Response,
    bind=RUNTIME_DEPENDENCY,
):
    return deliver(
        service.review(actor, identifier, body, key, request_id(request), "REVOKE", bind), response
    )


@router.post("/proposals/{identifier}/cancel", response_model=c.ProposalOut)
def cancel(
    identifier: UUID,
    body: c.Review,
    key: Key,
    actor: ActorDep,
    request: Request,
    response: Response,
    bind=RUNTIME_DEPENDENCY,
):
    return deliver(
        service.cancel(actor, identifier, body, key, request_id(request), bind), response
    )


@router.post("/proposals/{identifier}/execute", response_model=c.ExecutionOut)
def execute(
    identifier: UUID,
    body: c.Review,
    key: Key,
    actor: ActorDep,
    request: Request,
    response: Response,
    bind=RUNTIME_DEPENDENCY,
):
    return deliver(
        service.execute(actor, identifier, body, key, request_id(request), bind), response
    )


@router.get("/executions/{identifier}", response_model=c.ExecutionOut)
def execution(identifier: UUID, actor: ActorDep, bind=RUNTIME_DEPENDENCY):
    return queries.execution(actor, identifier, bind)


@router.get("/tasks", response_model=c.Page[c.TaskOut])
def tasks(
    actor: ActorDep,
    limit: Limit = 25,
    offset: Offset = 0,
    status: c.TaskStatus | None = None,
    department_id: int | None = Query(None, gt=0),
    supplier_id: int | None = Query(None, gt=0),
    employee_id: int | None = Query(None, gt=0),
    overdue: bool = False,
    priority: c.Priority | None = None,
    search: str | None = Query(None, max_length=150),
    bind=RUNTIME_DEPENDENCY,
):
    return queries.operational(
        actor,
        "task",
        limit=limit,
        offset=offset,
        status=status,
        department_id=department_id,
        supplier_id=supplier_id,
        employee_id=employee_id,
        overdue=overdue,
        priority=priority,
        search=search,
        bind=bind,
    )


@router.get("/tasks/{identifier}", response_model=c.TaskOut)
def task(identifier: UUID, actor: ActorDep, bind=RUNTIME_DEPENDENCY):
    return queries.operational(actor, "task", identifier=identifier, bind=bind)


@router.get("/tasks/{identifier}/notes", response_model=c.Page[c.NoteOut])
def notes(
    identifier: UUID,
    actor: ActorDep,
    limit: Limit = 25,
    offset: Offset = 0,
    bind=RUNTIME_DEPENDENCY,
):
    return queries.task_history(actor, identifier, "notes", limit, offset, bind)


@router.get("/tasks/{identifier}/assignments", response_model=c.Page[c.AssignmentOut])
def assignments(
    identifier: UUID,
    actor: ActorDep,
    limit: Limit = 25,
    offset: Offset = 0,
    bind=RUNTIME_DEPENDENCY,
):
    return queries.task_history(actor, identifier, "assignments", limit, offset, bind)


@router.get("/escalations", response_model=c.Page[c.EscalationOut])
def escalations(
    actor: ActorDep,
    limit: Limit = 25,
    offset: Offset = 0,
    status: str | None = None,
    department_id: int | None = Query(None, gt=0),
    supplier_id: int | None = Query(None, gt=0),
    overdue: bool = False,
    priority: c.Priority | None = None,
    search: str | None = Query(None, max_length=150),
    bind=RUNTIME_DEPENDENCY,
):
    return queries.operational(
        actor,
        "escalation",
        limit=limit,
        offset=offset,
        status=status,
        department_id=department_id,
        supplier_id=supplier_id,
        overdue=overdue,
        priority=priority,
        search=search,
        bind=bind,
    )


@router.get("/escalations/{identifier}", response_model=c.EscalationOut)
def escalation(identifier: UUID, actor: ActorDep, bind=RUNTIME_DEPENDENCY):
    return queries.operational(actor, "escalation", identifier=identifier, bind=bind)


@router.get("/audit", response_model=c.Page[c.AuditOut])
def audit(
    actor: ActorDep,
    limit: Limit = 25,
    offset: Offset = 0,
    proposal_id: UUID | None = None,
    actor_id: UUID | None = None,
    object_id: UUID | None = None,
    action: str | None = Query(None, max_length=80),
    search: str | None = Query(None, max_length=150),
    newest: bool = False,
    bind=RUNTIME_DEPENDENCY,
):
    return queries.audit(
        actor,
        limit,
        offset,
        proposal_id,
        actor_id,
        bind,
        object_id=object_id,
        action=action,
        search=search,
        newest=newest,
    )


@router.get("/summary", response_model=c.SummaryOut)
def summary(actor: ActorDep, bind=RUNTIME_DEPENDENCY):
    return queries.summary(actor, bind)
