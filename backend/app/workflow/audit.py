import uuid

from sqlalchemy import insert

from app.workflow import schema as s
from app.workflow.common import canonical


def event(
    db,
    actor,
    action,
    *,
    request_id,
    department_id=None,
    object_type="workflow",
    object_id=None,
    proposal_id=None,
    execution_id=None,
    before=None,
    after=None,
    reason=None,
    result="SUCCESS",
):
    """No credentials, token digests or authentication request bodies enter the audit."""
    identifier = uuid.uuid4()
    # Canonical JSON conversion keeps UUID/datetime values portable without losing identity.
    import json

    db.execute(
        insert(s.audit).values(
            id=identifier,
            actor_id=actor.id if actor else None,
            department_id=department_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            proposal_id=proposal_id,
            execution_id=execution_id,
            before_state=json.loads(canonical(before or {})),
            after_state=json.loads(canonical(after or {})),
            reason=reason,
            result=result,
            request_id=request_id,
        )
    )
    return identifier
