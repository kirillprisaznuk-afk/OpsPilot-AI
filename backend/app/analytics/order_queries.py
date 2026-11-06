"""One reusable full-order completion definition for inbound and outbound service."""

from app.analytics.common import optional


def order_ctes(kind):
    purchase = kind == "purchase"
    head = "purchase_orders" if purchase else "sales_orders"
    line = "purchase_order_lines" if purchase else "sales_order_lines"
    event = "goods_receipts" if purchase else "fulfilments"
    line_fk = "purchase_order_line_id" if purchase else "sales_order_line_id"
    header_fk = "purchase_order_id" if purchase else "sales_order_id"
    event_day = "received_on" if purchase else "fulfilled_on"
    prefix = "po" if purchase else "so"
    supplier_columns = "h.supplier_id, s.name AS supplier_name, h.contract_id," if purchase else ""
    supplier_join = "JOIN suppliers s ON s.id=h.supplier_id" if purchase else ""
    supplier_filter = (
        f"AND {optional('h.supplier_id', 'supplier_id')} "
        f"AND {optional('s.category', 'supplier_category', 'text')}"
        if purchase
        else ""
    )
    supplier_group = ", h.supplier_id, s.name, h.contract_id" if purchase else ""
    matched = (
        f"{optional('l.product_id', 'product_id')} AND "
        f"{optional('p.category', 'product_category', 'text')}"
    )
    return f"""
      {prefix}_events AS (
        SELECT e.{line_fk} AS line_id, sum(e.quantity) AS received,
               min(e.{event_day}) AS first_event, max(e.{event_day}) AS last_event,
               count(*) AS event_count,
               count(*) FILTER (WHERE e.{event_day}<=h.promised_on) AS punctual
        FROM {event} e JOIN {line} l ON l.id=e.{line_fk}
        JOIN {head} h ON h.id=l.{header_fk}
        WHERE e.{event_day}<=:as_of GROUP BY e.{line_fk}
      ),
      {prefix}_lines AS (
        SELECT l.*, coalesce(e.received,0) AS received, e.first_event, e.last_event,
               coalesce(e.event_count,0) AS event_count, coalesce(e.punctual,0) AS punctual,
               ({matched}) AS matched
        FROM {line} l JOIN products p ON p.id=l.product_id
        LEFT JOIN {prefix}_events e ON e.line_id=l.id
      ),
      {prefix}_facts AS (
        SELECT h.id, h.ordered_on, h.promised_on, h.warehouse_id, w.name AS warehouse_name,
               {supplier_columns}
               sum(l.quantity) FILTER (WHERE l.matched) AS ordered_units,
               sum(l.received) FILTER (WHERE l.matched) AS received_units,
               sum(l.quantity*l.unit_price) FILTER (WHERE l.matched) AS order_value,
               sum((l.quantity-l.received)*l.unit_price) FILTER (WHERE l.matched) AS open_value,
               sum(l.quantity-l.received) FILTER (WHERE l.matched) AS remaining_units,
               sum(l.received) AS all_received, bool_and(l.received>=l.quantity) AS complete,
               CASE WHEN bool_and(l.received>=l.quantity) THEN max(l.last_event) END AS
               completed_on,
               bool_or(l.event_count>1) AS split_receipts,
               sum(l.event_count) AS receipt_events, sum(l.punctual) AS punctual_receipts
        FROM {head} h JOIN {prefix}_lines l ON l.{header_fk}=h.id
        JOIN warehouses w ON w.id=h.warehouse_id {supplier_join}
        WHERE h.ordered_on<=:as_of AND {optional("h.warehouse_id", "warehouse_id")}
          {supplier_filter}
        GROUP BY h.id, w.name {supplier_group} HAVING bool_or(l.matched)
      )
    """


def order_aggregates(kind):
    purchase = kind == "purchase"
    fields = f"""
      count(id) AS {"purchase_orders" if purchase else "sales_orders"},
      coalesce(sum(ordered_units),0) AS ordered_units,
      coalesce(sum(received_units),0) AS {"received_units" if purchase else "dispatched_units"},
      coalesce(sum(remaining_units),0) AS outstanding_units,
      count(*) FILTER (WHERE complete) AS completed_orders,
      count(*) FILTER (WHERE NOT complete) AS open_orders,
      count(*) FILTER (WHERE NOT complete AND all_received>0) AS partial_orders,
      count(*) FILTER (WHERE promised_on<=:as_of) AS due_orders,
      count(*) FILTER (WHERE complete AND promised_on<=:as_of AND completed_on<=promised_on) AS
      on_time_orders,
      count(*) FILTER (WHERE complete AND completed_on>promised_on) AS late_orders,
      count(*) FILTER (WHERE NOT complete AND promised_on<=:as_of) AS overdue_outstanding_orders,
      avg(completed_on-promised_on) FILTER (WHERE complete AND completed_on>promised_on) AS
      average_lateness
    """
    if purchase:
        fields += """,
          coalesce(sum(order_value),0) AS order_value,
          coalesce(sum(open_value) FILTER (WHERE NOT complete),0) AS open_commitment,
          coalesce(sum(open_value) FILTER (WHERE NOT complete AND promised_on<=:as_of),0) AS
          overdue_commitment,
          count(*) FILTER (WHERE split_receipts) AS split_receipt_orders,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY completed_on-promised_on)
            FILTER (WHERE complete AND completed_on>promised_on) AS median_lateness,
          avg(CAST(:as_of AS date)-promised_on) FILTER (WHERE NOT complete AND
          promised_on<=:as_of) AS average_overdue_age,
          avg(completed_on-ordered_on) FILTER (WHERE complete) AS average_lead_time,
          coalesce(sum(receipt_events),0) AS receipt_events,
          coalesce(sum(punctual_receipts),0) AS punctual_receipts
        """
    else:
        fields += ", coalesce(sum(remaining_units),0) AS backorder_units"
    return fields
