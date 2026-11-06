"""Exact contiguous source ranges, section boundaries and whole-paragraph packing."""

import hashlib
import re

from app.knowledge.embeddings import CONFIG_ID, KnowledgeError


def parse_chunks(meta, value, embedder):
    lines = value.splitlines(keepends=True)
    if not lines or not lines[0].startswith("# ") or "\x00" in value:
        raise KnowledgeError(
            "malformed_markdown", "Markdown requires a title and valid textual content."
        )
    sections, headings = [], []
    start = None
    for i, line in enumerate(lines):
        match = re.match(r"^(#{2,6}) (.+?)\s*$", line)
        if match:
            if start is not None:
                sections.append((start, i, list(headings)))
            level = len(match[1]) - 1
            headings = headings[: level - 1] + [match[2]]
            start = i
    if start is not None:
        sections.append((start, len(lines), headings))
    if not sections:
        raise KnowledgeError(
            "malformed_markdown", "Markdown requires a named terms or policy section."
        )
    result = []
    for first, end, heading in sections:
        # Small real documents remain intact; long sections split only at blank lines.
        positions = [first] + [i + 1 for i in range(first + 1, end) if not lines[i].strip()] + [end]
        positions = sorted(set(positions))
        chunk_start = first
        for boundary in positions[1:]:
            passage = "".join(lines[chunk_start:boundary]).strip()
            embedding = meta["title"] + "\n" + " / ".join(heading) + "\n" + passage
            if embedder.token_count(embedding) <= 240:
                continue
            previous = max(
                (p for p in positions if chunk_start < p < boundary), default=chunk_start
            )
            if previous == chunk_start:
                raise KnowledgeError(
                    "clause_too_long",
                    "A complete paragraph exceeds the model budget; source review is required.",
                )
            result.append(make_chunk(meta, lines, chunk_start, previous, heading, embedder))
            chunk_start = previous
        if "".join(lines[chunk_start:end]).strip():
            result.append(make_chunk(meta, lines, chunk_start, end, heading, embedder))
    for ordinal, chunk in enumerate(result):
        chunk["ordinal"] = ordinal
        chunk["id"] = hashlib.sha256(
            f"{meta['version_id']}:{ordinal}:{chunk['text_sha256']}:{CONFIG_ID}".encode()
        ).hexdigest()
    return result


def make_chunk(meta, lines, first, end, heading, embedder):
    while first < end and not lines[first].strip():
        first += 1
    while end > first and not lines[end - 1].strip():
        end -= 1
    passage = "".join(lines[first:end])
    embedding = meta["title"] + "\n" + " / ".join(heading) + "\n" + passage
    count = embedder.token_count(embedding)
    if count > 256:
        raise KnowledgeError("clause_too_long", "A paragraph exceeds the embedding budget.")
    return dict(
        index_id=1,
        document_id=meta["document_id"],
        version_id=meta["version_id"],
        heading_path=heading,
        line_start=first + 1,
        line_end=end,
        text=passage,
        text_sha256=hashlib.sha256(passage.encode()).hexdigest(),
        source_sha256=meta["sha256"],
        search_text="\n".join(
            str(v or "")
            for v in [
                meta["code"],
                meta["contract_reference"],
                meta["title"],
                meta["supplier"],
                passage,
            ]
        ),
        embedding_text=embedding,
        token_count=count,
    )
