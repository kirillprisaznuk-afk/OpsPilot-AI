import hashlib
import re

from app.knowledge.corpus import documents, source
from app.knowledge.embeddings import KnowledgeError
from app.knowledge.schema import chunks
from sqlalchemy import select


def citation(row, meta):
    return dict(
        citation_id="kc_" + row["id"],
        document_id=meta["document_id"],
        document_version_id=meta["version_id"],
        chunk_id=row["id"],
        title=meta["title"],
        version=meta["version"],
        section=row["heading_path"],
        line_start=row["line_start"],
        line_end=row["line_end"],
        effective_on=meta["effective_on"],
        source_sha256=meta["sha256"],
        text_sha256=row["text_sha256"],
        source_reference=f"/api/v1/knowledge/documents/{meta['document_id']}/versions/{meta['version_id']}",
    )


def verify(row, meta):
    value = source(meta)
    resolved = "".join(value.splitlines(keepends=True)[row["line_start"] - 1 : row["line_end"]])
    if (
        row["document_id"] != meta["document_id"]
        or row["version_id"] != meta["version_id"]
        or row["source_sha256"] != meta["sha256"]
        or resolved != row["text"]
        or hashlib.sha256(resolved.encode()).hexdigest() != row["text_sha256"]
    ):
        raise KnowledgeError(
            "citation_integrity_failure",
            "Indexed passage no longer resolves to the registered source.",
        )
    return resolved


def resolve(db, identifier):
    if not re.fullmatch(r"kc_[a-f0-9]{64}", identifier):
        raise KnowledgeError("invalid_citation", "Citation identifier is invalid.", 422)
    row = db.execute(select(chunks).where(chunks.c.id == identifier[3:])).mappings().first()
    if row is None:
        raise KnowledgeError(
            "citation_not_found", "Citation is no longer present in the active index.", 404
        )
    meta = next((m for m in documents(db) if m["version_id"] == row["version_id"]), None)
    if meta is None:
        raise KnowledgeError("source_unavailable", "Citation source registration is unavailable.")
    return {"citation": citation(row, meta), "text": verify(row, meta), "verified": True}
