"""Shared, one-row-per-entity historical facts. No final statuses backfilled into history."""

INCIDENT_CTES = """
 incident_facts AS (
   SELECT i.*, coalesce(i.warehouse_id, po.warehouse_id, so.warehouse_id,
                        invoice_po.warehouse_id, supply_po.warehouse_id) AS affected_warehouse_id,
          coalesce(po.supplier_id, invoice_po.supplier_id, supply_po.supplier_id) AS supplier_id,
          coalesce(i.purchase_order_id, invoice_po.id, supply_po.id) AS affected_purchase_order_id,
          coalesce(i.sales_order_id, sl.sales_order_id) AS affected_sales_order_id,
          sl.product_id AS shortage_product_id
   FROM incidents i
   LEFT JOIN purchase_orders po ON po.id=i.purchase_order_id
   LEFT JOIN supplier_invoices inv ON inv.id=i.invoice_id AND inv.issued_on<=:as_of
   LEFT JOIN purchase_orders invoice_po ON invoice_po.id=inv.purchase_order_id
   LEFT JOIN shortages sh ON sh.id=i.shortage_id AND sh.detected_on<=:as_of
   LEFT JOIN sales_order_lines sl ON sl.id=sh.sales_order_line_id
   LEFT JOIN sales_orders so ON so.id=coalesce(i.sales_order_id,sl.sales_order_id)
   LEFT JOIN purchase_order_lines pl ON pl.id=sh.expected_purchase_line_id
   LEFT JOIN purchase_orders supply_po ON supply_po.id=pl.purchase_order_id
   WHERE i.created_at<:cutoff
 )
"""

TASK_CTES = """
 task_latest AS (
   SELECT DISTINCT ON (task_id) task_id, status
   FROM task_status_history WHERE created_at<:cutoff
   ORDER BY task_id, created_at DESC, id DESC
 ),
 task_facts AS (
   SELECT t.*,
     CASE WHEN t.completed_at<:cutoff THEN t.completed_at END AS observed_completed_at,
     CASE WHEN t.completed_at<:cutoff THEN 'completed' ELSE h.status END AS observed_status
   FROM tasks t LEFT JOIN task_latest h ON h.task_id=t.id WHERE t.created_at<:cutoff
 )
"""

EXPENSE_FACTS = """
 expense_facts AS (
   SELECT e.*, coalesce(po.supplier_id,i.supplier_id) AS supplier_id
   FROM operational_expenses e
   LEFT JOIN purchase_orders po ON po.id=e.purchase_order_id AND po.ordered_on<=:as_of
   LEFT JOIN incident_facts i ON i.id=e.incident_id
   WHERE e.incurred_on<=:as_of
 )
"""

EXPENSE_CTES = INCIDENT_CTES + "," + EXPENSE_FACTS

INVOICE_CTES = """
 invoice_order_values AS (
   SELECT purchase_order_id, sum(quantity*unit_price) AS purchase_value
   FROM purchase_order_lines GROUP BY purchase_order_id
 ),
 invoice_payments AS (
   SELECT invoice_id, sum(amount) AS paid FROM payments WHERE paid_on<=:as_of GROUP BY invoice_id
 ),
 invoice_facts AS (
   SELECT inv.*, po.supplier_id, po.warehouse_id, s.name AS supplier_name, s.category AS
   supplier_category,
          w.name AS warehouse_name, v.purchase_value,
          coalesce(p.paid,0) AS paid, inv.amount-coalesce(p.paid,0) AS remaining,
          EXISTS (SELECT 1 FROM incidents i WHERE i.invoice_id=inv.id
                  AND i.category='invoice' AND i.created_at<:cutoff) AS has_review
   FROM supplier_invoices inv JOIN purchase_orders po ON po.id=inv.purchase_order_id
   JOIN suppliers s ON s.id=po.supplier_id JOIN warehouses w ON w.id=po.warehouse_id
   JOIN invoice_order_values v ON v.purchase_order_id=po.id
   LEFT JOIN invoice_payments p ON p.invoice_id=inv.id WHERE inv.issued_on<=:as_of
 )
"""
