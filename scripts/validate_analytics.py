"""Stage 2 acceptance: immutable data, SQL plans, bounded queries and actual API results."""

import argparse
import hashlib
import json
import statistics
import time
from decimal import Decimal
from pathlib import Path

import httpx
from app.analytics import finance, inventory, procurement, relationships, workforce
from app.analytics.common import bindings
from app.analytics.contracts import AnalyticsQuery
from app.db.session import engine
from app.main import app
from app.services.integrity import load_dataset, validate
from app.services.scenarios import verify_scenarios
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.orm import Session

DOMAINS = [
    "overview",
    "procurement",
    "suppliers",
    "inventory",
    "warehouses",
    "fulfilment",
    "finance",
    "workforce",
    "incidents",
    "insights",
]


def number(result, key):
    value = result["metrics"][key]["value"]
    return Decimal(str(value)) if value is not None else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live-url", help="Optional actual Compose API URL, e.g. http://127.0.0.1:8001"
    )
    parser.add_argument("--output", type=Path, default=Path("reports/stage2-validation.json"))
    args = parser.parse_args()
    q = AnalyticsQuery()
    record = {
        "observation_start": str(q.start_date),
        "observation_end": str(q.end_date),
        "as_of": str(q.as_of),
        "schema_migration_added": False,
        "analytics_architecture": "PostgreSQL aggregations; bounded Python response construction",
    }
    with Session(engine()) as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        dataset = load_dataset(db)
        record["integrity"] = validate(dataset)
        for version in dataset.rows["document_versions"]:
            content = Path(version["path"]).read_bytes()
            if hashlib.sha256(content).hexdigest() != version["sha256"]:
                raise ValueError("Document checksum changed")
            dataset.documents[version["path"]] = content.decode("utf-8")
        baseline = json.loads(Path("reports/docker-acceptance.json").read_text())["fingerprint"]
        record["fingerprint_before"] = baseline
        record["fingerprint_after"] = dataset.fingerprint()
        if record["fingerprint_after"] != baseline:
            raise ValueError("Stage 1 dataset fingerprint changed")
        record["stage1_scenarios"] = verify_scenarios(db)
        record["migration_head"] = db.scalar(text("SELECT version_num FROM alembic_version"))
        record["postgres_version"] = db.scalar(text("SHOW server_version"))
        shortage_id = record["stage1_scenarios"]["A_procurement_to_customer"]["shortage_id"]
        queries = {
            "procurement": (procurement.aggregate_sql(), {}),
            "supplier_comparison_grain": (procurement.aggregate_sql("supplier"), {}),
            "inventory": (inventory.aggregate_sql(), {}),
            "finance": (finance.aggregate_sql(), {}),
            "workforce": (workforce.aggregate_sql(), {}),
            "investigation": (
                relationships.evidence_sql(),
                {"root_type": "shortage", "root_id": shortage_id},
            ),
        }
        record["query_plans"] = {}
        for name, (sql, extra) in queries.items():
            timings = []
            for _ in range(3):
                start = time.perf_counter()
                db.execute(text(sql), {**bindings(q), **extra}).all()
                timings.append(1000 * (time.perf_counter() - start))
            plan = db.execute(
                text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql), {**bindings(q), **extra}
            ).scalar_one()[0]
            record["query_plans"][name] = {
                "median_ms": round(statistics.median(timings), 3),
                "planning_ms": plan["Planning Time"],
                "execution_ms": plan["Execution Time"],
                "plan": plan["Plan"],
            }
    # In-process capture proves constant SQL round trips. Live HTTP timing is separate.
    statements = []

    def capture(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().lower().startswith(("select", "with")):
            statements.append(statement)

    event.listen(engine(), "before_cursor_execute", capture)
    record["sql_query_counts"] = {}
    try:
        with TestClient(app) as local:
            for domain in DOMAINS:
                statements.clear()
                response = local.get("/api/v1/analytics/" + domain)
                response.raise_for_status()
                record["sql_query_counts"][domain] = len(statements)
    finally:
        event.remove(engine(), "before_cursor_execute", capture)
    cache = {}
    record["api_median_ms"] = {}
    client = httpx.Client(base_url=args.live_url, timeout=30) if args.live_url else TestClient(app)
    with client as client:
        for domain in DOMAINS:
            timings = []
            for _ in range(3):
                start = time.perf_counter()
                response = client.get("/api/v1/analytics/" + domain)
                response.raise_for_status()
                timings.append(1000 * (time.perf_counter() - start))
            cache[domain] = response.json()
            record["api_median_ms"][domain] = round(statistics.median(timings), 3)
        for key, metric in cache["overview"]["metrics"].items():
            domain, field = key.split(".", 1)
            if metric != cache[domain]["metrics"][field]:
                raise ValueError("Overview/domain mismatch: " + key)
        # Comparison rows describe the current period only; request the same scope
        # from the detail endpoint rather than comparing different comparison metadata.
        supplier = client.get("/api/v1/analytics/suppliers/1?include_comparison=false")
        supplier.raise_for_status()
        if (
            supplier.json()["metrics"]["on_time_rate"]
            != cache["suppliers"]["breakdowns"][0]["metrics"]["on_time_rate"]
        ):
            raise ValueError("Supplier detail/comparison mismatch")
        roots = {
            "supplier": 1,
            "purchase_order": 1,
            "sales_order": 1,
            "shortage": shortage_id,
            "warehouse": 1,
            "incident": record["stage1_scenarios"]["A_procurement_to_customer"]["incident_id"],
            "invoice": record["stage1_scenarios"]["D_invoice_review"]["invoice_id"],
            "department": 1,
            "task": record["stage1_scenarios"]["A_procurement_to_customer"]["task_id"],
            "product": 1,
        }
        record["investigations"] = {}
        for kind, identifier in roots.items():
            response = client.get(f"/api/v1/analytics/investigations/{kind}/{identifier}?limit=100")
            response.raise_for_status()
            body = response.json()
            assert body["evidence"] and len(body["evidence"]) <= 100
            assert all(r["event_time"] < "2026-10-01" for r in body["evidence"])
            record["investigations"][kind] = {
                "entity_id": identifier,
                "total_evidence": body["total"],
                "returned_evidence": len(body["evidence"]),
            }

        def focused(path):
            response = client.get("/api/v1/analytics/investigations/" + path)
            response.raise_for_status()
            return response.json()

        operational = {}
        for kind in ("supplier", "department"):
            mode = "open_tasks_only" if kind == "supplier" else "overdue_tasks_only"
            first = focused(f"{kind}/1?evidence_kind=tasks&{mode}=true&limit=100")
            workforce_report = client.get(
                f"/api/v1/analytics/workforce?{kind}_id=1&include_trends=false"
            )
            workforce_report.raise_for_status()
            metric = "open_tasks" if kind == "supplier" else "overdue_tasks"
            assert first["total"] == int(number(workforce_report.json(), metric))
            evidence = list(first["evidence"])
            for offset in range(100, first["total"], 100):
                evidence.extend(
                    focused(f"{kind}/1?evidence_kind=tasks&{mode}=true&limit=100&offset={offset}")[
                        "evidence"
                    ]
                )
            assert len({e["entity_id"] for e in evidence}) == first["total"]
            assert all(
                e["observed_status"] in {"open", "active", "escalated"}
                and e["title"]
                and e["due_at"]
                for e in evidence
            )
            operational[kind + "_unfinished_tasks"] = {
                "total": first["total"],
                "all_pages_verified": True,
            }
        warehouse_case = record["stage1_scenarios"]["B_warehouse_capacity"]
        costs = focused(f"incident/{warehouse_case['incident_id']}?evidence_kind=costs")
        assert costs["total"] == len(costs["evidence"]) == 1
        assert Decimal(costs["evidence"][0]["amount_gbp"]) == warehouse_case["amount"]
        receipts = focused(f"shortage/{shortage_id}?evidence_kind=receipts")
        assert receipts["total"] == len(receipts["evidence"]) == 1
        assert (
            receipts["evidence"][0]["related_entity_id"]
            == record["stage1_scenarios"]["A_procurement_to_customer"]["receipt_id"]
        )
        operational["explicit_warehouse_cost"] = {
            "expense_id": costs["evidence"][0]["entity_id"],
            "amount_gbp": costs["evidence"][0]["amount_gbp"],
        }
        operational["exact_replenishment_receipt"] = {
            "receipt_id": receipts["evidence"][0]["related_entity_id"]
        }
        record["operational_queries"] = operational
        supplier_costs = focused("supplier/1?evidence_kind=costs&limit=100")
        supplier_amount = sum(
            (Decimal(r["amount_gbp"]) for r in supplier_costs["evidence"]), Decimal(0)
        )
        assert supplier_costs["total"] == len(supplier_costs["evidence"])
        assert supplier_amount == number(supplier.json(), "additional_linked_costs")
        record["operational_queries"]["supplier_direct_cost_reconciliation"] = {
            "supplier_id": 1,
            "amount_gbp": str(supplier_amount),
            "matched": True,
        }
        assert client.get("/ready").json() == {"status": "ready"}
        assert client.get("/api/v1/demo/summary").json()["fingerprint"] == baseline
    p, i, f, s = cache["procurement"], cache["inventory"], cache["finance"], cache["fulfilment"]
    assert number(p, "due_orders") == number(p, "on_time_orders") + number(
        p, "late_orders"
    ) + number(p, "overdue_outstanding_orders")
    assert number(f, "invoice_value") == number(f, "paid_amount") + number(f, "outstanding_amount")
    assert number(i, "closing_stock") == number(i, "opening_stock") + number(
        i, "received_units"
    ) - number(i, "dispatched_units") + number(i, "adjusted_units")
    assert number(s, "ordered_units") == number(s, "dispatched_units") + number(
        s, "outstanding_units"
    )
    assert number(cache["warehouses"], "stock_on_hand") == number(i, "stock_on_hand")
    record["reconciliations"] = {
        "overview_domains": True,
        "supplier_detail_comparison": True,
        "purchase_service_population": True,
        "invoice_paid_outstanding": True,
        "stock_ledger": True,
        "sales_order_quantities": True,
        "warehouse_stock": True,
    }
    record["headline_metrics"] = cache["overview"]["metrics"]
    record["insights"] = cache["insights"]
    record["live_url"] = args.live_url
    record["all_checks_passed"] = True
    args.output.write_text(
        json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "all_checks_passed": True,
                "fingerprint": record["fingerprint_after"],
                "api_median_ms": record["api_median_ms"],
                "sql_query_counts": record["sql_query_counts"],
                "query_median_ms": {
                    key: v["median_ms"] for key, v in record["query_plans"].items()
                },
                "investigations": record["investigations"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
