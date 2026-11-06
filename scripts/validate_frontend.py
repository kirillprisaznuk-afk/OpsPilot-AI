"""Prove Stage 6 preserved original source, prior workflow rows and unrelated resources."""

import argparse
import json
from pathlib import Path

import httpx
from app.db.session import engine
from app.workflow import schema as s
from app.workflow.common import digest
from sqlalchemy import select, text

from scripts.validate_workflow import docker, snapshot, unrelated_resources

BASELINE = Path(".local-tools/stage6-baseline")
OUTPUT = Path("reports/stage6-preservation.json")
AUTH_TABLES = {"auth_principals", "auth_roles", "auth_role_assignments", "auth_sessions"}


def row_hashes():
    with engine().begin() as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        return {
            table.name: {
                "|".join(str(row[c.name]) for c in table.primary_key.columns): digest(dict(row))
                for row in db.execute(select(table)).mappings()
            }
            for table in s.metadata.sorted_tables
            if table.name.startswith("workflow_") or table.name in AUTH_TABLES
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    database = json.loads(json.dumps(snapshot(), default=str))
    resources, rows = unrelated_resources(), row_hashes()
    base_file, row_file = args.baseline / "baseline.json", args.baseline / "row-digests.json"
    if args.capture:
        args.baseline.mkdir(parents=True, exist_ok=True)
        if base_file.exists() or row_file.exists():
            raise SystemExit("Existing Stage 6 baseline preserved; refusing to replace it.")
        base_file.write_text(
            json.dumps({"database": database, "docker": resources}, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        row_file.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        return
    accepted = json.loads(base_file.read_text(encoding="utf-8"))
    prior = json.loads(row_file.read_text(encoding="utf-8"))
    assert database["source"] == accepted["database"]["source"]
    assert database["index"] == accepted["database"]["index"]
    assert database["migration"] == "0004"
    for table, originals in prior.items():
        assert all(rows[table].get(k) == v for k, v in originals.items()), table
    assert resources["containers"] == accepted["docker"]["containers"]
    assert resources["network_ids"] == accepted["docker"]["network_ids"]
    original_volumes = set(accepted["docker"]["volume_names"])
    current_volumes = set(resources["volume_names"])
    assert original_volumes <= current_volumes
    assert current_volumes - original_volumes <= {"opspilot-stage1_opspilot_frontend_sessions"}
    with engine().connect() as db:
        assert (
            db.scalar(text("SELECT count(*) FROM pg_database WHERE datname LIKE 'opspilot_test_%'"))
            == 0
        )
    with httpx.Client(base_url="http://127.0.0.1:8001", timeout=20) as client:
        assert client.get("/ready").json() == {"status": "ready"}
        tools = client.get("/api/v1/agent/tools").json()["tools"]
        assert len(tools) == 17 and all(t["read_only"] for t in tools)
        capabilities = client.get("/api/v1/hybrid/capabilities").json()["capabilities"]
        assert len(capabilities) == 14
        knowledge = client.get("/api/v1/knowledge/status").json()
        assert knowledge["documents"] == knowledge["chunks"] == knowledge["versions"] == 44
    assert httpx.get("http://127.0.0.1:3106/login", timeout=15).status_code == 200
    report = {
        "passed": True,
        "source_fingerprint": database["source"]["fingerprint"],
        "source_integrity": database["source"]["integrity"],
        "source_scenarios": len(database["source"]["scenarios"]),
        "migration": database["migration"],
        "knowledge_documents": 44,
        "original_row_counts_verified": {name: len(items) for name, items in prior.items()},
        "current_row_counts": {name: len(items) for name, items in rows.items()},
        "prior_auth_workflow_audit_rows_unchanged": True,
        "unrelated_containers_preserved": len(resources["containers"]),
        "unrelated_networks_and_volumes_preserved": True,
        "compose": docker(
            "compose", "ps", "--format", "{{.Service}} {{.State}} {{.Health}}"
        ).splitlines(),
        "deterministic_capabilities": len(capabilities),
        "read_only_agent_tools": len(tools),
        "test_databases_remaining": 0,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({k: report[k] for k in ("passed", "source_fingerprint", "migration", "compose")})
    )


if __name__ == "__main__":
    main()
