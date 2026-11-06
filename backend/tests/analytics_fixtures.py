"""Hand-authored numerical fixture, independent of the company generator."""

from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from app.models import Base
from app.services.seeding import reset
from sqlalchemy import text


def day(value):
    return date.fromisoformat(value)


def timestamp(value):
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


@pytest.fixture
def small_db(db):
    name = db.scalar(text("SELECT current_database()"))
    assert name.startswith("opspilot_test_")
    reset(db, f"DELETE SYNTHETIC DATA FROM {name}")
    data = defaultdict(list)

    def add(table, **values):
        event_date = next(
            (
                values[key]
                for key in (
                    "received_on",
                    "fulfilled_on",
                    "occurred_on",
                    "paid_on",
                    "issued_on",
                    "incurred_on",
                    "detected_on",
                    "ordered_on",
                )
                if key in values
            ),
            day("2025-10-01"),
        )
        row = {
            "id": len(data[table]) + 1,
            "created_at": timestamp("2025-10-01"),
            "synthetic": True,
            **values,
        }
        if "created_at" not in values:
            row["created_at"] = datetime.combine(event_date, datetime.min.time(), UTC)
        data[table].append(row)
        return row

    for label in [
        "Fixture Operations",
        "Fixture Procurement",
        "Fixture Warehouse",
        "Fixture Finance",
    ]:
        add("departments", name=label)
    add(
        "employees",
        name="Synthetic Fixture Colleague",
        department_id=1,
        business_email="fixture@northstar.example",
    )
    for identifier in range(1, 4):
        add(
            "suppliers",
            name=f"Synthetic Fixture Supplier {identifier}",
            country="GB",
            category="office",
            status="active",
        )
        add(
            "supplier_contracts",
            supplier_id=identifier,
            reference=f"FIX-{identifier}",
            effective_date=day("2025-10-01"),
            expires_on=day("2026-09-30"),
            on_time_target=Decimal("95.00"),
            payment_days=30,
            escalation_days=2,
        )
    for label in ["Fixture procurement warehouse", "Fixture stock warehouse"]:
        add("warehouses", name=label, city="Synthetic City")
    for i in range(3):
        add(
            "products",
            sku=f"FIX-{i + 1}",
            name=f"Synthetic fixture unit {i + 1}",
            category="office",
            reorder_point=0,
        )
    add("customers", name="Synthetic Fixture Customer", sector="office")
    # Supplier 1: eight due orders fully on time, one late split delivery,
    # one overdue, plus an immature open order excluded from the denominator.
    for i in range(11):
        add(
            "purchase_orders",
            supplier_id=1,
            contract_id=1,
            warehouse_id=1,
            ordered_on=day("2025-10-01"),
            promised_on=day("2025-11-20" if i == 10 else "2025-11-02"),
            status="received" if i < 9 else "open",
            currency="GBP",
        )
        add(
            "purchase_order_lines",
            purchase_order_id=i + 1,
            product_id=1,
            quantity=10,
            unit_price=Decimal("100.00") if i == 0 else Decimal("10.00"),
        )
        if i < 8:
            add(
                "goods_receipts",
                purchase_order_line_id=i + 1,
                received_on=day("2025-11-01"),
                quantity=10,
            )
        elif i == 8:
            add(
                "goods_receipts",
                purchase_order_line_id=9,
                received_on=day("2025-11-01"),
                quantity=4,
            )
            add(
                "goods_receipts",
                purchase_order_line_id=9,
                received_on=day("2025-11-04"),
                quantity=6,
            )
    # Independent inventory example: opening 20 + receipts 15 - dispatch 25 = 10.
    add(
        "purchase_orders",
        supplier_id=2,
        contract_id=2,
        warehouse_id=2,
        ordered_on=day("2025-10-01"),
        promised_on=day("2025-10-10"),
        status="received",
        currency="GBP",
    )
    add(
        "purchase_order_lines",
        purchase_order_id=12,
        product_id=2,
        quantity=15,
        unit_price=Decimal("2.00"),
    )
    add("goods_receipts", purchase_order_line_id=12, received_on=day("2025-10-10"), quantity=15)

    sales = [
        (2, "2025-10-15"),
        (1, "2025-11-02"),
        (1, "2025-11-02"),
        (1, "2025-11-20"),
        (1, "2025-11-02"),
    ]
    for i, (warehouse, promise) in enumerate(sales, 1):
        add(
            "sales_orders",
            customer_id=1,
            warehouse_id=warehouse,
            ordered_on=day("2025-10-01"),
            promised_on=day(promise),
            status="fulfilled" if i in (1, 2, 5) else "backorder",
            currency="GBP",
        )
        add(
            "sales_order_lines",
            sales_order_id=i,
            product_id=2 if i == 1 else 1,
            quantity=25 if i == 1 else 1 if i == 5 else 10,
            unit_price=Decimal("12.00"),
        )
    add("sales_order_lines", sales_order_id=5, product_id=3, quantity=1, unit_price=Decimal("5.00"))
    for line, when, quantity in [
        (1, "2025-10-15", 25),
        (2, "2025-11-01", 4),
        (2, "2025-11-04", 6),
        (5, "2025-11-01", 1),
        (6, "2025-11-04", 1),
    ]:
        add(
            "fulfilments",
            sales_order_line_id=line,
            fulfilled_on=day(when),
            quantity=quantity,
            delivery_status="dispatched",
        )
    add(
        "shortages",
        sales_order_line_id=3,
        expected_purchase_line_id=10,
        detected_on=day("2025-10-01"),
        resolved_on=None,
        quantity=10,
    )

    for product, quantity in [(2, 20), (3, 10)]:
        add(
            "stock_movements",
            product_id=product,
            warehouse_id=2 if product == 2 else 1,
            occurred_on=day("2025-10-01"),
            kind="adjustment",
            quantity=quantity,
            receipt_id=None,
            fulfilment_id=None,
            reason="Hand-authored fixture opening adjustment",
        )
    for receipt in data["goods_receipts"]:
        line = data["purchase_order_lines"][receipt["purchase_order_line_id"] - 1]
        po = data["purchase_orders"][line["purchase_order_id"] - 1]
        add(
            "stock_movements",
            product_id=line["product_id"],
            warehouse_id=po["warehouse_id"],
            occurred_on=receipt["received_on"],
            kind="receipt",
            quantity=receipt["quantity"],
            receipt_id=receipt["id"],
            fulfilment_id=None,
            reason=None,
        )
    for event in data["fulfilments"]:
        line = data["sales_order_lines"][event["sales_order_line_id"] - 1]
        so = data["sales_orders"][line["sales_order_id"] - 1]
        add(
            "stock_movements",
            product_id=line["product_id"],
            warehouse_id=so["warehouse_id"],
            occurred_on=event["fulfilled_on"],
            kind="issue",
            quantity=-event["quantity"],
            receipt_id=None,
            fulfilment_id=event["id"],
            reason=None,
        )
    add(
        "supplier_invoices",
        purchase_order_id=1,
        reference="FIX-INV-1",
        issued_on=day("2025-10-02"),
        due_on=day("2025-10-31"),
        amount=Decimal("1000.00"),
        status="partial",
        currency="GBP",
        discrepancy_note=None,
    )
    add(
        "supplier_invoices",
        purchase_order_id=2,
        reference="FIX-INV-2",
        issued_on=day("2025-10-02"),
        due_on=day("2025-11-01"),
        amount=Decimal("125.00"),
        status="disputed",
        currency="GBP",
        discrepancy_note="Synthetic GBP 25 discrepancy, recorded by review on 5 November",
    )
    for when, amount in [("2025-10-03", "400.00"), ("2025-10-04", "350.00")]:
        add("payments", invoice_id=1, paid_on=day(when), amount=Decimal(amount))
    for category, when, dep, links, closed, status in [
        ("invoice", "2025-11-05", 4, {"invoice_id": 2}, None, "open"),
        ("supplier_delay", "2025-11-03", 2, {"purchase_order_id": 9}, "2025-11-04", "resolved"),
        ("capacity", "2025-10-15", 3, {"warehouse_id": 2, "sales_order_id": 1}, None, "escalated"),
        ("shortage", "2025-11-01", 3, {"shortage_id": 1, "sales_order_id": 3}, None, "open"),
    ]:
        row = add(
            "incidents",
            category=category,
            severity="high",
            status=status,
            description="Synthetic independent fixture evidence",
            department_id=dep,
            created_at=timestamp(when),
            closed_at=timestamp(closed) if closed else None,
            purchase_order_id=None,
            shortage_id=None,
            sales_order_id=None,
            warehouse_id=None,
            invoice_id=None,
        )
        row.update(links)
    for i, completed in enumerate(
        ["2025-11-01T08:00:00", "2025-11-02T08:00:00", "2025-11-04T08:00:00", None], 1
    ):
        add(
            "tasks",
            title=f"Synthetic fixture task {i}",
            description="Independent numerical test",
            owner_id=1,
            department_id=1,
            incident_id=3,
            supplier_id=None,
            priority="high",
            status="completed" if completed else "escalated",
            created_at=timestamp("2025-10-30"),
            due_at=timestamp("2025-11-02T12:00:00"),
            completed_at=timestamp(completed) if completed else None,
        )
        add("task_status_history", task_id=i, status="open", created_at=timestamp("2025-10-30"))
        add(
            "task_status_history",
            task_id=i,
            status="completed" if completed else "escalated",
            created_at=timestamp(completed or "2025-11-03"),
        )
    add(
        "operational_expenses",
        department_id=2,
        warehouse_id=1,
        incident_id=2,
        purchase_order_id=9,
        incurred_on=day("2025-11-05"),
        category="expediting",
        amount=Decimal("85.00"),
        currency="GBP",
        basis="Synthetic explicit carrier rebooking",
    )
    add(
        "operational_expenses",
        department_id=3,
        warehouse_id=2,
        incident_id=3,
        purchase_order_id=None,
        incurred_on=day("2025-10-15"),
        category="overtime",
        amount=Decimal("120.00"),
        currency="GBP",
        basis="Synthetic four overtime hours at GBP 30",
    )
    for table in Base.metadata.sorted_tables:
        records = data.get(table.name)
        if records:
            if table.name == "stock_movements":
                records = sorted(records, key=lambda r: (r["occurred_on"], r["id"]))
            db.execute(table.insert(), records)
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    return db
