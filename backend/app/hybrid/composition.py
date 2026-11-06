"""Business presentation of verified runtime facts; no evaluation answers or calculations."""

from app.hybrid.evidence import target_comparisons


def metric_text(fact):
    metric = fact.value
    label = metric["metric"].replace(".", ": ").replace("_", " ").capitalize()
    value = metric.get("value")
    unit = metric["unit"].replace("_", " ")
    if value is None:
        result = f"{label}: {metric.get('status', 'unavailable')} (no numeric value)"
    else:
        result = f"{label}: {value}" + ("%" if unit == "percent" else f" {unit}")
    if metric.get("denominator") is not None:
        result += f"; numerator {metric.get('numerator')}, denominator {metric['denominator']}"
    if fact.window:
        result += (
            f"; period {fact.window['observation_start']} to {fact.window['observation_end']}, "
            f"as of {fact.window['as_of']}"
        )
    if metric.get("limitations"):
        result += "; " + " ".join(metric["limitations"])
    return result + f" [{fact.evidence_id}:{fact.pointer}]"


def compose(response):
    # Failed independent verification must never leak selected facts into prose.
    graph = response.evidence_graph.model_copy(
        update={"facts": [f for f in response.evidence_graph.facts if f.verified]}
    )
    if response.status == "refused":
        return (
            "This request asks for execution outside the read-only business capabilities. "
            "No action was performed."
        )
    if response.status == "clarification_required":
        return "Clarification required: " + " ".join(
            response.follow_up_questions or response.limitations
        )
    parts = []
    if response.operating_mode == "DETERMINISTIC" or response.execution.fallback_used:
        parts.append("Evidence-based analytical response; local language synthesis is limited.")
    if response.language_interpretation:
        parts.append(
            "Local interpretation selected relevant verified evidence; factual wording "
            "and quantities below are rendered by the server."
        )
    if (
        response.interpretation
        and any(o.capability == "recorded_costs" for o in response.interpretation.objectives)
        and graph.facts
    ):
        parts.append(
            "Financial values describe recorded costs or exposure. "
            "Unrecorded loss and profit remain unknown."
        )
    if response.interpretation and response.interpretation.unsupported_concept:
        parts.append(
            "The requested conclusion is not established by analytics or retrieved evidence. "
            "No unsupported quantity, legal conclusion or automatic penalty is asserted."
        )
    rank_evidence = {
        e.evidence_id: e for e in response.evidence if e.tool_name == "compare_suppliers"
    }
    for eid, evidence in rank_evidence.items():
        if not any(f.kind == "metric" and f.evidence_id == eid for f in graph.facts):
            continue
        parts.append(
            f"Supplier ranking by {evidence.arguments['sort'].replace('_', ' ')} "
            f"({evidence.arguments['direction']}); complete scoped population: "
            f"{evidence.payload['total_segments']}. Undefined values are last; "
            "ties retain supplier identity order."
        )
        for entity in [
            s
            for f in response.key_findings
            for s in f.entities
            if s.get("rank") and s["evidence_id"] == eid
        ]:
            parts.append(
                f"{entity['rank']}. {entity.get('label')} (supplier {entity['entity_id']})"
            )
            parts.extend(
                metric_text(fact)
                for fact in graph.facts
                if fact.evidence_id == eid
                and fact.subject
                and fact.subject.entity_id == entity["entity_id"]
            )
    for subject in response.resolved_entities:
        facts = [
            f
            for f in graph.facts
            if f.subject
            and f.subject.entity_type == subject.entity_type
            and f.subject.entity_id == subject.entity_id
            and f.evidence_id not in rank_evidence
            and f.kind == "metric"
        ]
        if facts:
            parts.append(
                f"{subject.entity_type.replace('_', ' ').title()}: "
                f"{subject.label} (ID {subject.entity_id})"
            )
            parts.extend(metric_text(f) for f in facts)
    parts.extend(
        metric_text(f)
        for f in graph.facts
        if f.kind == "metric" and not f.subject and f.evidence_id not in rank_evidence
    )
    for comparison in target_comparisons(graph):
        parts.append(
            f"{comparison['subject'].label}: observed supplier delivery performance is "
            f"{comparison['relation']} the applicable target. This is an operational "
            "comparison; legal breach is not established."
        )
    linked = [f for f in graph.facts if f.kind == "relationship"]
    if linked:
        importance = {
            "sole_recorded_late_replenishment": 0,
            "expected_replenishment_association": 1,
            "recorded_shortage": 2,
            "physically_received": 3,
            "dispatched_quantity": 4,
            "explicit_recorded_cost": 5,
            "affected_entity": 6,
            "dispatch_location": 7,
        }
        linked.sort(
            key=lambda f: (
                importance.get(f.value["relationship_type"], 8),
                f.value["event_time"],
                f.fact_id,
            )
        )
        parts.append(
            "Operational links below are observed associations. A simulated_causal_chain "
            "label describes a modelled dataset scenario; it is not universal causal proof. "
            "Supplier purchase obligations and customer sales dispatch promises remain separate."
        )
        if len(linked) > 12:
            parts.append(
                "The following links are a presentation sample; all retrieved verified "
                "links and their provenance remain in the evidence graph."
            )
        for fact in linked[:12]:
            value = fact.value
            measures = ""
            if value.get("quantity") is not None:
                measures += f" quantity {value['quantity']} units;"
            if value.get("amount_gbp") is not None:
                measures += f" recorded amount {value['amount_gbp']} GBP;"
            parts.append(
                f"{value['entity_type']} {value['entity_id']} -> "
                f"{value['related_entity_type']} {value['related_entity_id']}: "
                f"{value['relationship_type']} ({value['evidence_class']}); "
                f"observed {value['event_time']};{measures} source {value['source_reference']}."
            )
    for fact in [f for f in graph.facts if f.kind == "document"]:
        value = fact.value
        metadata, citation = value["metadata"], value["citation"]
        parts.append(
            f"Source {metadata['code']}: {metadata['title']}; {metadata['document_type']}; "
            f"effective {metadata['effective_on']}. Citation {citation['citation_id']}."
        )
        parts.append("Verified source excerpt (untrusted document content):\n" + value["text"])
    if response.interpretation and response.interpretation.causality == "universal":
        parts.append(
            "These bounded linked records do not establish that the supplier caused every "
            "shortage. Universal causation is not proven."
        )
    if not graph.facts:
        parts.append(
            "The evidence does not establish the requested facts. "
            "No missing or undefined value is presented as zero."
        )
    if response.limitations:
        parts.append("Limitations: " + " ".join(dict.fromkeys(response.limitations)))
    return "\n\n".join(parts)
