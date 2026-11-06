from app.analytics.common import one, paged, report, rows, segments, trends, validate_query
from app.analytics.order_queries import order_aggregates, order_ctes

ALLOWED = {"warehouse_id", "product_id", "product_category"}
SORTS = {
    "id": "entity_id",
    "outstanding_units": "outstanding_units",
    "on_time_rate": "100.0*on_time_orders/NULLIF(due_orders,0)",
}


def aggregate_sql(group=None):
    fields, suffix = "", ""
    if group == "month":
        fields = "date_trunc('month',f.ordered_on)::date AS month,"
        suffix = "GROUP BY 1 ORDER BY 1"
    elif group:
        fields = "f.warehouse_id AS entity_id, f.warehouse_name AS label,"
        suffix = "GROUP BY f.warehouse_id,f.warehouse_name"
    return f"""
      WITH {order_ctes("sales")}, delay_evidence AS (
        SELECT sh.sales_order_line_id, sl.sales_order_id,
          bool_or(po.promised_on<=:as_of AND (NOT coalesce(r.received>=pl.quantity,false)
            OR r.last_received>po.promised_on)) AS late_supply
        FROM shortages sh JOIN sales_order_lines sl ON sl.id=sh.sales_order_line_id
        LEFT JOIN purchase_order_lines pl ON pl.id=sh.expected_purchase_line_id
        LEFT JOIN purchase_orders po ON po.id=pl.purchase_order_id
        LEFT JOIN (
          SELECT purchase_order_line_id, sum(quantity) AS received,max(received_on) AS last_received
          FROM goods_receipts WHERE received_on<=:as_of GROUP BY purchase_order_line_id
        ) r ON r.purchase_order_line_id=pl.id
        WHERE sh.detected_on<=:as_of GROUP BY sh.sales_order_line_id,sl.sales_order_id
      )
      SELECT {fields} {order_aggregates("sales")},
        count(*) FILTER (WHERE (completed_on>promised_on OR (NOT complete AND promised_on<=:as_of))
          AND EXISTS (SELECT 1 FROM delay_evidence d WHERE d.sales_order_id=f.id)) AS
          shortage_linked_delays,
        count(*) FILTER (WHERE (completed_on>promised_on OR (NOT complete AND promised_on<=:as_of))
          AND EXISTS (SELECT 1 FROM delay_evidence d WHERE d.sales_order_id=f.id AND
          d.late_supply)) AS late_supply_linked_delays,
        count(*) FILTER (WHERE (completed_on>promised_on OR (NOT complete AND promised_on<=:as_of))
          AND EXISTS (SELECT 1 FROM incidents i WHERE i.sales_order_id=f.id AND
          i.category='capacity'
                      AND i.created_at<:cutoff)) AS capacity_linked_delays
      FROM so_facts f WHERE f.ordered_on BETWEEN :start AND :end {suffix}
    """


def compute(db, q):
    return one(db, aggregate_sql(), q)


def get_fulfilment(db, q):
    validate_query(q, ALLOWED, ("warehouse",), SORTS)
    raw = compute(db, q)
    previous = compute(db, q.previous()) if q.include_comparison and q.previous() else None
    grouped, total = paged(db, aggregate_sql("warehouse"), q, SORTS)
    return report(
        "fulfilment",
        q,
        raw,
        previous,
        segments("fulfilment", "warehouse", grouped),
        trends("fulfilment", q, rows(db, aggregate_sql("month"), q)) if q.include_trends else [],
        total,
        limitations=[
            (
                "Service measures full dispatch, not carrier arrival. All original lines "
                "define completion."
            ),
            (
                "Bottleneck categories overlap and are explicit associations, not "
                "additive or exclusive causal explanations."
            ),
        ],
    )
