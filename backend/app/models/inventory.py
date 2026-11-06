from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Record


class Warehouse(Record, Base):
    __tablename__ = "warehouses"
    name: Mapped[str] = mapped_column(String(100), unique=True)
    city: Mapped[str] = mapped_column(String(80))


class Product(Record, Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("reorder_point >= 0", name="reorder"),)
    sku: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(60))
    reorder_point: Mapped[int]


class GoodsReceipt(Record, Base):
    __tablename__ = "goods_receipts"
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity"),)
    purchase_order_line_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_order_lines.id"), index=True
    )
    received_on: Mapped[date] = mapped_column(index=True)
    quantity: Mapped[int]


class StockMovement(Record, Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        Index("ix_stock_partition", "product_id", "warehouse_id", "occurred_on", "id"),
        UniqueConstraint("receipt_id"),
        UniqueConstraint("fulfilment_id"),
        CheckConstraint(
            "(kind='receipt' AND quantity > 0 AND receipt_id IS NOT NULL "
            "AND fulfilment_id IS NULL) OR (kind='issue' AND quantity < 0 "
            "AND fulfilment_id IS NOT NULL AND receipt_id IS NULL) OR "
            "(kind='adjustment' AND quantity <> 0 AND receipt_id IS NULL "
            "AND fulfilment_id IS NULL AND reason IS NOT NULL)",
            name="source",
        ),
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    occurred_on: Mapped[date] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[int]
    receipt_id: Mapped[int | None] = mapped_column(ForeignKey("goods_receipts.id"))
    fulfilment_id: Mapped[int | None] = mapped_column(ForeignKey("fulfilments.id"))
    reason: Mapped[str | None]


class Shortage(Record, Base):
    __tablename__ = "shortages"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity"),
        CheckConstraint("resolved_on IS NULL OR resolved_on >= detected_on", name="dates"),
    )
    sales_order_line_id: Mapped[int] = mapped_column(
        ForeignKey("sales_order_lines.id"), unique=True
    )
    expected_purchase_line_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_order_lines.id"), index=True
    )
    detected_on: Mapped[date]
    resolved_on: Mapped[date | None]
    quantity: Mapped[int]
