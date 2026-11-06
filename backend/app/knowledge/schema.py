"""Derived retrieval tables have separate metadata from the business fingerprint."""

from app.models import Document, DocumentVersion
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Column,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

metadata = MetaData(
    naming_convention={"pk": "pk_%(table_name)s", "ix": "ix_%(table_name)s_%(column_0_name)s"}
)
indexes = Table(
    "knowledge_indexes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("config_id", String(64), nullable=False),
    Column("config", JSONB, nullable=False),
    Column("manifest", JSONB, nullable=False),
    Column("indexed_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("id=1", name="single_active_knowledge_index"),
)
chunks = Table(
    "knowledge_chunks",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("index_id", ForeignKey(indexes.c.id), nullable=False),
    Column("document_id", ForeignKey(Document.id), nullable=False),
    Column("version_id", ForeignKey(DocumentVersion.id), nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("heading_path", JSONB, nullable=False),
    Column("line_start", Integer, nullable=False),
    Column("line_end", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("text_sha256", String(64), nullable=False),
    Column("source_sha256", String(64), nullable=False),
    Column("search_text", Text, nullable=False),
    Column("embedding_text", Text, nullable=False),
    Column("token_count", Integer, nullable=False),
    Column("embedding", Vector(384), nullable=False),
    Column(
        "search_vector",
        TSVECTOR,
        Computed("to_tsvector('english'::regconfig, search_text)", persisted=True),
    ),
    UniqueConstraint("version_id", "ordinal", name="uq_knowledge_chunk_version_ordinal"),
    CheckConstraint(
        "ordinal>=0 AND line_start>0 AND line_end>=line_start "
        "AND token_count>0 AND token_count<=256",
        name="knowledge_chunk_bounds",
    ),
    Index("ix_knowledge_chunks_search_vector", "search_vector", postgresql_using="gin"),
    Index("ix_knowledge_chunks_version_id", "version_id"),
)
