"""Eight explicit internal actions. This module never mutates historical business tables."""

import uuid
from dataclasses import dataclass
from datetime import UTC, timedelta

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models import Base
from app.workflow import contracts as c
from app.workflow import schema as s
from app.workflow.common import WorkflowError, digest, now


@dataclass(frozen=True)
class ActionSpec:
    model: type
    target: str
    risk: str
    permission: str = "execute"
    approval_count: int = 1
    distinct_reviewer: bool = True


REGISTRY = {
    "CREATE_WORKFLOW_TASK": ActionSpec(c.CreateTask, "new_workflow_task", "moderate_internal"),
    "ASSIGN_WORKFLOW_TASK": ActionSpec(c.AssignTask, "workflow_task", "moderate_internal"),
    "UPDATE_WORKFLOW_TASK_STATUS": ActionSpec(c.SetStatus, "workflow_task", "moderate_internal"),
    "UPDATE_WORKFLOW_TASK_PRIORITY": ActionSpec(
        c.SetPriority, "workflow_task", "moderate_internal"
    ),
    "UPDATE_WORKFLOW_TASK_DUE_DATE": ActionSpec(c.SetDue, "workflow_task", "moderate_internal"),
    "ADD_WORKFLOW_TASK_NOTE": ActionSpec(c.AddNote, "workflow_task", "low_internal"),
    "CREATE_INTERNAL_ESCALATION": ActionSpec(
        c.CreateEscalation, "new_escalation", "moderate_internal"
    ),
    "CLOSE_INTERNAL_ESCALATION": ActionSpec(c.CloseEscalation, "escalation", "moderate_internal"),
}
TRANSITIONS = {
    "open": {"active", "cancelled"},
    "active": {"blocked", "completed", "cancelled"},
    "blocked": {"active", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


def one(db, table, identifier, *, locked=False):
    query = select(table).where(table.c.id == identifier)
    if locked:
        query = query.with_for_update()
    row = db.execute(query).mappings().first()
    if not row:
        raise WorkflowError("object_not_found", "The referenced object does not exist.", 404)
    return dict(row)


def department(db, identifier):
    one(db, Base.metadata.tables["departments"], identifier)


def employee_assignment(db, identifier, department_id):
    department(db, department_id)
    if identifier is not None:
        row = one(db, Base.metadata.tables["employees"], identifier)
        if row["department_id"] != department_id:
            raise WorkflowError(
                "invalid_assignment", "Employee must belong to the owning department.", 422
            )


def business_state(db, subject):
    table = Base.metadata.tables[s.SUBJECT_TABLES[subject.kind]]
    return digest(one(db, table, subject.entity_id))


def subject_row(db, subject):
    business_state(db, subject)
    return (
        db.execute(
            pg_insert(s.subjects)
            .values(kind=subject.kind, **{subject.kind + "_id": subject.entity_id})
            .on_conflict_do_nothing()
            .returning(s.subjects.c.id)
        ).scalar_one_or_none()
        or db.execute(
            select(s.subjects.c.id).where(
                s.subjects.c.kind == subject.kind, s.subjects.c.entity_id == subject.entity_id
            )
        ).scalar_one()
    )


def subject_ref(db, identifier):
    row = one(db, s.subjects, identifier)
    return c.Subject(kind=row["kind"], entity_id=row["entity_id"])


def due_date(value):
    value = value.astimezone(UTC)
    if not now() < value <= now() + timedelta(days=366):
        raise WorkflowError("invalid_due_date", "Due date must be future UTC within one year.", 422)
    return value


def prepare(db, action, department_id, *, execute=False):
    """Validate references and capture target preconditions; never calculate business KPIs."""
    department(db, department_id)
    scopes = {department_id}
    preconditions = {}
    if isinstance(action, c.TaskTarget):
        row = one(db, s.tasks, action.task_id, locked=execute)
        if row["department_id"] != department_id:
            raise WorkflowError(
                "target_scope_mismatch", "Task does not belong to that department.", 403
            )
        if row["version"] != action.expected_version:
            raise WorkflowError("stale_target", "Task changed; create a new reviewed proposal.")
        if row["status"] in {"completed", "cancelled"} and not isinstance(action, c.AddNote):
            raise WorkflowError("terminal_task", "Completed or cancelled tasks cannot be modified.")
        if isinstance(action, c.SetStatus) and action.status not in TRANSITIONS[row["status"]]:
            raise WorkflowError("invalid_task_transition", "This task transition is not permitted.")
        if isinstance(action, c.AssignTask):
            new_department = action.department_id or department_id
            employee_assignment(db, action.employee_id, new_department)
            scopes.add(new_department)
        subject = subject_ref(db, row["subject_id"])
        subject_id = row["subject_id"]
        preconditions.update(target_id=str(row["id"]), target_version=row["version"])
    elif isinstance(action, c.CloseEscalation):
        row = one(db, s.escalations, action.escalation_id, locked=execute)
        if row["department_id"] != department_id:
            raise WorkflowError(
                "target_scope_mismatch", "Escalation is outside that department.", 403
            )
        if row["version"] != action.expected_version:
            raise WorkflowError("stale_target", "Escalation changed; create a new proposal.")
        if row["status"] != "open":
            raise WorkflowError("terminal_escalation", "Escalation is already closed.")
        subject = subject_ref(db, row["subject_id"])
        subject_id = row["subject_id"]
        preconditions.update(target_id=str(row["id"]), target_version=row["version"])
    else:
        subject = action.subject
        if execute:
            subject_id = db.execute(
                select(s.subjects.c.id).where(
                    s.subjects.c.kind == subject.kind, s.subjects.c.entity_id == subject.entity_id
                )
            ).scalar_one()
        else:
            subject_id = subject_row(db, subject)
        if isinstance(action, c.CreateTask):
            employee_assignment(db, action.employee_id, department_id)
        if isinstance(action, c.CreateEscalation) and action.task_id:
            related = one(db, s.tasks, action.task_id, locked=execute)
            if related["subject_id"] != subject_id or related["department_id"] != department_id:
                raise WorkflowError(
                    "related_task_scope", "Related task must share subject and department.", 422
                )
            preconditions["related_task_version"] = related["version"]
    if hasattr(action, "due_at"):
        due_date(action.due_at)
    preconditions["business_state"] = business_state(db, subject)
    return subject_id, sorted(scopes), preconditions


def state(row):
    return {
        k: row[k]
        for k in (
            "id",
            "version",
            "status",
            "priority",
            "department_id",
            "due_at",
            "employee_id",
            "completed_at",
            "closed_at",
            "resolution",
        )
        if k in row
    }


def apply(db, action, proposal, executor, execution_id):
    """Called only inside the approved executor's atomic business savepoint."""
    department_id = proposal["department_id"]
    base = {
        "department_id": department_id,
        "subject_id": proposal["subject_id"],
        "created_by": proposal["proposer_id"],
        "proposal_id": proposal["id"],
        "execution_id": execution_id,
        "version": 1,
    }
    before = {}
    if isinstance(action, c.CreateTask):
        identifier = uuid.uuid4()
        db.execute(
            insert(s.tasks).values(
                id=identifier,
                title=action.title,
                description=action.description,
                status="open",
                priority=action.priority,
                due_at=due_date(action.due_at),
                employee_id=action.employee_id,
                **base,
            )
        )
        db.execute(
            insert(s.task_assignments).values(
                task_id=identifier,
                department_id=department_id,
                employee_id=action.employee_id,
                actor_id=executor.id,
                execution_id=execution_id,
            )
        )
        after = state(one(db, s.tasks, identifier))
        return "task.created", "task", identifier, before, after, {"task_id": identifier}
    if isinstance(action, c.CreateEscalation):
        identifier = uuid.uuid4()
        db.execute(
            insert(s.escalations).values(
                id=identifier,
                title=action.title,
                reason=action.reason,
                status="open",
                priority=action.priority,
                due_at=due_date(action.due_at),
                task_id=action.task_id,
                **base,
            )
        )
        after = state(one(db, s.escalations, identifier))
        return (
            "escalation.created",
            "escalation",
            identifier,
            before,
            after,
            {"escalation_id": identifier},
        )
    if isinstance(action, c.CloseEscalation):
        identifier = action.escalation_id
        row = one(db, s.escalations, identifier, locked=True)
        before = state(row)
        db.execute(
            update(s.escalations)
            .where(s.escalations.c.id == identifier)
            .values(
                status="closed",
                closed_at=now(),
                resolution=action.resolution,
                version=row["version"] + 1,
                updated_at=now(),
            )
        )
        after = state(one(db, s.escalations, identifier))
        return (
            "escalation.closed",
            "escalation",
            identifier,
            before,
            after,
            {"escalation_id": identifier},
        )
    identifier = action.task_id
    row = one(db, s.tasks, identifier, locked=True)
    before = state(row)
    values = {"version": row["version"] + 1, "updated_at": now()}
    outputs = {"task_id": identifier}
    if isinstance(action, c.AssignTask):
        values.update(
            department_id=action.department_id or department_id, employee_id=action.employee_id
        )
        db.execute(
            insert(s.task_assignments).values(
                task_id=identifier,
                department_id=values["department_id"],
                employee_id=action.employee_id,
                actor_id=executor.id,
                execution_id=execution_id,
            )
        )
        action_name = "task.assigned"
    elif isinstance(action, c.SetStatus):
        values.update(
            status=action.status, completed_at=now() if action.status == "completed" else None
        )
        action_name = "task.status_changed"
    elif isinstance(action, c.SetPriority):
        values["priority"] = action.priority
        action_name = "task.priority_changed"
    elif isinstance(action, c.SetDue):
        values["due_at"] = due_date(action.due_at)
        action_name = "task.due_changed"
    elif isinstance(action, c.AddNote):
        note_id = uuid.uuid4()
        db.execute(
            insert(s.notes).values(
                id=note_id,
                task_id=identifier,
                actor_id=executor.id,
                execution_id=execution_id,
                text=action.text,
            )
        )
        outputs["note_id"] = note_id
        action_name = "task.note_added"
    else:
        raise WorkflowError("unsupported_action", "Action is not registered.", 422)
    db.execute(update(s.tasks).where(s.tasks.c.id == identifier).values(**values))
    after = state(one(db, s.tasks, identifier))
    return action_name, "task", identifier, before, after, outputs
