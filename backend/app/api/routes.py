from typing import Annotated, Literal

from app.db.session import session
from app.models import Incident, Product, Supplier, Task, Warehouse
from app.repositories.catalog import page
from app.schemas.responses import (
    IncidentResponse,
    OrderTimeline,
    Page,
    ProductResponse,
    SummaryResponse,
    SupplierResponse,
    TaskResponse,
    WarehouseResponse,
)
from app.services.demo import order_timeline, summary
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1")
DB = Annotated[Session, Depends(session)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=1000000)]


@router.get("/demo/summary", response_model=SummaryResponse)
def get_summary(db: DB):
    return summary(db)


@router.get("/catalog/suppliers", response_model=Page[SupplierResponse])
def suppliers(
    db: DB,
    limit: Limit = 25,
    offset: Offset = 0,
    status: Literal["active", "under_review", "inactive"] | None = None,
):
    return page(db, Supplier, limit, offset, [Supplier.status == status] if status else [])


@router.get("/catalog/warehouses", response_model=Page[WarehouseResponse])
def warehouses(db: DB, limit: Limit = 25, offset: Offset = 0):
    return page(db, Warehouse, limit, offset)


@router.get("/catalog/products", response_model=Page[ProductResponse])
def products(db: DB, limit: Limit = 25, offset: Offset = 0):
    return page(db, Product, limit, offset)


@router.get("/operations/incidents", response_model=Page[IncidentResponse])
def incidents(
    db: DB,
    limit: Limit = 25,
    offset: Offset = 0,
    status: Literal["open", "investigating", "resolved", "escalated"] | None = None,
):
    return page(db, Incident, limit, offset, [Incident.status == status] if status else [])


@router.get("/operations/tasks", response_model=Page[TaskResponse])
def tasks(
    db: DB,
    limit: Limit = 25,
    offset: Offset = 0,
    status: Literal["open", "active", "completed", "escalated"] | None = None,
):
    return page(db, Task, limit, offset, [Task.status == status] if status else [])


@router.get("/operations/orders/{order_id}/timeline", response_model=OrderTimeline)
def get_timeline(db: DB, order_id: int, kind: Literal["purchase", "sales"] = "purchase"):
    if order_id <= 0:
        raise HTTPException(422, "Order ID must be positive")
    result = order_timeline(db, order_id, kind)
    if result is None:
        raise HTTPException(404, "Order not found")
    return result
