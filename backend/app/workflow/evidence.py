from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import insert, text

from app.hybrid.contracts import HybridRequest
from app.hybrid.engine import query_hybrid
from app.knowledge.citations import resolve as resolve_citation
from app.knowledge.contracts import SearchRequest
from app.knowledge.embeddings import KnowledgeError
from app.knowledge.search import eligible_documents
from app.models import Base
from app.workflow import contracts as c
from app.workflow import schema as s
from app.workflow.actions import due_date, employee_assignment, one, subject_ref, subject_row
from app.workflow.audit import event
from app.workflow.common import WorkflowError, canonical, digest, now, transaction, workflow_engine
from app.workflow.permissions import require
from app.workflow.unit import run


def source_state(db):
    """Detect source changes outside the trusted workflow write boundary, including KPI inputs."""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    values = {}
    for name in sorted(Base.metadata.tables):
        if name != "seed_runs":
            # Names come only from frozen application metadata, never from a request.
            values[name] = db.scalar(
                text(
                    "SELECT md5(coalesce(string_agg(to_jsonb(t)::text,'|' ORDER BY id),'')) "
                    f'FROM "{name}" t'
                )
            )
    return digest(values)


async def capture(actor, body, key, request_id, bind=None):
    with transaction("review", bind) as db:
        require(db, actor, "propose", [body.department_id])
        initial_source = source_state(db)
    response = await query_hybrid(
        HybridRequest(question=body.question, as_of=body.as_of, mode="DETERMINISTIC"),
        bind=bind or workflow_engine(),
    )
    if (
        response.status not in {"completed", "partial"}
        or not response.evidence_graph.facts
        or any(not f.verified for f in response.evidence_graph.facts)
        or response.usage.llm_calls != 0
    ):
        raise WorkflowError(
            "evidence_unavailable", "The investigation did not establish verified facts.", 422
        )
    if not any(
        x.entity_type == body.subject.kind and x.entity_id == body.subject.entity_id
        for x in response.resolved_entities
    ):
        raise WorkflowError(
            "evidence_subject_mismatch", "Investigation does not establish that subject.", 422
        )
    payload = {
        "source_state": initial_source,
        "mode": "DETERMINISTIC",
        "subject": body.subject.model_dump(mode="json"),
        "as_of": str(response.as_of),
        "question": body.question,
        "status": response.status,
        "answer": response.answer,
        "facts": [f.model_dump(mode="json") for f in response.evidence_graph.facts],
        "citations": response.citations,
        "limitations": response.limitations,
        "llm_calls": 0,
        "tool_calls": response.usage.tool_calls,
        "authority": "Verified historical evidence; never an approval or execution instruction.",
    }

    def guard(db):
        require(db, actor, "propose", [body.department_id])
        return {"department_id": body.department_id}

    def persist(db, _):
        if source_state(db) != initial_source:
            raise WorkflowError(
                "evidence_source_changed", "Source changed during investigation; recapture."
            )
        subject = subject_row(db, body.subject)
        row = dict(
            db.execute(
                insert(s.evidence)
                .values(
                    created_by=actor.id,
                    subject_id=subject,
                    department_id=body.department_id,
                    payload=payload,
                    digest=digest(payload),
                    expires_at=now() + timedelta(days=1),
                )
                .returning(s.evidence)
            )
            .mappings()
            .one()
        )
        event(
            db,
            actor,
            "evidence.captured",
            request_id=request_id,
            department_id=body.department_id,
            object_type="evidence",
            object_id=row["id"],
            after={"digest": row["digest"], "subject_id": subject, "status": response.status},
        )
        return row

    return run(
        actor,
        "review",
        "evidence.capture",
        body.model_dump(mode="json"),
        key,
        request_id,
        guard,
        persist,
        bind,
    )


def validate(db, identifier, subject_id, department_id, fact_ids, *, required=False):
    if not identifier:
        if required or fact_ids:
            raise WorkflowError(
                "evidence_required", "A server-verified investigation is required.", 422
            )
        return None
    snapshot = one(db, s.evidence, identifier)
    if snapshot["subject_id"] != subject_id or snapshot["department_id"] != department_id:
        raise WorkflowError(
            "evidence_scope_mismatch", "Evidence belongs to another subject or department.", 403
        )
    if snapshot["expires_at"] <= now():
        raise WorkflowError("evidence_expired", "Capture a fresh verified investigation.")
    payload = snapshot["payload"]
    if digest(payload) != snapshot["digest"] or payload.get("mode") != "DETERMINISTIC":
        raise WorkflowError("evidence_invalid", "Evidence integrity validation failed.")
    if payload.get("source_state") != source_state(db):
        raise WorkflowError(
            "evidence_source_changed", "Historical source state changed; recapture evidence."
        )
    known = {f["fact_id"] for f in payload["facts"] if f["verified"]}
    if not fact_ids or not set(fact_ids) <= known:
        raise WorkflowError(
            "forged_evidence_reference", "Select actual verified fact identifiers.", 422
        )
    actual_subject = subject_ref(db, subject_id).model_dump(mode="json")
    if payload["subject"] != actual_subject:
        raise WorkflowError("evidence_scope_mismatch", "Evidence subject identity differs.", 403)
    try:
        eligible = {
            m["version_id"]
            for m in eligible_documents(
                db,
                SearchRequest(
                    query="workflow evidence", as_of=date.fromisoformat(payload["as_of"])
                ),
            )
        }
        for citation in payload["citations"]:
            resolved = resolve_citation(db, citation["citation_id"])
            if (
                canonical(resolved["citation"]) != canonical(citation)
                or citation["document_version_id"] not in eligible
            ):
                raise WorkflowError("evidence_invalid", "Registered source identity changed.")
    except KnowledgeError as exc:
        raise WorkflowError("evidence_invalid", "Registered evidence no longer resolves.") from exc
    return {
        "id": str(identifier),
        "digest": snapshot["digest"],
        "fact_ids": fact_ids,
        "as_of": payload["as_of"],
        "limitations": payload["limitations"],
    }


def recommendation(actor, body, bind=None):
    with transaction("read", bind) as db:
        snapshot = one(db, s.evidence, body.evidence_id)
        require(db, actor, "propose", [snapshot["department_id"]])
        payload = snapshot["payload"]
        due_date(body.due_at)
        employee_assignment(db, body.employee_id, snapshot["department_id"])
        supporting = []
        for fact in payload["facts"]:
            subject = fact.get("subject") or {}
            if (
                subject.get("entity_type") != payload["subject"]["kind"]
                or subject.get("entity_id") != payload["subject"]["entity_id"]
            ):
                continue
            value = fact["value"]
            if fact["kind"] != "metric" or value.get("value") is None:
                continue
            metric = value["metric"].rsplit(".", 1)[-1]
            if (metric == "gap_percentage_points" and Decimal(str(value["value"])) < 0) or (
                metric in {"overdue_tasks", "overdue_outstanding_orders"}
                and Decimal(str(value["value"])) > 0
            ):
                supporting.append(fact["fact_id"])
        if not supporting:
            raise WorkflowError(
                "recommendation_unsupported",
                "No verified below-target or overdue condition supports this recommendation.",
                422,
            )
        subject = subject_ref(db, snapshot["subject_id"])
        validate(
            db,
            body.evidence_id,
            snapshot["subject_id"],
            snapshot["department_id"],
            supporting,
            required=True,
        )
        proposal = c.ProposalInput(
            department_id=snapshot["department_id"],
            source_type="DETERMINISTIC_RECOMMENDATION",
            evidence_id=body.evidence_id,
            fact_ids=supporting[:16],
            reason="Review the identified verified operational concern.",
            business_context="Due date, priority and assignment are proposed settings; "
            "they are not inferred contractual requirements.",
            action=c.CreateTask(
                type="CREATE_WORKFLOW_TASK",
                title=body.title,
                description=body.description,
                priority=body.priority,
                due_at=body.due_at,
                employee_id=body.employee_id,
                subject=subject,
            ),
        )
        return {
            "proposal": proposal.model_dump(mode="json"),
            "persisted": False,
            "approval_granted": False,
            "llm_calls": 0,
            "limitations": ["This recommendation creates no task and grants no approval."],
        }
