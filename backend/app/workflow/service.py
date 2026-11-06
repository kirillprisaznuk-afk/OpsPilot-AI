import json
import uuid
from datetime import UTC, timedelta

from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import SQLAlchemyError

from app.workflow import actions, evidence, policy
from app.workflow import contracts as c
from app.workflow import schema as s
from app.workflow.audit import event
from app.workflow.common import (
    Result,
    WorkflowError,
    canonical,
    digest,
    now,
    principal_locks,
)
from app.workflow.permissions import member, owner_or_admin, require
from app.workflow.unit import run

TERMINAL = {"COMPLETED", "FAILED", "REJECTED", "CANCELLED", "EXPIRED"}


def proposal_view(db, proposal):
    result = dict(proposal)
    result["effective_status"] = (
        "EXPIRED"
        if proposal["status"] not in TERMINAL and proposal["expires_at"] <= now()
        else proposal["status"]
    )
    result["approvals"] = [
        dict(r)
        for r in db.execute(
            select(s.approvals).where(s.approvals.c.proposal_id == proposal["id"])
        ).mappings()
    ]
    result["executions"] = [
        dict(r)
        for r in db.execute(
            select(s.executions).where(s.executions.c.proposal_id == proposal["id"])
        ).mappings()
    ]
    result["approval_policy_current"] = (
        policy.current(db)["id"] == proposal["material"]["policy"]["version"]
    )
    result["stale"] = not result["approval_policy_current"]
    parameters = proposal["material"]["action"]
    table, identifier = (
        (s.tasks, parameters.get("task_id"))
        if parameters.get("task_id")
        else (s.escalations, parameters.get("escalation_id"))
    )
    if identifier and parameters.get("expected_version"):
        version = db.execute(
            select(table.c.version).where(table.c.id == uuid.UUID(identifier))
        ).scalar_one_or_none()
        result["stale"] |= version != parameters["expected_version"]
    proposer = member(db, proposal["proposer_id"])
    result["stale"] |= (
        not proposer
        or proposer["authz_version"] != proposal["material"]["policy"]["proposer_authz_version"]
    )
    if proposal["status"] == "APPROVED":
        try:
            policy.executable_approval(db, proposal)
        except WorkflowError:
            result["stale"] = True
    result["limitations"] = [
        "Internal demo governance; this is not a contractual penalty or external commitment.",
        "Proposed due dates and priorities are operational settings requiring human review.",
    ] + (proposal["material"].get("evidence") or {}).get("limitations", [])
    if result["stale"]:
        result["limitations"].append(
            "Target or authorization context changed; review a new revision."
        )
    return result


def _guard(db, actor, identifier, permission, *, ownership=False):
    row = actions.one(db, s.proposals, identifier, locked=True)
    require(db, actor, permission, row["material"]["policy"]["scopes"])
    if ownership:
        owner_or_admin(db, actor, row)
    return row


def _draft(db, actor, body, request_id, previous=None):
    action = body.action
    # All due-date material is normalized to UTC before canonical digest construction.
    if hasattr(action, "due_at"):
        action = action.model_copy(update={"due_at": action.due_at.astimezone(UTC)})
    subject_id, scopes, conditions = actions.prepare(db, action, body.department_id)
    require(db, actor, "propose", scopes)
    require_evidence = body.source_type != "HUMAN" or isinstance(action, c.CreateEscalation)
    binding = evidence.validate(
        db,
        body.evidence_id,
        subject_id,
        body.department_id,
        body.fact_ids,
        required=require_evidence,
    )
    governance = policy.snapshot(db, actor, action, scopes)
    expiry = body.expires_at or now() + timedelta(hours=2)
    expiry = expiry.astimezone(UTC)
    if not now() < expiry <= now() + timedelta(hours=governance["max_validity_hours"]):
        raise WorkflowError(
            "invalid_proposal_expiry", "Proposal expiry is outside current governance bounds.", 422
        )
    if binding and expiry > actions.one(db, s.evidence, body.evidence_id)["expires_at"]:
        raise WorkflowError(
            "evidence_validity", "Proposal must expire before its supporting evidence.", 422
        )
    version = previous["version"] + 1 if previous else 1
    material = {
        "action": action.model_dump(mode="json"),
        "source_type": body.source_type,
        "department_id": body.department_id,
        "proposer_id": str(actor.id),
        "revision": version,
        "subject": actions.subject_ref(db, subject_id).model_dump(mode="json"),
        "reason": body.reason,
        "business_context": body.business_context,
        "evidence": binding,
        "policy": governance,
        "preconditions": conditions,
        "expires_at": expiry.isoformat(),
    }
    row = dict(
        db.execute(
            insert(s.proposals)
            .values(
                proposer_id=actor.id,
                department_id=body.department_id,
                subject_id=subject_id,
                evidence_id=body.evidence_id,
                previous_id=previous["id"] if previous else None,
                version=version,
                action_type=action.type,
                source_type=body.source_type,
                material=material,
                digest=digest(material),
                status="DRAFT",
                expires_at=expiry,
            )
            .returning(s.proposals)
        )
        .mappings()
        .one()
    )
    event(
        db,
        actor,
        "proposal.revised" if previous else "proposal.created",
        request_id=request_id,
        department_id=body.department_id,
        object_type="proposal",
        object_id=row["id"],
        proposal_id=row["id"],
        reason=body.reason,
        after={
            "version": version,
            "digest": row["digest"],
            "action": action.type,
            "previous_id": previous["id"] if previous else None,
        },
    )
    return proposal_view(db, row)


def create(actor, body, key, request_id, bind=None):
    def guard(db):
        require(db, actor, "propose", [body.department_id])
        return {"department_id": body.department_id}

    return run(
        actor,
        "review",
        "proposal.create",
        body.model_dump(mode="json"),
        key,
        request_id,
        guard,
        lambda db, _: _draft(db, actor, body, request_id),
        bind,
    )


def submit(actor, identifier, body, key, request_id, bind=None):
    def handler(db, row):
        principal_locks(db, [actor.id, row["proposer_id"]])
        require(db, actor, "submit", row["material"]["policy"]["scopes"])
        policy.reviewed(row, body)
        policy.integrity(db, row)
        if row["status"] != "DRAFT":
            raise WorkflowError("invalid_proposal_transition", "Only a draft can be submitted.")
        material = row["material"]
        evidence.validate(
            db,
            row["evidence_id"],
            row["subject_id"],
            row["department_id"],
            (material.get("evidence") or {}).get("fact_ids", []),
            required=row["source_type"] != "HUMAN"
            or row["action_type"] == "CREATE_INTERNAL_ESCALATION",
        )
        db.execute(
            update(s.proposals)
            .where(s.proposals.c.id == identifier)
            .values(status="PENDING_REVIEW", updated_at=now())
        )
        event(
            db,
            actor,
            "proposal.submitted",
            request_id=request_id,
            department_id=row["department_id"],
            object_type="proposal",
            object_id=identifier,
            proposal_id=identifier,
            after={"status": "PENDING_REVIEW", "digest": row["digest"]},
            reason=body.reason,
        )
        return proposal_view(db, actions.one(db, s.proposals, identifier))

    return run(
        actor,
        "review",
        "proposal.submit:" + str(identifier),
        body.model_dump(mode="json"),
        key,
        request_id,
        lambda db: _guard(db, actor, identifier, "submit", ownership=True),
        handler,
        bind,
    )


def review(actor, identifier, body, key, request_id, decision, bind=None):
    if decision not in {"APPROVE", "REJECT", "REVOKE"}:
        raise ValueError("Unknown internal decision")

    def guard(db):
        row = _guard(db, actor, identifier, "review")
        if row["proposer_id"] == actor.id:
            raise WorkflowError(
                "self_approval_forbidden", "A distinct authenticated reviewer is required.", 403
            )
        return row

    def handler(db, row):
        principal_locks(db, [actor.id, row["proposer_id"]])
        require(db, actor, "review", row["material"]["policy"]["scopes"])
        policy.reviewed(row, body)
        policy.integrity(db, row)
        expected = "APPROVED" if decision == "REVOKE" else "PENDING_REVIEW"
        if row["status"] != expected:
            raise WorkflowError("invalid_review_state", "Proposal is not awaiting this decision.")
        if decision == "REVOKE":
            prior = (
                db.execute(
                    select(s.approvals.c.actor_id).where(
                        s.approvals.c.proposal_id == identifier, s.approvals.c.decision == "APPROVE"
                    )
                )
                .scalars()
                .all()
            )
            if actor.id not in prior:
                require(db, actor, "admin", row["material"]["policy"]["scopes"])
        valid_until = min(
            row["expires_at"],
            now() + timedelta(minutes=row["material"]["policy"]["approval_validity_minutes"]),
        )
        db.execute(
            insert(s.approvals).values(
                proposal_id=identifier,
                actor_id=actor.id,
                proposal_version=row["version"],
                digest=row["digest"],
                decision=decision,
                authz_version=actor.authz_version,
                reason=body.reason,
                valid_until=valid_until,
            )
        )
        new_status = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "REVOKE": "CANCELLED"}[decision]
        db.execute(
            update(s.proposals)
            .where(s.proposals.c.id == identifier)
            .values(status=new_status, updated_at=now())
        )
        event(
            db,
            actor,
            {
                "APPROVE": "proposal.approved",
                "REJECT": "proposal.rejected",
                "REVOKE": "approval.revoked",
            }[decision],
            request_id=request_id,
            department_id=row["department_id"],
            object_type="proposal",
            object_id=identifier,
            proposal_id=identifier,
            after={"digest": row["digest"], "status": new_status, "version": row["version"]},
            reason=body.reason,
        )
        return proposal_view(db, actions.one(db, s.proposals, identifier))

    return run(
        actor,
        "review",
        "proposal." + decision.lower() + ":" + str(identifier),
        body.model_dump(mode="json"),
        key,
        request_id,
        guard,
        handler,
        bind,
    )


def cancel(actor, identifier, body, key, request_id, bind=None):
    def handler(db, row):
        policy.reviewed(row, body)
        if row["status"] not in {"DRAFT", "PENDING_REVIEW", "APPROVED"}:
            raise WorkflowError("invalid_proposal_transition", "This proposal cannot be cancelled.")
        db.execute(
            update(s.proposals)
            .where(s.proposals.c.id == identifier)
            .values(status="CANCELLED", updated_at=now())
        )
        event(
            db,
            actor,
            "proposal.cancelled",
            request_id=request_id,
            department_id=row["department_id"],
            object_type="proposal",
            object_id=identifier,
            proposal_id=identifier,
            reason=body.reason,
            after={"status": "CANCELLED"},
        )
        return proposal_view(db, actions.one(db, s.proposals, identifier))

    return run(
        actor,
        "review",
        "proposal.cancel:" + str(identifier),
        body.model_dump(mode="json"),
        key,
        request_id,
        lambda db: _guard(db, actor, identifier, "propose", ownership=True),
        handler,
        bind,
    )


def revise(actor, identifier, body, key, request_id, bind=None):
    def handler(db, row):
        policy.reviewed(row, body)
        if row["status"] in {"COMPLETED", "EXECUTING"}:
            raise WorkflowError(
                "invalid_revision", "Completed/executing actions cannot be replaced."
            )
        require(db, actor, "propose", [body.proposal.department_id])
        if row["status"] in {"DRAFT", "PENDING_REVIEW", "APPROVED"}:
            db.execute(
                update(s.proposals)
                .where(s.proposals.c.id == identifier)
                .values(status="CANCELLED", updated_at=now())
            )
            event(
                db,
                actor,
                "proposal.superseded",
                request_id=request_id,
                proposal_id=identifier,
                object_type="proposal",
                object_id=identifier,
                department_id=row["department_id"],
                after={"status": "CANCELLED"},
            )
        return _draft(db, actor, body.proposal, request_id, row)

    return run(
        actor,
        "review",
        "proposal.revise:" + str(identifier),
        body.model_dump(mode="json"),
        key,
        request_id,
        lambda db: _guard(db, actor, identifier, "propose", ownership=True),
        handler,
        bind,
    )


def execute(actor, identifier, body, key, request_id, bind=None):
    def handler(db, row):
        reviewers = (
            db.execute(
                select(s.approvals.c.actor_id).where(s.approvals.c.proposal_id == identifier)
            )
            .scalars()
            .all()
        )
        principal_locks(db, [actor.id, row["proposer_id"], *reviewers])
        require(db, actor, "execute", row["material"]["policy"]["scopes"])
        policy.reviewed(row, body)
        if row["status"] == "COMPLETED":
            return dict(
                db.execute(select(s.executions).where(s.executions.c.proposal_id == identifier))
                .mappings()
                .one()
            )
        policy.integrity(db, row)
        if row["status"] != "APPROVED":
            raise WorkflowError("approval_required", "Only an approved proposal can execute.")
        approved = policy.executable_approval(db, row)
        execution_id = uuid.uuid4()
        db.execute(
            update(s.proposals)
            .where(s.proposals.c.id == identifier)
            .values(status="EXECUTING", updated_at=now())
        )
        db.execute(
            insert(s.executions).values(
                id=execution_id,
                proposal_id=identifier,
                actor_id=actor.id,
                approver_id=approved["actor_id"],
                status="EXECUTING",
                result={},
            )
        )
        started = event(
            db,
            actor,
            "execution.started",
            request_id=request_id,
            department_id=row["department_id"],
            object_type="execution",
            object_id=execution_id,
            proposal_id=identifier,
            execution_id=execution_id,
            after={"action": row["action_type"], "digest": row["digest"]},
        )
        try:
            with db.begin_nested():
                action = actions.REGISTRY[row["action_type"]].model.model_validate(
                    row["material"]["action"]
                )
                _, scopes, conditions = actions.prepare(
                    db, action, row["department_id"], execute=True
                )
                if (
                    conditions != row["material"]["preconditions"]
                    or scopes != row["material"]["policy"]["scopes"]
                ):
                    raise WorkflowError(
                        "stale_target",
                        "Target or linked business state changed; create a new revision.",
                    )
                evidence.validate(
                    db,
                    row["evidence_id"],
                    row["subject_id"],
                    row["department_id"],
                    (row["material"].get("evidence") or {}).get("fact_ids", []),
                    required=row["source_type"] != "HUMAN"
                    or row["action_type"] == "CREATE_INTERNAL_ESCALATION",
                )
                db.execute(
                    text("SELECT set_config('opspilot.execution_id',:identifier,true)"),
                    {"identifier": str(execution_id)},
                )
                name, kind, object_id, before, after, objects = actions.apply(
                    db, action, row, actor, execution_id
                )
                action_event = event(
                    db,
                    actor,
                    name,
                    request_id=request_id,
                    department_id=row["department_id"],
                    object_type=kind,
                    object_id=object_id,
                    proposal_id=identifier,
                    execution_id=execution_id,
                    before=before,
                    after=after,
                    reason=row["material"]["reason"],
                )
                completed = event(
                    db,
                    actor,
                    "execution.completed",
                    request_id=request_id,
                    department_id=row["department_id"],
                    object_type="execution",
                    object_id=execution_id,
                    proposal_id=identifier,
                    execution_id=execution_id,
                    after={"object_type": kind, "object_id": object_id},
                )
                receipt = json.loads(
                    canonical(
                        {
                            "action": row["action_type"],
                            "subject": row["material"]["subject"],
                            "objects": objects,
                            "before": before,
                            "after": after,
                            "approved_by": approved["actor_id"],
                            "proposal_digest": row["digest"],
                            "audit_events": [started, action_event, completed],
                            "idempotency_key": key,
                            "limitations": [
                                "Internal workflow state only; no external side effects."
                            ],
                        }
                    )
                )
                db.execute(
                    update(s.executions)
                    .where(s.executions.c.id == execution_id)
                    .values(status="COMPLETED", result=receipt, finished_at=now())
                )
                db.execute(
                    update(s.proposals)
                    .where(s.proposals.c.id == identifier)
                    .values(status="COMPLETED", updated_at=now())
                )
        except (WorkflowError, SQLAlchemyError) as exc:
            # A real SAVEPOINT rollback removes all business mutations and their success events.
            code = exc.code if isinstance(exc, WorkflowError) else "execution_database_failure"
            failed = event(
                db,
                actor,
                "execution.failed",
                request_id=request_id,
                department_id=row["department_id"],
                object_type="execution",
                object_id=execution_id,
                proposal_id=identifier,
                execution_id=execution_id,
                result="FAILED",
                after={"code": code},
            )
            db.execute(
                update(s.executions)
                .where(s.executions.c.id == execution_id)
                .values(
                    status="FAILED",
                    error_code=code,
                    finished_at=now(),
                    result={
                        "action": row["action_type"],
                        "objects": {},
                        "audit_events": [str(started), str(failed)],
                        "idempotency_key": str(key),
                        "rolled_back": True,
                    },
                )
            )
            db.execute(
                update(s.proposals)
                .where(s.proposals.c.id == identifier)
                .values(status="FAILED", updated_at=now())
            )
            return Result(
                error=WorkflowError(
                    code,
                    "Execution failed safely; no business mutation committed.",
                    details={"execution_id": str(execution_id)},
                ),
                status=409,
            )
        return dict(actions.one(db, s.executions, execution_id))

    return run(
        actor,
        "execute",
        "proposal.execute:" + str(identifier),
        body.model_dump(mode="json"),
        key,
        request_id,
        lambda db: _guard(db, actor, identifier, "execute", ownership=True),
        handler,
        bind,
    )


def deny_edit(actor, identifier, key, request_id, bind=None):
    def handler(db, row):
        raise WorkflowError(
            "proposal_immutable", "Create a new proposal revision; material is immutable."
        )

    return run(
        actor,
        "review",
        "proposal.edit:" + str(identifier),
        {},
        key,
        request_id,
        lambda db: _guard(db, actor, identifier, "propose", ownership=True),
        handler,
        bind,
    )
