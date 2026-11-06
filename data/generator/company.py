"""Deterministic event simulation. No wall clock, external data, or hidden row drops."""

import hashlib
import json
import random
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

START = date(2025, 10, 1)
END = date(2026, 9, 30)
SEED = 20251001
VERSION = "1.0"
DEPARTMENTS = [
    "Operations",
    "Procurement",
    "Warehouse & Logistics",
    "Finance",
    "Customer Operations",
    "Management",
]
POLICIES = [
    (
        "Procurement procedure",
        2,
        "Record promised dates against the applicable supplier contract. "
        "Escalate missed receipts after the contract escalation interval; "
        "never revise the original promise.",
    ),
    (
        "Warehouse receiving procedure",
        3,
        "Record each partial receipt against its purchase line. "
        "Reject over-receipts. Post one positive ledger movement per accepted receipt.",
    ),
    (
        "Inventory control policy",
        3,
        "Issue only physically available units. Opening stock is zero. "
        "Backorders retain outstanding quantities; never create negative inventory.",
    ),
    (
        "Incident escalation procedure",
        1,
        "Assign a department and corrective task to each incident. "
        "High-severity unresolved incidents require management review after seven calendar days.",
    ),
    (
        "Payment review policy",
        4,
        "Compare invoice amount with purchase line value excluding VAT. "
        "Hold discrepant invoices for review. Record partial payments explicitly; never overpay.",
    ),
    (
        "Incident response instructions",
        1,
        "Preserve linked order, shortage or invoice evidence. "
        "Close incidents only after a recorded corrective action. Review overdue tasks weekly.",
    ),
    (
        "Customer fulfilment policy",
        5,
        "Promises are dispatch commitments, not arrival estimates. "
        "Use FIFO backorders and partial dispatches. Escalate shortages and capacity queues.",
    ),
    (
        "Capacity pressure instruction",
        3,
        "During declared pressure at the Midlands warehouse, "
        "allow a three-calendar-day handling queue. "
        "Record approved overtime as explicit cost events.",
    ),
]


def stamp(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), UTC)


class Dataset:
    def __init__(self):
        self.rows = defaultdict(list)
        self.documents = {}

    def add(self, table, day=START, **values):
        row = {
            "id": len(self.rows[table]) + 1,
            "created_at": stamp(day),
            "synthetic": True,
            **values,
        }
        self.rows[table].append(row)
        return row

    def get(self, table, identifier):
        return self.rows[table][identifier - 1]

    def fingerprint(self):
        payload = {"tables": dict(sorted(self.rows.items())), "documents": self.documents}

        def canonical(value):
            return format(value, ".2f") if isinstance(value, Decimal) else str(value)

        return hashlib.sha256(
            json.dumps(payload, default=canonical, sort_keys=True).encode()
        ).hexdigest()

    def write_documents(self, root: Path):
        for path, content in self.documents.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")


def generate(seed=SEED):
    rng = random.Random(seed)
    ds = Dataset()
    add = ds.add
    for name in DEPARTMENTS:
        dep = add("departments", name=name)
        add(
            "business_roles",
            name=f"{name} coordinator",
            responsibility=f"Coordinate synthetic {name.lower()} records and corrective actions.",
        )
        for j in range(8):
            employee = add(
                "employees",
                name=f"Synthetic {name.split()[0]} Colleague {j + 1}",
                department_id=dep["id"],
                business_email=f"staff{dep['id']:02}{j + 1:02}@northstar.example",
            )
            add("responsibilities", employee_id=employee["id"], role_id=dep["id"])
    for city, label in [
        ("Birmingham", "Midlands"),
        ("Leeds", "Northern"),
        ("Bristol", "Western"),
        ("Reading", "Southern"),
    ]:
        add("warehouses", name=f"Northstar {label} (synthetic)", city=city)
    categories = ["office", "industrial", "technology"]
    for i in range(200):
        category = categories[i % 3]
        add(
            "products",
            sku=f"NS-{i + 1:04}",
            name=f"Synthetic {category} unit {i + 1:03}",
            category=category,
            reorder_point=15 + i % 20,
        )
    prefixes = ["Amberwick", "Brindleford", "Cobaltmere", "Dovewick", "Eldermark", "Fernholt"]
    suffixes = [
        "Office Works",
        "Industrial Supply",
        "Technology Trade",
        "Business Goods",
        "Distribution",
        "Procurement House",
    ]
    for i in range(36):
        supplier = add(
            "suppliers",
            name=f"{prefixes[i // 6]} {suffixes[i % 6]} (synthetic)",
            country="GB",
            category=categories[i % 3],
            status="under_review" if i % 6 == 0 else "active",
        )
        add(
            "supplier_contracts",
            supplier_id=supplier["id"],
            reference=f"NS-CON-{i + 1:03}",
            effective_date=START,
            expires_on=END,
            on_time_target=Decimal("95.00"),
            payment_days=30 if i % 2 else 45,
            escalation_days=3 if i % 3 else 2,
        )
    for i in range(120):
        add(
            "customers",
            name=f"Synthetic {prefixes[i % 6]} Business Customer {i + 1:03}",
            sector=["professional services", "manufacturing", "education"][i % 3],
        )

    receipt_events = defaultdict(list)
    sales_events = defaultdict(list)
    po_lines = defaultdict(list)
    so_lines = defaultdict(list)
    # First isolated product supplies an independently testable cross-domain causal case.
    for i in range(2400):
        ordered = START + timedelta(days=rng.randrange(359))
        supplier_id = rng.randrange(1, 37)
        warehouse_id = rng.randrange(1, 5)
        promised = ordered + timedelta(days=rng.randrange(3, 8))
        products = rng.sample(range(2, 201), 2)
        if i == 0:
            ordered, promised, supplier_id, warehouse_id, products = (
                START,
                date(2025, 10, 8),
                1,
                1,
                [1],
            )
        po = add(
            "purchase_orders",
            ordered,
            supplier_id=supplier_id,
            contract_id=supplier_id,
            warehouse_id=warehouse_id,
            ordered_on=ordered,
            promised_on=promised,
            status="open",
            currency="GBP",
        )
        weak = supplier_id % 6 == 1
        delay = rng.randrange(3, 15) if rng.random() < (0.60 if weak else 0.12) else -1
        if i == 0:
            delay = 12
        receipt_day = promised + timedelta(days=delay)
        for product in products:
            price = Decimal(rng.randrange(400, 15000)) / 100
            # Reliable suppliers trade at an explicit commercial premium.
            price = (price * (Decimal("0.90") if weak else Decimal("1.08"))).quantize(
                Decimal(".01")
            )
            line = add(
                "purchase_order_lines",
                ordered,
                purchase_order_id=po["id"],
                product_id=product,
                quantity=40 if i == 0 else rng.randrange(35, 100),
                unit_price=price,
            )
            po_lines[po["id"]].append(line)
            first = line["quantity"] // 2 if i % 7 == 0 and i != 0 else line["quantity"]
            receipt_events[receipt_day].append((line, first))
            if first < line["quantity"]:
                receipt_events[receipt_day + timedelta(days=3)].append(
                    (line, line["quantity"] - first)
                )
        if i % 4 != 3:
            sales_day = min(END, promised - timedelta(days=1))
            due = min(END, promised + timedelta(days=1))
            if i == 0:
                sales_day, due = date(2025, 10, 9), date(2025, 10, 10)
            so = add(
                "sales_orders",
                sales_day,
                customer_id=rng.randrange(1, 121),
                warehouse_id=warehouse_id,
                ordered_on=sales_day,
                promised_on=due,
                status="open",
                currency="GBP",
            )
            for pl in po_lines[po["id"]]:
                seasonal = Decimal("1.3") if sales_day.month in (11, 12) else Decimal("0.85")
                quantity = 30 if i == 0 else max(1, int(pl["quantity"] * seasonal))
                sl = add(
                    "sales_order_lines",
                    sales_day,
                    sales_order_id=so["id"],
                    product_id=pl["product_id"],
                    quantity=quantity,
                    unit_price=(pl["unit_price"] * Decimal("1.25")).quantize(Decimal(".01")),
                )
                so_lines[so["id"]].append(sl)
                sales_events[sales_day].append(sl)

    balances = defaultdict(int)
    received = defaultdict(int)
    fulfilled = defaultdict(int)
    shortages = {}
    pending = []
    capacity_cases = []
    day = START
    while day <= END:
        for pl, quantity in receipt_events[day]:
            po = ds.get("purchase_orders", pl["purchase_order_id"])
            receipt = add(
                "goods_receipts",
                day,
                purchase_order_line_id=pl["id"],
                received_on=day,
                quantity=quantity,
            )
            received[pl["id"]] += quantity
            key = (pl["product_id"], po["warehouse_id"])
            balances[key] += quantity
            add(
                "stock_movements",
                day,
                product_id=key[0],
                warehouse_id=key[1],
                occurred_on=day,
                kind="receipt",
                quantity=quantity,
                receipt_id=receipt["id"],
                fulfilment_id=None,
                reason=None,
            )
        pending.extend(sales_events[day])
        remaining = []
        for sl in pending:
            so = ds.get("sales_orders", sl["sales_order_id"])
            key = sl["product_id"], so["warehouse_id"]
            outstanding = sl["quantity"] - fulfilled[sl["id"]]
            capacity = so["warehouse_id"] == 1 and so["ordered_on"].month in (11, 12, 6)
            ready_on = so["ordered_on"] + timedelta(days=3 if capacity else 0)
            if day == so["ordered_on"] and balances[key] < outstanding:
                candidates = [
                    pl
                    for lines in po_lines.values()
                    for pl in lines
                    if pl["product_id"] == key[0]
                    and ds.get("purchase_orders", pl["purchase_order_id"])["warehouse_id"] == key[1]
                    and ds.get("purchase_orders", pl["purchase_order_id"])["ordered_on"] <= day
                    and received[pl["id"]] < pl["quantity"]
                ]
                candidates.sort(
                    key=lambda pl: (
                        ds.get("purchase_orders", pl["purchase_order_id"])["promised_on"],
                        pl["id"],
                    )
                )
                shortage = add(
                    "shortages",
                    day,
                    sales_order_line_id=sl["id"],
                    expected_purchase_line_id=candidates[0]["id"] if candidates else None,
                    detected_on=day,
                    resolved_on=None,
                    quantity=outstanding - balances[key],
                )
                shortages[sl["id"]] = shortage
            if capacity and day == so["ordered_on"] and balances[key] >= outstanding:
                capacity_cases.append((so, day))
            quantity = min(outstanding, balances[key]) if day >= ready_on else 0
            if quantity:
                event = add(
                    "fulfilments",
                    day,
                    sales_order_line_id=sl["id"],
                    fulfilled_on=day,
                    quantity=quantity,
                    delivery_status="delivered" if day < END - timedelta(days=2) else "dispatched",
                )
                balances[key] -= quantity
                fulfilled[sl["id"]] += quantity
                add(
                    "stock_movements",
                    day,
                    product_id=key[0],
                    warehouse_id=key[1],
                    occurred_on=day,
                    kind="issue",
                    quantity=-quantity,
                    receipt_id=None,
                    fulfilment_id=event["id"],
                    reason=None,
                )
            if fulfilled[sl["id"]] < sl["quantity"]:
                remaining.append(sl)
            elif sl["id"] in shortages:
                shortages[sl["id"]]["resolved_on"] = day
        pending = remaining
        day += timedelta(days=1)
    for po in ds.rows["purchase_orders"]:
        lines = po_lines[po["id"]]
        po["status"] = (
            "received"
            if all(received[x["id"]] == x["quantity"] for x in lines)
            else "partial"
            if any(received[x["id"]] for x in lines)
            else "open"
        )
    for so in ds.rows["sales_orders"]:
        lines = so_lines[so["id"]]
        so["status"] = (
            "fulfilled"
            if all(fulfilled[x["id"]] == x["quantity"] for x in lines)
            else "partial"
            if any(fulfilled[x["id"]] for x in lines)
            else "backorder"
        )
    generate_operations(ds, rng, po_lines, capacity_cases)
    generate_documents(ds)
    return ds


def generate_operations(ds, rng, po_lines, capacity_cases):
    add = ds.add

    def incident(day, category, department, description, resolved=None, **links):
        inc = add(
            "incidents",
            day,
            category=category,
            severity="high",
            status="resolved" if resolved else "escalated" if category == "capacity" else "open",
            description=f"SYNTHETIC: {description}",
            department_id=department,
            purchase_order_id=None,
            shortage_id=None,
            sales_order_id=None,
            warehouse_id=None,
            invoice_id=None,
            closed_at=stamp(resolved) if resolved else None,
        )
        inc.update(links)
        # Operations carries triage workload even when another team owns the incident.
        task_department = 1 if inc["id"] % 3 else department
        status = "completed" if resolved else ["active", "open", "escalated"][inc["id"] % 3]
        task = add(
            "tasks",
            day,
            title=f"Review {category} evidence {inc['id']}",
            description="Synthetic corrective action: verify linked evidence "
            "and record resolution.",
            owner_id=(task_department - 1) * 8 + 1 + inc["id"] % 8,
            department_id=task_department,
            incident_id=inc["id"],
            supplier_id=None,
            priority="high",
            status=status,
            due_at=stamp(min(END, day + timedelta(days=7))),
            completed_at=stamp(resolved) if resolved else None,
        )
        add("task_status_history", day, task_id=task["id"], status="open")
        if status != "open":
            add("task_status_history", resolved or day, task_id=task["id"], status=status)
        return inc

    for shortage in ds.rows["shortages"]:
        sl = ds.get("sales_order_lines", shortage["sales_order_line_id"])
        so = ds.get("sales_orders", sl["sales_order_id"])
        incident(
            shortage["detected_on"],
            "shortage",
            3,
            f"Sales line {sl['id']} lacked {shortage['quantity']} units at order entry.",
            resolved=shortage["resolved_on"],
            shortage_id=shortage["id"],
            sales_order_id=so["id"],
        )
    receipt_days = defaultdict(list)
    for r in ds.rows["goods_receipts"]:
        pl = ds.get("purchase_order_lines", r["purchase_order_line_id"])
        receipt_days[pl["purchase_order_id"]].append(r["received_on"])
    for po in ds.rows["purchase_orders"]:
        contract = ds.get("supplier_contracts", po["contract_id"])
        last_receipt = max(receipt_days[po["id"]], default=None)
        threshold = po["promised_on"] + timedelta(days=contract["escalation_days"])
        if threshold <= END and (last_receipt is None or last_receipt >= threshold):
            inc = incident(
                threshold,
                "supplier_delay",
                2,
                f"Purchase order {po['id']} exceeded the contractual "
                "receiving escalation interval.",
                resolved=last_receipt if po["status"] == "received" else None,
                purchase_order_id=po["id"],
            )
            if po["id"] % 5 == 1:
                add(
                    "operational_expenses",
                    threshold,
                    department_id=2,
                    warehouse_id=po["warehouse_id"],
                    incident_id=inc["id"],
                    purchase_order_id=po["id"],
                    incurred_on=threshold,
                    category="expediting",
                    amount=Decimal("85.00"),
                    currency="GBP",
                    basis="Synthetic scenario assumption: one approved carrier "
                    "rebooking fee, GBP 85 net.",
                )
        if not receipt_days[po["id"]]:
            continue
        issued = min(receipt_days[po["id"]])
        total = sum((x["quantity"] * x["unit_price"] for x in po_lines[po["id"]]), Decimal(0))
        disputed = po["id"] % 37 == 0
        amount = total + (Decimal("25.00") if disputed else Decimal(0))
        due = issued + timedelta(days=contract["payment_days"])
        paid_day = issued + timedelta(days=20)
        status = (
            "disputed"
            if disputed
            else "outstanding"
            if paid_day > END
            else "partial"
            if po["id"] % 11 == 0
            else "paid"
        )
        invoice = add(
            "supplier_invoices",
            issued,
            purchase_order_id=po["id"],
            reference=f"SYN-INV-{po['id']:05}",
            issued_on=issued,
            due_on=due,
            amount=amount,
            status=status,
            currency="GBP",
            discrepancy_note="Synthetic unsupported surcharge GBP 25 net" if disputed else None,
        )
        if status in ("paid", "partial"):
            add(
                "payments",
                paid_day,
                invoice_id=invoice["id"],
                paid_on=paid_day,
                amount=amount if status == "paid" else (amount / 2).quantize(Decimal(".01")),
            )
        if disputed:
            incident(
                issued,
                "invoice",
                4,
                "Invoice includes an unsupported GBP 25 surcharge; payment held.",
                invoice_id=invoice["id"],
            )
    seen = set()
    for so, day in capacity_cases:
        if so["id"] in seen:
            continue
        seen.add(so["id"])
        inc = incident(
            day,
            "capacity",
            3,
            "Midlands handling queue imposed a three-day dispatch hold despite available stock.",
            sales_order_id=so["id"],
            warehouse_id=1,
        )
        add(
            "operational_expenses",
            day,
            department_id=3,
            warehouse_id=1,
            incident_id=inc["id"],
            purchase_order_id=None,
            incurred_on=day,
            category="overtime",
            amount=Decimal("120.00"),
            currency="GBP",
            basis="Synthetic scenario assumption: four approved overtime hours "
            "at GBP 30 net per hour.",
        )
    for month in range(12):
        year, zero_month = divmod(START.year * 12 + START.month - 1 + month, 12)
        day = date(year, zero_month + 1, 1)
        for warehouse in range(1, 5):
            add(
                "operational_expenses",
                day,
                department_id=3,
                warehouse_id=warehouse,
                incident_id=None,
                purchase_order_id=None,
                incurred_on=day,
                category="rent",
                amount=Decimal(3500 + warehouse * 500),
                currency="GBP",
                basis="Synthetic monthly warehouse occupancy charge, net of VAT.",
            )


def generate_documents(ds):
    for contract in ds.rows["supplier_contracts"]:
        supplier = ds.get("suppliers", contract["supplier_id"])
        body = (
            f"Supplier: {supplier['name']}\n\nContract reference: {contract['reference']}. "
            f"Target: {contract['on_time_target']}% of fully received purchase orders received "
            "on or before the original promised date. "
            "Open overdue orders remain failures at the cutoff. "
            f"Escalate after {contract['escalation_days']} calendar days past promise. "
            f"Payment term: {contract['payment_days']} calendar days from invoice issue. "
            "All prices are GBP net of VAT. Partial receipts are allowed; "
            "over-receipts require rejection. "
            "Review below-target delivery performance; no automatic penalties are assumed."
        )
        add_document(
            ds,
            f"CON-{contract['id']:03}",
            f"Agreement — {supplier['name']}",
            "supplier_agreement",
            2,
            body,
            contract["id"],
        )
    for i, (title, dep, content) in enumerate(POLICIES, 1):
        add_document(ds, f"POL-{i:03}", title, "policy", dep, content, None)


def add_document(ds, code, title, kind, department, body, contract):
    document = ds.add(
        "documents",
        code=code,
        title=title,
        document_type=kind,
        department_id=department,
        contract_id=contract,
    )
    content = (
        f"# {title}\n\n**SYNTHETIC — fictional Northstar Supply demonstration only.**\n\n"
        f"- Document ID: {code}\n- Type: {kind}\n- Version: 1\n"
        f"- Effective date: {START}\n- Department: {DEPARTMENTS[department - 1]}\n"
        f"- Contract ID: {contract or 'N/A'}\n\n## Instructions and terms\n\n{body}\n"
    )
    path = f"knowledge/synthetic_documents/{code}.md"
    ds.documents[path] = content
    ds.add(
        "document_versions",
        document_id=document["id"],
        version=1,
        effective_on=START,
        path=path,
        sha256=hashlib.sha256(content.encode()).hexdigest(),
    )
