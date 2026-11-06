"""Read-only runtime/regression acceptance. Does not automatically call a paid LLM."""

import argparse
import json
import subprocess
import time
from pathlib import Path

import httpx
from app.agent.database import agent_session, verify_reader
from app.db.session import engine
from app.knowledge.evaluation import evaluate
from sqlalchemy import text
from sqlalchemy.orm import Session

from scripts.validate_knowledge import business_check, docker, index_snapshot, live_checks


def agent_http(client):
    r = client.get("/api/v1/agent/status")
    r.raise_for_status()
    state = r.json()
    r = client.get("/api/v1/agent/tools")
    r.raise_for_status()
    tools = r.json()["tools"]
    assert len(tools) == 17 and all(t["read_only"] for t in tools)
    assert not {
        "execute_sql",
        "shell",
        "create_task",
        "approve_invoice",
        "read_file",
        "browse_web",
    } & {t["name"] for t in tools}
    result = {"status": state, "tools": len(tools), "query_invoked": False}
    if state["state"] == "provider_not_configured":
        r = client.post(
            "/api/v1/agent/query",
            json={
                "question": (
                    "Compare supplier performance with its applicable contract "
                    "and escalation policy."
                )
            },
        )
        r.raise_for_status()
        body = r.json()
        assert body["status"] == "provider_not_configured" and body["usage"]["llm_calls"] == 0
        assert body["usage"]["total_tokens"] is None and not body["evidence"]
        result.update(query_invoked=True, unconfigured_response=body)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--restart", action="store_true")
    p.add_argument("--expected-migration", default="0003")
    p.add_argument("--baseline", default=".local-tools/stage4-baseline/stage3-baseline.json")
    p.add_argument("--output", default="reports/stage4-validation.json")
    p.add_argument("--retrieval-output", default="reports/stage4-retrieval-regression.json")
    args = p.parse_args()
    baseline = json.loads(Path(args.baseline).read_text())
    accepted = json.loads(Path("reports/stage3-validation.json").read_text())
    report = {"baseline_fingerprint": baseline["fingerprint"]}
    with Session(engine()) as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        report["business_before"] = business_check(db, baseline)
        report["index_before"] = index_snapshot(db)
        assert report["index_before"] == accepted["index_after_restart"]
        report["migration"] = db.scalar(text("SELECT version_num FROM alembic_version"))
        assert report["migration"] == args.expected_migration
        assert db.scalar(text("SELECT count(*) FROM knowledge_chunks")) == 44
        report["pgvector"] = db.scalar(
            text("SELECT extversion FROM pg_extension WHERE extname='vector'")
        )
        regression = evaluate(db)
    previous = json.loads(Path("reports/stage3-retrieval-evaluation.json").read_text())
    for mode, values in previous["modes"].items():
        for key in [
            "recall_at_1",
            "recall_at_3",
            "recall_at_5",
            "mrr_at_5",
            "citation_resolution_accuracy",
            "no_answer_accuracy",
        ]:
            assert abs(regression["modes"][mode][key] - values[key]) < 1e-9
    Path(args.retrieval_output).write_text(
        json.dumps(regression, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    report["retrieval_quality_unchanged"] = True
    with agent_session() as db:
        verify_reader(db)
        report["reader_role"] = db.scalar(text("SELECT current_user"))
        report["reader_isolation"] = db.scalar(text("SHOW transaction_isolation"))
        report["reader_transaction"] = db.scalar(text("SHOW transaction_read_only"))
        for privilege in ["INSERT", "UPDATE", "DELETE", "TRUNCATE"]:
            assert not db.scalar(
                text("SELECT has_table_privilege(current_user,'suppliers',:privilege)"),
                {"privilege": privilege},
            )
    with httpx.Client(base_url="http://127.0.0.1:8001", timeout=60) as client:
        report["prior_live_before"] = live_checks(client, baseline)
        report["agent_before"] = agent_http(client)
        for identifier in report["index_before"]["ids"]:
            r = client.get("/api/v1/knowledge/citations/kc_" + identifier)
            r.raise_for_status()
            assert r.json()["verified"]
        report["all_citations_resolved"] = 44
        if args.restart:
            subprocess.run(["docker", "compose", "restart", "db", "api"], check=True)
            for _ in range(40):
                try:
                    if client.get("/ready").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("OpsPilot readiness failed after restart.")
            report["prior_live_after"] = live_checks(client, baseline)
            report["agent_after"] = agent_http(client)
    with Session(engine()) as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        report["business_after"] = business_check(db, baseline)
        report["index_after"] = index_snapshot(db)
        assert report["index_before"] == report["index_after"]
        assert (
            db.scalar(text("SELECT count(*) FROM pg_database WHERE datname LIKE 'opspilot_test_%'"))
            == 0
        )
    unchanged = []
    for original in baseline["containers"]:
        if original["name"].startswith("/opspilot-stage1-"):
            continue
        current = json.loads(docker("inspect", original["id"]))[0]
        assert current["Name"] == original["name"] and current["Image"] == original["image"]
        for key, old in [
            ("Status", original["status"]),
            ("StartedAt", original["started_at"]),
            ("FinishedAt", original["finished_at"]),
        ]:
            assert current["State"][key] == old
        unchanged.append(original["name"])
    assert set(baseline["volumes"]) <= set(
        docker("volume", "ls", "--format", "{{.Name}}").splitlines()
    )
    assert set(baseline["networks"]) <= set(
        docker("network", "ls", "--format", "{{.ID}} {{.Name}}").splitlines()
    )
    report.update(
        unrelated_containers_preserved=unchanged,
        restart_executed=args.restart,
        prior_stages_runtime_passed=True,
        test_database_cleanup=True,
        live_llm_acceptance="BLOCKED"
        if report["agent_before"]["status"]["state"] == "provider_not_configured"
        else "NOT_RUN",
        ready_for_stage5=False,
    )
    Path(args.output).write_text(
        json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "migration",
                    "pgvector",
                    "retrieval_quality_unchanged",
                    "reader_role",
                    "restart_executed",
                    "prior_stages_runtime_passed",
                    "live_llm_acceptance",
                    "ready_for_stage5",
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
