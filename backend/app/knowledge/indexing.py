"""Single-transaction publication: failure preserves the previously committed index."""

import time
from datetime import UTC, datetime

from app.knowledge.chunking import parse_chunks
from app.knowledge.corpus import documents, metadata_signature, source, validate_metadata
from app.knowledge.embeddings import CONFIG, CONFIG_ID, KnowledgeError, provider
from app.knowledge.schema import chunks, indexes
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert


def index_corpus(db, rebuild=False, embedder=None):
    start = time.perf_counter()
    db.execute(text("SELECT pg_advisory_xact_lock(741902512)"))
    current = db.execute(select(indexes)).mappings().first()
    if (
        current
        and (current["config_id"] != CONFIG_ID or current["config"] != CONFIG)
        and not rebuild
    ):
        raise KnowledgeError(
            "reindex_required",
            "Embedding/chunking configuration changed; explicit --rebuild required.",
        )
    records = documents(db)
    manifest, changed, summaries = {}, [], {}
    parsing = chunking_time = embedding_time = 0.0
    embedder = embedder or provider()
    for meta in records:
        begin = time.perf_counter()
        value = source(meta)
        validate_metadata(meta, value)
        parsing += time.perf_counter() - begin
        key = str(meta["version_id"])
        manifest[key] = {
            "sha256": meta["sha256"],
            "document_id": meta["document_id"],
            "metadata": metadata_signature(meta),
        }
        previous = current["manifest"].get(key) if current else None
        if not rebuild and previous == manifest[key]:
            summaries[key] = "unchanged"
        else:
            begin = time.perf_counter()
            rows = parse_chunks(meta, value, embedder)
            chunking_time += time.perf_counter() - begin
            changed.append((meta["version_id"], rows))
            summaries[key] = "indexed"
    # Generate/validate every replacement before deleting any current record.
    for _, rows in changed:
        begin = time.perf_counter()
        vectors = embedder.encode([r["embedding_text"] for r in rows])
        for row, vector in zip(rows, vectors, strict=True):
            row["embedding"] = vector
        embedding_time += time.perf_counter() - begin
    if current and not changed and manifest == current["manifest"]:
        versions = db.scalar(select(func.count(func.distinct(chunks.c.version_id))))
        if versions != len(records):
            raise KnowledgeError(
                "incomplete_index",
                "Stored version coverage is incomplete; explicit rebuild required.",
            )
        return summary(
            db, records, summaries, 0, 0, parsing, 0, time.perf_counter() - start, chunking_time
        )
    values = dict(
        id=1, config_id=CONFIG_ID, config=CONFIG, manifest=manifest, indexed_at=datetime.now(UTC)
    )
    db.execute(
        insert(indexes)
        .values(**values)
        .on_conflict_do_update(index_elements=[indexes.c.id], set_=values)
    )
    if rebuild:
        db.execute(delete(chunks))
    else:
        keep = [int(v) for v in manifest]
        db.execute(delete(chunks).where(chunks.c.version_id.not_in(keep)))
    for version_id, rows in changed:
        db.execute(delete(chunks).where(chunks.c.version_id == version_id))
        if rows:
            db.execute(chunks.insert(), rows)
    count = db.scalar(select(func.count()).select_from(chunks))
    versions = db.scalar(select(func.count(func.distinct(chunks.c.version_id))))
    if versions != len(records) or (records and count < len(records)):
        raise KnowledgeError("incomplete_index", "Indexed version coverage failed validation.")
    return summary(
        db,
        records,
        summaries,
        sum(len(rows) for _, rows in changed),
        sum(len(rows) for _, rows in changed),
        parsing,
        embedding_time,
        time.perf_counter() - start,
        chunking_time,
    )


def summary(db, records, states, written, generated, parsing, embeddings, elapsed, chunking):
    return {
        "documents_examined": len({r["document_id"] for r in records}),
        "versions_examined": len(records),
        "documents_indexed": sum(v == "indexed" for v in states.values()),
        "documents_unchanged": sum(v == "unchanged" for v in states.values()),
        "chunks_indexed": written,
        "total_chunks": db.scalar(select(func.count()).select_from(chunks)),
        "embeddings_generated": generated,
        "failures": 0,
        "model": CONFIG,
        "source_validation_seconds": round(parsing, 6),
        "chunk_generation_seconds": round(chunking, 6),
        "parsing_chunking_seconds": round(parsing + chunking, 6),
        "embedding_seconds": round(embeddings, 6),
        "elapsed_seconds": round(elapsed, 6),
    }
