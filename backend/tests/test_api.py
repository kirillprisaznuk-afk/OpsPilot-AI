import pytest
from app.db.session import session
from app.main import app
from sqlalchemy.exc import OperationalError


def test_health_and_readiness(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}


@pytest.mark.parametrize(
    "path,total,first",
    [
        ("catalog/suppliers", 36, "Amberwick Office Works (synthetic)"),
        ("catalog/warehouses", 4, "Northstar Midlands (synthetic)"),
        ("catalog/products", 200, "Synthetic office unit 001"),
    ],
)
def test_catalog_pagination(client, path, total, first):
    result = client.get(f"/api/v1/{path}?limit=2").json()
    assert result["total"] == total
    assert [r["id"] for r in result["items"]] == [1, 2]
    assert result["items"][0]["name"] == first
    second = client.get(f"/api/v1/{path}?limit=2&offset=2").json()
    assert [r["id"] for r in second["items"]] == [3, 4]
    assert client.get(f"/api/v1/{path}?offset=9999").json()["items"] == []


def test_summary_comes_from_database(client, dataset):
    result = client.get("/api/v1/demo/summary").json()
    assert result["counts"] == {name: len(rows) for name, rows in dataset.rows.items()}
    assert result["fingerprint"] == dataset.fingerprint()


@pytest.mark.parametrize("entity", ["tasks", "incidents"])
def test_operation_filter(client, db, entity):
    result = client.get(f"/api/v1/operations/{entity}?status=open&limit=100").json()
    from sqlalchemy import text

    expected = db.scalar(text(f"SELECT count(*) FROM {entity} WHERE status='open'"))
    assert result["total"] == expected > 0
    assert all(row["status"] == "open" for row in result["items"])


def test_purchase_and_sales_timelines(client):
    purchase = client.get("/api/v1/operations/orders/1/timeline").json()
    sales = client.get("/api/v1/operations/orders/1/timeline?kind=sales").json()
    assert purchase["order_kind"] == "purchase" and sales["order_kind"] == "sales"
    assert next(e for e in purchase["events"] if e["kind"] == "receipt")["quantity"] == 40
    assert next(e for e in sales["events"] if e["kind"] == "fulfilment")["quantity"] == 30
    assert (
        next(e for e in sales["events"] if e["kind"] == "shortage")["occurred_on"] == "2025-10-09"
    )


@pytest.mark.parametrize(
    "path,status",
    [
        ("catalog/products?limit=0", 422),
        ("catalog/products?limit=101", 422),
        ("catalog/products?offset=-1", 422),
        ("operations/tasks?status=unknown", 422),
        ("operations/orders/999999/timeline", 404),
        ("operations/orders/1/timeline?kind=invalid", 422),
        ("operations/orders/0/timeline", 422),
    ],
)
def test_api_errors(client, path, status):
    assert client.get(f"/api/v1/{path}").status_code == status


def test_api_has_no_write_routes(client):
    assert client.post("/api/v1/catalog/products", json={"name": "x"}).status_code == 405
    for route in app.routes:
        assert not getattr(route, "methods", set()) & {"POST", "PUT", "PATCH", "DELETE"}


def test_database_errors_do_not_leak(client):
    def unavailable():
        raise OperationalError("secret internal SQL", {}, Exception("password=private"))

    app.dependency_overrides[session] = unavailable
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
