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
from app.analytics.facts import EXPENSE_CTES, INVOICE_CTES

ALLOWED = {"supplier_id", "warehouse_id"}
SORTS = {
    "id": "entity_id",
    "outstanding_amount": "outstanding_amount",
    "invoice_value": "invoice_value",
}


def invoice_filter(alias="f"):
    return (
        f"{optional(alias + '.supplier_id', 'supplier_id')} AND "
        f"{optional(alias + '.warehouse_id', 'warehouse_id')}"
    )


INVOICE_SUMS = """
 count(*) AS invoices, coalesce(sum(amount),0) AS invoice_value,
 coalesce(sum(paid),0) AS paid_amount, coalesce(sum(remaining),0) AS outstanding_amount,
 count(*) FILTER (WHERE remaining>0 AND due_on<=:as_of) AS overdue_invoices,
 coalesce(sum(remaining) FILTER (WHERE due_on<=:as_of),0) AS overdue_amount,
 count(*) FILTER (WHERE remaining=0) AS fully_paid_invoices,
 count(*) FILTER (WHERE paid>0 AND remaining>0) AS partially_paid_invoices,
 count(*) FILTER (WHERE paid=0) AS unpaid_invoices,
 count(*) FILTER (WHERE has_review AND amount<>purchase_value) AS discrepancy_invoices,
 coalesce(sum(amount-purchase_value) FILTER (WHERE has_review AND amount<>purchase_value),0) AS
 documented_discrepancy_amount
"""
EXPENSE_SUMS = """
 coalesce(sum(amount),0) AS operating_expenses,
 coalesce(sum(amount) FILTER (WHERE category IN ('expediting','overtime')),0) AS additional_costs,
 coalesce(sum(amount) FILTER (WHERE category='expediting'),0) AS expediting_costs,
 coalesce(sum(amount) FILTER (WHERE category='overtime'),0) AS overtime_costs
"""


def aggregate_sql(group=None):
    invoice_fields = expense_fields = payment_fields = ""
    invoice_group = expense_group = payment_group = ""
    if group == "month":
        invoice_fields = "date_trunc('month',issued_on)::date AS key,"
        expense_fields = "date_trunc('month',incurred_on)::date AS key,"
        payment_fields = "date_trunc('month',p.paid_on)::date AS key,"
        invoice_group = expense_group = payment_group = "GROUP BY 1"
    elif group:
        identifier, label = (
            ("supplier_id", "supplier_name")
            if group == "supplier"
            else ("warehouse_id", "warehouse_name")
        )
        invoice_fields = f"f.{identifier} AS key, f.{label} AS label,"
        expense_fields = f"e.{identifier} AS key,"
        payment_fields = f"f.{identifier} AS key,"
        invoice_group = f"GROUP BY f.{identifier},f.{label}"
        expense_group = f"GROUP BY e.{identifier}"
        payment_group = f"GROUP BY f.{identifier}"
    selects = "inv.*,pay.*,exp.*"
    final = "FROM inv CROSS JOIN pay CROSS JOIN exp"
    if group:
        # A union of keys retains cash/expense months and warehouses without invoices.
        keys = "keys AS (SELECT key FROM inv UNION SELECT key FROM pay UNION SELECT key FROM exp)"
        numeric_invoice = [
            "invoices",
            "invoice_value",
            "paid_amount",
            "outstanding_amount",
            "overdue_invoices",
            "overdue_amount",
            "fully_paid_invoices",
            "partially_paid_invoices",
            "unpaid_invoices",
            "discrepancy_invoices",
            "documented_discrepancy_amount",
        ]
        selects = ",".join(f"coalesce(inv.{field},0) AS {field}" for field in numeric_invoice)
        selects += ",coalesce(pay.payments_made,0) AS payments_made,pay.average_payment_days,"
        selects += ",".join(
            f"coalesce(exp.{field},0) AS {field}"
            for field in [
                "operating_expenses",
                "additional_costs",
                "expediting_costs",
                "overtime_costs",
            ]
        )
        if group == "month":
            selects = "k.key AS month," + selects
        else:
            table = "suppliers" if group == "supplier" else "warehouses"
            selects = (
                "k.key AS entity_id, coalesce(master.name,'Unattributed supplier') AS label,"
                + selects
            )
        final = (
            "FROM keys k LEFT JOIN inv ON inv.key IS NOT DISTINCT FROM k.key "
            "LEFT JOIN pay ON pay.key IS NOT DISTINCT FROM k.key "
            "LEFT JOIN exp ON exp.key IS NOT DISTINCT FROM k.key"
        )
        if group != "month":
            final += f" LEFT JOIN {table} master ON master.id=k.key"
        else:
            final += " ORDER BY k.key"
    return f"""
      WITH {INVOICE_CTES}, {EXPENSE_CTES},
      inv AS (SELECT {invoice_fields} {INVOICE_SUMS} FROM invoice_facts f
        WHERE issued_on BETWEEN :start AND :end AND {invoice_filter()} {invoice_group}),
      pay AS (
        SELECT {payment_fields} coalesce(sum(p.amount),0) AS payments_made,
          avg(p.paid_on-f.issued_on) AS average_payment_days
        FROM payments p JOIN invoice_facts f ON f.id=p.invoice_id
        WHERE p.paid_on BETWEEN :start AND :end AND p.paid_on<=:as_of
          AND {invoice_filter()} {payment_group}
      ),
      exp AS (SELECT {expense_fields} {EXPENSE_SUMS} FROM expense_facts e
        WHERE incurred_on BETWEEN :start AND :end AND {invoice_filter("e")} {expense_group})
      {("," + keys) if group else ""}
      SELECT {selects} {final}
    """


def compute(db, q):
    return one(db, aggregate_sql(), q)


def get_finance(db, q):
    validate_query(q, ALLOWED, ("supplier", "warehouse"), SORTS)
    raw = compute(db, q)
    previous = compute(db, q.previous()) if q.include_comparison and q.previous() else None
    group = q.group_by or "supplier"
    grouped, total = paged(db, aggregate_sql(group), q, SORTS)
    result = report(
        "finance",
        q,
        raw,
        previous,
        segments("finance", group, grouped),
        trends("finance", q, rows(db, aggregate_sql("month"), q)) if q.include_trends else [],
        total,
        limitations=[
            (
                "Invoice cohort value = paid amount + outstanding amount. Period cash "
                "payments are a separate flow."
            ),
            (
                "Invoice discrepancy exposure is not an operating expense, penalty or "
                "established legal liability."
            ),
        ],
    )
    # Cost categories stay independently visible at their authoritative event grain.
    categories = rows(
        db,
        f"""WITH {EXPENSE_CTES}
      SELECT category AS label, NULL::integer AS entity_id, {EXPENSE_SUMS}
      FROM expense_facts e WHERE incurred_on BETWEEN :start AND :end AND {invoice_filter("e")}
      GROUP BY category ORDER BY category""",
        q,
    )
    result.cost_categories = segments("finance", "cost_category", categories)
    return result
