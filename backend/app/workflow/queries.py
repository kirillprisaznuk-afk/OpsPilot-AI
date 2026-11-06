from sqlalchemy import String, cast, func, or_, select

from app.workflow import schema as s
from app.workflow.actions import one
from app.workflow.common import WorkflowError, now, transaction
from app.workflow.permissions import require, visible
from app.workflow.service import proposal_view


def _page(db, query, count_query, limit, offset, decorate=lambda row: dict(row)):
    rows = db.execute(query.limit(limit).offset(offset)).mappings().all()
    return {
        "items": [decorate(row) for row in rows],
        "total": db.scalar(count_query),
        "limit": limit,
        "offset": offset,
    }


def proposal(actor, identifier, bind=None):
    with transaction("read", bind) as db:
        row = one(db, s.proposals, identifier)
        require(db, actor, "read", [row["department_id"]])
        return proposal_view(db, row)


def proposals(actor, limit, offset, status=None, department_id=None, source_type=None, bind=None):
    with transaction("read", bind) as db:
        predicate = [visible(db, actor, s.proposals.c.department_id)]
        for name, value in (
            ("status", status),
            ("department_id", department_id),
            ("source_type", source_type),
        ):
            if value is not None:
                predicate.append(s.proposals.c[name] == value)
        return _page(
            db,
            select(s.proposals)
            .where(*predicate)
            .order_by(s.proposals.c.created_at.desc(), s.proposals.c.id),
            select(func.count()).select_from(s.proposals).where(*predicate),
            limit,
            offset,
            lambda row: proposal_view(db, row),
        )


def operational(
    actor,
    kind,
    *,
    identifier=None,
    limit=25,
    offset=0,
    status=None,
    department_id=None,
    supplier_id=None,
    employee_id=None,
    overdue=False,
    priority=None,
    search=None,
    bind=None,
):
    table = {"task": s.tasks, "escalation": s.escalations}[kind]
    with transaction("read", bind) as db:
        predicate = [visible(db, actor, table.c.department_id)]
        if identifier is not None:
            row = one(db, table, identifier)
            require(db, actor, "read", [row["department_id"]])
            predicate.append(table.c.id == identifier)
        for name, value in (("status", status), ("department_id", department_id)):
            if value is not None:
                predicate.append(table.c[name] == value)
        if priority is not None:
            predicate.append(table.c.priority == priority)
        if search:
            term = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            predicate.append(table.c.title.ilike("%" + term + "%", escape="\\"))
        if employee_id is not None:
            if kind != "task":
                raise WorkflowError(
                    "unsupported_filter", "Employee filter applies to tasks only.", 422
                )
            predicate.append(table.c.employee_id == employee_id)
        if supplier_id is not None:
            predicate.extend(
                [s.subjects.c.kind == "supplier", s.subjects.c.entity_id == supplier_id]
            )
        if overdue:
            predicate.extend(
                [
                    table.c.due_at < now(),
                    table.c.status.not_in(
                        ["completed", "cancelled"] if kind == "task" else ["closed"]
                    ),
                ]
            )
        joined = table.join(s.subjects, s.subjects.c.id == table.c.subject_id).join(
            s.proposals, s.proposals.c.id == table.c.proposal_id
        )
        query = (
            select(
                table,
                s.subjects.c.kind.label("subject_kind"),
                s.subjects.c.entity_id.label("business_entity_id"),
                s.proposals.c.source_type,
                s.proposals.c.evidence_id,
            )
            .select_from(joined)
            .where(*predicate)
        )

        def decorate(row):
            data = dict(row)
            data["subject"] = {
                "kind": data.pop("subject_kind"),
                "entity_id": data.pop("business_entity_id"),
            }
            return data

        if identifier is not None:
            return decorate(db.execute(query).mappings().one())
        return _page(
            db,
            query.order_by(table.c.created_at.desc(), table.c.id),
            select(func.count()).select_from(joined).where(*predicate),
            limit,
            offset,
            decorate,
        )


def task_history(actor, identifier, kind, limit, offset, bind=None):
    table = {"notes": s.notes, "assignments": s.task_assignments}[kind]
    with transaction("read", bind) as db:
        task = one(db, s.tasks, identifier)
        require(db, actor, "read", [task["department_id"]])
        condition = table.c.task_id == identifier
        return _page(
            db,
            select(table).where(condition).order_by(table.c.created_at, table.c.id),
            select(func.count()).select_from(table).where(condition),
            limit,
            offset,
        )


def execution(actor, identifier, bind=None):
    with transaction("read", bind) as db:
        row = one(db, s.executions, identifier)
        parent = one(db, s.proposals, row["proposal_id"])
        require(db, actor, "read", [parent["department_id"]])
        return row


def captured_evidence(actor, identifier, bind=None):
    with transaction("read", bind) as db:
        row = one(db, s.evidence, identifier)
        require(db, actor, "read", [row["department_id"]])
        return row


def audit(
    actor,
    limit,
    offset,
    proposal_id=None,
    actor_id=None,
    bind=None,
    *,
    object_id=None,
    action=None,
    search=None,
    newest=False,
):
    with transaction("read", bind) as db:
        predicate = [
            or_(visible(db, actor, s.audit.c.department_id), s.audit.c.actor_id == actor.id)
        ]
        if proposal_id:
            parent = one(db, s.proposals, proposal_id)
            require(db, actor, "read", [parent["department_id"]])
            predicate.append(s.audit.c.proposal_id == proposal_id)
        if actor_id:
            if actor_id != actor.id:
                require(db, actor, "admin", [None])
            predicate.append(s.audit.c.actor_id == actor_id)
        if object_id:
            predicate.append(s.audit.c.object_id == object_id)
        if action:
            predicate.append(s.audit.c.action == action)
        if search:
            term = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            actors = select(s.principals.c.id).where(
                s.principals.c.username.ilike(term, escape="\\")
            )
            predicate.append(
                or_(
                    s.audit.c.action.ilike(term, escape="\\"),
                    s.audit.c.reason.ilike(term, escape="\\"),
                    cast(s.audit.c.object_id, String).ilike(term, escape="\\"),
                    s.audit.c.actor_id.in_(actors),
                )
            )
        return _page(
            db,
            select(s.audit)
            .where(*predicate)
            .order_by(s.audit.c.sequence.desc() if newest else s.audit.c.sequence),
            select(func.count()).select_from(s.audit).where(*predicate),
            limit,
            offset,
        )


def summary(actor, bind=None):
    with transaction("read", bind) as db:
        moment = now()

        def count(table, *conditions):
            return db.scalar(
                select(func.count())
                .select_from(table)
                .where(visible(db, actor, table.c.department_id), *conditions)
            )

        completed = (
            select(func.count())
            .select_from(
                s.executions.join(s.proposals, s.proposals.c.id == s.executions.c.proposal_id)
            )
            .where(
                visible(db, actor, s.proposals.c.department_id),
                s.executions.c.status == "COMPLETED",
                s.executions.c.finished_at
                >= moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
            )
        )
        active = s.tasks.c.status.in_(["open", "active", "blocked"])
        return {
            "source": "stage5_workflow_state",
            "as_of": moment,
            "open_tasks": count(s.tasks, active),
            "overdue_tasks": count(s.tasks, active, s.tasks.c.due_at < moment),
            "open_escalations": count(s.escalations, s.escalations.c.status == "open"),
            "pending_proposals": count(
                s.proposals,
                s.proposals.c.status == "PENDING_REVIEW",
                s.proposals.c.expires_at > moment,
            ),
            "rejected_proposals": count(s.proposals, s.proposals.c.status == "REJECTED"),
            "completed_actions_this_month": db.scalar(completed),
            "limitations": [
                "These operational records exclude the immutable seeded tasks and Stage 2 KPIs.",
                "Counts are scoped to the authenticated principal's current permissions.",
            ],
        }
