"""Explicit capabilities only. No model-selected code, SQL, URLs or filesystem paths."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.agent.contracts import AgentError, Strict
from app.agent.ranking import compare_suppliers
from app.analytics import (
    finance,
    fulfilment,
    incidents,
    insights,
    inventory,
    overview,
    procurement,
    relationships,
    suppliers,
    warehouses,
    workforce,
)
from app.analytics.contracts import (
    AnalyticsQuery,
    AnalyticsReport,
    InsightReport,
    Investigation,
    InvestigationQuery,
)
from app.knowledge import citations, context, search, service
from app.knowledge.contracts import (
    CitationPreview,
    ContextRequest,
    ContextResponse,
    SearchRequest,
    SearchResponse,
    SourcePreview,
)
from openai import pydantic_function_tool
from pydantic import Field
from sqlalchemy import text


class AnalyticsArgs(AnalyticsQuery):
    limit: int = Field(5, ge=1, le=100)
    include_trends: bool = False
    include_comparison: bool = False


class SupplierArgs(Strict):
    supplier_id: int = Field(gt=0, le=2147483647)
    query: AnalyticsArgs = Field(default_factory=AnalyticsArgs)


class AgentInvestigationQuery(InvestigationQuery):
    limit: int = Field(25, ge=1, le=100)
    include_trends: bool = False
    include_comparison: bool = False


class InvestigationArgs(Strict):
    entity_type: Literal[
        "supplier",
        "purchase_order",
        "sales_order",
        "shortage",
        "warehouse",
        "incident",
        "invoice",
        "department",
        "task",
        "product",
    ]
    entity_id: int = Field(gt=0, le=2147483647)
    query: AgentInvestigationQuery = Field(default_factory=AgentInvestigationQuery)


class KnowledgeArgs(SearchRequest):
    top_k: int = Field(5, ge=1, le=8)


class ContextArgs(ContextRequest):
    top_k: int = Field(5, ge=1, le=8)
    context_budget: int = Field(4096, ge=128, le=8192)


class PreviewArgs(Strict):
    document_id: int = Field(gt=0, le=2147483647)
    version_id: int | None = Field(None, gt=0, le=2147483647)
    as_of: date = date(2026, 9, 30)


class CitationArgs(Strict):
    citation_id: str = Field(pattern=r"^kc_[a-f0-9]{64}$")


class EntityArgs(Strict):
    entity_type: Literal[
        "supplier",
        "warehouse",
        "department",
        "incident",
        "purchase_order",
        "sales_order",
        "task",
        "product",
        "employee",
        "customer",
        "invoice",
        "shortage",
    ]
    term: str = Field(min_length=1, max_length=150)
    as_of: date = date(2026, 9, 30)


class EntityMatch(Strict):
    entity_type: str
    entity_id: int
    name: str


class EntityResult(Strict):
    status: Literal["resolved", "ambiguous", "not_found"]
    matches: list[EntityMatch]
    total_matches: int
    truncated: bool


def resolve_entity(db, args):
    tables = {
        "supplier": ("suppliers", "name"),
        "warehouse": ("warehouses", "name"),
        "department": ("departments", "name"),
        "product": ("products", "name"),
        "employee": ("employees", "name"),
        "customer": ("customers", "name"),
        "invoice": ("supplier_invoices", None),
        "shortage": ("shortages", None),
        "incident": ("incidents", None),
        "purchase_order": ("purchase_orders", None),
        "sales_order": ("sales_orders", None),
        "task": ("tasks", "title"),
    }
    table, label = tables[args.entity_type]
    if not label and not args.term.isdecimal():
        return EntityResult(status="not_found", matches=[], total_matches=0, truncated=False)
    params = {"term": args.term, "as_of": args.as_of}
    if args.term.isdecimal():
        condition = "id=:id"
        params["id"] = int(args.term)
        if params["id"] > 2147483647:
            return EntityResult(status="not_found", matches=[], total_matches=0, truncated=False)
    else:
        condition = f"strpos(lower({label}),lower(:term))>0"
    display = label or "CAST(id AS text)"
    rows = (
        db.execute(
            text(
                f"SELECT id,{display} name,count(*) OVER() total FROM {table} "
                f"WHERE {condition} AND created_at < CAST(:as_of AS date)"
                "+interval '1 day' ORDER BY id LIMIT 20"
            ),
            params,
        )
        .mappings()
        .all()
    )
    exact = [r for r in rows if str(r["name"]).casefold() == args.term.casefold()]
    selected = exact if len(exact) == 1 else rows
    total = 1 if len(exact) == 1 else int(rows[0]["total"]) if rows else 0
    return EntityResult(
        status="resolved" if total == 1 else "ambiguous" if total else "not_found",
        matches=[
            EntityMatch(entity_type=args.entity_type, entity_id=r["id"], name=r["name"])
            for r in selected
        ],
        total_matches=total,
        truncated=total > len(selected),
    )


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments: type
    response: type
    execute: object
    permission: str = "read_business_and_synthetic_knowledge"

    def declaration(self):
        function = dict(
            pydantic_function_tool(self.arguments, name=self.name, description=self.description)[
                "function"
            ]
        )

        def clean(value):
            if isinstance(value, dict):
                value.pop("default", None)
                for v in value.values():
                    clean(v)
            elif isinstance(value, list):
                for v in value:
                    clean(v)

        clean(function)
        return {"type": "function", **function}


def supplier_tool(db, args):
    result = suppliers.get_suppliers(db, args.query, args.supplier_id)
    if result is None:
        raise AgentError("entity_not_found", "Supplier does not exist.")
    return result


def investigation_tool(db, args):
    result = relationships.investigate(db, args.entity_type, args.entity_id, args.query)
    if result is None:
        raise AgentError("entity_not_found", "Investigation entity does not exist.")
    return result


TOOLS = {
    t.name: t
    for t in [
        Tool(
            "resolve_business_entity",
            (
                "Resolve names or numeric IDs using actual records. Multiple "
                "matches require clarification. Order/incident references are "
                "numeric IDs; do not invent reference formats."
            ),
            EntityArgs,
            EntityResult,
            resolve_entity,
        ),
        Tool(
            "get_enterprise_overview",
            "Executive operations metrics with explicit units and observation window.",
            AnalyticsArgs,
            AnalyticsReport,
            overview.get_overview,
        ),
        Tool(
            "get_procurement_performance",
            "Aggregate PURCHASING: Northstar buys from suppliers. Purchase cohorts, receipts "
            "and commitments; supplier rankings use compare_suppliers, not warehouse groups.",
            AnalyticsArgs,
            AnalyticsReport,
            procurement.get_procurement,
        ),
        Tool(
            "compare_suppliers",
            (
                "Rank SUPPLIERS using Stage 2 metrics. on_time_rate asc finds weak punctuality; "
                "overdue_outstanding_orders desc counts overdue orders; overdue_commitment desc "
                "ranks overdue GBP exposure. These are different measures. Preserve denominators "
                "and windows; small observation counts limit conclusions."
            ),
            AnalyticsArgs,
            AnalyticsReport,
            compare_suppliers,
        ),
        Tool(
            "get_supplier_performance",
            (
                "Detail ONE supplier's purchase performance, due-order volumes and effective SLA "
                "targets owed to Northstar. Not customer dispatch terms. Below target is an "
                "operational concern, not established legal breach. Ranking uses compare_suppliers."
            ),
            SupplierArgs,
            AnalyticsReport,
            supplier_tool,
        ),
        Tool(
            "get_inventory_status",
            "Ledger stock, receipts, dispatches and shortage exposure; no reservations.",
            AnalyticsArgs,
            AnalyticsReport,
            inventory.get_inventory,
        ),
        Tool(
            "get_warehouse_performance",
            "Warehouse inventory, delays, incidents and recorded costs; no invented utilization.",
            AnalyticsArgs,
            AnalyticsReport,
            warehouses.get_warehouses,
        ),
        Tool(
            "get_customer_fulfilment",
            "Aggregate SALES: Northstar's dispatch promises to customers, partial fulfilment "
            "and overdue demand. A specific customer order uses investigate_business_entity "
            "with entity_type sales_order. Supplier SLAs do not define customer promises.",
            AnalyticsArgs,
            AnalyticsReport,
            fulfilment.get_fulfilment,
        ),
        Tool(
            "get_operational_costs",
            (
                "Exact GBP invoice exposure, payments and explicitly attributed "
                "additional costs; no profit or recovered penalties."
            ),
            AnalyticsArgs,
            AnalyticsReport,
            finance.get_finance,
        ),
        Tool(
            "get_workforce_tasks",
            (
                "Owned task workload and observed completion history. Not an "
                "employee productivity score."
            ),
            AnalyticsArgs,
            AnalyticsReport,
            workforce.get_workforce,
        ),
        Tool(
            "get_operational_incidents",
            (
                "Incident cohorts by supported category, department or warehouse. No order_id "
                "filter: investigate_business_entity links specific orders. Historical escalation "
                "may be unavailable; association does not prove cause."
            ),
            AnalyticsArgs,
            AnalyticsReport,
            incidents.get_incidents,
        ),
        Tool(
            "get_deterministic_insights",
            "Transparent backend threshold signals, not a substitute for deeper investigation.",
            AnalyticsArgs,
            InsightReport,
            insights.get_insights,
        ),
        Tool(
            "investigate_business_entity",
            (
                "Investigate an explicit entity_type and numeric entity_id. sales_order is a "
                "customer purchase from Northstar; purchase_order is Northstar buying from a "
                "supplier. Bound source-record relationships, not automatic causal proof. Narrow "
                "Use only for linked event investigations, not routine supplier SLA comparison. "
                "tasks/costs/receipts/incident selectors preserve direct "
                "attribution; all-graph associations are not costs or proven "
                "causes."
            ),
            InvestigationArgs,
            Investigation,
            investigation_tool,
        ),
        Tool(
            "search_corporate_knowledge",
            (
                "Retrieve actual effective contracts or internal policies. Default hybrid; "
                "natural-language query and optional typed filters. Contract scope uses supplier "
                "metadata; general policy has separate scope. Returned passages already include "
                "verified citations and full section qualifications. No match is not a tool error."
            ),
            KnowledgeArgs,
            SearchResponse,
            search.search,
        ),
        Tool(
            "build_knowledge_context",
            (
                "Build a bounded verified source context with untrusted-data "
                "metadata, without generating an answer."
            ),
            ContextArgs,
            ContextResponse,
            context.build_context,
        ),
        Tool(
            "get_document_details",
            "Preview a KNOWN registered document_id/version only if retrieved passages lack "
            "needed detail. Search already returns verified passages; avoid redundant previews. "
            "No path inputs; dates must match this run.",
            PreviewArgs,
            SourcePreview,
            lambda db, a: service.preview(db, a.document_id, a.version_id, a.as_of),
        ),
        Tool(
            "resolve_source_citation",
            "Resolve an actual registered chunk citation and verify original source lines/hash.",
            CitationArgs,
            CitationPreview,
            lambda db, a: citations.resolve(db, a.citation_id),
        ),
    ]
}
