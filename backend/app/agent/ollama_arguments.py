"""Explicit native wire contracts, translated into unchanged application contracts."""

import copy
import json

from app.agent.contracts import Strict
from app.agent.tools import TOOLS, AgentInvestigationQuery, AnalyticsArgs
from pydantic import Field, ValidationError, create_model


def wire_model(name, base, fields):
    original = TOOLS[name].arguments.model_fields
    return create_model(
        "Ollama" + TOOLS[name].arguments.__name__,
        __base__=base,
        **{key: (original[key].annotation, copy.deepcopy(original[key])) for key in fields},
    )


WIRE_MODELS = {
    "get_supplier_performance": wire_model(
        "get_supplier_performance", AnalyticsArgs, ("supplier_id",)
    ),
    "investigate_business_entity": wire_model(
        "investigate_business_entity", AgentInvestigationQuery, ("entity_type", "entity_id")
    ),
}
ROOT_FIELDS = {
    "get_supplier_performance": ("supplier_id",),
    "investigate_business_entity": ("entity_type", "entity_id"),
}


def argument_schema(name):
    return WIRE_MODELS.get(name, TOOLS[name].arguments).model_json_schema()


def standard_model(name):
    model = WIRE_MODELS.get(name, TOOLS[name].arguments)
    hidden = {
        "as_of",
        "start_date",
        "end_date",
        "include_trends",
        "include_comparison",
        "offset",
        "product_category",
        "supplier_category",
        "incident_category",
        "priority",
    }
    fields = {}
    for key, info in model.model_fields.items():
        if key in hidden:
            continue
        value = copy.deepcopy(info)
        if key == "limit":
            maximum = 25 if name == "investigate_business_entity" else 5
            value = Field(
                maximum,
                ge=1,
                le=maximum,
                description=f"Bounded page, at most {maximum} records. "
                "Expand to advanced parameters for larger pages.",
            )
        fields[key] = (info.annotation, value)
    return create_model("Standard" + model.__name__, __base__=Strict, **fields)


def standard_error(name, values):
    if name not in TOOLS:
        return None
    try:
        standard_model(name).model_validate_json(json.dumps(values), strict=True)
    except ValidationError as exc:
        return {
            "fields": [
                {"path": "/".join(map(str, e["loc"])), "kind": e["type"]}
                for e in exc.errors(include_input=False, include_url=False)[:8]
            ],
            "hint": "Standard mode omits date/advanced options and caps pages at five. "
            "Use omitted defaults or explicitly request advanced_parameters expansion.",
        }
    return None


def canonical_arguments(name, values):
    if name not in WIRE_MODELS:
        return values
    try:
        parsed = WIRE_MODELS[name].model_validate_json(json.dumps(values), strict=True)
    except ValidationError:
        # Never discard unknown fields or repair invalid values. The canonical
        # gateway will return its normal structured validation error.
        return values
    data = {key: value for key, value in parsed.model_dump(mode="json").items() if key in values}
    result = {key: data.pop(key) for key in ROOT_FIELDS[name]}
    return {**result, "query": data}


def history_arguments(name, values):
    if name not in WIRE_MODELS or not isinstance(values.get("query"), dict):
        return values
    root = {key: values[key] for key in ROOT_FIELDS[name] if key in values}
    query = dict(values["query"])
    for key, value in root.items():
        if key in query and query[key] not in (None, value):
            return values
        query.pop(key, None)
    return {**query, **root}
