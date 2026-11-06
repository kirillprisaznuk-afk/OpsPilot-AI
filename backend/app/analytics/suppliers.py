from app.analytics import procurement
from app.analytics.common import (
    AnalyticsInputError,
    metrics,
    one,
    optional,
    paged,
    percent,
    report,
    rows,
    segments,
    trends,
    validate_query,
)
from app.analytics.contracts import ContractAssessment
from app.analytics.facts import EXPENSE_CTES
from app.analytics.order_queries import order_ctes
from app.analytics.registry import REGISTRY

ALLOWED = {"supplier_id", "warehouse_id", "supplier_category"}
SORTS = {**procurement.SORTS, "additional_linked_costs": "additional_linked_costs"}


def linked_costs_sql():
    return f"""
      SELECT e.supplier_id, sum(e.amount) AS additional_linked_costs
      FROM expense_facts e JOIN suppliers s ON s.id=e.supplier_id
      WHERE e.incurred_on BETWEEN :start AND :end AND e.category IN ('expediting','overtime')
        AND {optional("e.supplier_id", "supplier_id")}
        AND {optional("e.warehouse_id", "warehouse_id")}
        AND {optional("s.category", "supplier_category", "text")}
      GROUP BY e.supplier_id
    """


def assessment_rows(db, q, selected):
    sql = f"""
      WITH {order_ctes("purchase")}
      SELECT c.id AS contract_id, c.supplier_id, c.reference, c.effective_date, c.expires_on,
             c.on_time_target AS target_percent,
             count(f.id) FILTER (WHERE f.promised_on<=:as_of) AS due_orders,
             count(f.id) FILTER (WHERE f.promised_on<=:as_of AND f.complete
                                AND f.completed_on<=f.promised_on) AS on_time_orders
      FROM supplier_contracts c JOIN suppliers s ON s.id=c.supplier_id
      LEFT JOIN po_facts f ON f.contract_id=c.id AND f.ordered_on BETWEEN :start AND :end
        AND f.ordered_on BETWEEN c.effective_date AND c.expires_on
      WHERE c.effective_date<=:end AND c.expires_on>=:start AND c.created_at<:cutoff
        AND {optional("c.supplier_id", "supplier_id")}
        AND {optional("s.category", "supplier_category", "text")}
        AND c.supplier_id=ANY(CAST(:selected_suppliers AS integer[]))
      GROUP BY c.id ORDER BY c.id LIMIT 100
    """
    return rows(db, sql, q, selected_suppliers=list(selected))


def get_suppliers(db, q, supplier_id=None):
    if supplier_id is not None:
        if q.supplier_id is not None and q.supplier_id != supplier_id:
            raise AnalyticsInputError("supplier_id", "Path and filter supplier IDs must agree")
        q = q.model_copy(update={"supplier_id": supplier_id, "offset": 0})
        exists = one(
            db,
            "SELECT count(*) AS n FROM suppliers WHERE id=:supplier_id AND created_at<:cutoff",
            q,
        )
        if not exists["n"]:
            return None
    validate_query(q, ALLOWED, ("supplier",), SORTS)
    raw = procurement.compute(db, q)
    previous = (
        procurement.compute(db, q.previous()) if q.include_comparison and q.previous() else None
    )
    base = procurement.aggregate_sql("supplier")
    values = []
    for field in raw:
        spec = REGISTRY.get(f"procurement.{field}")
        if spec is not None:
            expression = f"p.{field}" if spec.unit == "days" else f"coalesce(p.{field},0)"
            values.append(f"{expression} AS {field}")
    comparison_sql = f"""
      WITH {EXPENSE_CTES}, costs AS ({linked_costs_sql()}),
      targets AS (
        SELECT supplier_id, CASE WHEN count(DISTINCT on_time_target)=1 THEN max(on_time_target)
        END AS target
        FROM supplier_contracts WHERE effective_date<=:end AND expires_on>=:start
        AND created_at<:cutoff GROUP BY
        supplier_id
      )
      SELECT s.id AS entity_id, s.name AS label, {",".join(values)},
             coalesce(c.additional_linked_costs,0) AS additional_linked_costs,
             t.target AS sla_target_percent,
             round(100.0*p.on_time_orders/nullif(p.due_orders,0)-t.target,2) AS sla_gap
      FROM suppliers s LEFT JOIN ({base}) p ON p.entity_id=s.id
      LEFT JOIN costs c ON c.supplier_id=s.id LEFT JOIN targets t ON t.supplier_id=s.id
      WHERE s.created_at<:cutoff AND {optional("s.id", "supplier_id")}
        AND {optional("s.category", "supplier_category", "text")}
    """
    grouped, total = paged(db, comparison_sql, q, SORTS)
    breakdowns = segments("procurement", "supplier", grouped)
    for segment, raw_segment in zip(breakdowns, grouped, strict=True):
        segment.metrics.update(metrics("suppliers", raw_segment))
    result = report(
        "suppliers",
        q,
        raw,
        previous,
        breakdowns,
        trends("procurement", q, rows(db, procurement.aggregate_sql("month"), q))
        if q.include_trends
        else [],
        total=total,
        metric_domain="procurement",
        limitations=[
            "SLA concerns are operational observations, never legal breach findings.",
            "Targets differing across contracts remain separate; no blended target is invented.",
            "Contract assessments are bounded to 100 across the current supplier page.",
        ],
    )
    cost = one(
        db,
        (
            f"WITH {EXPENSE_CTES} SELECT coalesce(sum(additional_linked_costs),0) AS "
            f"additional_linked_costs FROM ({linked_costs_sql()}) c"
        ),
        q,
    )
    old_cost = (
        one(
            db,
            (
                f"WITH {EXPENSE_CTES} SELECT coalesce(sum(additional_linked_costs),0) AS "
                f"additional_linked_costs FROM ({linked_costs_sql()}) c"
            ),
            q.previous(),
        )
        if q.include_comparison and q.previous()
        else None
    )
    result.metrics.update(metrics("suppliers", cost, old_cost, q.previous(), q.include_comparison))
    # Contract assessment population is bounded by the supplier page, not an N+1 loop.
    selected = {s.entity_id for s in breakdowns}
    assessments = assessment_rows(db, q, selected)
    for a in assessments:
        if a["supplier_id"] not in selected:
            continue
        observed = percent(a["on_time_orders"], a["due_orders"])
        gap = observed - a["target_percent"] if observed is not None else None
        result.contracts.append(
            ContractAssessment(
                **a,
                observed_percent=observed,
                gap_percentage_points=gap,
                potential_operational_concern=gap < 0 if gap is not None else None,
            )
        )
    return result
