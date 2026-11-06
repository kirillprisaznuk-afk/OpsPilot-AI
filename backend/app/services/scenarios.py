"""Evidence queries, never canned analytic conclusions returned by the demo API."""

from sqlalchemy import text

SCENARIOS = {
    "A_procurement_to_customer": """
        SELECT s.id AS supplier_id, po.id AS purchase_order_id, r.id AS receipt_id,
               sm.id AS movement_id, sh.id AS shortage_id, so.id AS sales_order_id,
               f.id AS fulfilment_id, i.id AS incident_id, t.id AS task_id,
               po.promised_on, r.received_on, so.promised_on AS customer_promise, f.fulfilled_on
        FROM suppliers s JOIN purchase_orders po ON po.supplier_id=s.id
        JOIN purchase_order_lines pl ON pl.purchase_order_id=po.id
        JOIN goods_receipts r ON r.purchase_order_line_id=pl.id
        JOIN stock_movements sm ON sm.receipt_id=r.id
        JOIN shortages sh ON sh.expected_purchase_line_id=pl.id
        JOIN sales_order_lines sl ON sl.id=sh.sales_order_line_id
        JOIN sales_orders so ON so.id=sl.sales_order_id AND so.warehouse_id=po.warehouse_id
        JOIN fulfilments f ON f.sales_order_line_id=sl.id AND f.fulfilled_on>=r.received_on
        JOIN incidents i ON i.shortage_id=sh.id JOIN tasks t ON t.incident_id=i.id
        WHERE r.received_on>po.promised_on AND f.fulfilled_on>so.promised_on
          AND sh.detected_on<r.received_on AND sl.product_id=pl.product_id
        ORDER BY po.id, r.id, f.id, t.id LIMIT 1
    """,
    "B_warehouse_capacity": """
        SELECT w.id AS warehouse_id, so.id AS sales_order_id, i.id AS incident_id,
               e.id AS expense_id, e.amount, t.id AS task_id, i.status
        FROM warehouses w JOIN incidents i ON i.warehouse_id=w.id
        JOIN sales_orders so ON so.id=i.sales_order_id
        JOIN operational_expenses e ON e.incident_id=i.id
        JOIN tasks t ON t.incident_id=i.id
        WHERE i.category='capacity' AND i.status='escalated' AND e.category='overtime'
          AND EXISTS (SELECT 1 FROM sales_order_lines sl JOIN fulfilments f
                      ON f.sales_order_line_id=sl.id
                      WHERE sl.sales_order_id=so.id AND f.fulfilled_on>so.ordered_on)
        ORDER BY i.id LIMIT 1
    """,
    "C_contract_concern": """
        WITH delivered AS (
          SELECT po.id, po.supplier_id, po.contract_id, po.promised_on, po.status,
                 max(r.received_on) AS completed_on
          FROM purchase_orders po JOIN purchase_order_lines pl ON pl.purchase_order_id=po.id
          LEFT JOIN goods_receipts r ON r.purchase_order_line_id=pl.id
          WHERE po.promised_on<='2026-09-30'
          GROUP BY po.id
        )
        SELECT c.id AS contract_id, c.supplier_id, c.on_time_target,
          count(*) AS due_orders,
          count(*) FILTER
            (WHERE d.status='received' AND completed_on<=promised_on) AS on_time_orders,
          round(100.0 * count(*) FILTER
          (WHERE d.status='received' AND completed_on<=promised_on)/count(*),2) AS observed_percent
        FROM supplier_contracts c JOIN delivered d ON d.contract_id=c.id
        GROUP BY c.id HAVING 100.0 * count(*) FILTER
          (WHERE d.status='received' AND completed_on<=promised_on)/count(*)<c.on_time_target
        ORDER BY c.id LIMIT 1
    """,
    "D_invoice_review": """
        SELECT inv.id AS invoice_id, inv.purchase_order_id, inv.amount,
               sum(pl.quantity*pl.unit_price) AS purchase_value,
               i.id AS incident_id, t.id AS task_id, inv.status
        FROM supplier_invoices inv JOIN purchase_order_lines pl
          ON pl.purchase_order_id=inv.purchase_order_id
        JOIN incidents i ON i.invoice_id=inv.id JOIN tasks t ON t.incident_id=i.id
        WHERE inv.status='disputed' AND i.status='open'
        GROUP BY inv.id, i.id, t.id HAVING inv.amount<>sum(pl.quantity*pl.unit_price)
        ORDER BY inv.id LIMIT 1
    """,
    "E_overdue_workload": """
        SELECT d.id AS department_id, d.name, count(*) AS overdue_tasks,
               count(DISTINCT t.owner_id) AS owners
        FROM tasks t JOIN departments d ON d.id=t.department_id
        WHERE t.status<>'completed' AND t.due_at<'2026-10-01T00:00:00+00:00'
        GROUP BY d.id HAVING count(*)>20 ORDER BY count(*) DESC, d.id LIMIT 1
    """,
}


def verify_scenarios(db):
    report = {}
    for name, query in SCENARIOS.items():
        row = db.execute(text(query)).mappings().first()
        if row is None:
            raise ValueError(f"Scenario evidence missing: {name}")
        report[name] = dict(row)
    return report
