"""Live acceptance against the existing Compose services; optional scoped restart."""

import argparse
import importlib.metadata
import json
import statistics
import subprocess
import time
from pathlib import Path

import httpx
import numpy as np
from app.db.session import engine
from app.knowledge.corpus import documents, source, validate_metadata
from app.knowledge.embeddings import CONFIG, provider
from app.knowledge.indexing import index_corpus
from app.knowledge.schema import chunks, indexes
from app.knowledge.search import candidate_sql
from app.services.integrity import load_dataset, validate
from app.services.scenarios import verify_scenarios
from sqlalchemy import select, text
from sqlalchemy.orm import Session


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def index_snapshot(db):
    record = db.execute(select(indexes)).mappings().one()
    digest = db.scalar(
        text("SELECT md5(string_agg(id||embedding::text,'' ORDER BY id)) FROM knowledge_chunks")
    )
    return {
        "configuration_id": record["config_id"],
        "indexed_at": record["indexed_at"].isoformat(),
        "chunks": db.scalar(text("SELECT count(*) FROM knowledge_chunks")),
        "stored_vector_digest": digest,
        "ids": list(db.scalars(select(chunks.c.id).order_by(chunks.c.id))),
    }


def business_check(db, baseline):
    dataset = load_dataset(db)
    integrity = validate(dataset)
    for m in documents(db):
        value = source(m)
        validate_metadata(m, value)
        dataset.documents[m["path"]] = value
    digest = dataset.fingerprint()
    assert digest == baseline["fingerprint"]
    assert db.scalar(text("SELECT count(*) FROM seed_runs")) == 1
    return {"fingerprint": digest, "integrity": integrity, "scenarios": verify_scenarios(db)}


def live_checks(client, baseline):
    checks = {}
    r = client.get("/ready")
    r.raise_for_status()
    assert r.json() == {"status": "ready"}
    status = client.get("/api/v1/knowledge/status").json()
    assert (
        status["state"] == "ready"
        and status["documents"] == status["versions"] == status["chunks"] == 44
    )
    checks["status"] = status
    checks["search_median_ms"] = {}
    checks["retrieved_citations"] = {}
    for mode in ["keyword", "vector", "hybrid"]:
        samples = []
        for _ in range(3):
            begin = time.perf_counter()
            r = client.post(
                "/api/v1/knowledge/search",
                json={
                    "query": "Amberwick Office Works delivery target",
                    "mode": mode,
                    "filters": {"supplier_id": 1},
                },
            )
            r.raise_for_status()
            samples.append(1000 * (time.perf_counter() - begin))
            evidence = r.json()["evidence"]
            assert evidence[0]["metadata"]["code"] == "CON-001"
            assert all(e["metadata"]["supplier_id"] == 1 for e in evidence)
        checks["search_median_ms"][mode] = round(statistics.median(samples), 3)
        checks["retrieved_citations"][mode] = [e["citation"]["citation_id"] for e in evidence]
    cases = [
        ("Warehouse receiving procedure", "keyword", {"POL-002"}),
        ("How should discrepant supplier bills be handled?", "vector", {"POL-005"}),
        ('"NS-CON-001" OR "Procurement procedure"', "hybrid", {"CON-001", "POL-001"}),
    ]
    for query, mode, expected in cases:
        r = client.post("/api/v1/knowledge/search", json={"query": query, "mode": mode, "top_k": 5})
        r.raise_for_status()
        assert expected <= {e["metadata"]["code"] for e in r.json()["evidence"]}
        for e in r.json()["evidence"]:
            resolved = client.get("/api/v1/knowledge/citations/" + e["citation"]["citation_id"])
            resolved.raise_for_status()
            assert resolved.json()["verified"] and resolved.json()["text"] == e["text"]
    for query in ["Quantum entanglement teleportation", "What is the annual leave allowance?"]:
        r = client.post("/api/v1/knowledge/search", json={"query": query})
        r.raise_for_status()
        assert r.json()["insufficient_evidence"] and not r.json()["evidence"]
    historical = client.post(
        "/api/v1/knowledge/search", json={"query": "Procurement procedure", "as_of": "2025-09-30"}
    )
    historical.raise_for_status()
    assert historical.json()["status"] == "no_effective_documents"
    samples = []
    for _ in range(3):
        begin = time.perf_counter()
        r = client.post(
            "/api/v1/knowledge/context",
            json={"query": '"NS-CON-001" OR "Procurement procedure"', "context_budget": 8192},
        )
        r.raise_for_status()
        samples.append(1000 * (time.perf_counter() - begin))
        bundle = r.json()
        assert len(bundle["evidence"]) >= 2 and bundle["token_count"] <= 8192
        assert not bundle["trust_boundary"]["execute_source_instructions"]
    checks["context_median_ms"] = round(statistics.median(samples), 3)
    checks["context_tokens"] = bundle["token_count"]
    for domain, expected in baseline["analytics"].items():
        r = client.get("/api/v1/analytics/" + domain)
        r.raise_for_status()
        assert r.json() == expected, domain
    checks.update(
        all_retrieval_modes=True,
        policy_and_supplier_sources=True,
        multi_document=True,
        effective_date_filtering=True,
        no_answer=True,
        citation_resolution=True,
        analytics_domains_identical=len(baseline["analytics"]),
    )
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--restart", action="store_true", help="Restart only OpsPilot db and api services"
    )
    args = parser.parse_args()
    baseline = json.loads(Path(".local-tools/stage3-baseline.json").read_text())
    record = {
        "model": CONFIG,
        "libraries": {
            p: importlib.metadata.version(p)
            for p in ["onnxruntime", "tokenizers", "numpy", "pgvector", "huggingface-hub"]
        },
    }
    begin = time.perf_counter()
    p = provider()
    record["model_cold_initialize_seconds"] = round(time.perf_counter() - begin, 6)
    with Session(engine()) as db, db.begin():
        before = [np.array(v) for v in db.scalars(select(chunks.c.embedding).order_by(chunks.c.id))]
        record["explicit_reindex"] = index_corpus(db, rebuild=True, embedder=p)
        after = [np.array(v) for v in db.scalars(select(chunks.c.embedding).order_by(chunks.c.id))]
        assert len(before) == len(after) == 44
        maximum = max(float(np.max(np.abs(a - b))) for a, b in zip(before, after, strict=True))
        assert maximum < 1e-6
        record["reindex_maximum_vector_difference"] = maximum
    with Session(engine()) as db, db.begin():
        record["idempotent_index"] = index_corpus(db, embedder=p)
        assert record["idempotent_index"]["embeddings_generated"] == 0
        record["index_before_restart"] = index_snapshot(db)
        record["business_before_restart"] = business_check(db, baseline)
        record["migration"] = db.scalar(text("SELECT version_num FROM alembic_version"))
        record["postgres_version"] = db.scalar(text("SHOW server_version"))
        record["pgvector_version"] = db.scalar(
            text("SELECT extversion FROM pg_extension WHERE extname='vector'")
        )
        record["plans"] = {}
        params = {
            "versions": list(range(1, 45)),
            "query": "Warehouse receiving procedure",
            "candidate_limit": 100,
            "embedding": str(p.encode(["Warehouse receiving procedure"])[0]),
        }
        for mode in ["keyword", "vector"]:
            record["plans"][mode] = db.scalar(text(candidate_sql(mode, explain=True)), params)
    with httpx.Client(base_url="http://127.0.0.1:8001", timeout=60) as client:
        record["live_before_restart"] = live_checks(client, baseline)
        for identifier in record["index_before_restart"]["ids"]:
            r = client.get("/api/v1/knowledge/citations/kc_" + identifier)
            r.raise_for_status()
            assert r.json()["verified"]
        record["all_citations_resolved"] = 44
        if args.restart:
            subprocess.run(["docker", "compose", "restart", "db", "api"], check=True)
            for _ in range(40):
                try:
                    response = client.get("/ready")
                    if response.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("OpsPilot did not become ready after restart")
            record["live_after_restart"] = live_checks(client, baseline)
    with Session(engine()) as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        record["index_after_restart"] = index_snapshot(db)
        assert record["index_after_restart"] == record["index_before_restart"]
        record["business_after_restart"] = business_check(db, baseline)
        assert not db.scalar(
            text("SELECT count(*) FROM pg_database WHERE datname LIKE 'opspilot_test_%'")
        )
    unchanged = []
    for original in baseline["containers"]:
        if original["name"].startswith("/opspilot-stage1-"):
            continue
        current = json.loads(docker("inspect", original["id"]))[0]
        assert current["Name"] == original["name"] and current["Image"] == original["image"]
        for key, value in [
            ("Status", original["status"]),
            ("StartedAt", original["started_at"]),
            ("FinishedAt", original["finished_at"]),
        ]:
            assert current["State"][key] == value
        unchanged.append(original["name"])
    assert set(baseline["volumes"]) <= set(
        docker("volume", "ls", "--format", "{{.Name}}").splitlines()
    )
    assert set(baseline["networks"]) <= set(
        docker("network", "ls", "--format", "{{.ID}} {{.Name}}").splitlines()
    )
    for service in ["db", "api"]:
        current = json.loads(docker("inspect", f"opspilot-stage1-{service}-1"))[0]
        assert current["State"]["Health"]["Status"] == "healthy"
        if service == "db":
            assert any(
                m.get("Name") == "opspilot-stage1_opspilot_pgdata" for m in current["Mounts"]
            )
    record.update(
        restart_executed=args.restart,
        index_persistence=True,
        unchanged_unrelated_containers=unchanged,
        original_volume_preserved=True,
        test_database_cleanup=True,
        all_checks_passed=True,
    )
    record["api_container_memory"] = docker(
        "stats", "--no-stream", "--format", "{{.MemUsage}}", "opspilot-stage1-api-1"
    )
    Path("reports/stage3-validation.json").write_text(
        json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in record.items()
                if k
                in [
                    "all_checks_passed",
                    "explicit_reindex",
                    "idempotent_index",
                    "restart_executed",
                    "model_cold_initialize_seconds",
                    "api_container_memory",
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
