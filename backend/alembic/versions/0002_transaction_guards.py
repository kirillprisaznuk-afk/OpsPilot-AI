"""Enforce cross-row event, ledger and payment contracts in PostgreSQL."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE FUNCTION guard_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE ordered date; permitted integer; prior bigint;
    BEGIN
      SELECT po.ordered_on, pl.quantity INTO ordered, permitted
        FROM purchase_order_lines pl JOIN purchase_orders po ON po.id=pl.purchase_order_id
        WHERE pl.id=NEW.purchase_order_line_id FOR UPDATE OF pl;
      SELECT coalesce(sum(quantity),0) INTO prior FROM goods_receipts
        WHERE purchase_order_line_id=NEW.purchase_order_line_id;
      IF NEW.received_on < ordered OR prior+NEW.quantity>permitted THEN
        RAISE EXCEPTION 'Receipt violates purchase chronology or quantity' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER receipt_guard BEFORE INSERT ON goods_receipts
      FOR EACH ROW EXECUTE FUNCTION guard_receipt();

    CREATE FUNCTION guard_fulfilment() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE ordered date; permitted integer; prior bigint;
    BEGIN
      SELECT so.ordered_on, sl.quantity INTO ordered, permitted
        FROM sales_order_lines sl JOIN sales_orders so ON so.id=sl.sales_order_id
        WHERE sl.id=NEW.sales_order_line_id FOR UPDATE OF sl;
      SELECT coalesce(sum(quantity),0) INTO prior FROM fulfilments
        WHERE sales_order_line_id=NEW.sales_order_line_id;
      IF NEW.fulfilled_on < ordered OR prior+NEW.quantity>permitted THEN
        RAISE EXCEPTION 'Fulfilment violates sales chronology or quantity' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER fulfilment_guard BEFORE INSERT ON fulfilments
      FOR EACH ROW EXECUTE FUNCTION guard_fulfilment();

    CREATE FUNCTION guard_payment() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE issued date; permitted numeric; prior numeric; state text;
    BEGIN
      SELECT issued_on, amount, status INTO issued, permitted, state
        FROM supplier_invoices WHERE id=NEW.invoice_id FOR UPDATE;
      SELECT coalesce(sum(amount),0) INTO prior FROM payments WHERE invoice_id=NEW.invoice_id;
      IF NEW.paid_on < issued OR prior+NEW.amount>permitted OR state='disputed' THEN
        RAISE EXCEPTION 'Payment violates invoice rules' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER payment_guard BEFORE INSERT ON payments
      FOR EACH ROW EXECUTE FUNCTION guard_payment();

    CREATE FUNCTION guard_stock() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE p integer; w integer; q integer; d date; minimum bigint;
    BEGIN
      PERFORM pg_advisory_xact_lock(NEW.product_id, NEW.warehouse_id);
      IF NEW.kind='receipt' THEN
        SELECT pl.product_id, po.warehouse_id, r.quantity, r.received_on INTO p,w,q,d
          FROM goods_receipts r JOIN purchase_order_lines pl ON pl.id=r.purchase_order_line_id
          JOIN purchase_orders po ON po.id=pl.purchase_order_id WHERE r.id=NEW.receipt_id;
      ELSIF NEW.kind='issue' THEN
        SELECT sl.product_id, so.warehouse_id, -f.quantity, f.fulfilled_on INTO p,w,q,d
          FROM fulfilments f JOIN sales_order_lines sl ON sl.id=f.sales_order_line_id
          JOIN sales_orders so ON so.id=sl.sales_order_id WHERE f.id=NEW.fulfilment_id;
      ELSE
        p:=NEW.product_id; w:=NEW.warehouse_id; q:=NEW.quantity; d:=NEW.occurred_on;
      END IF;
      IF (p,w,q,d) IS DISTINCT FROM
         (NEW.product_id,NEW.warehouse_id,NEW.quantity,NEW.occurred_on) THEN
        RAISE EXCEPTION 'Stock source mismatch' USING ERRCODE='23514';
      END IF;
      SELECT min(running) INTO minimum FROM (
        SELECT sum(quantity) OVER (ORDER BY occurred_on,id) AS running
        FROM stock_movements WHERE product_id=NEW.product_id AND warehouse_id=NEW.warehouse_id
      ) x;
      IF minimum<0 THEN
        RAISE EXCEPTION 'Negative historical inventory' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER stock_guard AFTER INSERT ON stock_movements
      FOR EACH ROW EXECUTE FUNCTION guard_stock();

    CREATE FUNCTION require_ledger() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE posted integer;
    BEGIN
      IF TG_TABLE_NAME='goods_receipts' THEN
        SELECT count(*) INTO posted FROM stock_movements WHERE receipt_id=NEW.id;
      ELSE
        SELECT count(*) INTO posted FROM stock_movements WHERE fulfilment_id=NEW.id;
      END IF;
      IF posted<>1 THEN
        RAISE EXCEPTION 'Operational event requires exactly one stock movement'
          USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE CONSTRAINT TRIGGER receipt_ledger AFTER INSERT ON goods_receipts
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION require_ledger();
    CREATE CONSTRAINT TRIGGER fulfilment_ledger AFTER INSERT ON fulfilments
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION require_ledger();

    CREATE FUNCTION immutable_event() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      RAISE EXCEPTION 'Event records are immutable; use explicit corrective events'
        USING ERRCODE='23514';
    END $$;
    CREATE TRIGGER immutable_stock BEFORE UPDATE OR DELETE ON stock_movements
      FOR EACH ROW EXECUTE FUNCTION immutable_event();
    CREATE TRIGGER immutable_receipt BEFORE UPDATE OR DELETE ON goods_receipts
      FOR EACH ROW EXECUTE FUNCTION immutable_event();
    CREATE TRIGGER immutable_fulfilment BEFORE UPDATE OR DELETE ON fulfilments
      FOR EACH ROW EXECUTE FUNCTION immutable_event();
    CREATE TRIGGER immutable_payment BEFORE UPDATE OR DELETE ON payments
      FOR EACH ROW EXECUTE FUNCTION immutable_event();
    CREATE INDEX ix_stock_partition ON stock_movements(product_id,warehouse_id,occurred_on,id);
    """)


def downgrade():
    op.execute("""
    DROP INDEX ix_stock_partition;
    DROP TRIGGER immutable_stock ON stock_movements;
    DROP TRIGGER immutable_receipt ON goods_receipts;
    DROP TRIGGER immutable_fulfilment ON fulfilments;
    DROP TRIGGER immutable_payment ON payments;
    DROP TRIGGER receipt_ledger ON goods_receipts;
    DROP TRIGGER fulfilment_ledger ON fulfilments;
    DROP TRIGGER stock_guard ON stock_movements;
    DROP TRIGGER payment_guard ON payments;
    DROP TRIGGER fulfilment_guard ON fulfilments;
    DROP TRIGGER receipt_guard ON goods_receipts;
    DROP FUNCTION immutable_event();
    DROP FUNCTION require_ledger();
    DROP FUNCTION guard_stock();
    DROP FUNCTION guard_payment();
    DROP FUNCTION guard_fulfilment();
    DROP FUNCTION guard_receipt();
    """)
