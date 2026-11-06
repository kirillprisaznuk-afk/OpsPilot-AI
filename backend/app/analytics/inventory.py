from app.analytics.common import (
    metrics,
    one,
    optional,
    paged,
    report,
    rows,
    segments,
    validate_query,
)
from app.analytics.contracts import TrendPoint, Window

ALLOWED = {"warehouse_id", "product_id", "product_category"}
SORTS = {
    "id": "entity_id",
    "stock_on_hand": "stock_on_hand",
    "outstanding_shortage_units": "outstanding_shortage_units",
}


def ctes():
    return f"""
      inventory_positions AS (
        SELECT m.product_id, m.warehouse_id, p.name AS product_name, w.name AS warehouse_name,
          sum(m.quantity) AS stock_on_hand,
          coalesce(sum(m.quantity) FILTER (WHERE m.occurred_on<:start),0) AS opening_stock,
          coalesce(sum(m.quantity) FILTER (WHERE m.occurred_on<=:end),0) AS closing_stock,
          coalesce(sum(m.quantity) FILTER (WHERE m.kind='receipt' AND m.occurred_on BETWEEN
          :start AND :end),0) AS received_units,
          coalesce(-sum(m.quantity) FILTER (WHERE m.kind='issue' AND m.occurred_on BETWEEN
          :start AND :end),0) AS dispatched_units,
          coalesce(sum(m.quantity) FILTER (WHERE m.kind='adjustment' AND m.occurred_on BETWEEN
          :start AND :end),0) AS adjusted_units
        FROM stock_movements m JOIN products p ON p.id=m.product_id
        JOIN warehouses w ON w.id=m.warehouse_id
        WHERE m.occurred_on<=:as_of AND {optional("m.warehouse_id", "warehouse_id")}
          AND {optional("m.product_id", "product_id")} AND
          {optional("p.category", "product_category", "text")}
        GROUP BY m.product_id, m.warehouse_id, p.name, w.name
      ),
      inventory_dispatch AS (
        SELECT sales_order_line_id, sum(quantity) AS quantity FROM fulfilments
        WHERE fulfilled_on<=:as_of GROUP BY sales_order_line_id
      ),
      inventory_demand AS (
        SELECT l.id AS sales_line_id, l.product_id, so.warehouse_id,
          l.quantity-coalesce(f.quantity,0) AS remaining, sh.id AS shortage_id, sh.detected_on
        FROM sales_order_lines l JOIN sales_orders so ON so.id=l.sales_order_id
        JOIN products p ON p.id=l.product_id
        LEFT JOIN inventory_dispatch f ON f.sales_order_line_id=l.id
        LEFT JOIN shortages sh ON sh.sales_order_line_id=l.id AND sh.detected_on<=:as_of
        WHERE so.ordered_on<=:as_of AND {optional("so.warehouse_id", "warehouse_id")}
          AND {optional("l.product_id", "product_id")} AND
          {optional("p.category", "product_category", "text")}
      ),
      inventory_shortage_incidents AS (
        SELECT l.product_id, so.warehouse_id, count(*) AS shortage_incidents
        FROM incidents i JOIN shortages sh ON sh.id=i.shortage_id
        JOIN sales_order_lines l ON l.id=sh.sales_order_line_id
        JOIN sales_orders so ON so.id=l.sales_order_id JOIN products p ON p.id=l.product_id
        WHERE i.created_at>=:begin AND i.created_at<:finish AND i.created_at<:cutoff
          AND {optional("so.warehouse_id", "warehouse_id")} AND
          {optional("l.product_id", "product_id")}
          AND {optional("p.category", "product_category", "text")}
        GROUP BY l.product_id, so.warehouse_id
      )
    """


STOCK_SUMS = """
 coalesce(sum(opening_stock),0) AS opening_stock, coalesce(sum(closing_stock),0) AS closing_stock,
 coalesce(sum(stock_on_hand),0) AS stock_on_hand,
 coalesce(sum(received_units),0) AS received_units, coalesce(sum(dispatched_units),0) AS
 dispatched_units,
 coalesce(sum(adjusted_units),0) AS adjusted_units, count(*) AS stock_positions,
 count(*) FILTER (WHERE stock_on_hand>0) AS positive_stock_positions
"""
DEMAND_SUMS = """
 coalesce(sum(remaining),0) AS outstanding_demand_units,
 count(*) FILTER (WHERE shortage_id IS NOT NULL AND remaining>0) AS open_shortages,
 coalesce(sum(remaining) FILTER (WHERE shortage_id IS NOT NULL AND remaining>0),0) AS
 outstanding_shortage_units,
 count(*) FILTER (WHERE detected_on BETWEEN :start AND :end) AS shortage_occurrences
"""


def aggregate_sql(group=None):
    if group:
        key = "warehouse_id" if group == "warehouse" else "product_id"
        masters = "warehouses" if group == "warehouse" else "products"
        category_filter = (
            "AND " + optional("master.category", "product_category", "text")
            if group == "product"
            else ""
        )
        return f"""
          WITH {ctes()}, stock AS (
            SELECT {key} AS id, {STOCK_SUMS} FROM inventory_positions GROUP BY {key}
          ), demand AS (
            SELECT {key} AS id, {DEMAND_SUMS} FROM inventory_demand GROUP BY {key}
          ), incidents AS (
            SELECT {key} AS id, sum(shortage_incidents) AS shortage_incidents
            FROM inventory_shortage_incidents GROUP BY {key}
          )
          SELECT master.id AS entity_id, master.name AS label,
            coalesce(s.opening_stock,0) AS opening_stock, coalesce(s.closing_stock,0) AS
            closing_stock,
            coalesce(s.stock_on_hand,0) AS stock_on_hand, coalesce(s.received_units,0) AS
            received_units,
            coalesce(s.dispatched_units,0) AS dispatched_units, coalesce(s.adjusted_units,0) AS
            adjusted_units,
            coalesce(s.stock_positions,0) AS stock_positions,
            coalesce(s.positive_stock_positions,0) AS positive_stock_positions,
            coalesce(d.outstanding_demand_units,0) AS outstanding_demand_units,
            coalesce(d.open_shortages,0) AS open_shortages,
            coalesce(d.outstanding_shortage_units,0) AS outstanding_shortage_units,
            coalesce(d.shortage_occurrences,0) AS shortage_occurrences,
            coalesce(i.shortage_incidents,0) AS shortage_incidents
          FROM {masters} master LEFT JOIN stock s ON s.id=master.id
          LEFT JOIN demand d ON d.id=master.id LEFT JOIN incidents i ON i.id=master.id
          WHERE master.created_at<:cutoff
            AND {optional("master.id", "warehouse_id" if group == "warehouse" else "product_id")}
            {category_filter}
        """
    return f"""
      WITH {ctes()}
      SELECT s.*, d.*, i.* FROM (SELECT {STOCK_SUMS} FROM inventory_positions) s
      CROSS JOIN (SELECT {DEMAND_SUMS} FROM inventory_demand) d
      CROSS JOIN (SELECT coalesce(sum(shortage_incidents),0) AS shortage_incidents FROM
      inventory_shortage_incidents) i
    """


def compute(db, q):
    return one(db, aggregate_sql(), q)


def monthly(db, q):
    sql = f"""
      WITH periods AS (
        SELECT greatest(m::date,CAST(:start AS date)) AS start_on,
          least((m+interval '1 month - 1 day')::date,CAST(:end AS date)) AS end_on
        FROM generate_series(date_trunc('month',CAST(:start AS date)),
                             date_trunc('month',CAST(:end AS date)),interval '1 month') m
      ), filtered_movements AS (
        SELECT m.* FROM stock_movements m JOIN products p ON p.id=m.product_id
        WHERE m.occurred_on<=:as_of AND {optional("m.warehouse_id", "warehouse_id")}
          AND {optional("m.product_id", "product_id")} AND
          {optional("p.category", "product_category", "text")}
      )
      SELECT x.start_on, x.end_on,
        coalesce(sum(m.quantity) FILTER (WHERE m.occurred_on<x.start_on),0) AS opening_stock,
        coalesce(sum(m.quantity),0) AS closing_stock, coalesce(sum(m.quantity),0) AS stock_on_hand,
        coalesce(sum(m.quantity) FILTER (WHERE m.kind='receipt' AND
        m.occurred_on>=x.start_on),0) AS received_units,
        coalesce(-sum(m.quantity) FILTER (WHERE m.kind='issue' AND
        m.occurred_on>=x.start_on),0) AS dispatched_units,
        coalesce(sum(m.quantity) FILTER (WHERE m.kind='adjustment' AND
        m.occurred_on>=x.start_on),0) AS adjusted_units
      FROM periods x LEFT JOIN filtered_movements m ON m.occurred_on<=x.end_on
      GROUP BY x.start_on,x.end_on ORDER BY x.start_on
    """
    return [
        TrendPoint(
            window=Window(
                observation_start=r["start_on"], observation_end=r["end_on"], as_of=r["end_on"]
            ),
            metrics=metrics("inventory", r),
        )
        for r in rows(db, sql, q)
    ]


def get_inventory(db, q):
    validate_query(q, ALLOWED, ("product", "warehouse"), SORTS)
    raw = compute(db, q)
    previous = compute(db, q.previous()) if q.include_comparison and q.previous() else None
    group = q.group_by or "product"
    grouped, total = paged(db, aggregate_sql(group), q, SORTS)
    return report(
        "inventory",
        q,
        raw,
        previous,
        segments("inventory", group, grouped),
        monthly(db, q) if q.include_trends else [],
        total,
        limitations=[
            (
                "Stock positions are observed movement positions, not a capacity or "
                "availability denominator."
            ),
            "No reservations exist. Outstanding demand and physical stock are separate quantities.",
        ],
    )
