"""Bound SQL execution, validated dimensions, periods and metric construction."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.analytics.contracts import (
    AnalyticsReport,
    Comparison,
    Metric,
    Segment,
    TrendPoint,
    Window,
)
from app.analytics.registry import REGISTRY
from sqlalchemy import text

FILTERS = {
    "supplier_id",
    "warehouse_id",
    "product_id",
    "product_category",
    "supplier_category",
    "department_id",
    "employee_id",
    "incident_category",
    "priority",
}


class AnalyticsInputError(ValueError):
    def __init__(self, field, message):
        self.field = field
        super().__init__(message)


def validate_query(q, allowed, groups=(), sorts=("id",)):
    for field in FILTERS - set(allowed):
        if getattr(q, field) is not None:
            raise AnalyticsInputError(field, f"{field} is not supported for this metric population")
    if q.group_by is not None and q.group_by not in groups:
        raise AnalyticsInputError("group_by", f"Supported groups: {', '.join(groups) or 'none'}")
    if q.sort not in sorts:
        raise AnalyticsInputError("sort", f"Supported sorts: {', '.join(sorts)}")


def optional(column, parameter, kind="integer"):
    return f"(CAST(:{parameter} AS {kind}) IS NULL OR {column}=CAST(:{parameter} AS {kind}))"


def bindings(q):
    return {
        **q.model_dump(),
        "start": q.start_date,
        "end": q.end_date,
        "cutoff": datetime.combine(q.as_of + timedelta(days=1), datetime.min.time(), UTC),
        "begin": datetime.combine(q.start_date, datetime.min.time(), UTC),
        "finish": datetime.combine(q.end_date + timedelta(days=1), datetime.min.time(), UTC),
    }


def rows(db, sql, q, **extra):
    return [dict(r) for r in db.execute(text(sql), {**bindings(q), **extra}).mappings()]


def one(db, sql, q, **extra):
    return rows(db, sql, q, **extra)[0]


def percent(numerator, denominator):
    if numerator is None or not denominator:
        return None
    return (Decimal(numerator) * 100 / Decimal(denominator)).quantize(Decimal(".01"))


def window(q):
    return Window(observation_start=q.start_date, observation_end=q.end_date, as_of=q.as_of)


def comparison(value, previous, unit, previous_query):
    if previous_query is None:
        return Comparison(
            status="unavailable",
            reason="Equivalent previous period starts before observation history",
        )
    if value is None or previous is None:
        return Comparison(
            previous_window=window(previous_query),
            previous_value=previous,
            status="undefined",
            reason="Current or previous metric is undefined/unavailable",
        )
    delta = Decimal(value) - Decimal(previous)
    return Comparison(
        previous_window=window(previous_query),
        previous_value=previous,
        absolute_change=delta,
        relative_change_percent=percent(delta, abs(previous)),
        change_percentage_points=delta if unit == "percent" else None,
        status="available" if previous else "undefined",
        reason="Relative change undefined for zero baseline" if not previous else None,
    )


def metrics(domain, raw, previous=None, previous_query=None, comparisons=False, unavailable=None):
    result = {}
    unavailable = dict(unavailable or {})
    if domain == "workforce" and raw.get("unknown_status_tasks", 0):
        unavailable.update(
            {
                field: "Task status history is incomplete at the requested cutoff"
                for field in ("open_tasks", "overdue_tasks", "completion_rate")
            }
        )
    if domain == "incidents" and raw.get("escalated_incidents") is None:
        unavailable["escalated_incidents"] = (
            "Incident escalation status has no historical event timestamps"
        )
    if domain == "incidents" and raw.get("unknown_corrective_status", 0):
        unavailable["open_corrective_tasks"] = "Linked corrective task status history is incomplete"
    if domain == "suppliers" and "sla_target_percent" in raw and raw["sla_target_percent"] is None:
        unavailable.update(
            {
                key: "No single common effective contract target is available"
                for key in ("sla_target_percent", "sla_gap")
            }
        )
    for name, spec in REGISTRY.items():
        prefix, field = name.split(".", 1)
        if prefix != domain:
            continue
        if spec.denominator:
            if spec.numerator not in raw or spec.denominator not in raw:
                continue
            value = percent(raw[spec.numerator], raw[spec.denominator])
            old = (
                percent(previous.get(spec.numerator), previous.get(spec.denominator))
                if previous
                else None
            )
        elif field in raw:
            value = raw[field]
            old = previous.get(field) if previous else None
        else:
            continue
        if isinstance(value, float):
            value = Decimal(str(value))
        if isinstance(value, Decimal):
            value = value.quantize(Decimal(".01"))
        if isinstance(old, float):
            old = Decimal(str(old))
        if isinstance(old, Decimal):
            old = old.quantize(Decimal(".01"))
        if value is not None and spec.unit in {"count", "units"}:
            if value != int(value):
                raise ValueError(f"Non-integral discrete metric: {name}")
            value = int(value)
        if old is not None and spec.unit in {"count", "units"}:
            if old != int(old):
                raise ValueError(f"Non-integral previous discrete metric: {name}")
            old = int(old)
        if field in unavailable:
            value = None
        change = comparison(value, old, spec.unit, previous_query) if comparisons else None
        if change is not None and previous_query is not None:
            if field in unavailable:
                change.status, change.reason = "unavailable", unavailable[field]
            elif domain == "incidents" and field == "escalated_incidents" and old is None:
                change.status = "unavailable"
                change.reason = "Previous escalation state has no historical event timestamps"
            elif domain == "workforce" and previous and previous.get("unknown_status_tasks", 0):
                if field in {"open_tasks", "overdue_tasks", "completion_rate"}:
                    change.status = "unavailable"
                    change.reason = "Previous task state history is incomplete"
        result[field] = Metric(
            metric=name,
            value=value,
            unit=spec.unit,
            time_basis=spec.time_basis,
            grain=spec.grain,
            numerator=raw.get(spec.numerator) if spec.numerator else None,
            denominator=raw.get(spec.denominator) if spec.denominator else None,
            status="unavailable"
            if field in unavailable
            else "undefined"
            if value is None
            else "available",
            limitations=[unavailable[field]] if field in unavailable else [],
            comparison=change,
        )
    return result


def paged(db, sql, q, sort_columns):
    if q.sort not in sort_columns:
        raise AnalyticsInputError("sort", f"Supported sorts: {', '.join(sort_columns)}")
    # Every interpolated SQL expression comes from an internal whitelist.
    order = sort_columns[q.sort]
    query = (
        f"SELECT r.*, count(*) OVER() AS segment_total FROM ({sql}) r "
        f"ORDER BY {order} {q.direction} NULLS LAST, entity_id NULLS LAST, label "
        "LIMIT :limit OFFSET :offset"
    )
    result = rows(db, query, q)
    total = (
        result[0]["segment_total"]
        if result
        else one(db, f"SELECT count(*) AS n FROM ({sql}) r", q)["n"]
    )
    return result, total


def report(
    domain,
    q,
    raw,
    previous=None,
    breakdowns=(),
    trends=(),
    total=0,
    metric_domain=None,
    unavailable=None,
    limitations=(),
):
    metric_domain = metric_domain or domain
    return AnalyticsReport(
        domain=domain,
        window=window(q),
        filters={key: getattr(q, key) for key in sorted(FILTERS) if getattr(q, key) is not None},
        metrics=metrics(
            metric_domain, raw, previous, q.previous(), q.include_comparison, unavailable
        ),
        breakdowns=list(breakdowns),
        trends=list(trends),
        total_segments=total,
        limit=q.limit,
        offset=q.offset,
        limitations=list(limitations),
    )


def segments(domain, entity_type, records, unavailable=None):
    return [
        Segment(
            entity_type=entity_type,
            entity_id=r.get("entity_id"),
            label=r["label"],
            metrics=metrics(domain, r, unavailable=unavailable),
        )
        for r in records
    ]


def trends(domain, q, records):
    result = []
    for r in records:
        month = r["month"]
        if isinstance(month, datetime):
            month = month.date()
        year, zero_month = divmod(month.year * 12 + month.month, 12)
        end = date(year, zero_month + 1, 1) - timedelta(days=1)
        result.append(
            TrendPoint(
                window=Window(
                    observation_start=max(q.start_date, month),
                    observation_end=min(q.end_date, end),
                    as_of=q.as_of,
                ),
                metrics=metrics(domain, r),
            )
        )
    return result
