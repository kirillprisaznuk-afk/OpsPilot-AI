"""Provenance and numeric projection checks; not a semantic-entailment oracle."""

import re
from decimal import Decimal

from app.agent.contracts import AgentError, Draft, Finding
from app.agent.quality import validate_interpretation, validate_prose
from app.knowledge.citations import resolve
from app.knowledge.contracts import Citation, SearchRequest
from app.knowledge.search import eligible_documents
from pydantic import ValidationError

NUMBER = re.compile(
    (
        "\\d|\\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|ele"
        "ven|twelve|hundred|thousand|million|billion|ninety|eighty|seventy"
        "|sixty|fifty|forty|thirty|twenty)\\b"
    ),
    re.I,
)
ACTION = re.compile(
    r"\b(?:i|we|agent)\s+(?:have\s+)?(?:created|updated|deleted|approved|sent|executed|assigned)\b|"
    r"\b(?:task|invoice|payment|record)\s+(?:was\s+)?"
    r"(?:created|approved|updated|deleted)\s+successfully\b",
    re.I,
)


def pointer(payload, path):
    current = payload
    try:
        for raw in path.split("/")[1:]:
            key = raw.replace("~1", "/").replace("~0", "~")
            current = current[int(key)] if isinstance(current, list) else current[key]
    except (KeyError, ValueError, TypeError, IndexError) as exc:
        raise AgentError(
            "invalid_metric_reference", "Metric pointer was not returned by a tool in this run."
        ) from exc
    return current


def citation_map(payload):
    result = {}

    def visit(item):
        if isinstance(item, dict):
            if "citation_id" in item and "chunk_id" in item and "line_start" in item:
                result[item["citation_id"]] = item
            for value in item.values():
                visit(value)
        elif isinstance(item, list):
            for value in item:
                visit(value)

    visit(payload)
    return result


def verify_final(raw, evidence, db, as_of):
    try:
        draft = Draft.model_validate_json(raw)
    except (ValidationError, ValueError) as exc:
        raise AgentError(
            "malformed_final_output", "Model did not return the required structured response."
        ) from exc
    by_id = {e.evidence_id: e for e in evidence}
    available = {}
    for e in evidence:
        available.update(citation_map(e.payload))
    active = {
        m["version_id"]: m
        for m in eligible_documents(db, SearchRequest(query="source verification", as_of=as_of))
    }
    findings = []
    ranking_positions = {}
    citations = {}
    for f in draft.findings:
        if not f.evidence_ids or any(identifier not in by_id for identifier in f.evidence_ids):
            raise AgentError(
                "invalid_evidence_reference", "Finding must cite evidence returned in this run."
            )
        if NUMBER.search(f.text):
            raise AgentError(
                "unverified_numerical_prose",
                (
                    "Numerical facts must use server-rendered metric references, not "
                    "model-written values."
                ),
            )
        if ACTION.search(f.text):
            raise AgentError(
                "unsupported_action_claim",
                "Read-only analysis cannot claim an action was executed.",
            )
        metrics = []
        entities = []
        relationships = []
        for ref in f.entity_refs:
            if ref.evidence_id not in f.evidence_ids:
                raise AgentError(
                    "invalid_entity_reference", "Subject evidence must support the finding."
                )
            e = by_id[ref.evidence_id]
            value = pointer(e.payload, ref.pointer) if ref.pointer else e.payload
            if not isinstance(value, dict) or not {"entity_type", "entity_id"} <= value.keys():
                raise AgentError(
                    "invalid_entity_reference", "Subject must be a returned business entity."
                )
            entities.append(
                {
                    "evidence_id": ref.evidence_id,
                    "pointer": ref.pointer,
                    **{k: value.get(k) for k in ("entity_type", "entity_id", "label", "name")},
                }
            )
            if f.claim_type == "ranking":
                if (
                    e.tool_name != "compare_suppliers"
                    or not ref.pointer.startswith("/breakdowns/")
                    or e.arguments.get("sort", "id") == "id"
                ):
                    raise AgentError(
                        "invalid_ranking_reference", "Ranking needs a metric-sorted supplier row."
                    )
                position = int(ref.pointer.split("/")[2])
                ranking_positions.setdefault(ref.evidence_id, []).append(position)
                entities[-1].update(
                    rank=e.payload.get("offset", 0) + position + 1,
                    criterion=e.arguments["sort"],
                    direction=e.arguments.get("direction", "asc"),
                )
        for ref in f.relationship_refs:
            if ref.evidence_id not in f.evidence_ids:
                raise AgentError(
                    "invalid_relationship_reference", "Relationship evidence is missing."
                )
            row = pointer(by_id[ref.evidence_id].payload, ref.pointer)
            if (
                not isinstance(row, dict)
                or not {"evidence_class", "relationship_type", "source_reference"} <= row.keys()
            ):
                raise AgentError(
                    "invalid_relationship_reference", "Select a typed relationship record."
                )
            relationships.append({"evidence_id": ref.evidence_id, "pointer": ref.pointer, **row})
        for ref in f.metric_refs:
            if ref.evidence_id not in f.evidence_ids:
                raise AgentError(
                    "invalid_metric_reference", "Metric evidence must support this finding."
                )
            e = by_id[ref.evidence_id]
            if f.quality_profile == "references" and ref.pointer.startswith("/metrics/"):
                row_subject = any(
                    x["evidence_id"] == ref.evidence_id and x["pointer"].startswith("/breakdowns/")
                    for x in entities
                )
                if row_subject and (
                    e.tool_name == "compare_suppliers" or e.payload.get("total_segments", 0) > 1
                ):
                    raise AgentError(
                        "metric_entity_mismatch",
                        "Aggregate metrics cannot be attributed to "
                        "an individual result row. Select its row metric.",
                    )
            if f.quality_profile == "references" and ref.pointer.startswith("/breakdowns/"):
                parent = ref.pointer.split("/metrics/", 1)[0]
                if not any(
                    x["evidence_id"] == ref.evidence_id and x["pointer"] == parent for x in entities
                ):
                    raise AgentError(
                        "metric_entity_mismatch", "Metric belongs to a different subject row."
                    )
            value = pointer(e.payload, ref.pointer)
            if isinstance(value, dict) and {"metric", "value", "unit"} <= set(value):
                metrics.append(
                    {
                        "evidence_id": ref.evidence_id,
                        "pointer": ref.pointer,
                        **value,
                        "window": e.payload.get("window"),
                    }
                )
            elif ref.pointer.startswith("/contracts/") and ref.pointer.split("/")[-1] in {
                "target_percent",
                "observed_percent",
                "gap_percentage_points",
                "due_orders",
                "on_time_orders",
            }:
                if f.quality_profile == "references":
                    contract = pointer(e.payload, ref.pointer.rsplit("/", 1)[0])
                    supplier_ids = {
                        x["entity_id"] for x in entities if x["entity_type"] == "supplier"
                    }
                    if contract["supplier_id"] not in supplier_ids:
                        raise AgentError(
                            "metric_entity_mismatch",
                            "Contract metric needs its actual supplier subject.",
                        )
                if value is not None:
                    try:
                        Decimal(str(value))
                    except Exception as exc:
                        raise AgentError(
                            "invalid_metric_reference", "Contract numeric reference is invalid."
                        ) from exc
                field = ref.pointer.split("/")[-1]
                metrics.append(
                    {
                        "evidence_id": ref.evidence_id,
                        "pointer": ref.pointer,
                        "metric": field,
                        "value": value,
                        "unit": "percentage_points"
                        if field == "gap_percentage_points"
                        else "percent"
                        if "percent" in field
                        else "count",
                        "window": e.payload.get("window"),
                    }
                )
            else:
                raise AgentError(
                    "invalid_metric_reference",
                    (
                        "Only authoritative analytics metric objects or supported contract"
                        " fields can supply numbers."
                    ),
                )
        passages = {}
        source_metadata = []
        for identifier in f.citation_ids:
            if identifier not in available or not any(
                identifier in citation_map(by_id[e].payload) for e in f.evidence_ids
            ):
                raise AgentError(
                    "invalid_citation_reference",
                    "Citation was not supplied by the supporting tool evidence.",
                )
            resolved = resolve(db, identifier)
            citation = Citation.model_validate(resolved["citation"]).model_dump(mode="json")
            if citation["document_version_id"] not in active or citation != available[identifier]:
                raise AgentError(
                    "citation_not_applicable",
                    "Citation is altered or not the effective source for this request.",
                )
            citations[identifier] = citation
            source_metadata.append(active[citation["document_version_id"]])
            passages[identifier] = resolved["text"]
        if any(identifier not in f.citation_ids for identifier in f.quote_citation_ids):
            raise AgentError(
                "invalid_citation_reference",
                "A requested quotation must use a verified supporting citation.",
            )
        if f.quality_profile == "references":
            if f.claim_type == "ranking" and (
                not entities
                or any(
                    not any(
                        m["evidence_id"] == entity["evidence_id"]
                        and m["pointer"] == entity["pointer"] + "/metrics/" + entity["criterion"]
                        for m in metrics
                    )
                    for entity in entities
                )
            ):
                raise AgentError(
                    "incomplete_ranking", "Each ranked supplier needs its actual sorting metric."
                )
            validate_interpretation(f, metrics, entities, relationships, source_metadata)
        findings.append(
            Finding(
                text=f.text,
                entities=entities,
                relationships=relationships,
                claim_type=f.claim_type,
                evidence_ids=f.evidence_ids,
                metrics=metrics,
                citation_ids=f.citation_ids,
                quotations=[
                    {
                        "citation_id": identifier,
                        "text": passages[identifier],
                        "trust": "untrusted_source_data",
                    }
                    for identifier in f.quote_citation_ids
                ],
            )
        )
    if draft.status == "completed" and not findings:
        raise AgentError("unsupported_completion", "Completed answers require verified findings.")
    for positions in ranking_positions.values():
        unique = list(dict.fromkeys(positions))
        if unique != list(range(len(unique))):
            raise AgentError(
                "ranking_order_mismatch", "Render the leading ranked rows in source order."
            )
    # Other free prose is restricted too; numbers are rendered exclusively from checked facts.
    if any(NUMBER.search(v) for v in draft.limitations + draft.follow_up_questions):
        raise AgentError(
            "unverified_numerical_prose",
            "Use source references rather than numeric claims in prose.",
        )
    if draft.quality_profile == "references" or any(
        f.quality_profile == "references" for f in draft.findings
    ):
        for text in draft.limitations + draft.follow_up_questions:
            validate_prose(text)
    return draft, findings, list(citations.values())
