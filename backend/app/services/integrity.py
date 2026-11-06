"""Cross-row contracts shared by seeding and independent database verification."""

from collections import defaultdict
from decimal import Decimal

from app.models import Base
from sqlalchemy import select

from data.generator.company import END, START, Dataset


def load_dataset(db):
    ds = Dataset()
    for table in Base.metadata.sorted_tables:
        if table.name != "seed_runs":
            ds.rows[table.name] = [
                dict(row) for row in db.execute(select(table).order_by(table.c.id)).mappings()
            ]
    return ds


def validate(ds):
    """Raise on every invalid dataset; no filtering or silent repair."""
    tables = ds.rows
    lookup = {name: {r["id"]: r for r in rows} for name, rows in tables.items()}

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    for table in Base.metadata.sorted_tables:
        rows = tables.get(table.name, [])
        require(len({r["id"] for r in rows}) == len(rows), f"duplicate IDs: {table.name}")
        for row in rows:
            require(row["synthetic"], f"non-synthetic row: {table.name}")
            require(row["created_at"].tzinfo is not None, f"naive timestamp: {table.name}")
            require(START <= row["created_at"].date() <= END, f"outside observation: {table.name}")
            for fk in table.foreign_keys:
                value = row.get(fk.parent.name)
                require(
                    value is None or value in lookup.get(fk.column.table.name, {}),
                    f"dangling FK: {table.name}.{fk.parent.name}",
                )
    get = lambda table, identifier: lookup[table][identifier]  # noqa: E731
    received, issued, payments = defaultdict(int), defaultdict(int), defaultdict(Decimal)
    receipt_movements, issue_movements = defaultdict(int), defaultdict(int)
    for r in tables["goods_receipts"]:
        pl = get("purchase_order_lines", r["purchase_order_line_id"])
        po = get("purchase_orders", pl["purchase_order_id"])
        require(po["ordered_on"] <= r["received_on"] <= END, "receipt chronology")
        require(r["quantity"] > 0, "receipt quantity")
        received[pl["id"]] += r["quantity"]
    for pl in tables["purchase_order_lines"]:
        require(0 <= received[pl["id"]] <= pl["quantity"], "over receipt")
        require(
            pl["unit_price"] > 0 and pl["unit_price"].as_tuple().exponent >= -2, "price precision"
        )
    for po in tables["purchase_orders"]:
        contract = get("supplier_contracts", po["contract_id"])
        require(contract["supplier_id"] == po["supplier_id"], "contract supplier mismatch")
        require(
            contract["effective_date"] <= po["ordered_on"] <= contract["expires_on"],
            "contract dates",
        )
        require(po["ordered_on"] <= po["promised_on"], "purchase chronology")
        lines = [p for p in tables["purchase_order_lines"] if p["purchase_order_id"] == po["id"]]
        require(bool(lines), "empty purchase order")
        status = (
            "received"
            if all(received[p["id"]] == p["quantity"] for p in lines)
            else "partial"
            if any(received[p["id"]] for p in lines)
            else "open"
        )
        require(po["status"] == status, "purchase receipt status")
    for f in tables["fulfilments"]:
        sl = get("sales_order_lines", f["sales_order_line_id"])
        so = get("sales_orders", sl["sales_order_id"])
        require(so["ordered_on"] <= f["fulfilled_on"] <= END, "fulfilment chronology")
        require(f["quantity"] > 0, "fulfilment quantity")
        issued[sl["id"]] += f["quantity"]
    for sl in tables["sales_order_lines"]:
        require(0 <= issued[sl["id"]] <= sl["quantity"], "over fulfilment")
    for so in tables["sales_orders"]:
        require(so["ordered_on"] <= so["promised_on"], "sales chronology")
        lines = [s for s in tables["sales_order_lines"] if s["sales_order_id"] == so["id"]]
        require(bool(lines), "empty sales order")
        status = (
            "fulfilled"
            if all(issued[s["id"]] == s["quantity"] for s in lines)
            else "partial"
            if any(issued[s["id"]] for s in lines)
            else "backorder"
        )
        require(so["status"] == status, "sales fulfilment status")
    balance = defaultdict(int)
    for m in sorted(tables["stock_movements"], key=lambda x: (x["occurred_on"], x["id"])):
        key = m["product_id"], m["warehouse_id"]
        balance[key] += m["quantity"]
        require(balance[key] >= 0, "negative stock prefix")
        if m["kind"] == "receipt":
            r = get("goods_receipts", m["receipt_id"])
            pl = get("purchase_order_lines", r["purchase_order_line_id"])
            po = get("purchase_orders", pl["purchase_order_id"])
            require(
                (m["product_id"], m["warehouse_id"], m["occurred_on"], m["quantity"])
                == (pl["product_id"], po["warehouse_id"], r["received_on"], r["quantity"]),
                "receipt ledger mismatch",
            )
            receipt_movements[r["id"]] += 1
        elif m["kind"] == "issue":
            f = get("fulfilments", m["fulfilment_id"])
            sl = get("sales_order_lines", f["sales_order_line_id"])
            so = get("sales_orders", sl["sales_order_id"])
            require(
                (m["product_id"], m["warehouse_id"], m["occurred_on"], m["quantity"])
                == (sl["product_id"], so["warehouse_id"], f["fulfilled_on"], -f["quantity"]),
                "issue ledger mismatch",
            )
            issue_movements[f["id"]] += 1
        else:
            require(m["kind"] == "adjustment" and bool(m["reason"]), "unsupported stock movement")
    require(
        all(receipt_movements[r["id"]] == 1 for r in tables["goods_receipts"]),
        "missing receipt movement",
    )
    require(
        all(issue_movements[f["id"]] == 1 for f in tables["fulfilments"]), "missing issue movement"
    )
    for p in tables["payments"]:
        invoice = get("supplier_invoices", p["invoice_id"])
        require(
            invoice["issued_on"] <= p["paid_on"] <= END and p["amount"] > 0,
            "payment chronology/amount",
        )
        payments[p["invoice_id"]] += p["amount"]
    for invoice in tables["supplier_invoices"]:
        require(
            invoice["issued_on"] <= invoice["due_on"] and invoice["amount"] > 0,
            "invoice dates/amount",
        )
        total = sum(
            (
                p["quantity"] * p["unit_price"]
                for p in tables["purchase_order_lines"]
                if p["purchase_order_id"] == invoice["purchase_order_id"]
            ),
            Decimal(0),
        )
        require(
            invoice["amount"] == total + (Decimal("25") if invoice["status"] == "disputed" else 0),
            "invoice reconciliation",
        )
        paid = payments[invoice["id"]]
        require(0 <= paid <= invoice["amount"], "overpayment")
        require((invoice["status"] == "paid") == (paid == invoice["amount"]), "paid status")
        require(
            (invoice["status"] == "partial") == (0 < paid < invoice["amount"]),
            "partial payment status",
        )
    for s in tables["shortages"]:
        sl = get("sales_order_lines", s["sales_order_line_id"])
        so = get("sales_orders", sl["sales_order_id"])
        require(s["quantity"] > 0 and s["detected_on"] == so["ordered_on"], "shortage detection")
        if s["expected_purchase_line_id"]:
            pl = get("purchase_order_lines", s["expected_purchase_line_id"])
            po = get("purchase_orders", pl["purchase_order_id"])
            require(
                pl["product_id"] == sl["product_id"] and po["warehouse_id"] == so["warehouse_id"],
                "shortage procurement link",
            )
        require(
            (s["resolved_on"] is not None) == (issued[sl["id"]] == sl["quantity"]),
            "shortage resolution",
        )
        if s["resolved_on"]:
            require(s["resolved_on"] >= s["detected_on"], "shortage duration")
    for inc in tables["incidents"]:
        if inc["category"] == "invoice":
            require(
                get("supplier_invoices", inc["invoice_id"])["status"] == "disputed",
                "incident invoice evidence",
            )
        elif inc["category"] == "supplier_delay":
            po = get("purchase_orders", inc["purchase_order_id"])
            require(inc["created_at"].date() > po["promised_on"], "incident delay evidence")
        elif inc["category"] == "shortage":
            require(
                inc["created_at"].date() == get("shortages", inc["shortage_id"])["detected_on"],
                "incident shortage evidence",
            )
        else:
            require(
                inc["category"] == "capacity"
                and inc["warehouse_id"] == 1
                and inc["sales_order_id"],
                "incident capacity evidence",
            )
        require((inc["status"] == "resolved") == bool(inc["closed_at"]), "incident closure status")
        require(
            not inc["closed_at"] or inc["closed_at"] >= inc["created_at"],
            "incident closure chronology",
        )
    for task in tables["tasks"]:
        require(
            get("employees", task["owner_id"])["department_id"] == task["department_id"],
            "task ownership",
        )
        require(task["due_at"] >= task["created_at"], "task due chronology")
        require(
            (task["status"] == "completed") == bool(task["completed_at"]), "task completion status"
        )
        require(
            not task["completed_at"] or task["completed_at"] >= task["created_at"],
            "task completion chronology",
        )
        history = sorted(
            [h for h in tables["task_status_history"] if h["task_id"] == task["id"]],
            key=lambda h: (h["created_at"], h["id"]),
        )
        require(
            bool(history)
            and history[0]["status"] == "open"
            and history[-1]["status"] == task["status"],
            "task history",
        )
        require(all(h["created_at"] >= task["created_at"] for h in history), "history chronology")
    for expense in tables["operational_expenses"]:
        require(
            expense["amount"] > 0 and expense["basis"] and expense["currency"] == "GBP",
            "expense basis",
        )
    return {
        "validated": True,
        "counts": {k: len(v) for k, v in sorted(tables.items())},
        "closing_stock_units": sum(balance.values()),
        "period": f"{START}/{END}",
    }
