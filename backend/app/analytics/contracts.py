"""Public, typed analytics contracts. All percentages use the 0–100 convention."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from data.generator.company import END, START

Number = int | Decimal


class AnalyticsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_date: date = START
    end_date: date | None = None
    as_of: date = END
    supplier_id: int | None = Field(None, gt=0, le=2147483647)
    warehouse_id: int | None = Field(None, gt=0, le=2147483647)
    product_id: int | None = Field(None, gt=0, le=2147483647)
    product_category: Literal["office", "industrial", "technology"] | None = None
    supplier_category: Literal["office", "industrial", "technology"] | None = None
    department_id: int | None = Field(None, gt=0, le=2147483647)
    employee_id: int | None = Field(None, gt=0, le=2147483647)
    incident_category: Literal["supplier_delay", "shortage", "capacity", "invoice"] | None = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    group_by: str | None = None
    sort: str = "id"
    direction: Literal["asc", "desc"] = "asc"
    limit: int = Field(25, ge=1, le=100)
    offset: int = Field(0, ge=0, le=1000000)
    include_trends: bool = True
    include_comparison: bool = True

    @model_validator(mode="after")
    def dates(self):
        self.end_date = self.end_date or self.as_of
        if not START <= self.start_date <= self.end_date <= self.as_of <= END:
            raise ValueError("Require 2025-10-01 <= start_date <= end_date <= as_of <= 2026-09-30")
        return self

    def previous(self):
        duration = (self.end_date - self.start_date).days + 1
        start = self.start_date - timedelta(days=duration)
        if start < START:
            return None
        return self.model_copy(
            update={
                "start_date": start,
                "end_date": self.start_date - timedelta(days=1),
                "as_of": self.as_of - timedelta(days=duration),
            }
        )


class Window(BaseModel):
    observation_start: date
    observation_end: date
    as_of: date
    timezone: Literal["UTC"] = "UTC"


class InvestigationQuery(AnalyticsQuery):
    evidence_kind: Literal["all", "tasks", "costs", "receipts", "incidents"] = "all"
    open_tasks_only: bool = False
    overdue_tasks_only: bool = False


class Comparison(BaseModel):
    previous_window: Window | None = None
    previous_value: Number | None = None
    absolute_change: Decimal | None = None
    relative_change_percent: Decimal | None = None
    change_percentage_points: Decimal | None = None
    status: Literal["available", "undefined", "unavailable"]
    reason: str | None = None


class Metric(BaseModel):
    metric: str
    value: Number | None
    unit: Literal["count", "units", "GBP", "percent", "percentage_points", "days"]
    numerator: Number | None = None
    denominator: Number | None = None
    status: Literal["available", "undefined", "unavailable"] = "available"
    time_basis: str
    grain: str
    limitations: list[str] = Field(default_factory=list)
    comparison: Comparison | None = None


class Segment(BaseModel):
    entity_type: str
    entity_id: int | None = None
    label: str
    metrics: dict[str, Metric]


class TrendPoint(BaseModel):
    window: Window
    metrics: dict[str, Metric]


class ContractAssessment(BaseModel):
    contract_id: int
    supplier_id: int
    reference: str
    effective_date: date
    expires_on: date
    target_percent: Decimal
    observed_percent: Decimal | None
    gap_percentage_points: Decimal | None
    due_orders: int
    on_time_orders: int
    potential_operational_concern: bool | None
    legal_breach_established: Literal[False] = False


class PriceBand(BaseModel):
    product_id: int
    sku: str
    ordered_units: int
    minimum_unit_price_gbp: Decimal
    maximum_unit_price_gbp: Decimal
    weighted_mean_unit_price_gbp: Decimal


class AnalyticsReport(BaseModel):
    domain: str
    window: Window
    filters: dict[str, int | str]
    metrics: dict[str, Metric]
    breakdowns: list[Segment] = Field(default_factory=list)
    trends: list[TrendPoint] = Field(default_factory=list)
    total_segments: int = 0
    limit: int = 25
    offset: int = 0
    contracts: list[ContractAssessment] = Field(default_factory=list)
    price_bands: list[PriceBand] = Field(default_factory=list)
    cost_categories: list[Segment] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    entity_type: str
    entity_id: int
    related_entity_type: str
    related_entity_id: int
    event_time: datetime
    relationship_type: str
    evidence_class: Literal["explicit_link", "simulated_causal_chain"] = "explicit_link"
    quantity: int | None = None
    amount_gbp: Decimal | None = None
    source_reference: str
    observed_status: str | None = None
    title: str | None = None
    due_at: datetime | None = None
    priority: str | None = None
    cost_category: Literal["rent", "handling", "expediting", "overtime"] | None = None
    recorded_basis: str | None = None


class Investigation(BaseModel):
    entity_type: str
    entity_id: int
    window: Window
    metrics: dict[str, Metric]
    evidence: list[Evidence]
    total: int
    limit: int
    offset: int
    limitations: list[str]


class Insight(BaseModel):
    rule_id: str
    severity: Literal["critical", "warning", "opportunity", "information"]
    statement: str
    entity_type: str | None = None
    entity_id: int | None = None
    evidence: dict[str, Metric]
    source_reference: str


class InsightReport(BaseModel):
    window: Window
    items: list[Insight]
    total: int
    limit: int
    offset: int
