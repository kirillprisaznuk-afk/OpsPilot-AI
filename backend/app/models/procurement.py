from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Record


class Supplier(Record, Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint("status IN ('active','under_review','inactive')", name="status"),
    )
    name: Mapped[str] = mapped_column(String(150), unique=True)
    country: Mapped[str] = mapped_column(String(2))
    category: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20))


class SupplierContract(Record, Base):
    __tablename__ = "supplier_contracts"
    __table_args__ = (
        CheckConstraint("effective_date <= expires_on", name="dates"),
        CheckConstraint("on_time_target BETWEEN 0 AND 100", name="target"),
        CheckConstraint("payment_days > 0 AND escalation_days > 0", name="terms"),
    )
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    reference: Mapped[str] = mapped_column(String(50), unique=True)
    effective_date: Mapped[date]
    expires_on: Mapped[date]
    on_time_target: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    payment_days: Mapped[int]
    escalation_days: Mapped[int]


class PurchaseOrder(Record, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        CheckConstraint("ordered_on <= promised_on", name="dates"),
        CheckConstraint("status IN ('open','partial','received')", name="status"),
        CheckConstraint("currency = 'GBP'", name="currency"),
    )
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("supplier_contracts.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    ordered_on: Mapped[date]
    promised_on: Mapped[date] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(3), default="GBP")


class PurchaseOrderLine(Record, Base):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        UniqueConstraint("purchase_order_id", "product_id"),
        CheckConstraint("quantity > 0 AND unit_price > 0", name="amounts"),
    )
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int]
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
