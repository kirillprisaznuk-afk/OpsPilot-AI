from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Record


class Department(Record, Base):
    __tablename__ = "departments"
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Employee(Record, Base):
    __tablename__ = "employees"
    name: Mapped[str] = mapped_column(String(100))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    business_email: Mapped[str] = mapped_column(String(150), unique=True)


class BusinessRole(Record, Base):
    __tablename__ = "business_roles"
    name: Mapped[str] = mapped_column(String(100), unique=True)
    responsibility: Mapped[str]


class Responsibility(Record, Base):
    __tablename__ = "responsibilities"
    __table_args__ = (UniqueConstraint("employee_id", "role_id"),)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("business_roles.id"))
