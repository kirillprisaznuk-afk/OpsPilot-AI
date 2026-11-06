from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Record


class Incident(Record, Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(
            "category IN ('supplier_delay','shortage','capacity','invoice')", name="category"
        ),
        CheckConstraint("severity IN ('low','medium','high','critical')", name="severity"),
        CheckConstraint("status IN ('open','investigating','resolved','escalated')", name="status"),
        CheckConstraint("closed_at IS NULL OR closed_at >= created_at", name="dates"),
        CheckConstraint("(status='resolved') = (closed_at IS NOT NULL)", name="closure"),
        CheckConstraint(
            "(category='supplier_delay' AND purchase_order_id IS NOT NULL) OR "
            "(category='shortage' AND shortage_id IS NOT NULL) OR "
            "(category='capacity' AND sales_order_id IS NOT NULL AND warehouse_id IS NOT NULL) OR "
            "(category='invoice' AND invoice_id IS NOT NULL)",
            name="evidence",
        ),
    )
    category: Mapped[str] = mapped_column(String(30), index=True)
    severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), index=True)
    description: Mapped[str]
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    purchase_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_orders.id"), index=True
    )
    shortage_id: Mapped[int | None] = mapped_column(ForeignKey("shortages.id"), index=True)
    sales_order_id: Mapped[int | None] = mapped_column(ForeignKey("sales_orders.id"), index=True)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("supplier_invoices.id"), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Task(Record, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("priority IN ('low','normal','high','urgent')", name="priority"),
        CheckConstraint("status IN ('open','active','completed','escalated')", name="status"),
        CheckConstraint("due_at >= created_at", name="due"),
        CheckConstraint("completed_at IS NULL OR completed_at >= created_at", name="completion"),
        CheckConstraint(
            "(status='completed') = (completed_at IS NOT NULL)", name="status_completion"
        ),
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str]
    owner_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"), index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"))
    priority: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskStatusHistory(Record, Base):
    __tablename__ = "task_status_history"
    __table_args__ = (
        CheckConstraint("status IN ('open','active','completed','escalated')", name="status"),
    )
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    status: Mapped[str] = mapped_column(String(20))
