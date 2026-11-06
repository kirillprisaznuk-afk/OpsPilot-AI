"""Lossless model transport projection; canonical evidence stays on the server."""

import hashlib
import json


def project_payload(payload, metric_names=None):
    definitions = {}
    omitted_names = set()
    selected = set(metric_names or [])

    def walk(value):
        if isinstance(value, list):
            return [walk(child) for child in value]
        if not isinstance(value, dict):
            return value
        if {"metric", "value", "unit", "time_basis", "grain"} <= value.keys():
            metadata = {k: value[k] for k in ("time_basis", "grain", "limitations") if k in value}
            encoded = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
            key = hashlib.sha256(encoded.encode()).hexdigest()[:16]
            if key in definitions and definitions[key] != metadata:
                raise ValueError("Metric definition collision")
            definitions[key] = metadata
            return {
                **{k: walk(v) for k, v in value.items() if k not in metadata},
                "definition_ref": key,
            }
        result = {}
        for key, child in value.items():
            if key == "metrics" and isinstance(child, dict) and selected and "*" not in selected:
                visible = {}
                for name, metric in child.items():
                    identifier = metric.get("metric", name) if isinstance(metric, dict) else name
                    if (
                        name in selected
                        or identifier in selected
                        or identifier.rsplit(".", 1)[-1] in selected
                    ):
                        visible[name] = walk(metric)
                    else:
                        omitted_names.add(name)
                result[key] = visible
            else:
                result[key] = walk(child)
        return result

    result = walk(payload)
    if definitions:
        if "metric_definitions" in result:
            raise ValueError("Reserved projection key")
        result["metric_definitions"] = definitions
    if omitted_names:
        result["agent_view"] = {
            "selected_metric_names": sorted(selected),
            "additional_metric_names": sorted(omitted_names),
            "notice": "Other metric columns remain in canonical API evidence. "
            "Use metric_names expansion to display them. No source text or selected metric "
            "qualifications, denominators, units, nulls or periods were removed.",
        }
    return result


def restore_payload(projected):
    """Resolve every fact/definition exactly; also used for independent round-trip tests."""
    definitions = projected.get("metric_definitions", {})
    if "agent_view" in projected:
        raise ValueError("Focused views resolve omitted columns from canonical evidence.")

    def walk(value):
        if isinstance(value, list):
            return [walk(child) for child in value]
        if not isinstance(value, dict):
            return value
        result = {key: walk(child) for key, child in value.items() if key != "definition_ref"}
        if "definition_ref" in value:
            result.update(definitions[value["definition_ref"]])
        return result

    return walk({k: v for k, v in projected.items() if k != "metric_definitions"})
