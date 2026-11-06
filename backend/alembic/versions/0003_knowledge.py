"""Derived knowledge index and pgvector; business tables remain untouched."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

revision = "0003"
down_revision = "0002"
branch_labels = depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_indexes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_id", sa.String(64), nullable=False),
        sa.Column("config", JSONB(), nullable=False),
        sa.Column("manifest", JSONB(), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id=1", name="single_active_knowledge_index"),
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("index_id", sa.Integer(), sa.ForeignKey("knowledge_indexes.id"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column(
            "version_id", sa.Integer(), sa.ForeignKey("document_versions.id"), nullable=False
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading_path", JSONB(), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(64), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("embedding_text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column(
            "search_vector",
            TSVECTOR(),
            sa.Computed("to_tsvector('english'::regconfig, search_text)", persisted=True),
        ),
        sa.UniqueConstraint("version_id", "ordinal", name="uq_knowledge_chunk_version_ordinal"),
        sa.CheckConstraint(
            "ordinal>=0 AND line_start>0 AND line_end>=line_start "
            "AND token_count>0 AND token_count<=256",
            name="knowledge_chunk_bounds",
        ),
    )
    op.create_index(
        "ix_knowledge_chunks_search_vector",
        "knowledge_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.create_index("ix_knowledge_chunks_version_id", "knowledge_chunks", ["version_id"])


def downgrade():
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_indexes")
    # The extension may be shared by other application schemas; retain it safely.
