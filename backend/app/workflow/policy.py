from sqlalchemy import select

from app.workflow import schema as s
from app.workflow.actions import REGISTRY
from app.workflow.common import WorkflowError, digest, now
from app.workflow.permissions import allowed, member


def current(db):
    return dict(
        db.execute(
            select(s.policies)
            .join(s.policy_control, s.policy_control.c.policy_id == s.policies.c.id)
            .where(s.policy_control.c.id == 1)
        )
        .mappings()
        .one()
    )


def snapshot(db, actor, action, scopes):
    active = current(db)
    spec = REGISTRY[action.type]
    return {
        "origin": "Stage 5 local-demo application governance, not corporate contract law",
        "version": active["id"],
        "risk": spec.risk,
        "scopes": scopes,
        "required_approvals": spec.approval_count,
        "separation_of_duties": True,
        "reviewer_roles": ["WORKFLOW_APPROVER", "WORKFLOW_ADMIN"],
        "proposer_authz_version": actor.authz_version,
        "max_validity_hours": active["max_validity_hours"],
        "approval_validity_minutes": active["approval_validity_minutes"],
    }


def integrity(db, proposal, *, require_validity=True):
    material = proposal["material"]
    if digest(material) != proposal["digest"]:
        raise WorkflowError("proposal_modified", "Proposal integrity check failed.")
    if current(db)["id"] != material["policy"]["version"]:
        raise WorkflowError("policy_changed", "Governance policy changed; create a new revision.")
    proposer = member(db, proposal["proposer_id"])
    if (
        not proposer
        or not proposer["active"]
        or not proposer["is_human"]
        or proposer["authz_version"] != material["policy"]["proposer_authz_version"]
        or not allowed(db, proposer["id"], "propose", material["policy"]["scopes"])
    ):
        raise WorkflowError(
            "proposer_permission_changed", "Proposer permissions changed; revise the proposal."
        )
    if require_validity and proposal["expires_at"] <= now():
        raise WorkflowError(
            "proposal_expired", "Proposal expired; create a fresh reviewed revision."
        )


def reviewed(proposal, body):
    if body.proposal_version != proposal["version"] or body.digest != proposal["digest"]:
        raise WorkflowError(
            "reviewed_payload_mismatch", "Review the exact current proposal version and digest."
        )


def executable_approval(db, proposal):
    candidates = (
        db.execute(
            select(s.approvals).where(
                s.approvals.c.proposal_id == proposal["id"], s.approvals.c.decision == "APPROVE"
            )
        )
        .mappings()
        .all()
    )
    for candidate in candidates:
        principal = member(db, candidate["actor_id"])
        if (
            candidate["actor_id"] != proposal["proposer_id"]
            and principal
            and principal["active"]
            and principal["is_human"]
            and principal["authz_version"] == candidate["authz_version"]
            and candidate["digest"] == proposal["digest"]
            and candidate["proposal_version"] == proposal["version"]
            and candidate["valid_until"] > now()
            and allowed(
                db, candidate["actor_id"], "review", proposal["material"]["policy"]["scopes"]
            )
        ):
            return dict(candidate)
    raise WorkflowError(
        "approval_invalid", "A current, distinct, authorized human approval is required."
    )
