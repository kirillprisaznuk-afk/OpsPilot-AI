from datetime import date
from decimal import Decimal

import pytest
from app.analytics import (
    finance,
    fulfilment,
    incidents,
    inventory,
    procurement,
    relationships,
    suppliers,
    workforce,
)
from app.analytics.common import comparison, metrics, percent
from app.analytics.contracts import AnalyticsQuery
from app.db.session import session
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import text


def q(**kwargs):
    return AnalyticsQuery(
        as_of=date(2025, 11, 6), include_trends=False, include_comparison=False, **kwargs
    )


def values(report):
    return {key: metric.value for key, metric in report.metrics.items()}


def test_supplier_eight_of_ten_due(small_db):
    result = suppliers.get_suppliers(small_db, q(), 1)
    v = values(result)
    assert (
        v["purchase_orders"],
        v["due_orders"],
        v["on_time_orders"],
        v["late_orders"],
        v["overdue_outstanding_orders"],
    ) == (11, 10, 8, 1, 1)
    assert v["on_time_rate"] == Decimal("80.00")
    assert v["order_value"] == Decimal("2000.00")
    assert v["average_lateness"] == v["median_lateness"] == Decimal("2.00")
    assert v["open_commitment"] == Decimal("200.00")
    assert result.contracts[0].observed_percent == Decimal("80.00")
    assert result.contracts[0].gap_percentage_points == Decimal("-15.00")
    assert result.contracts[0].potential_operational_concern is True
    assert result.contracts[0].legal_breach_established is False


def test_partial_receipt_does_not_complete_order(small_db):
    result = procurement.get_procurement(
        small_db, AnalyticsQuery(as_of=date(2025, 11, 2), supplier_id=1, include_trends=False)
    )
    v = values(result)
    assert (
        v["on_time_orders"],
        v["late_orders"],
        v["overdue_outstanding_orders"],
        v["partial_orders"],
    ) == (8, 0, 2, 1)
    assert v["on_time_rate"] == Decimal("80.00")
    assert v["receipt_punctuality_rate"] == Decimal("100.00")
    assert v["order_value"] == Decimal("2000.00")


def test_procurement_throughput_is_a_separate_completion_flow(small_db):
    result = procurement.get_procurement(
        small_db,
        AnalyticsQuery(
            start_date=date(2025, 11, 1),
            end_date=date(2025, 11, 6),
            as_of=date(2025, 11, 6),
            supplier_id=1,
            group_by="supplier",
        ),
    )
    assert result.metrics["purchase_orders"].value == 0
    assert result.metrics["completed_in_period"].value == 9
    assert result.breakdowns[0].metrics["completed_in_period"].value == 9
    assert result.trends[0].metrics["completed_in_period"].value == 9
    assert result.trends[0].metrics["purchase_orders"].value == 0


def test_price_bands_compare_identical_products(small_db):
    result = procurement.get_procurement(small_db, q(supplier_id=1))
    band = result.price_bands[0]
    assert band.product_id == 1
    assert band.minimum_unit_price_gbp == Decimal("10.00")
    assert band.maximum_unit_price_gbp == Decimal("100.00")
    assert band.weighted_mean_unit_price_gbp == Decimal("18.18")


def test_empty_supplier_population_and_no_due_denominator(small_db):
    result = suppliers.get_suppliers(small_db, q(), 3)
    assert values(result)["purchase_orders"] == 0
    assert result.metrics["on_time_rate"].value is None
    assert result.metrics["on_time_rate"].status == "undefined"
    assert result.contracts[0].potential_operational_concern is None
    assert result.breakdowns[0].metrics["order_value"].value == Decimal("0")


@pytest.mark.parametrize(
    "as_of,expected",
    [("2025-10-01", 20), ("2025-10-10", 35), ("2025-10-15", 10), ("2025-11-06", 10)],
)
def test_inventory_prefixes(small_db, as_of, expected):
    result = inventory.get_inventory(
        small_db,
        AnalyticsQuery(
            as_of=date.fromisoformat(as_of), warehouse_id=2, product_id=2, include_trends=False
        ),
    )
    assert values(result)["stock_on_hand"] == expected


def test_opening_receipt_dispatch_reconcile(small_db):
    result = inventory.get_inventory(
        small_db,
        AnalyticsQuery(
            start_date=date(2025, 10, 2),
            end_date=date(2025, 10, 31),
            as_of=date(2025, 11, 6),
            warehouse_id=2,
            product_id=2,
        ),
    )
    v = values(result)
    assert (
        v["opening_stock"],
        v["received_units"],
        v["dispatched_units"],
        v["adjusted_units"],
        v["closing_stock"],
    ) == (20, 15, 25, 0, 10)
    assert (
        v["closing_stock"]
        == v["opening_stock"] + v["received_units"] - v["dispatched_units"] + v["adjusted_units"]
    )
    assert result.trends[0].window.as_of == date(2025, 10, 31)


def test_full_dispatch_all_lines_and_immature_order(small_db):
    result = fulfilment.get_fulfilment(small_db, q(product_id=1))
    v = values(result)
    assert (
        v["sales_orders"],
        v["due_orders"],
        v["completed_orders"],
        v["late_orders"],
        v["overdue_outstanding_orders"],
    ) == (4, 3, 2, 2, 1)
    assert v["ordered_units"] == 31 and v["dispatched_units"] == 11 and v["outstanding_units"] == 20
    early = relationships.investigate(
        small_db, "sales_order", 5, AnalyticsQuery(as_of=date(2025, 11, 2), include_trends=False)
    )
    assert early.metrics["completed_orders"].value == 0
    assert early.metrics["partial_orders"].value == 1


def test_finance_thousand_minus_two_payments(small_db):
    result = relationships.investigate(small_db, "invoice", 1, q())
    assert values(result)["invoice_value"] == Decimal("1000.00")
    assert values(result)["paid_amount"] == Decimal("750.00")
    assert values(result)["outstanding_amount"] == Decimal("250.00")
    earlier = relationships.investigate(
        small_db, "invoice", 1, AnalyticsQuery(as_of=date(2025, 10, 3))
    )
    assert values(earlier)["paid_amount"] == Decimal("400.00")
    assert values(earlier)["outstanding_amount"] == Decimal("600.00")


def test_discrepancy_knowledge_cannot_leak_before_incident(small_db):
    before = finance.get_finance(
        small_db, AnalyticsQuery(as_of=date(2025, 11, 4), include_trends=False)
    )
    after = finance.get_finance(small_db, q())
    assert values(before)["discrepancy_invoices"] == 0
    assert values(after)["discrepancy_invoices"] == 1
    assert values(after)["documented_discrepancy_amount"] == Decimal("25.00")
    assert values(after)["additional_costs"] == Decimal("205.00")
    assert values(before)["additional_costs"] == Decimal("120.00")
    assert sum(s.metrics["additional_costs"].value for s in after.breakdowns) == Decimal("205.00")


def test_four_task_states_at_cutoff(small_db):
    result = workforce.get_workforce(small_db, q())
    v = values(result)
    assert (v["total_tasks"], v["completed_on_time"], v["completed_late"], v["overdue_tasks"]) == (
        4,
        2,
        1,
        1,
    )
    assert v["completion_rate"] == Decimal("75.00")
    early = workforce.get_workforce(
        small_db, AnalyticsQuery(as_of=date(2025, 11, 1), include_trends=False)
    )
    assert values(early)["completed_tasks"] == 1
    assert values(early)["open_tasks"] == 3
    assert values(early)["overdue_tasks"] == 0


def test_missing_task_history_returns_unavailable(small_db):
    small_db.execute(text("DELETE FROM task_status_history WHERE task_id=4"))
    result = workforce.get_workforce(small_db, q())
    assert values(result)["unknown_status_tasks"] == 1
    assert result.metrics["overdue_tasks"].value is None
    assert result.metrics["overdue_tasks"].status == "unavailable"


def test_incidence_prevalence_and_historical_escalation(small_db):
    early = incidents.get_incidents(
        small_db, AnalyticsQuery(as_of=date(2025, 11, 3), include_trends=False)
    )
    v = values(early)
    assert v["total_incidents"] == 3 and v["open_incidents"] == 3 and v["resolved_incidents"] == 0
    assert early.metrics["escalated_incidents"].value is None
    assert early.metrics["escalated_incidents"].status == "unavailable"
    recent = incidents.get_incidents(
        small_db,
        AnalyticsQuery(
            start_date=date(2025, 11, 4),
            end_date=date(2025, 11, 6),
            as_of=date(2025, 11, 6),
            include_trends=False,
        ),
    )
    v = values(recent)
    assert v["new_incidents"] == 1 and v["total_incidents"] == 4 and v["open_incidents"] == 3
    assert v["corrective_tasks"] == 4


@pytest.mark.parametrize(
    "current,old,relative",
    [(5, 0, None), (0, 0, None), (15, 10, Decimal("50.00")), (-5, -10, Decimal("50.00"))],
)
def test_period_changes_and_zero_baselines(current, old, relative):
    previous = AnalyticsQuery(
        start_date=date(2026, 5, 1), end_date=date(2026, 5, 31), as_of=date(2026, 6, 30)
    )
    result = comparison(current, old, "GBP", previous)
    assert result.absolute_change == Decimal(current - old)
    assert result.relative_change_percent == relative


def test_previous_period_equal_length_and_observation_lag():
    current = AnalyticsQuery(
        start_date=date(2026, 7, 1), end_date=date(2026, 7, 31), as_of=date(2026, 9, 30)
    )
    previous = current.previous()
    assert (previous.end_date - previous.start_date).days == 30
    assert (previous.as_of - previous.end_date) == (current.as_of - current.end_date)
    assert AnalyticsQuery().previous() is None
    assert percent(0, 0) is None
    assert comparison(80, 95, "percent", previous).change_percentage_points == Decimal("-15")


def test_comparisons_use_identical_numeric_precision():
    previous = AnalyticsQuery(start_date=date(2026, 5, 1), end_date=date(2026, 5, 31))
    result = metrics(
        "procurement",
        {"average_lateness": Decimal("3.3333333"), "purchase_orders": 4},
        {"average_lateness": Decimal("3.3333333"), "purchase_orders": 3},
        previous,
        True,
    )
    assert result["average_lateness"].comparison.absolute_change == Decimal("0.00")
    assert isinstance(result["purchase_orders"].comparison.previous_value, int)


def test_unavailable_escalation_comparison_is_explicit():
    previous = AnalyticsQuery(start_date=date(2026, 8, 1), end_date=date(2026, 8, 31))
    result = metrics(
        "incidents", {"escalated_incidents": 65}, {"escalated_incidents": None}, previous, True
    )
    assert result["escalated_incidents"].comparison.status == "unavailable"


def test_hand_fixture_api_contract_and_counts(small_db):
    app.dependency_overrides[session] = lambda: small_db
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/analytics/suppliers/1?as_of=2025-11-06&include_trends=false"
            )
            assert response.status_code == 200
            result = response.json()
            assert result["metrics"]["on_time_rate"]["value"] == "80.00"
            assert result["metrics"]["on_time_rate"]["numerator"] == 8
            assert result["metrics"]["on_time_rate"]["denominator"] == 10
            assert result["metrics"]["order_value"]["unit"] == "GBP"
    finally:
        app.dependency_overrides.clear()
