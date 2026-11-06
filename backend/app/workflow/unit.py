"""Shared database idempotency and durable denial auditing, not process-local write locks."""

import json
import logging
import time

from sqlalchemy import insert, select, update
from sqlalchemy.exc import SQLAlchemyError

from app.workflow import schema as s
from app.workflow.audit import event
from app.workflow.common import Result, WorkflowError, canonical, digest, lock, now, transaction
from app.workflow.permissions import session_valid


def run(actor, role, operation, request_body, key, request_id, guard, handler, bind=None):
    started = time.perf_counter()
    result = _run(actor, role, operation, request_body, key, request_id, guard, handler, bind)
    result.transaction_ms = round((time.perf_counter() - started) * 1000, 3)
    return result


def _run(actor, role, operation, request_body, key, request_id, guard, handler, bind):
    result = Result()
    request_digest = digest(request_body)
    with transaction(role, bind) as db:
        lock(db, "workflow-policy", 1, shared=True)
        lock(db, "workflow-idempotency", key)
        context = None
        try:
            session_valid(db, actor)
            context = guard(db)
            previous = (
                db.execute(select(s.idempotency).where(s.idempotency.c.key == key))
                .mappings()
                .first()
            )
            if previous:
                if (
                    previous["actor_id"] != actor.id
                    or previous["operation"] != operation
                    or previous["request_digest"] != request_digest
                ):
                    raise WorkflowError(
                        "idempotency_conflict",
                        "This key is already bound to another request or actor.",
                    )
                stored = previous["response"]
                if stored.get("error"):
                    error = stored["error"]
                    result.error = WorkflowError(
                        error["code"],
                        error["message"],
                        previous["http_status"],
                        details=error.get("details"),
                    )
                else:
                    result.data = stored["data"]
                result.status = previous["http_status"]
                event(
                    db,
                    actor,
                    "request.replayed",
                    request_id=request_id,
                    department_id=context.get("department_id") if context else None,
                    after={"operation": operation, "idempotency_key": str(key)},
                )
                return result
            try:
                with db.begin_nested():
                    value = handler(db, context)
                    result = value if isinstance(value, Result) else Result(data=value)
            except WorkflowError as exc:
                result.error, result.status = exc, exc.status
            except SQLAlchemyError:
                result.error = WorkflowError(
                    "database_conflict", "The operation could not be committed safely."
                )
                result.status = 409
            if result.error:
                if result.error.code == "proposal_expired" and context and context.get("id"):
                    db.execute(
                        update(s.proposals)
                        .where(
                            s.proposals.c.id == context["id"],
                            s.proposals.c.status.in_(["DRAFT", "PENDING_REVIEW", "APPROVED"]),
                            s.proposals.c.expires_at <= now(),
                        )
                        .values(status="EXPIRED", updated_at=now())
                    )
                    event(
                        db,
                        actor,
                        "proposal.expired",
                        request_id=request_id,
                        proposal_id=context["id"],
                        object_type="proposal",
                        object_id=context["id"],
                        department_id=context["department_id"],
                    )
                event(
                    db,
                    actor,
                    operation + ".denied",
                    request_id=request_id,
                    after={"code": result.error.code},
                    result="DENIED",
                    department_id=context.get("department_id") if context else None,
                    proposal_id=context.get("id") if context else None,
                )
            if result.data is not None:
                result.data = json.loads(canonical(result.data))
            payload = (
                {
                    "error": {
                        "code": result.error.code,
                        "message": str(result.error),
                        "details": result.error.details,
                    }
                }
                if result.error
                else {"data": result.data}
            )
            db.execute(
                insert(s.idempotency).values(
                    key=key,
                    actor_id=actor.id,
                    operation=operation,
                    request_digest=request_digest,
                    response=json.loads(canonical(payload)),
                    http_status=result.status,
                )
            )
        except WorkflowError as exc:
            # Guard failures cannot expose cached responses or cause a business mutation.
            result = Result(error=exc, status=exc.status)
            event(
                db,
                actor,
                operation + ".denied",
                request_id=request_id,
                after={"code": exc.code},
                result="DENIED",
            )
        except SQLAlchemyError as exc:
            logging.getLogger("opspilot.workflow").warning(
                "Workflow transaction failed: %s", type(exc).__name__
            )
            raise
    return result
