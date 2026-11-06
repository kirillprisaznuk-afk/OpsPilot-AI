import uuid
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from app.knowledge.schema import metadata as knowledge_metadata
from app.models import Base, SeedRun
from app.services.integrity import load_dataset, validate
from app.services.scenarios import verify_scenarios
from app.services.seeding import reset, seed
from app.workflow.schema import metadata as workflow_metadata
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError


def test_migration_head_and_schema(db, postgres):
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
    assert set(inspect(postgres).get_table_names()) == set(Base.metadata.tables) | set(
        knowledge_metadata.tables
    ) | set(workflow_metadata.tables) | {"alembic_version"}
    for table in Base.metadata.sorted_tables:
        assert len(inspect(postgres).get_foreign_keys(table.name)) == len(table.foreign_keys)
    command.check(Config("alembic.ini"))


def test_database_integrity_and_reproducibility(db, dataset):
    loaded = load_dataset(db)
    validate(loaded)
    loaded.documents = dataset.documents
    assert loaded.fingerprint() == dataset.fingerprint()
    assert db.get(SeedRun, 1).fingerprint == dataset.fingerprint()


def test_scenarios_have_measured_evidence(db):
    report = verify_scenarios(db)
    a = report["A_procurement_to_customer"]
    assert a["purchase_order_id"] == a["sales_order_id"] == 1
    assert (a["received_on"] - a["promised_on"]).days == 12
    assert (a["fulfilled_on"] - a["customer_promise"]).days == 10
    assert report["B_warehouse_capacity"]["amount"] == Decimal("120.00")
    assert report["C_contract_concern"]["observed_percent"] < Decimal("95")
    finance = report["D_invoice_review"]
    assert finance["amount"] - finance["purchase_value"] == Decimal("25.00")
    assert report["E_overdue_workload"]["department_id"] == 1


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE employees SET department_id=9999 WHERE id=1",
        "UPDATE purchase_orders SET status='imaginary' WHERE id=1",
        "UPDATE tasks SET completed_at=created_at-interval '1 day' WHERE status='completed'",
        "UPDATE supplier_invoices SET amount=-1 WHERE id=1",
        "UPDATE stock_movements SET quantity=quantity+1 WHERE id=1",
        """INSERT INTO goods_receipts
         (id,created_at,synthetic,purchase_order_line_id,received_on,quantity)
         VALUES(99999,'2026-09-30',true,1,'2026-09-30',1)""",
        """INSERT INTO fulfilments
         (id,created_at,synthetic,sales_order_line_id,fulfilled_on,quantity,delivery_status)
         VALUES(99999,'2026-09-30',true,1,'2026-09-30',99999,'dispatched')""",
        """INSERT INTO payments(id,created_at,synthetic,invoice_id,paid_on,amount)
         VALUES(99999,'2026-09-30',true,1,'2026-09-30',99999999)""",
        """INSERT INTO stock_movements
         (id,created_at,synthetic,product_id,warehouse_id,occurred_on,kind,quantity,reason)
         VALUES(99999,'2025-10-01',true,1,1,'2025-10-01','adjustment',-1,'negative opening')""",
    ],
)
def test_database_rejects_invalid_writes(db, sql):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text(sql))


def test_exact_financial_math(db):
    result = db.scalar(
        text("SELECT sum(quantity*unit_price) FROM purchase_order_lines WHERE purchase_order_id=1")
    )
    assert isinstance(result, Decimal)
    assert result == db.scalar(
        text("SELECT amount FROM supplier_invoices WHERE purchase_order_id=1")
    )
    assert result.as_tuple().exponent == -2


def test_reseed_refused_without_changes(db):
    fingerprint = db.scalar(select(SeedRun.fingerprint))
    with pytest.raises(ValueError, match="not empty"):
        seed(db)
    assert db.scalar(select(SeedRun.fingerprint)) == fingerprint


def test_explicit_reset_and_reseed(db, dataset):
    with pytest.raises(ValueError, match="requires"):
        reset(db, "yes")
    name = db.scalar(text("SELECT current_database()"))
    reset(db, f"DELETE SYNTHETIC DATA FROM {name}")
    assert db.scalar(text("SELECT count(*) FROM purchase_orders")) == 0
    result = seed(db)
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    assert result["fingerprint"] == dataset.fingerprint()
    assert db.scalar(text("SELECT count(*) FROM purchase_orders")) == 2400


def test_migration_downgrade_roundtrip(postgres):
    name = "opspilot_test_" + uuid.uuid4().hex
    admin = create_engine(postgres.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    isolated = create_engine(postgres.url.set(database=name))
    try:
        with isolated.connect() as connection:
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            command.downgrade(config, "base")
            assert set(inspect(connection).get_table_names()) <= {"alembic_version"}
            connection.commit()
            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
    finally:
        isolated.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def test_receipts_require_matching_ledger_at_commit(db):
    # Find a still-open purchase line, receive one unit, but omit the ledger entry.
    line_id = db.scalar(
        text("""
      SELECT pl.id FROM purchase_order_lines pl
      LEFT JOIN goods_receipts r ON r.purchase_order_line_id=pl.id
      GROUP BY pl.id HAVING coalesce(sum(r.quantity),0)<pl.quantity ORDER BY pl.id LIMIT 1
    """)
    )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text("""
          INSERT INTO goods_receipts
          (id,created_at,synthetic,purchase_order_line_id,received_on,quantity)
          VALUES(99999,'2026-09-30',true,:line_id,'2026-09-30',1)
        """),
            {"line_id": line_id},
        )
        db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_api_session_transactions_are_read_only(postgres):
    from app.db.session import session

    dependency = session()
    db = next(dependency)
    try:
        assert db.scalar(text("SHOW transaction_read_only")) == "on"
    finally:
        dependency.close()
