from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Record


class Customer(Record, Base):
    __tablename__ = "customers"
    name: Mapped[str] = mapped_column(String(150), unique=True)
    sector: Mapped[str] = mapped_column(String(60))


class SalesOrder(Record, Base):
    __tablename__ = "sales_orders"
    __table_args__ = (
        CheckConstraint("ordered_on <= promised_on", name="dates"),
        CheckConstraint("status IN ('open','backorder','partial','fulfilled')", name="status"),
        CheckConstraint("currency = 'GBP'", name="currency"),
    )
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    ordered_on: Mapped[date]
    promised_on: Mapped[date] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(3), default="GBP")


class SalesOrderLine(Record, Base):
    __tablename__ = "sales_order_lines"
    __table_args__ = (
        UniqueConstraint("sales_order_id", "product_id"),
        CheckConstraint("quantity > 0 AND unit_price > 0", name="amounts"),
    )
    sales_order_id: Mapped[int] = mapped_column(ForeignKey("sales_orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int]
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class Fulfilment(Record, Base):
    __tablename__ = "fulfilments"
    sales_order_line_id: Mapped[int] = mapped_column(ForeignKey("sales_order_lines.id"), index=True)
    fulfilled_on: Mapped[date] = mapped_column(index=True)
    quantity: Mapped[int]
    delivery_status: Mapped[str] = mapped_column(String(20))
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity"),
        CheckConstraint("delivery_status IN ('dispatched','delivered')", name="delivery_status"),
    )
