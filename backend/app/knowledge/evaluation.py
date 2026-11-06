"""Offline relevance labels are consumed only by evaluation, never production search."""

import json
import math
import statistics
import time
from pathlib import Path

from app.knowledge.citations import resolve
from app.knowledge.contracts import SearchRequest
from app.knowledge.embeddings import CONFIG
from app.knowledge.search import search


def evaluate(db, dataset_path=Path("data/evaluation/retrieval.json")):
    data = json.loads(dataset_path.read_text())
    results = {
        "dataset_version": data["version"],
        "queries": len(data["cases"]),
        "model": CONFIG,
        "modes": {},
    }
    for mode in ["keyword", "vector", "hybrid"]:
        rows = []
        citation_ok = citation_total = 0
        for case in data["cases"]:
            request = SearchRequest(
                query=case["query"],
                mode=mode,
                top_k=5,
                as_of=case.get("as_of", "2026-09-30"),
                filters=case.get("filters", {}),
            )
            begin = time.perf_counter()
            response = search(db, request)
            milliseconds = (time.perf_counter() - begin) * 1000
            expected = {(r["code"], r["section"]) for r in case["relevant"]}
            retrieved = [
                (r["metadata"]["code"], " / ".join(r["section"])) for r in response["evidence"]
            ]
            relevant = [r in expected for r in retrieved]
            recalls = (
                {str(k): len(set(retrieved[:k]) & expected) / len(expected) for k in [1, 3, 5]}
                if expected
                else None
            )
            reciprocal = (
                next((1 / i for i, good in enumerate(relevant, 1) if good), 0) if expected else None
            )
            for e in response["evidence"]:
                citation_total += 1
                check = resolve(db, e["citation"]["citation_id"])
                citation_ok += check["verified"] and check["text"] == e["text"]
            dcg = sum(int(good) / math.log2(i + 1) for i, good in enumerate(relevant, 1))
            ideal = sum(1 / math.log2(i + 1) for i in range(1, min(5, len(expected)) + 1))
            rows.append(
                dict(
                    id=case["id"],
                    query=case["query"],
                    kind=case["kind"],
                    expected=sorted(expected),
                    retrieved=retrieved,
                    recall=recalls,
                    reciprocal_rank=reciprocal,
                    precision_at_5=sum(relevant) / 5 if expected else None,
                    ndcg_at_5=dcg / ideal if ideal else None,
                    no_answer_correct=not response["evidence"] if not expected else None,
                    status=response["status"],
                    elapsed_ms=round(milliseconds, 3),
                )
            )
        positives = [r for r in rows if r["recall"] is not None]
        negatives = [r for r in rows if r["no_answer_correct"] is not None]
        latencies = sorted(r["elapsed_ms"] for r in rows)
        results["modes"][mode] = {
            "answerable_queries": len(positives),
            "negative_queries": len(negatives),
            "recall_at_1": statistics.mean(r["recall"]["1"] for r in positives),
            "recall_at_3": statistics.mean(r["recall"]["3"] for r in positives),
            "recall_at_5": statistics.mean(r["recall"]["5"] for r in positives),
            "mrr_at_5": statistics.mean(r["reciprocal_rank"] for r in positives),
            "precision_at_5": statistics.mean(r["precision_at_5"] for r in positives),
            "ndcg_at_5": statistics.mean(r["ndcg_at_5"] for r in positives),
            "citation_resolution_accuracy": citation_ok / citation_total
            if citation_total
            else None,
            "no_answer_accuracy": statistics.mean(r["no_answer_correct"] for r in negatives),
            "latency_median_ms": statistics.median(latencies),
            "latency_p95_ms": latencies[math.ceil(0.95 * len(latencies)) - 1],
            "first_query_ms": rows[0]["elapsed_ms"],
            "cases": rows,
        }
    return results
