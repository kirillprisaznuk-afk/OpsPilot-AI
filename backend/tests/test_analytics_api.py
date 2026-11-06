from datetime import date
from decimal import Decimal

import pytest
from app.analytics import suppliers
from app.analytics.contracts import AnalyticsQuery
from sqlalchemy import event, text

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
]


def value(result, key):
    raw = result["metrics"][key]["value"]
    return Decimal(str(raw)) if raw is not None else None


@pytest.mark.parametrize("domain", DOMAINS)
def test_all_analytics_response_contracts(client, domain):
    response = client.get(
        "/api/v1/analytics/" + domain + "?include_trends=false&include_comparison=false"
    )
    assert response.status_code == 200
    result = response.json()
    assert result["window"] == {
        "observation_start": "2025-10-01",
        "observation_end": "2026-09-30",
        "as_of": "2026-09-30",
        "timezone": "UTC",
    }
    assert len(result["breakdowns"]) <= result["limit"]
    for metric in result["metrics"].values():
        assert metric["unit"] in {"count", "units", "GBP", "days", "percent", "percentage_points"}
        if metric["unit"] == "percent" and metric["value"] is not None:
            assert 0 <= Decimal(str(metric["value"])) <= 100
        if metric["unit"] in {"count", "units"} and metric["value"] is not None:
            assert isinstance(metric["value"], int)


def test_overview_matches_every_detailed_domain(client):
    overview = client.get("/api/v1/analytics/overview?include_comparison=false").json()
    by_domain = {}
    for key, metric in overview["metrics"].items():
        domain, field = key.split(".", 1)
        if domain not in by_domain:
            response = client.get(
                f"/api/v1/analytics/{domain}?include_trends=false&include_comparison=false"
            )
            response.raise_for_status()
            by_domain[domain] = response.json()
        assert metric == by_domain[domain]["metrics"][field]


def test_default_reconciliations_and_independent_sql(client, db):
    procurement = client.get("/api/v1/analytics/procurement?include_trends=false").json()
    inventory = client.get("/api/v1/analytics/inventory?include_trends=false").json()
    finance = client.get("/api/v1/analytics/finance?include_trends=false").json()
    fulfilment = client.get("/api/v1/analytics/fulfilment?include_trends=false").json()
    expected_purchase_value = db.scalar(
        text("SELECT sum(quantity*unit_price) FROM purchase_order_lines")
    )
    assert value(procurement, "order_value") == expected_purchase_value
    assert (
        value(inventory, "stock_on_hand")
        == db.scalar(text("SELECT sum(quantity) FROM stock_movements"))
        == 99213
    )
    assert value(inventory, "closing_stock") == value(inventory, "opening_stock") + value(
        inventory, "received_units"
    ) - value(inventory, "dispatched_units") + value(inventory, "adjusted_units")
    assert value(finance, "invoice_value") == value(finance, "paid_amount") + value(
        finance, "outstanding_amount"
    )
    assert value(finance, "invoice_value") == db.scalar(
        text("SELECT sum(amount) FROM supplier_invoices")
    )
    assert value(finance, "paid_amount") == db.scalar(text("SELECT sum(amount) FROM payments"))
    assert value(fulfilment, "ordered_units") == value(fulfilment, "dispatched_units") + value(
        fulfilment, "outstanding_units"
    )
    assert value(procurement, "due_orders") == value(procurement, "on_time_orders") + value(
        procurement, "late_orders"
    ) + value(procurement, "overdue_outstanding_orders")
    assert value(fulfilment, "due_orders") == value(fulfilment, "on_time_orders") + value(
        fulfilment, "late_orders"
    ) + value(fulfilment, "overdue_outstanding_orders")


@pytest.mark.parametrize(
    "domain", ["suppliers", "inventory", "warehouses", "workforce", "incidents", "finance"]
)
def test_analytics_pagination_and_empty_offset(client, domain):
    path = f"/api/v1/analytics/{domain}?include_trends=false&include_comparison=false&limit=2"
    first = client.get(path).json()
    second = client.get(path + "&offset=2").json()
    assert len(first["breakdowns"]) == 2
    assert set(s["label"] for s in first["breakdowns"]).isdisjoint(
        s["label"] for s in second["breakdowns"]
    )
    empty = client.get(path + "&offset=999999").json()
    assert empty["breakdowns"] == []
    assert empty["total_segments"] == first["total_segments"]


@pytest.mark.parametrize(
    "path",
    [
        "overview?as_of=2025-09-30",
        "overview?as_of=2026-10-01",
        "procurement?start_date=2026-09-30&end_date=2026-01-01",
        "inventory?as_of=2025-10-10&end_date=2025-10-11",
        "inventory?sql=DROP%20TABLE%20products",
        "suppliers?sort=DROP%20TABLE%20suppliers",
        "inventory?supplier_id=1",
        "finance?product_id=1",
        "overview?department_id=1",
        "incidents?priority=urgent",
        "workforce?priority=imaginary",
        "suppliers?limit=101",
        "workforce?offset=-1",
        "suppliers?supplier_id=0",
        "finance?group_by=arbitrary_sql",
        "inventory?product_category=nonexistent",
        "suppliers/1?supplier_id=2",
        "investigations/unknown/1",
        "investigations/supplier/0",
    ],
)
def test_invalid_analytics_inputs_are_rejected(client, path):
    response = client.get("/api/v1/analytics/" + path)
    assert response.status_code == 422
    assert "traceback" not in response.text.lower()


@pytest.mark.parametrize("path", ["suppliers/999999", "investigations/invoice/999999"])
def test_missing_analytics_entities(client, path):
    result = client.get("/api/v1/analytics/" + path)
    assert result.status_code == 404
    assert result.json()["detail"]["code"] == "not_found"


@pytest.mark.parametrize("domain", DOMAINS + ["insights"])
def test_analytics_has_no_write_routes(client, domain):
    assert client.post("/api/v1/analytics/" + domain, json={}).status_code == 405


def test_segment_totals_match_and_filter_excludes_unrelated_rows(client):
    inventory = client.get(
        "/api/v1/analytics/inventory?group_by=warehouse&limit=100&include_trends=false"
    ).json()
    assert sum(
        value({"metrics": s["metrics"]}, "stock_on_hand") for s in inventory["breakdowns"]
    ) == value(inventory, "stock_on_hand")
    for segment in inventory["breakdowns"]:
        specific = client.get(
            f"/api/v1/analytics/inventory?warehouse_id={segment['entity_id']}&include_trends=false"
        ).json()
        assert value(specific, "stock_on_hand") == value(
            {"metrics": segment["metrics"]}, "stock_on_hand"
        )
    suppliers_result = client.get(
        "/api/v1/analytics/suppliers?supplier_category=industrial&limit=100&include_trends=false"
    ).json()
    assert suppliers_result["total_segments"] == 12


def test_original_supplier_sla_and_backlog_scenarios(client):
    supplier = client.get("/api/v1/analytics/suppliers/1?include_trends=false").json()
    contract = supplier["contracts"][0]
    assert (contract["due_orders"], contract["on_time_orders"]) == (72, 24)
    assert Decimal(contract["observed_percent"]) == Decimal("33.33")
    assert contract["legal_breach_established"] is False
    workforce = client.get(
        "/api/v1/analytics/workforce?department_id=1&include_trends=false"
    ).json()
    assert value(workforce, "overdue_tasks") == 123


@pytest.mark.parametrize(
    "kind,identifier",
    [
        ("supplier", 1),
        ("purchase_order", 1),
        ("sales_order", 1),
        ("shortage", 16),
        ("warehouse", 1),
        ("incident", 16),
        ("invoice", 37),
        ("department", 1),
        ("task", 16),
        ("product", 1),
    ],
)
def test_each_investigation_domain_has_real_bounded_sources(client, kind, identifier):
    response = client.get(f"/api/v1/analytics/investigations/{kind}/{identifier}?limit=100")
    assert response.status_code == 200
    report = response.json()
    assert 0 < len(report["evidence"]) <= 100
    assert report["total"] >= len(report["evidence"])
    for evidence in report["evidence"]:
        assert evidence["source_reference"].split(":")[1].isdigit()
        assert evidence["event_time"] < "2026-10-01"
        assert evidence["evidence_class"] in {"explicit_link", "simulated_causal_chain"}


def test_full_causal_case_and_explicit_cost_evidence(client):
    result = client.get("/api/v1/analytics/investigations/shortage/16?limit=100").json()
    entities = {(r["related_entity_type"], r["related_entity_id"]) for r in result["evidence"]}
    assert {
        ("receipt", 185),
        ("stock_movement", 332),
        ("fulfilment", 149),
        ("task", 16),
    } <= entities
    assert any(r["evidence_class"] == "simulated_causal_chain" for r in result["evidence"])
    finance = client.get("/api/v1/analytics/investigations/invoice/37?limit=100").json()
    assert value(finance, "documented_discrepancy_amount") == Decimal("25.00")
    assert any(
        r["related_entity_type"] == "task" and r["related_entity_id"] == 1153
        for r in finance["evidence"]
    )
    warehouse = client.get("/api/v1/analytics/investigations/incident/1729?limit=100").json()
    costs = [r for r in warehouse["evidence"] if r["relationship_type"] == "explicit_recorded_cost"]
    assert len(costs) == 1 and Decimal(costs[0]["amount_gbp"]) == Decimal("120.00")


def test_historical_investigation_has_no_future_receipts_or_completion(client):
    result = client.get(
        "/api/v1/analytics/investigations/purchase_order/1?as_of=2025-10-09&limit=100"
    ).json()
    assert value(result, "completed_orders") == 0
    assert value(result, "received_units") == 0
    assert not any(r["related_entity_type"] == "receipt" for r in result["evidence"])
    assert all(r["event_time"] < "2025-10-10" for r in result["evidence"])


def test_insights_are_deterministic_and_evidenced(client):
    path = "/api/v1/analytics/insights?limit=100"
    first = client.get(path).json()
    assert first == client.get(path).json()
    assert any(
        i["rule_id"] == "overdue_corrective_work" and i["entity_id"] == 1 for i in first["items"]
    )
    assert all(
        i["evidence"] and i["source_reference"].startswith("/api/v1/analytics/")
        for i in first["items"]
    )
    assert all("statistically significant" not in i["statement"] for i in first["items"])


def test_query_count_does_not_scale_with_supplier_page(db, postgres):
    counts = []

    def capture(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().lower().startswith(("select", "with")):
            counts.append(statement)

    event.listen(postgres, "before_cursor_execute", capture)
    try:
        suppliers.get_suppliers(
            db, AnalyticsQuery(limit=1, include_trends=False, include_comparison=False)
        )
        small_count = len(counts)
        counts.clear()
        suppliers.get_suppliers(
            db, AnalyticsQuery(limit=100, include_trends=False, include_comparison=False)
        )
        assert len(counts) == small_count <= 6
    finally:
        event.remove(postgres, "before_cursor_execute", capture)


def test_production_session_has_consistent_read_only_snapshot(postgres):
    from app.db.session import session

    dependency = session()
    db = next(dependency)
    try:
        assert db.scalar(text("SHOW transaction_read_only")) == "on"
        assert db.scalar(text("SHOW transaction_isolation")) == "repeatable read"
    finally:
        dependency.close()


def test_shortage_historical_stock_is_not_final_balance(client):
    for when, stock in [("2025-10-08", 0), ("2025-10-20", 10)]:
        result = client.get(
            f"/api/v1/analytics/inventory?as_of={when}&product_id=1&warehouse_id=1&include_trends=false"
        ).json()
        assert value(result, "stock_on_hand") == stock


def test_comparison_window_is_eligible_and_explicit(client):
    result = client.get(
        "/api/v1/analytics/procurement?start_date=2026-09-01&end_date=2026-09-30&as_of=2026-09-30&include_trends=false"
    ).json()
    compared = result["metrics"]["order_value"]["comparison"]
    assert compared["previous_window"]["observation_start"] == "2026-08-02"
    assert compared["previous_window"]["observation_end"] == "2026-08-31"
    assert compared["previous_value"] is not None
    assert value(result, "order_value") - Decimal(compared["previous_value"]) == Decimal(
        compared["absolute_change"]
    )


def test_cash_flows_are_not_invoice_cohort_exposure(small_db):
    from app.analytics.finance import get_finance

    report = get_finance(
        small_db,
        AnalyticsQuery(
            start_date=date(2025, 10, 3),
            end_date=date(2025, 10, 4),
            as_of=date(2025, 11, 6),
            include_trends=False,
        ),
    )
    assert report.metrics["invoice_value"].value == Decimal("0")
    assert report.metrics["payments_made"].value == Decimal("750.00")


def test_exact_next_day_boundary_is_not_overdue(small_db):
    from app.analytics.workforce import get_workforce

    small_db.execute(text("UPDATE tasks SET due_at='2025-11-07T00:00:00+00:00' WHERE id=4"))
    report = get_workforce(small_db, AnalyticsQuery(as_of=date(2025, 11, 6), include_trends=False))
    assert report.metrics["overdue_tasks"].value == 0


def test_contract_windows_do_not_create_false_targets(small_db):
    small_db.execute(
        text("""INSERT INTO supplier_contracts
      (id,created_at,synthetic,supplier_id,reference,effective_date,expires_on,on_time_target,payment_days,escalation_days)
      VALUES(4,'2025-12-01',true,1,'FUTURE','2025-10-01','2026-09-30',80,30,2)
    """)
    )
    report = suppliers.get_suppliers(
        small_db, AnalyticsQuery(as_of=date(2025, 11, 6), include_trends=False), 1
    )
    assert len(report.contracts) == 1
    assert report.contracts[0].target_percent == Decimal("95.00")
    assert report.breakdowns[0].metrics["sla_target_percent"].value == Decimal("95.00")


def test_narrow_open_task_investigation_matches_workforce(client):
    response = client.get(
        "/api/v1/analytics/investigations/department/1?evidence_kind=tasks&open_tasks_only=true&limit=100"
    )
    assert response.status_code == 200
    result = response.json()
    expected = client.get("/api/v1/analytics/workforce?department_id=1&include_trends=false").json()
    assert result["total"] == int(value(expected, "open_tasks")) == 123
    assert len({r["entity_id"] for r in result["evidence"]}) == len(result["evidence"])
    assert all(
        r["entity_type"] == "task" and r["observed_status"] in {"open", "active", "escalated"}
        for r in result["evidence"]
    )


def test_narrow_supplier_tasks_costs_and_receipts(client):
    tasks = client.get(
        "/api/v1/analytics/investigations/supplier/1?evidence_kind=tasks&open_tasks_only=true&limit=100"
    ).json()
    expected = client.get("/api/v1/analytics/workforce?supplier_id=1&include_trends=false").json()
    assert tasks["total"] == int(value(expected, "open_tasks"))
    supplier_costs = client.get(
        "/api/v1/analytics/investigations/supplier/1?evidence_kind=costs&limit=100"
    ).json()
    supplier = client.get("/api/v1/analytics/suppliers/1?include_trends=false").json()
    assert sum((Decimal(r["amount_gbp"]) for r in supplier_costs["evidence"]), Decimal(0)) == value(
        supplier, "additional_linked_costs"
    )
    costs = client.get("/api/v1/analytics/investigations/incident/1729?evidence_kind=costs").json()
    assert costs["total"] == 1 and Decimal(costs["evidence"][0]["amount_gbp"]) == Decimal("120.00")
    assert costs["evidence"][0]["cost_category"] == "overtime"
    assert "GBP 30" in costs["evidence"][0]["recorded_basis"]
    receipts = client.get(
        "/api/v1/analytics/investigations/shortage/16?evidence_kind=receipts"
    ).json()
    assert receipts["total"] == 1 and receipts["evidence"][0]["related_entity_id"] == 185


def test_investigation_kind_is_whitelisted(client):
    for query in ["evidence_kind=sql", "open_tasks_only=true"]:
        assert client.get("/api/v1/analytics/investigations/supplier/1?" + query).status_code == 422


def test_overdue_task_evidence_has_owned_task_details(small_db):
    from app.analytics import relationships
    from app.analytics.contracts import InvestigationQuery

    result = relationships.investigate(
        small_db,
        "department",
        1,
        InvestigationQuery(as_of=date(2025, 11, 6), evidence_kind="tasks", overdue_tasks_only=True),
    )
    assert result.total == 1
    task = result.evidence[0]
    assert task.entity_type == "task" and task.entity_id == 4
    assert task.related_entity_type == "employee" and task.related_entity_id == 1
    assert task.observed_status == "escalated" and task.priority == "high"
    assert task.title == "Synthetic fixture task 4"
    assert task.due_at.date() == date(2025, 11, 2)
    earlier = relationships.investigate(
        small_db,
        "department",
        1,
        InvestigationQuery(as_of=date(2025, 11, 1), evidence_kind="tasks", overdue_tasks_only=True),
    )
    assert earlier.total == 0 and earlier.evidence == []
