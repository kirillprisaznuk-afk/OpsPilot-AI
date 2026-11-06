"""Run real PostgreSQL integrity/scenario queries and save reproducible evidence."""

import hashlib
import json
import statistics
import time
from pathlib import Path

from app.db.session import engine
from app.main import app
from app.services.integrity import load_dataset, validate
from app.services.scenarios import SCENARIOS, verify_scenarios
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from data.generator.company import generate


def main():
    begin = time.perf_counter()
    expected = generate()
    generation_seconds = time.perf_counter() - begin
    with Session(engine()) as db:
        loaded = load_dataset(db)
        report = validate(loaded)
        for version in loaded.rows["document_versions"]:
            content = Path(version["path"]).read_bytes()
            if hashlib.sha256(content).hexdigest() != version["sha256"]:
                raise ValueError(f"Document checksum mismatch: {version['path']}")
            loaded.documents[version["path"]] = content.decode("utf-8")
        fingerprint = loaded.fingerprint()
        if fingerprint != expected.fingerprint():
            raise ValueError("Database differs from the deterministic logical dataset")
        report["fingerprint"] = fingerprint
        report["scenarios"] = verify_scenarios(db)
        revision = db.scalar(text("SELECT version_num FROM alembic_version"))
        report["migration_head"] = revision
        report["postgres_version"] = db.scalar(text("SHOW server_version"))
        timings = []
        for _ in range(5):
            begin = time.perf_counter()
            db.execute(text(SCENARIOS["A_procurement_to_customer"])).all()
            timings.append((time.perf_counter() - begin) * 1000)
        report["join_median_ms"] = round(statistics.median(timings), 3)
        report["join_explain"] = [
            r[0]
            for r in db.execute(
                text("EXPLAIN (ANALYZE, BUFFERS) " + SCENARIOS["A_procurement_to_customer"])
            )
        ]
    with TestClient(app) as client:
        report["api_median_ms"] = {}
        for path in [
            "/health",
            "/ready",
            "/api/v1/demo/summary",
            "/api/v1/catalog/suppliers",
            "/api/v1/operations/orders/1/timeline",
        ]:
            timings = []
            for _ in range(5):
                begin = time.perf_counter()
                response = client.get(path)
                response.raise_for_status()
                timings.append((time.perf_counter() - begin) * 1000)
            report["api_median_ms"][path] = round(statistics.median(timings), 3)
    report["generation_seconds"] = round(generation_seconds, 3)
    target = Path("reports/stage1-validation.json")
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps({k: v for k, v in report.items() if k != "join_explain"}, indent=2, default=str)
    )


if __name__ == "__main__":
    main()
