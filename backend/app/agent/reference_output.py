"""Short model-selected references; no guessed numbers, names or source identifiers."""

import json
from typing import Literal

from app.agent.contracts import AgentError, Draft, Strict
from app.agent.grounding import pointer
from pydantic import Field


class ReferenceFinding(Strict):
    interpretation: str = Field(min_length=1, max_length=240)
    claim_type: Literal[
        "observation",
        "target_comparison",
        "ranking",
        "policy_requirement",
        "association",
        "possible_explanation",
        "causal_chain",
        "suggestion",
        "unavailable",
    ]
    subject: str | None
    supports: list[str] = Field(min_length=1, max_length=8)


class ReferenceDraft(Strict):
    status: Literal[
        "completed", "partial", "insufficient_evidence", "clarification_required", "refused"
    ]
    findings: list[ReferenceFinding] = Field(max_length=6)
    limitations: list[str] = Field(max_length=2)
    follow_up_questions: list[str] = Field(max_length=2)


def collected(history):
    result = {}
    for item in history:
        if item.get("type") == "function_call_output":
            data = json.loads(item["output"])
            if data.get("ok"):
                evidence = data["evidence"]
                result[evidence["evidence_id"]] = evidence
    return result


def catalogue(history, index):
    evidence = collected(history)
    entries = []

    def add(kind, e, **fields):
        identifier = kind[0].upper() + str(len(entries) + 1)
        entries.append({"ref": identifier, "kind": kind, "evidence_id": e, **fields})

    for item in index:
        e = evidence[item["evidence_id"]]
        payload = e["payload"]
        scope = dict(e["arguments"])
        nested = scope.get("query")
        if isinstance(nested, dict):
            scope.pop("query")
            scope.update(nested)
        add(
            "evidence",
            e["evidence_id"],
            tool=e["tool_name"],
            status=payload.get("status"),
            limitations=payload.get("limitations", []),
            scope={k: v for k, v in scope.items() if v is not None},
            window=payload.get("window"),
            total=payload.get("total", payload.get("total_segments")),
            limit=payload.get("limit"),
            offset=payload.get("offset"),
            preview={
                k: payload[k]
                for k in ("metadata", "text", "line_start", "line_end", "verified")
                if k in payload
            },
            available_metric_names=sorted(
                set(payload.get("metrics", {}))
                | {k for row in payload.get("breakdowns", []) for k in row.get("metrics", {})}
            ),
        )
        for root in ("breakdowns", "matches"):
            for position, row in enumerate(payload.get(root, [])):
                if {"entity_type", "entity_id"} <= row.keys():
                    add(
                        "subject",
                        e["evidence_id"],
                        pointer=f"/{root}/{position}",
                        entity_type=row["entity_type"],
                        entity_id=row["entity_id"],
                        label=row.get("label", row.get("name")),
                    )
        if {"entity_type", "entity_id"} <= payload.keys():
            add(
                "subject",
                e["evidence_id"],
                pointer="",
                entity_type=payload["entity_type"],
                entity_id=payload["entity_id"],
                label=None,
            )
        for path in item["metric_pointers"]:
            value = pointer(payload, path)
            details = (
                value
                if isinstance(value, dict)
                else {"metric": path.rsplit("/", 1)[-1], "value": value}
            )
            add("metric", e["evidence_id"], pointer=path, window=payload.get("window"), **details)
        for citation in item["citation_ids"]:

            def source_material(value, citation=citation):
                if isinstance(value, dict):
                    if (
                        isinstance(value.get("citation"), dict)
                        and value["citation"].get("citation_id") == citation
                    ):
                        return {
                            k: value[k]
                            for k in ("citation", "metadata", "text", "verified")
                            if k in value
                        }
                    for child in value.values():
                        found = source_material(child)
                        if found:
                            return found
                elif isinstance(value, list):
                    for child in value:
                        found = source_material(child)
                        if found:
                            return found
                return None

            add(
                "document",
                e["evidence_id"],
                citation_id=citation,
                code=item.get("citation_source_codes", {}).get(citation),
                source=source_material(payload),
            )
        for position, row in enumerate(payload.get("evidence", [])):
            if {"relationship_type", "evidence_class", "source_reference"} <= row.keys():
                add("relationship", e["evidence_id"], pointer=f"/evidence/{position}", **row)
    return entries


def response_schema(entries):
    schema = ReferenceDraft.model_json_schema()
    finding = schema["$defs"]["ReferenceFinding"]["properties"]
    finding["supports"]["items"] = {
        "type": "string",
        "enum": [e["ref"] for e in entries if e["kind"] != "subject"] or ["unavailable"],
    }
    subjects = [e["ref"] for e in entries if e["kind"] == "subject"]
    finding["subject"] = (
        {"anyOf": [{"type": "string", "enum": subjects}, {"type": "null"}]}
        if subjects
        else {"type": "null"}
    )
    if not entries:
        schema["properties"]["findings"]["maxItems"] = 0
        schema["properties"]["status"]["enum"].remove("completed")
    return schema


def canonical_response(raw, entries):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate field")
            result[key] = value
        return result

    try:
        result = ReferenceDraft.model_validate(
            json.loads(raw, object_pairs_hook=unique), strict=True
        )
    except ValueError as exc:
        raise AgentError(
            "malformed_final_output", "Return the required short-reference JSON."
        ) from exc
    known = {entry["ref"]: entry for entry in entries}
    findings = []
    for finding in result.findings:
        selected = []
        for ref in finding.supports:
            if ref not in known or known[ref]["kind"] == "subject":
                raise AgentError("invalid_evidence_reference", "Use a current support reference.")
            selected.append(known[ref])
        subject = known.get(finding.subject) if finding.subject else None
        if finding.subject and (not subject or subject["kind"] != "subject"):
            raise AgentError("invalid_entity_reference", "Use a returned subject reference.")
        findings.append(
            {
                "text": finding.interpretation,
                "quality_profile": "references",
                "claim_type": "comparison"
                if finding.claim_type == "target_comparison"
                else finding.claim_type,
                "evidence_ids": list(
                    dict.fromkeys(
                        [s["evidence_id"] for s in selected]
                        + ([subject["evidence_id"]] if subject else [])
                    )
                ),
                "entity_refs": [
                    {"evidence_id": subject["evidence_id"], "pointer": subject["pointer"]}
                ]
                if subject
                else [],
                "relationship_refs": [
                    {"evidence_id": s["evidence_id"], "pointer": s["pointer"]}
                    for s in selected
                    if s["kind"] == "relationship"
                ],
                "metric_refs": [
                    {"evidence_id": s["evidence_id"], "pointer": s["pointer"]}
                    for s in selected
                    if s["kind"] == "metric"
                ],
                "citation_ids": list(
                    dict.fromkeys(s["citation_id"] for s in selected if s["kind"] == "document")
                ),
                "quote_citation_ids": list(
                    dict.fromkeys(s["citation_id"] for s in selected if s["kind"] == "document")
                ),
            }
        )
    try:
        return Draft.model_validate(
            {
                "status": result.status,
                "quality_profile": "references",
                "findings": findings,
                "limitations": result.limitations,
                "follow_up_questions": result.follow_up_questions,
            },
            strict=True,
        ).model_dump_json()
    except ValueError as exc:
        raise AgentError(
            "malformed_final_output", "Too many sources or invalid references in finding."
        ) from exc
