from pathlib import Path

from app.core.config import settings
from app.knowledge.contracts import SearchRequest
from app.knowledge.corpus import (
    documents,
    metadata_signature,
    public_metadata,
    source,
    validate_metadata,
)
from app.knowledge.embeddings import CONFIG, CONFIG_ID, KnowledgeError
from app.knowledge.schema import chunks, indexes
from app.knowledge.search import eligible_documents
from sqlalchemy import func, select, text


def status(db):
    record = db.execute(select(indexes)).mappings().first()
    records = documents(db)
    state = "not_indexed"
    if record:
        state = "ready"
        if record["config_id"] != CONFIG_ID or record["config"] != CONFIG:
            state = "reindex_required"
        elif set(db.scalars(select(chunks.c.version_id).distinct())) != {
            int(v) for v in record["manifest"]
        }:
            state = "incomplete_index"
        elif set(record["manifest"]) != {str(m["version_id"]) for m in records} or any(
            record["manifest"][str(m["version_id"])]["metadata"] != metadata_signature(m)
            for m in records
        ):
            state = "stale"
    return dict(
        state=state,
        documents=len({m["document_id"] for m in records}),
        versions=len(records),
        chunks=db.scalar(select(func.count()).select_from(chunks)),
        configuration=record["config"] if record else None,
        configured_model=CONFIG,
        model_cached=(Path(settings().embedding_cache) / "revision.json").exists(),
        index_bytes=db.scalar(text("SELECT pg_total_relation_size('knowledge_chunks')")),
        indexed_at=record["indexed_at"].isoformat() if record else None,
    )


def list_documents(db, as_of, limit, offset):
    selected = eligible_documents(db, SearchRequest(query="list documents", as_of=as_of))
    return dict(
        documents=[public_metadata(m) for m in selected[offset : offset + limit]],
        total=len(selected),
        limit=limit,
        offset=offset,
    )


def preview(db, document_id, version_id, as_of):
    records = [m for m in documents(db) if m["document_id"] == document_id]
    if not records:
        raise KnowledgeError("document_not_found", "Registered document does not exist.", 404)
    if version_id:
        records = [m for m in records if m["version_id"] == version_id]
        if not records:
            raise KnowledgeError(
                "version_not_found", "Version does not belong to this document.", 404
            )
    effective = [
        m for m in records if m["effective_on"] <= as_of and m["published_at"].date() <= as_of
    ]
    if not effective:
        raise KnowledgeError(
            "document_not_effective",
            "Document version was not effective at the selected date.",
            404,
        )
    meta = max(effective, key=lambda m: (m["effective_on"], m["version"]))
    value = source(meta)
    validate_metadata(meta, value)
    return dict(
        metadata=public_metadata(meta),
        text=value,
        line_start=1,
        line_end=len(value.splitlines()),
        verified=True,
    )
