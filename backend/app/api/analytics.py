from typing import Annotated, Literal

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
from app.api.routes import DB
from fastapi import APIRouter, HTTPException, Path, Query

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])
Parameters = Annotated[AnalyticsQuery, Query()]
EntityID = Annotated[int, Path(gt=0, le=2147483647)]
EntityType = Literal[
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


@router.get("/overview", response_model=AnalyticsReport)
def get_overview(db: DB, query: Parameters):
    return overview.get_overview(db, query)


@router.get("/procurement", response_model=AnalyticsReport)
def get_procurement(db: DB, query: Parameters):
    return procurement.get_procurement(db, query)


@router.get("/suppliers", response_model=AnalyticsReport)
def get_suppliers(db: DB, query: Parameters):
    return suppliers.get_suppliers(db, query)


@router.get("/suppliers/{supplier_id}", response_model=AnalyticsReport)
def get_supplier(db: DB, supplier_id: EntityID, query: Parameters):
    result = suppliers.get_suppliers(db, query, supplier_id)
    if result is None:
        raise HTTPException(404, detail={"code": "not_found", "entity": "supplier"})
    return result


@router.get("/inventory", response_model=AnalyticsReport)
def get_inventory(db: DB, query: Parameters):
    return inventory.get_inventory(db, query)


@router.get("/warehouses", response_model=AnalyticsReport)
def get_warehouses(db: DB, query: Parameters):
    return warehouses.get_warehouses(db, query)


@router.get("/fulfilment", response_model=AnalyticsReport)
def get_fulfilment(db: DB, query: Parameters):
    return fulfilment.get_fulfilment(db, query)


@router.get("/finance", response_model=AnalyticsReport)
def get_finance(db: DB, query: Parameters):
    return finance.get_finance(db, query)


@router.get("/workforce", response_model=AnalyticsReport)
def get_workforce(db: DB, query: Parameters):
    return workforce.get_workforce(db, query)


@router.get("/incidents", response_model=AnalyticsReport)
def get_incidents(db: DB, query: Parameters):
    return incidents.get_incidents(db, query)


@router.get("/insights", response_model=InsightReport)
def get_insights(db: DB, query: Parameters):
    return insights.get_insights(db, query)


@router.get("/investigations/{entity_type}/{entity_id}", response_model=Investigation)
def get_investigation(
    db: DB,
    entity_type: EntityType,
    entity_id: EntityID,
    query: Annotated[InvestigationQuery, Query()],
):
    result = relationships.investigate(db, entity_type, entity_id, query)
    if result is None:
        raise HTTPException(404, detail={"code": "not_found", "entity": entity_type})
    return result
