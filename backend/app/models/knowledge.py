from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Record


class Document(Record, Base):
    __tablename__ = "documents"
    code: Mapped[str] = mapped_column(String(50), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    document_type: Mapped[str] = mapped_column(String(50))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("supplier_contracts.id"), index=True)


class DocumentVersion(Record, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version"),
        CheckConstraint("version > 0", name="version"),
    )
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    version: Mapped[int]
    effective_on: Mapped[date]
    path: Mapped[str] = mapped_column(String(200), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))


class SeedRun(Record, Base):
    __tablename__ = "seed_runs"
    seed: Mapped[int]
    generator_version: Mapped[str] = mapped_column(String(30))
    fingerprint: Mapped[str] = mapped_column(String(64))
