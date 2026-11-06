from decimal import Decimal

from app.models import (
    Fulfilment,
    GoodsReceipt,
    Incident,
    Payment,
    PurchaseOrder,
    PurchaseOrderLine,
    SalesOrder,
    SalesOrderLine,
    Shortage,
    SupplierInvoice,
    Task,
)
from sqlalchemy import select


def timeline(db, order_id, kind):
    model, line_model, fk = (
        (PurchaseOrder, PurchaseOrderLine, "purchase_order_id")
        if kind == "purchase"
        else (SalesOrder, SalesOrderLine, "sales_order_id")
    )
    order = db.get(model, order_id)
    if order is None:
        return None
    lines = db.scalars(select(line_model).where(getattr(line_model, fk) == order_id)).all()
    ids = [line.id for line in lines]
    events = [{"kind": "ordered", "entity_id": order.id, "occurred_on": order.ordered_on}]
    if kind == "purchase":
        receipts = db.scalars(
            select(GoodsReceipt).where(GoodsReceipt.purchase_order_line_id.in_(ids))
        )
        for r in receipts:
            events.append(
                {
                    "kind": "receipt",
                    "entity_id": r.id,
                    "occurred_on": r.received_on,
                    "quantity": r.quantity,
                }
            )
        invoices = db.scalars(
            select(SupplierInvoice).where(SupplierInvoice.purchase_order_id == order_id)
        ).all()
        for inv in invoices:
            events.append(
                {
                    "kind": "invoice",
                    "entity_id": inv.id,
                    "occurred_on": inv.issued_on,
                    "amount": inv.amount,
                }
            )
        for p in db.scalars(
            select(Payment).where(Payment.invoice_id.in_([x.id for x in invoices]))
        ):
            events.append(
                {"kind": "payment", "entity_id": p.id, "occurred_on": p.paid_on, "amount": p.amount}
            )
    else:
        for f in db.scalars(select(Fulfilment).where(Fulfilment.sales_order_line_id.in_(ids))):
            events.append(
                {
                    "kind": "fulfilment",
                    "entity_id": f.id,
                    "occurred_on": f.fulfilled_on,
                    "quantity": f.quantity,
                }
            )
        for s in db.scalars(select(Shortage).where(Shortage.sales_order_line_id.in_(ids))):
            events.append(
                {
                    "kind": "shortage",
                    "entity_id": s.id,
                    "occurred_on": s.detected_on,
                    "quantity": s.quantity,
                }
            )
    incidents = db.scalars(select(Incident).where(getattr(Incident, fk) == order_id)).all()
    for i in incidents:
        events.append({"kind": "incident", "entity_id": i.id, "occurred_on": i.created_at.date()})
    for t in db.scalars(select(Task).where(Task.incident_id.in_([x.id for x in incidents]))):
        events.append(
            {"kind": "task_created", "entity_id": t.id, "occurred_on": t.created_at.date()}
        )
    return {
        "order_id": order.id,
        "order_kind": kind,
        "status": order.status,
        "promised_on": order.promised_on,
        "line_value_gbp": sum((x.quantity * x.unit_price for x in lines), Decimal(0)),
        "events": sorted(events, key=lambda x: (x["occurred_on"], x["kind"], x["entity_id"])),
    }
