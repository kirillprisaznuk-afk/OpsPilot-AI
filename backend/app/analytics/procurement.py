from app.analytics.common import (
    one,
    optional,
    paged,
    report,
    rows,
    segments,
    trends,
    validate_query,
)
from app.analytics.contracts import PriceBand
from app.analytics.order_queries import order_aggregates, order_ctes
from app.analytics.registry import REGISTRY

ALLOWED = {"supplier_id", "warehouse_id", "product_id", "product_category", "supplier_category"}
SORTS = {
    "id": "entity_id",
    "order_value": "order_value",
    "on_time_rate": "100.0*on_time_orders/NULLIF(due_orders,0)",
    "overdue_commitment": "overdue_commitment",
}
GROUPS = {
    "supplier": ("supplier_id", "supplier_name"),
    "warehouse": ("warehouse_id", "warehouse_name"),
}


def aggregate_sql(group=None):
    fields, suffix = "", ""
    if group == "month":
        return f"""
          WITH {order_ctes("purchase")}, months AS (
            SELECT m::date AS month FROM generate_series(
              date_trunc('month',CAST(:start AS date)),
              date_trunc('month',CAST(:end AS date)),interval '1 month') m
          ), completed_flow AS (
            SELECT date_trunc('month',completed_on)::date AS month,count(*) AS n
            FROM po_facts WHERE completed_on BETWEEN :start AND :end GROUP BY 1
          )
          SELECT m.month, {order_aggregates("purchase")},
                 coalesce(max(c.n),0) AS completed_in_period
          FROM months m LEFT JOIN po_facts f
            ON date_trunc('month',f.ordered_on)::date=m.month
            AND f.ordered_on BETWEEN :start AND :end
          LEFT JOIN completed_flow c ON c.month=m.month GROUP BY m.month ORDER BY m.month
        """
    elif group:
        identifier, label = GROUPS[group]
        master = "suppliers" if group == "supplier" else "warehouses"
        projections = []
        for name, spec in REGISTRY.items():
            domain, field = name.split(".", 1)
            if domain != "procurement" or spec.denominator or field == "completed_in_period":
                continue
            value = f"c.{field}" if spec.unit == "days" else f"coalesce(c.{field},0)"
            projections.append(f"{value} AS {field}")
        category_filter = (
            "AND " + optional("m.category", "supplier_category", "text")
            if group == "supplier"
            else ""
        )
        return f"""
          WITH {order_ctes("purchase")}, cohort AS (
            SELECT {identifier} AS key,{order_aggregates("purchase")}
            FROM po_facts WHERE ordered_on BETWEEN :start AND :end GROUP BY {identifier}
          ), completion_flow AS (
            SELECT {identifier} AS key,count(*) AS n FROM po_facts
            WHERE completed_on BETWEEN :start AND :end GROUP BY {identifier}
          )
          SELECT m.id AS entity_id,m.name AS label,{",".join(projections)},
                 coalesce(f.n,0) AS completed_in_period
          FROM {master} m LEFT JOIN cohort c ON c.key=m.id
          LEFT JOIN completion_flow f ON f.key=m.id
          WHERE m.created_at<:cutoff AND {optional("m.id", identifier)} {category_filter}
        """
    return (
        f"WITH {order_ctes('purchase')} SELECT {fields} {order_aggregates('purchase')} "
        ", (SELECT count(*) FROM po_facts done WHERE done.completed_on BETWEEN :start AND :end "
        ") AS completed_in_period "
        f"FROM po_facts WHERE ordered_on BETWEEN :start AND :end {suffix}"
    )


def compute(db, q):
    return one(db, aggregate_sql(), q)


def get_procurement(db, q):
    validate_query(q, ALLOWED, GROUPS, SORTS)
    raw = compute(db, q)
    previous = compute(db, q.previous()) if q.include_comparison and q.previous() else None
    group = q.group_by or "warehouse"
    grouped, total = paged(db, aggregate_sql(group), q, SORTS)
    result = report(
        "procurement",
        q,
        raw,
        previous,
        segments("procurement", group, grouped),
        trends("procurement", q, rows(db, aggregate_sql("month"), q)) if q.include_trends else [],
        total=total,
        limitations=[
            (
                "Full-order completion always uses all original lines; product filters "
                "select monetary/quantity lines only."
            ),
            (
                "Completed-only lateness excludes outstanding orders, reported "
                "separately as overdue exposure."
            ),
        ],
    )
    price_sql = """
      SELECT p.id AS product_id, p.sku, sum(l.quantity) AS ordered_units,
        min(l.unit_price) AS minimum_unit_price_gbp, max(l.unit_price) AS maximum_unit_price_gbp,
        round(sum(l.quantity*l.unit_price)/sum(l.quantity),2) AS weighted_mean_unit_price_gbp
      FROM purchase_order_lines l JOIN products p ON p.id=l.product_id
      JOIN po_facts f ON f.id=l.purchase_order_id
      WHERE f.ordered_on BETWEEN :start AND :end
        AND (CAST(:product_id AS integer) IS NULL OR p.id=:product_id)
        AND (CAST(:product_category AS text) IS NULL OR p.category=:product_category)
      GROUP BY p.id ORDER BY p.id LIMIT :limit OFFSET :offset
    """
    result.price_bands = [
        PriceBand(**r) for r in rows(db, f"WITH {order_ctes('purchase')} {price_sql}", q)
    ]
    return result
