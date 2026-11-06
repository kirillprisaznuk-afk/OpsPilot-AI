"""Authenticated read projections for selectors; no new business calculations or writes."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from app.api.workflow import RUNTIME_DEPENDENCY, ActorDep, Limit, Offset
from app.models import Base
from app.workflow import schema as s
from app.workflow.common import WorkflowError, transaction
from app.workflow.permissions import memberships, require, session_valid, visible
from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sqlalchemy import Date, String, cast, func, or_, select, union

from data.generator.company import END, START

router = APIRouter(prefix="/api/v1/workspace", tags=["authenticated workspace projections"])
Kind = Literal[
    "supplier", "purchase_order", "sales_order", "warehouse", "product", "incident", "department"
]


class SubjectRow(BaseModel):
    id: int
    kind: Kind
    label: str
    status: str | None = None
    department_id: int | None = None
    supplier_id: int | None = None
    warehouse_id: int | None = None
    ordered_on: date | None = None
    promised_on: date | None = None
    recorded_on: date | None = None


class SubjectPage(BaseModel):
    items: list[SubjectRow]
    total: int
    limit: int
    offset: int


def historical_access(db, actor):
    session_valid(db, actor)
    if not memberships(db, actor.id):
        raise WorkflowError("permission_denied", "A workspace role is required.", 403)


@router.get("/status", response_model=dict[str, str])
def version(actor: ActorDep, request: Request, bind=RUNTIME_DEPENDENCY):
    with transaction("read", bind) as db:
        historical_access(db, actor)
    return {"api_version": request.app.version}


@router.get("/subjects", response_model=SubjectPage)
def subjects(
    actor: ActorDep,
    kind: Kind = "supplier",
    search: Annotated[str, Query(max_length=150)] = "",
    limit: Limit = 25,
    offset: Offset = 0,
    supplier_id: int | None = Query(None, gt=0),
    warehouse_id: int | None = Query(None, gt=0),
    status: str | None = Query(None, max_length=30),
    start_date: date | None = None,
    end_date: date | None = None,
    bind=RUNTIME_DEPENDENCY,
):
    table = Base.metadata.tables[s.SUBJECT_TABLES[kind]]
    with transaction("read", bind) as db:
        historical_access(db, actor)
        label = (
            table.c.name
            if "name" in table.c
            else (table.c.description if "description" in table.c else cast(table.c.id, String))
        )
        where = []
        recorded = table.c.ordered_on if "ordered_on" in table.c else cast(table.c.created_at, Date)
        if start_date is not None or end_date is not None:
            if not START <= (start_date or START) <= (end_date or END) <= END:
                raise WorkflowError(
                    "invalid_period", "Select a valid historical observation window.", 422
                )
            where.append(recorded.between(start_date or START, end_date or END))
        if search:
            term = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            where.append(
                or_(label.ilike("%" + term + "%", escape="\\"), cast(table.c.id, String) == search)
            )
        for field, value in (
            ("supplier_id", supplier_id),
            ("warehouse_id", warehouse_id),
            ("status", status),
        ):
            if value is not None:
                if field not in table.c:
                    raise WorkflowError(
                        "unsupported_filter", "This selector does not support that filter.", 422
                    )
                where.append(table.c[field] == value)
        fields = [table.c.id, label.label("label"), recorded.label("recorded_on")]
        fields += [
            table.c[k]
            for k in (
                "status",
                "department_id",
                "supplier_id",
                "warehouse_id",
                "ordered_on",
                "promised_on",
            )
            if k in table.c
        ]
        rows = db.execute(
            select(*fields).where(*where).order_by(table.c.id).limit(limit).offset(offset)
        ).mappings()
        return {
            "items": [{**r, "kind": kind} for r in rows],
            "total": db.scalar(select(func.count()).select_from(table).where(*where)),
            "limit": limit,
            "offset": offset,
        }


class Person(BaseModel):
    id: int
    name: str
    department_id: int


@router.get("/people", response_model=list[Person])
def people(actor: ActorDep, department_id: int | None = Query(None, gt=0), bind=RUNTIME_DEPENDENCY):
    employees = Base.metadata.tables["employees"]
    with transaction("read", bind) as db:
        session_valid(db, actor)
        query = select(employees.c.id, employees.c.name, employees.c.department_id).where(
            visible(db, actor, employees.c.department_id)
        )
        if department_id:
            query = query.where(employees.c.department_id == department_id)
        return [dict(r) for r in db.execute(query.order_by(employees.c.name).limit(100)).mappings()]


class PrincipalRow(BaseModel):
    id: str
    username: str
    active: bool
    is_human: bool
    created_at: datetime
    roles: list[dict]


class ActorLabel(BaseModel):
    id: UUID
    username: str


@router.get("/actor-labels", response_model=list[ActorLabel])
def actor_labels(
    actor: ActorDep,
    ids: Annotated[list[UUID], Query(min_length=1, max_length=100)],
    bind=RUNTIME_DEPENDENCY,
):
    with transaction("read", bind) as db:
        historical_access(db, actor)
        proposal_scope = visible(db, actor, s.proposals.c.department_id)
        known = union(
            select(s.proposals.c.proposer_id).where(proposal_scope),
            select(s.approvals.c.actor_id).join(s.proposals).where(proposal_scope),
            select(s.executions.c.actor_id).join(s.proposals).where(proposal_scope),
            select(s.audit.c.actor_id).where(visible(db, actor, s.audit.c.department_id)),
        )
        return [
            dict(r)
            for r in db.execute(
                select(s.principals.c.id, s.principals.c.username).where(
                    s.principals.c.id.in_(ids),
                    or_(s.principals.c.id == actor.id, s.principals.c.id.in_(known)),
                )
            ).mappings()
        ]


@router.get("/principals", response_model=list[PrincipalRow])
def principals(actor: ActorDep, bind=RUNTIME_DEPENDENCY):
    with transaction("read", bind) as db:
        require(db, actor, "admin", [None])
        rows = db.execute(
            select(
                s.principals.c.id,
                s.principals.c.username,
                s.principals.c.active,
                s.principals.c.is_human,
                s.principals.c.created_at,
            )
            .order_by(s.principals.c.username)
            .limit(100)
        ).mappings()
        return [
            {**r, "id": str(r["id"]), "roles": [dict(x) for x in memberships(db, r["id"])]}
            for r in rows
        ]
