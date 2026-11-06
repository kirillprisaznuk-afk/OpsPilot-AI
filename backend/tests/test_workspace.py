"""Stage 6 read projections against the real restricted Stage 5 PostgreSQL login."""

from backend.tests.test_workflows import (
    approved,
    headers,
    task_input,
    transition,
    wf,  # noqa: F401
    workflow_database,  # noqa: F401
)


def test_workspace_requires_real_session(wf):  # noqa: F811
    client, accounts, *_ = wf
    assert client.get("/api/v1/workspace/subjects").status_code == 401
    result = client.get("/api/v1/workspace/status", headers=headers(accounts, "viewer"))
    assert result.status_code == 200
    assert result.json()["api_version"] == "0.5.0"
    assert result.headers["cache-control"] == "no-store"


def test_order_selector_uses_real_historical_cohort(wf):  # noqa: F811
    client, accounts, *_ = wf
    query = "kind=purchase_order&start_date=2026-06-01&end_date=2026-06-30&limit=5"
    result = client.get("/api/v1/workspace/subjects?" + query, headers=headers(accounts))
    assert result.status_code == 200, result.text
    page = result.json()
    assert page["total"] > len(page["items"]) == 5
    assert all("2026-06-01" <= r["ordered_on"] <= "2026-06-30" for r in page["items"])
    bad = client.get(
        "/api/v1/workspace/subjects?kind=purchase_order&start_date=2027-01-01",
        headers=headers(accounts),
    )
    assert bad.status_code == 422


def test_people_selection_respects_department_scope(wf):  # noqa: F811
    client, accounts, *_ = wf
    rows = client.get("/api/v1/workspace/people", headers=headers(accounts, "viewer")).json()
    assert rows and all(r["department_id"] == 1 for r in rows)
    assert set(rows[0]) == {"id", "name", "department_id"}
    other = client.get("/api/v1/workspace/people?department_id=2", headers=headers(accounts))
    assert other.status_code == 200 and other.json() == []


def test_global_access_directory_never_exposes_authentication_material(wf):  # noqa: F811
    client, accounts, *_ = wf
    assert client.get("/api/v1/workspace/principals", headers=headers(accounts)).status_code == 403
    result = client.get("/api/v1/workspace/principals", headers=headers(accounts, "admin"))
    assert result.status_code == 200, result.text
    assert any(row["id"] == accounts["reviewer"]["id"] for row in result.json())
    assert all(
        set(r) == {"id", "username", "active", "is_human", "created_at", "roles"}
        for r in result.json()
    )


def test_actor_labels_require_visible_proposal_or_own_identity(wf):  # noqa: F811
    client, accounts, *_ = wf
    approved(client, accounts)
    query = "/api/v1/workspace/actor-labels?ids=" + accounts["operator"]["id"]
    actual = client.get(query, headers=headers(accounts, "reviewer"))
    assert actual.status_code == 200, actual.text
    assert actual.json() == [
        {"id": accounts["operator"]["id"], "username": accounts["operator"]["username"]}
    ]
    assert client.get(query, headers=headers(accounts, "outsider")).json() == []


def test_workflow_search_and_audit_filters_preserve_scope(wf):  # noqa: F811
    client, accounts, *_ = wf
    body = task_input()
    body["action"].update(title="Stage 6 scoped lookup unique", priority="urgent")
    p = approved(client, accounts, body)
    receipt = transition(client, accounts, p, "execute")
    task_id = receipt["result"]["objects"]["task_id"]
    task_query = "/api/v1/workflows/tasks?priority=urgent&search=Stage%206%20scoped%20lookup"
    own = client.get(task_query, headers=headers(accounts)).json()
    assert own["total"] == 1 and own["items"][0]["id"] == task_id
    assert client.get(task_query, headers=headers(accounts, "outsider")).json()["total"] == 0
    audit_query = f"/api/v1/workflows/audit?object_id={task_id}&action=task.created&newest=true"
    audit = client.get(audit_query, headers=headers(accounts)).json()
    assert audit["total"] == 1 and audit["items"][0]["proposal_id"] == p["id"]
    assert client.get(audit_query, headers=headers(accounts, "outsider")).json()["total"] == 0
