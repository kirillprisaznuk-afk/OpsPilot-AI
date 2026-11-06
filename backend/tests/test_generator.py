import copy
import hashlib
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from app.services.integrity import validate

from data.generator.company import END, START, generate


def test_full_generated_integrity(dataset):
    result = validate(dataset)
    assert result["closing_stock_units"] > 0
    assert len(dataset.rows["suppliers"]) == 36
    assert len(dataset.rows["products"]) == 200
    assert len(dataset.rows["employees"]) == 48
    assert len(dataset.rows["purchase_orders"]) == 2400
    assert len(dataset.rows["sales_orders"]) == 1800
    assert (START.isoformat(), END.isoformat()) == ("2025-10-01", "2026-09-30")


def test_determinism(dataset):
    assert dataset.fingerprint() == generate().fingerprint()
    assert dataset.fingerprint() != generate(999).fingerprint()


def test_document_corpus_matches_contracts(dataset):
    assert len(dataset.documents) == 44
    for version in dataset.rows["document_versions"]:
        content = Path(version["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == version["sha256"]
        assert b"SYNTHETIC" in content
    contract_text = dataset.documents["knowledge/synthetic_documents/CON-001.md"]
    contract = dataset.rows["supplier_contracts"][0]
    assert f"{contract['on_time_target']}%" in contract_text
    assert f"{contract['payment_days']} calendar days" in contract_text
    assert f"{contract['escalation_days']} calendar days" in contract_text


@pytest.mark.parametrize(
    "table,field,value,error",
    [
        ("employees", "department_id", 9999, "dangling FK"),
        ("goods_receipts", "quantity", 999999, "over receipt"),
        ("goods_receipts", "received_on", START - timedelta(days=1), "receipt chronology"),
        ("purchase_order_lines", "unit_price", Decimal("1.001"), "price precision"),
        ("purchase_orders", "supplier_id", 2, "contract supplier mismatch"),
        ("fulfilments", "quantity", 999999, "over fulfilment"),
        ("stock_movements", "quantity", -999999, "negative stock"),
        ("payments", "amount", Decimal("999999999"), "overpayment"),
        ("supplier_invoices", "amount", Decimal("0.01"), "invoice reconciliation"),
        ("tasks", "owner_id", 99999, "dangling FK"),
        ("tasks", "completed_at", None, "task completion status"),
        ("incidents", "closed_at", None, "incident closure status"),
    ],
)
def test_corrupt_data_fails_loudly(dataset, table, field, value, error):
    damaged = copy.deepcopy(dataset)
    # Find a completed task/incident when testing removal of its completion evidence.
    row = next(r for r in damaged.rows[table] if r.get(field) is not None)
    row[field] = value
    with pytest.raises(ValueError, match=error):
        validate(damaged)


def test_isolated_causal_case(dataset):
    po = dataset.get("purchase_orders", 1)
    so = dataset.get("sales_orders", 1)
    pl = dataset.get("purchase_order_lines", 1)
    receipt = next(r for r in dataset.rows["goods_receipts"] if r["purchase_order_line_id"] == 1)
    dispatch = next(f for f in dataset.rows["fulfilments"] if f["sales_order_line_id"] == 1)
    shortage = next(s for s in dataset.rows["shortages"] if s["sales_order_line_id"] == 1)
    assert pl["quantity"] == 40
    assert shortage["quantity"] == dispatch["quantity"] == 30
    assert shortage["expected_purchase_line_id"] == 1
    assert po["promised_on"].isoformat() == "2025-10-08"
    assert so["promised_on"].isoformat() == "2025-10-10"
    assert (
        receipt["received_on"].isoformat() == dispatch["fulfilled_on"].isoformat() == "2025-10-20"
    )
