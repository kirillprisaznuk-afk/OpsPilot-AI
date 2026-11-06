from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class RecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    synthetic: bool


class SupplierResponse(RecordResponse):
    name: str
    country: str
    category: str
    status: str


class WarehouseResponse(RecordResponse):
    name: str
    city: str


class ProductResponse(RecordResponse):
    sku: str
    name: str
    category: str
    reorder_point: int


class IncidentResponse(RecordResponse):
    category: str
    severity: str
    status: str
    description: str
    department_id: int
    created_at: datetime
    closed_at: datetime | None
    purchase_order_id: int | None
    sales_order_id: int | None
    shortage_id: int | None
    warehouse_id: int | None
    invoice_id: int | None


class TaskResponse(RecordResponse):
    title: str
    description: str
    owner_id: int
    department_id: int
    incident_id: int | None
    status: str
    priority: str
    created_at: datetime
    due_at: datetime
    completed_at: datetime | None


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: Literal["ok", "ready"]


class SummaryResponse(BaseModel):
    company: str
    synthetic: bool
    currency: str
    observation_start: date
    observation_end: date
    counts: dict[str, int]
    fingerprint: str | None


class TimelineEvent(BaseModel):
    kind: str
    entity_id: int
    occurred_on: date
    quantity: int | None = None
    amount: Decimal | None = None


class OrderTimeline(BaseModel):
    order_id: int
    order_kind: Literal["purchase", "sales"]
    status: str
    promised_on: date
    line_value_gbp: Decimal
    events: list[TimelineEvent]
