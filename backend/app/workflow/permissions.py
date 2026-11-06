from sqlalchemy import and_, select

from app.workflow import schema as s
from app.workflow.common import WorkflowError, now

ROLES = {
    "VIEWER": "Read permitted operational workflow records.",
    "OPERATIONS_ANALYST": "Capture evidence and prepare proposals; cannot approve or execute.",
    "WORKFLOW_OPERATOR": "Prepare, submit and execute approved proposals within scope.",
    "WORKFLOW_APPROVER": "Review another human's proposals within scope.",
    "WORKFLOW_ADMIN": "Manage local identities/policy; separation of duties still applies.",
}
PERMISSIONS = {
    "read": set(ROLES),
    "propose": {"OPERATIONS_ANALYST", "WORKFLOW_OPERATOR", "WORKFLOW_ADMIN"},
    "submit": {"WORKFLOW_OPERATOR", "WORKFLOW_ADMIN"},
    "execute": {"WORKFLOW_OPERATOR", "WORKFLOW_ADMIN"},
    "review": {"WORKFLOW_APPROVER", "WORKFLOW_ADMIN"},
    "admin": {"WORKFLOW_ADMIN"},
}
PUBLIC_PRINCIPAL = [
    s.principals.c.id,
    s.principals.c.username,
    s.principals.c.active,
    s.principals.c.is_human,
    s.principals.c.authz_version,
    s.principals.c.employee_id,
    s.principals.c.created_at,
]


def member(db, identifier):
    return (
        db.execute(select(*PUBLIC_PRINCIPAL).where(s.principals.c.id == identifier))
        .mappings()
        .first()
    )


def memberships(db, identifier):
    return (
        db.execute(
            select(s.assignments.c.role_code, s.assignments.c.department_id).where(
                s.assignments.c.principal_id == identifier, s.assignments.c.active
            )
        )
        .mappings()
        .all()
    )


def session_valid(db, actor):
    principal = member(db, actor.id)
    session = db.execute(
        select(s.sessions.c.id).where(
            s.sessions.c.id == actor.session_id,
            s.sessions.c.principal_id == actor.id,
            s.sessions.c.authz_version == actor.authz_version,
            s.sessions.c.expires_at > now(),
            s.sessions.c.revoked_at.is_(None),
        )
    ).first()
    if (
        not principal
        or not session
        or not principal["active"]
        or not principal["is_human"]
        or principal["authz_version"] != actor.authz_version
    ):
        raise WorkflowError("authentication_required", "Session is expired or revoked.", 401)
    return principal


def allowed(db, principal_id, permission, scopes):
    entries = memberships(db, principal_id)
    return all(
        any(
            r["role_code"] in PERMISSIONS[permission]
            and (r["department_id"] is None or r["department_id"] == scope)
            for r in entries
        )
        for scope in scopes
    )


def require(db, actor, permission, scopes):
    session_valid(db, actor)
    if not allowed(db, actor.id, permission, scopes):
        raise WorkflowError(
            "permission_denied", "This action is outside your permitted scope.", 403
        )


def visible(db, actor, column):
    session_valid(db, actor)
    entries = memberships(db, actor.id)
    if any(e["department_id"] is None for e in entries):
        return True
    departments = {e["department_id"] for e in entries}
    return and_(column.is_not(None), column.in_(departments))


def owner_or_admin(db, actor, proposal):
    if proposal["proposer_id"] != actor.id and not allowed(
        db, actor.id, "admin", proposal["material"]["policy"]["scopes"]
    ):
        raise WorkflowError(
            "proposal_ownership", "Only its proposer or scoped administrator may do this.", 403
        )
