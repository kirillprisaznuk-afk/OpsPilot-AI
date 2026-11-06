import asyncio
import json
import threading
import time
from datetime import UTC, date, datetime, timedelta

from app.agent.contracts import AgentError
from app.agent.database import agent_session, verify_reader
from app.agent.grounding import citation_map
from app.agent.tools import TOOLS
from app.agent.views import project_payload
from app.analytics.common import AnalyticsInputError
from app.knowledge.contracts import SearchRequest
from app.knowledge.embeddings import KnowledgeError
from app.knowledge.search import eligible_documents
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

ENTITY_TABLES = {
    "supplier_id": "suppliers",
    "warehouse_id": "warehouses",
    "department_id": "departments",
    "employee_id": "employees",
    "product_id": "products",
    "contract_id": "supplier_contracts",
    "document_id": "documents",
    "version_id": "document_versions",
}
ROOT_TABLES = {
    "supplier": "suppliers",
    "warehouse": "warehouses",
    "department": "departments",
    "purchase_order": "purchase_orders",
    "sales_order": "sales_orders",
    "incident": "incidents",
    "invoice": "supplier_invoices",
    "shortage": "shortages",
    "task": "tasks",
    "product": "products",
}


def validate_entities(db, args, as_of):
    cutoff = datetime.combine(as_of + timedelta(days=1), datetime.min.time(), UTC)

    def check(table, identifier):
        exists = db.scalar(
            text(f"SELECT EXISTS(SELECT 1 FROM {table} WHERE id=:id AND created_at<:cutoff)"),
            {"id": identifier, "cutoff": cutoff},
        )
        if not exists:
            raise AgentError(
                "entity_not_found", "Entity does not exist in the selected observation scope."
            )

    def visit(value):
        if not isinstance(value, dict):
            return
        for name, item in value.items():
            if name in ENTITY_TABLES and item is not None:
                check(ENTITY_TABLES[name], item)
            elif isinstance(item, dict):
                visit(item)

    values = args.model_dump(mode="json")
    visit(values)
    if "entity_id" in values:
        check(ROOT_TABLES[values["entity_type"]], values["entity_id"])


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field.")
        result[key] = value
    return result


def parse_arguments(name, raw, as_of):
    if name not in TOOLS:
        raise AgentError("unknown_tool", "Tool is not in the approved read-only registry.")
    if len(raw.encode()) > 12000:
        raise AgentError("invalid_arguments", "Arguments exceed the size limit.")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=unique_object,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        if not isinstance(value, dict):
            raise ValueError()
        model = TOOLS[name].arguments
        target = value.get("query") if isinstance(value.get("query"), dict) else value
        target_model = model.model_fields.get("query")
        has_asof = "as_of" in model.model_fields or (
            target_model
            and target_model.annotation
            and hasattr(target_model.annotation, "model_fields")
            and "as_of" in target_model.annotation.model_fields
        )
        if has_asof:
            if (
                target is value
                and "query" in model.model_fields
                and hasattr(target_model.annotation, "model_fields")
            ):
                value.setdefault("query", {})
                target = value["query"]
            if "as_of" in target and target["as_of"] != str(as_of):
                raise AgentError(
                    "incompatible_observation_window",
                    "Tool as_of must match the established request cutoff.",
                )
            target.setdefault("as_of", str(as_of))
        args = model.model_validate_json(json.dumps(value), strict=True)
    except ValidationError as exc:
        fields = [
            {"path": "/".join(str(part)[:40] for part in error["loc"]), "kind": error["type"]}
            for error in exc.errors(include_input=False, include_url=False, include_context=False)[
                :8
            ]
        ]
        raise AgentError(
            "invalid_arguments",
            "Correct the listed fields using the declared schema; do not "
            "change the requested entity or observation period.",
            details={"fields": fields},
        ) from exc
    except (ValueError, TypeError, RecursionError) as exc:
        raise AgentError("invalid_arguments", "Tool arguments failed the declared schema.") from exc
    return args


class Cancellation:
    def __init__(self):
        self.event = threading.Event()
        self.connection = None

    def cancel(self):
        self.event.set()
        connection = self.connection
        if connection:
            try:
                connection.cancel()
            except Exception:
                pass


class ToolExecutor:
    def __init__(self, settings, bind=None):
        self.settings, self.bind = settings, bind

    def worker(self, name, args, cancellation, timeout, as_of):
        try:
            with agent_session(timeout, cancellation, self.bind) as db:
                verify_reader(db)
                validate_entities(db, args, as_of)
                if cancellation.event.is_set():
                    raise AgentError("tool_cancelled", "Tool was cancelled.")
                result = TOOLS[name].execute(db, args)
                payload = TOOLS[name].response.model_validate(result).model_dump(mode="json")
                cited = citation_map(payload)
                preview = (
                    payload.get("metadata", {}).get("version_id")
                    if name == "get_document_details"
                    else None
                )
                if cited or preview:
                    active = {
                        m["version_id"]
                        for m in eligible_documents(
                            db, SearchRequest(query="source scope", as_of=as_of)
                        )
                    }
                    if any(c["document_version_id"] not in active for c in cited.values()) or (
                        preview and preview not in active
                    ):
                        raise AgentError(
                            "source_not_applicable",
                            "Source version is not effective at the request cutoff.",
                        )
                if cancellation.event.is_set():
                    raise AgentError("tool_cancelled", "Tool was cancelled.")
                transport = (
                    project_payload(payload)
                    if self.settings.llm_provider == "ollama"
                    and self.settings.ollama_compact_transport
                    else payload
                )
                if (
                    len(json.dumps(transport, ensure_ascii=False).encode())
                    > self.settings.agent_result_bytes
                ):
                    raise AgentError(
                        "tool_result_limit",
                        "Result exceeds the safe size; request a narrower filter or page.",
                    )
                return payload
        except ValidationError as exc:
            raise AgentError(
                "invalid_tool_output", "Tool returned an invalid response contract."
            ) from exc
        except (AnalyticsInputError, KnowledgeError) as exc:
            raise AgentError("tool_input_or_source_error", str(exc)) from exc
        except SQLAlchemyError as exc:
            raise AgentError(
                "tool_database_error", "Read-only database tool is unavailable."
            ) from exc

    async def run(self, name, args, remaining, as_of=None):
        cancellation = Cancellation()
        timeout = min(remaining, self.settings.agent_tool_timeout_seconds)
        started = time.perf_counter()
        as_of = as_of or getattr(
            args, "as_of", getattr(getattr(args, "query", None), "as_of", date(2026, 9, 30))
        )
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self.worker, name, args, cancellation, timeout, as_of), timeout
            )
            return result, 1000 * (time.perf_counter() - started)
        except TimeoutError as exc:
            cancellation.cancel()
            raise AgentError("tool_timeout", "Tool exceeded its execution deadline.") from exc
        except asyncio.CancelledError:
            cancellation.cancel()
            raise
