import hashlib
import json
from collections import defaultdict
from decimal import Decimal

from app.agent.contracts import AgentError
from app.agent.grounding import pointer, verify_final
from app.hybrid.contracts import Fact, Graph, Subject
from app.hybrid.registry import REGISTRY
from app.knowledge.citations import resolve as resolve_citation
from app.knowledge.contracts import Citation, DocumentMetadata, SearchRequest
from app.knowledge.embeddings import KnowledgeError
from app.knowledge.search import eligible_documents


def contract_metric(contract, field):
    value = {
        "metric": field,
        "value": contract[field],
        "unit": "percentage_points" if field == "gap_percentage_points" else "percent",
        "status": "available" if contract[field] is not None else "undefined",
        "time_basis": "Effective agreement within the observation window.",
        "grain": "supplier contract",
        "limitations": ["Operational target comparison is not legal breach."],
    }
    if field == "observed_percent":
        value.update(numerator=contract["on_time_orders"], denominator=contract["due_orders"])
    return value


def graph_from(evidence, step_capabilities, plan):
    graph = Graph()
    identities = {}
    for e in evidence:
        for i, row in enumerate(e.payload.get("matches", [])):
            identities[(row["entity_type"], row["entity_id"])] = (e.evidence_id, f"/matches/{i}")
    known = {(s.entity_type, s.entity_id): s for s in plan.subjects}
    seen_values = set()

    def add(e, path, kind, value, subject=None, subject_ref=None):
        scope = dict(e.arguments)
        if isinstance(scope.get("query"), dict):
            scope["query"] = {
                k: v for k, v in scope["query"].items() if k not in {"limit", "offset"}
            }
        semantic_key = json.dumps(
            [kind, value, e.payload.get("window")]
            if kind == "relationship"
            else [e.tool_name, scope, kind, value, subject.model_dump() if subject else None],
            sort_keys=True,
            default=str,
        )
        if semantic_key in seen_values:
            return
        seen_values.add(semantic_key)
        fid = "fact_" + hashlib.sha256((e.evidence_id + path).encode()).hexdigest()[:16]
        if any(f.fact_id == fid for f in graph.facts):
            return
        graph.facts.append(
            Fact(
                fact_id=fid,
                evidence_id=e.evidence_id,
                pointer=path,
                source_tool=e.tool_name,
                scope=e.arguments,
                kind=kind,
                value=value,
                window=e.payload.get("window"),
                subject=subject,
                subject_evidence_id=subject_ref[0] if subject_ref else None,
                subject_pointer=subject_ref[1] if subject_ref else None,
                verified=False,
            )
        )

    for e in evidence:
        capability_id = step_capabilities.get(e.evidence_id)
        if capability_id not in REGISTRY:
            continue
        cap = REGISTRY[capability_id]
        payload = e.payload
        related = [
            REGISTRY[o.capability]
            for o in plan.intent.objectives
            if e.tool_name in REGISTRY[o.capability].tools
        ]
        desired = set(cap.metrics)
        for candidate in related:
            desired.update(candidate.metrics)
        objective = next((o for o in plan.intent.objectives if o.capability == capability_id), None)
        if objective and objective.metric:
            desired = {objective.metric}
        subject, subject_ref = None, None
        if {"entity_type", "entity_id"} <= payload.keys():
            key = (payload["entity_type"], payload["entity_id"])
            subject = known.get(key) or Subject(
                entity_type=key[0],
                entity_id=key[1],
                label=f"{key[0]} {key[1]}",
                provenance="database_lookup",
            )
            subject_ref = (e.evidence_id, "")
        rows = payload.get("breakdowns", [])
        if e.tool_name == "get_supplier_performance" and rows:
            row = rows[0]
            subject = known.get((row["entity_type"], row["entity_id"]))
            subject_ref = (e.evidence_id, "/breakdowns/0")
        if subject is None:
            args = {
                **e.arguments,
                **(e.arguments.get("query") if isinstance(e.arguments.get("query"), dict) else {}),
            }
            selected = [s for s in plan.subjects if args.get(s.entity_type + "_id") == s.entity_id]
            if len(selected) == 1:
                subject = selected[0]
                subject_ref = identities.get((subject.entity_type, subject.entity_id))
        if e.tool_name == "compare_suppliers":
            for i, row in enumerate(rows):
                key = (row["entity_type"], row["entity_id"])
                row_subject = Subject(
                    entity_type=key[0],
                    entity_id=key[1],
                    label=row["label"],
                    provenance="verified_ranking",
                )
                for name, metric in row["metrics"].items():
                    if name in desired:
                        add(
                            e,
                            f"/breakdowns/{i}/metrics/{name}",
                            "metric",
                            metric,
                            row_subject,
                            (e.evidence_id, f"/breakdowns/{i}"),
                        )
        else:
            if capability_id in {"investigation", "overview"}:
                desired = set(payload.get("metrics", {}))
            elif not desired and payload.get("metrics"):
                desired = {
                    "on_time_rate",
                    "partial_orders",
                    "outstanding_units",
                    "additional_costs",
                    "overdue_tasks",
                }
            for name, metric in payload.get("metrics", {}).items():
                if name in desired:
                    add(e, "/metrics/" + name, "metric", metric, subject, subject_ref)
        if any(c.capability_id in {"supplier_sla", "contract_lookup"} for c in related):
            for i, contract in enumerate(payload.get("contracts", [])):
                for field in ("observed_percent", "target_percent", "gap_percentage_points"):
                    add(
                        e,
                        f"/contracts/{i}/{field}",
                        "metric",
                        contract_metric(contract, field),
                        subject,
                        subject_ref,
                    )
        for i, row in enumerate(payload.get("evidence", [])):
            if "citation" in row:
                add(e, f"/evidence/{i}", "document", row)
            elif "relationship_type" in row:
                add(e, f"/evidence/{i}", "relationship", row, subject, subject_ref)
    pages = defaultdict(list)
    for e in evidence:
        if e.tool_name == "investigate_business_entity":
            scope = {
                **e.arguments,
                "query": {
                    k: v
                    for k, v in e.arguments.get("query", {}).items()
                    if k not in {"limit", "offset"}
                },
            }
            pages[json.dumps(scope, sort_keys=True)].append(e.payload)
    for values in pages.values():
        cursor = 0
        for payload in sorted(values, key=lambda p: p["offset"]):
            if payload["offset"] != cursor:
                break
            cursor += len(payload["evidence"])
        if cursor < max(v["total"] for v in values) or len({v["total"] for v in values}) != 1:
            graph.missing.append(
                "Relationship records are a bounded sample, not the entire linked population."
            )
    for fact in graph.facts:
        if fact.kind == "relationship":
            value = fact.value
            graph.edges.append(
                {
                    "fact_id": fact.fact_id,
                    "relation": value["relationship_type"],
                    "from": {"type": value["entity_type"], "id": value["entity_id"]},
                    "to": {"type": value["related_entity_type"], "id": value["related_entity_id"]},
                    "evidence_class": value["evidence_class"],
                }
            )
        if fact.subject:
            graph.edges.append(
                {
                    "fact_id": fact.fact_id,
                    "relation": "concerns",
                    "entity_type": fact.subject.entity_type,
                    "entity_id": fact.subject.entity_id,
                }
            )
        if fact.kind == "document":
            metadata = fact.value["metadata"]
            graph.edges.append(
                {
                    "fact_id": fact.fact_id,
                    "relation": "source_scope",
                    "supplier_id": metadata.get("supplier_id"),
                    "department_id": metadata.get("department_id"),
                }
            )
    verify_graph(graph, evidence)
    return graph


def verify_graph(graph, evidence):
    by_id = {e.evidence_id: e for e in evidence}
    # No source/number is trusted just because the graph carries it.
    for fact in graph.facts:
        source = by_id[fact.evidence_id]
        original = pointer(source.payload, fact.pointer)
        if fact.kind == "metric" and fact.pointer.startswith("/contracts/"):
            contract = pointer(source.payload, fact.pointer.rsplit("/", 1)[0])
            valid = fact.value == contract_metric(contract, fact.pointer.split("/")[-1])
        else:
            valid = fact.value == original
        if (
            not valid
            or fact.window != source.payload.get("window")
            or fact.scope != source.arguments
            or fact.source_tool != source.tool_name
        ):
            raise AgentError(
                "graph_fact_mismatch", "Graph fact differs from canonical current-run evidence."
            )
        if fact.kind == "document":
            filters = source.arguments.get("filters", {})
            metadata = fact.value["metadata"]
            if any(
                filters.get(k) is not None and filters[k] != metadata.get(k)
                for k in ("supplier_id", "document_type", "document_id", "contract_id")
            ):
                raise AgentError(
                    "graph_source_mismatch",
                    "Source identity differs from the requested evidence scope.",
                )
        if fact.subject and fact.pointer.startswith("/metrics/"):
            args = source.arguments.get("query", source.arguments)
            if not isinstance(args, dict):
                args = source.arguments
            if source.tool_name == "get_supplier_performance":
                args = {**args, "supplier_id": source.arguments["supplier_id"]}
            if (
                source.tool_name != "investigate_business_entity"
                and args.get(fact.subject.entity_type + "_id") != fact.subject.entity_id
            ):
                raise AgentError(
                    "graph_entity_mismatch", "Metric scope does not match its subject."
                )
    return graph


def grounded_findings(graph, evidence, plan, db):
    verify_graph(graph, evidence)
    if any(e.as_of != plan.intent.as_of for e in evidence):
        raise AgentError("graph_window_mismatch", "Evidence uses a different historical cutoff.")
    # Verify the exact text and displayed metadata, beyond merely checking citation IDs.
    active = {
        m["version_id"]: m
        for m in eligible_documents(
            db, SearchRequest(query="source verification", as_of=plan.intent.as_of)
        )
    }
    try:
        for fact in graph.facts:
            if fact.kind != "document":
                continue
            value = fact.value
            resolved = resolve_citation(db, value["citation"]["citation_id"])
            metadata = active.get(value["metadata"]["version_id"])
            if (
                not metadata
                or value["text"] != resolved["text"]
                or value["metadata"]
                != DocumentMetadata.model_validate(metadata).model_dump(mode="json")
                or value["citation"]
                != Citation.model_validate(resolved["citation"]).model_dump(mode="json")
            ):
                raise AgentError("graph_source_mismatch", "Source passage or identity was altered.")
    except KnowledgeError as exc:
        raise AgentError(exc.code, "Registered source verification failed.") from exc
    groups = defaultdict(list)
    evidence_map = {e.evidence_id: e for e in evidence}
    for fact in graph.facts:
        key = (
            fact.evidence_id,
            fact.subject.entity_type if fact.subject else None,
            fact.subject.entity_id if fact.subject else None,
        )
        if evidence_map[fact.evidence_id].tool_name == "compare_suppliers":
            key = (fact.evidence_id, "ranking", int(fact.pointer.split("/")[2]) // 5)
        groups[key].append(fact)
    drafts = []
    evidence_map = {e.evidence_id: e for e in evidence}
    for (eid, _, _), group in groups.items():
        for offset in range(0, len(group), 8):
            facts = group[offset : offset + 8]
            source = evidence_map[eid]
            metrics = [f for f in facts if f.kind == "metric"]
            docs = [f for f in facts if f.kind == "document"]
            links = [f for f in facts if f.kind == "relationship"]
            common = {
                "quality_profile": "references",
                "claim_type": "observation",
                "text": "The recorded observations support these scoped analytical facts.",
                "evidence_ids": list(
                    dict.fromkeys(
                        [eid] + [f.subject_evidence_id for f in facts if f.subject_evidence_id]
                    )
                ),
                "entity_refs": [],
                "metric_refs": [{"evidence_id": eid, "pointer": f.pointer} for f in metrics[:8]],
                "relationship_refs": [
                    {"evidence_id": eid, "pointer": f.pointer} for f in links[:8]
                ],
                "citation_ids": [f.value["citation"]["citation_id"] for f in docs],
                "quote_citation_ids": [f.value["citation"]["citation_id"] for f in docs[:2]],
            }
            refs = {
                (f.subject_evidence_id, f.subject_pointer) for f in facts if f.subject_evidence_id
            }
            common["entity_refs"] = [{"evidence_id": e, "pointer": p} for e, p in sorted(refs)]
            if source.tool_name == "compare_suppliers":
                common.update(
                    claim_type="ranking",
                    text="Suppliers are ordered by the requested observed metric.",
                )
            elif links:
                common.update(
                    claim_type="association",
                    text="The records contain explicit operational links; "
                    "association alone does not establish causation.",
                )
            if docs:
                common.update(
                    claim_type="policy_requirement"
                    if docs[0].value["metadata"]["document_type"] == "policy"
                    else "observation",
                    text="The registered source provides the quoted terms and qualifications.",
                )
            drafts.append(common)
    # Verify all selections with the original independent numeric/source validator.
    findings, citations = [], {}
    for offset in range(0, len(drafts), 8):
        batch = drafts[offset : offset + 8]
        _, verified, cited = verify_final(
            __import__("json").dumps(
                {
                    "quality_profile": "references",
                    "status": "completed",
                    "findings": batch,
                    "limitations": [],
                    "follow_up_questions": [],
                }
            ),
            evidence,
            db,
            plan.intent.as_of,
        )
        findings.extend(verified)
        citations.update({c["citation_id"]: c for c in cited})
    for fact in graph.facts:
        fact.verified = True
    return findings, list(citations.values())


def target_comparisons(graph):
    """Predicate over authoritative values only; no recalculation of KPI or gap."""
    result = []
    for subject in {
        f.subject.entity_id
        for f in graph.facts
        if f.subject and f.subject.entity_type == "supplier"
    }:
        facts = [
            f
            for f in graph.facts
            if f.subject and f.subject.entity_type == "supplier" and f.subject.entity_id == subject
        ]
        for target in [f for f in facts if f.value.get("metric") == "target_percent"]:
            parent = target.pointer.rsplit("/", 1)[0]
            actual = next(
                (
                    f
                    for f in facts
                    if f.evidence_id == target.evidence_id
                    and f.pointer == parent + "/observed_percent"
                ),
                None,
            )
            if actual and actual.value["value"] is not None and target.value["value"] is not None:
                a, b = Decimal(str(actual.value["value"])), Decimal(str(target.value["value"]))
                result.append(
                    {
                        "subject": actual.subject,
                        "relation": "below" if a < b else "above" if a > b else "equal to",
                        "fact_ids": [actual.fact_id, target.fact_id],
                    }
                )
    return result
