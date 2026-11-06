from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Record


class SupplierInvoice(Record, Base):
    __tablename__ = "supplier_invoices"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount"),
        CheckConstraint("issued_on <= due_on", name="dates"),
        CheckConstraint("status IN ('outstanding','partial','paid','disputed')", name="status"),
        CheckConstraint("currency='GBP'", name="currency"),
    )
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), unique=True)
    reference: Mapped[str] = mapped_column(String(50), unique=True)
    issued_on: Mapped[date]
    due_on: Mapped[date]
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(3), default="GBP")
    discrepancy_note: Mapped[str | None]


class Payment(Record, Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="amount"),)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("supplier_invoices.id"), index=True)
    paid_on: Mapped[date]
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class OperationalExpense(Record, Base):
    __tablename__ = "operational_expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount"),
        CheckConstraint("currency='GBP'", name="currency"),
        CheckConstraint("category IN ('rent','handling','expediting','overtime')", name="category"),
    )
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"), index=True)
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"))
    incurred_on: Mapped[date]
    category: Mapped[str] = mapped_column(String(30))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="GBP")
    basis: Mapped[str]
