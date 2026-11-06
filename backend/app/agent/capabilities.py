"""A bounded model-selected catalogue, never a keyword/business-question dispatcher."""

import json
from typing import Literal

from app.agent.contracts import AgentError, Strict
from app.agent.tools import TOOLS
from app.analytics.registry import REGISTRY
from pydantic import Field, ValidationError


class Selection(Strict):
    mode: Literal["investigate", "explain", "refuse"] = Field(
        description="investigate: read recorded business facts, compare or retrieve sources; "
        "explain: explain a documented procedure; refuse: explicit prohibited execution only, "
        "with empty tools, document_types and metric_names. Missing data is not a refusal."
    )
    tools: list[str] = Field(max_length=6)
    document_types: list[Literal["supplier_agreement", "policy"]] = Field(max_length=2)
    parameters: Literal["standard", "advanced"] = "standard"
    metric_names: list[str] = Field(default_factory=list, max_length=8)


METRIC_NAMES = sorted({name.rsplit(".", 1)[-1] for name in REGISTRY} | {"*"})


def selection_schema():
    schema = Selection.model_json_schema()
    schema["properties"]["tools"]["items"]["enum"] = list(TOOLS)
    schema["properties"]["metric_names"]["items"]["enum"] = METRIC_NAMES
    return schema


def parse_selection(raw):
    try:
        selection = Selection.model_validate_json(raw, strict=True)
    except ValidationError as exc:
        raise AgentError("invalid_capability_selection", "Invalid capability selection.") from exc
    if any(name not in TOOLS for name in selection.tools) or (
        selection.mode != "refuse" and not selection.tools
    ):
        raise AgentError("invalid_capability_selection", "Choose available read-only capabilities.")
    if any(name not in METRIC_NAMES for name in selection.metric_names):
        raise AgentError("invalid_capability_selection", "Choose registered metric names only.")
    if selection.mode == "refuse" and (
        selection.tools or selection.document_types or selection.metric_names
    ):
        raise AgentError(
            "invalid_capability_selection", "Refusal contradicts selected business capabilities."
        )
    return selection


def catalogue():
    return [
        {
            "name": tool.name,
            "answers": tool.description,
            "required_arguments": [
                k for k, v in tool.arguments.model_fields.items() if v.is_required()
            ],
        }
        for tool in TOOLS.values()
    ]


def source_coverage(evidence, required):
    found = set()
    contract_suppliers = set()
    supplier_ids = {
        e["arguments"]["supplier_id"]
        for e in evidence.values()
        if e["tool_name"] == "get_supplier_performance"
    }

    def walk(value):
        if isinstance(value, dict):
            metadata = value.get("metadata")
            if isinstance(metadata, dict):
                kind = metadata.get("document_type")
                if kind == "supplier_agreement":
                    contract_suppliers.add(metadata.get("supplier_id"))
                if kind:
                    found.add(kind)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for e in evidence.values():
        walk(e["payload"])
    missing = set(required) - found
    if "supplier_agreement" in required and not supplier_ids <= contract_suppliers:
        missing.add("supplier_agreement")
    return {
        "required_document_types": sorted(required),
        "found_document_types": sorted(found),
        "missing_document_types": sorted(missing),
    }


def expansion(raw, enabled):
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(value, dict) or set(value) != {"need_tools"}:
        return None
    names = value["need_tools"]
    if (
        not isinstance(names, list)
        or not 1 <= len(names) <= 6
        or any(not isinstance(n, str) or n not in TOOLS for n in names)
    ):
        raise AgentError(
            "invalid_capability_selection", "Expansion can select registered tools only."
        )
    if not enabled:
        raise AgentError(
            "capability_expansion_limit", "The single capability expansion is exhausted."
        )
    return set(names)
