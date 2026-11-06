import json

from app.knowledge.embeddings import provider
from app.knowledge.search import TRUST, search


def build_context(db, request):
    response = search(db, request)
    bundle = dict(
        question=request.query,
        business_context=request.business_context,
        as_of=request.as_of,
        evidence=[],
        citations=[],
        coverage="no_evidence",
        insufficient_evidence=True,
        omitted_chunks=0,
        token_count=0,
        token_count_basis=(
            "MiniLM WordPiece count of complete serialized bundle; not a future LLM tokenizer"
        ),
        context_budget=request.context_budget,
        trust_boundary=TRUST,
    )
    tokenizer = provider()

    # Count the full serialized structure, including metadata/trust instructions.
    def count(value):
        return tokenizer.token_count(
            json.dumps(value, default=str, ensure_ascii=False, sort_keys=True)
        )

    selected = []
    for row in response["evidence"]:
        if any(r["chunk_id"] == row["chunk_id"] for r in selected):
            continue
        proposed = {
            **bundle,
            "evidence": selected + [row],
            "citations": [r["citation"]["citation_id"] for r in selected + [row]],
            "coverage": "bounded_evidence_completeness_unverified",
            "insufficient_evidence": False,
            "omitted_chunks": len(response["evidence"]) - len(selected) - 1,
            "token_count": request.context_budget,
        }
        if count(proposed) <= request.context_budget:
            selected.append(row)
    selected.sort(
        key=lambda r: (r["document_id"], r["document_version_id"], r["citation"]["line_start"])
    )
    bundle.update(
        evidence=selected,
        citations=[r["citation"]["citation_id"] for r in selected],
        coverage="bounded_evidence_completeness_unverified"
        if selected
        else "no_evidence_within_budget",
        insufficient_evidence=not selected,
        omitted_chunks=len(response["evidence"]) - len(selected),
    )
    bundle["token_count"] = count({**bundle, "token_count": request.context_budget})
    if bundle["token_count"] > request.context_budget:
        # Even the envelope cannot fit; do not silently exceed the requested budget.
        from app.knowledge.embeddings import KnowledgeError

        raise KnowledgeError(
            "context_budget_too_small", "Budget cannot hold the question and trust metadata.", 422
        )
    return bundle
