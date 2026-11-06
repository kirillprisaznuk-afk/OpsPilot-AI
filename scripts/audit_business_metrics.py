"""Compare selected live analytics with independent read-only SQL over the accepted data."""

import argparse
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import httpx
from app.db.session import engine
from sqlalchemy import text

SQL = {
    "procurement": """
        WITH receipts AS (
          SELECT purchase_order_line_id, SUM(quantity) units, MAX(received_on) last_receipt
          FROM goods_receipts WHERE received_on <= :end GROUP BY purchase_order_line_id
        ), orders AS (
          SELECT p.id, p.promised_on, BOOL_AND(COALESCE(r.units, 0) >= l.quantity) complete,
            MAX(r.last_receipt) completed_on,
            SUM((l.quantity - COALESCE(r.units, 0)) * l.unit_price) open_value
          FROM purchase_orders p JOIN purchase_order_lines l ON l.purchase_order_id=p.id
          LEFT JOIN receipts r ON r.purchase_order_line_id=l.id
          WHERE p.ordered_on BETWEEN :start AND :end GROUP BY p.id
        )
        SELECT COUNT(*) purchase_orders, COUNT(*) FILTER (WHERE promised_on <= :end) due_orders,
          COUNT(*) FILTER (WHERE complete AND promised_on <= :end
            AND completed_on <= promised_on) on_time_orders,
          COUNT(*) FILTER (WHERE complete AND completed_on > promised_on) late_orders,
          COALESCE(SUM(open_value) FILTER (WHERE NOT complete), 0) open_commitment,
          COALESCE(SUM(open_value) FILTER (WHERE NOT complete AND promised_on <= :end), 0)
            overdue_commitment
        FROM orders
    """,
    "inventory": """
        SELECT COALESCE(SUM(quantity), 0) stock_on_hand
        FROM stock_movements WHERE occurred_on <= :end
    """,
    "fulfilment": """
        WITH dispatch AS (
          SELECT sales_order_line_id, SUM(quantity) units
          FROM fulfilments WHERE fulfilled_on <= :end GROUP BY sales_order_line_id
        )
        SELECT COALESCE(SUM(l.quantity - COALESCE(d.units, 0)), 0) outstanding_units
        FROM sales_order_lines l JOIN sales_orders s ON s.id=l.sales_order_id
        LEFT JOIN dispatch d ON d.sales_order_line_id=l.id
        WHERE s.ordered_on BETWEEN :start AND :end
    """,
    "finance": """
        WITH invoices AS (
          SELECT f.amount, f.due_on, COALESCE((
            SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id=f.id AND p.paid_on <= :end
          ), 0) paid
          FROM supplier_invoices f WHERE f.issued_on BETWEEN :start AND :end
        )
        SELECT SUM(amount) invoice_value, SUM(paid) paid_amount,
          SUM(amount-paid) outstanding_amount,
          SUM(amount-paid) FILTER (WHERE due_on <= :end) overdue_amount,
          (SELECT SUM(amount) FROM operational_expenses
            WHERE incurred_on BETWEEN :start AND :end) operating_expenses,
          (SELECT SUM(amount) FROM operational_expenses WHERE incurred_on BETWEEN :start AND :end
            AND category IN ('expediting', 'overtime')) additional_costs
        FROM invoices
    """,
    "workforce": """
        WITH visible_tasks AS (
          SELECT t.id, t.department_id, t.owner_id, t.due_at,
            CASE WHEN t.completed_at < :cutoff THEN 'completed' ELSE (
              SELECT h.status FROM task_status_history h
              WHERE h.task_id=t.id AND h.created_at < :cutoff
              ORDER BY h.created_at DESC, h.id DESC LIMIT 1
            ) END observed_status
          FROM tasks t WHERE t.created_at < :cutoff
        )
        SELECT COUNT(*) total_tasks,
          COUNT(*) FILTER (WHERE observed_status <> 'completed') open_tasks,
          COUNT(*) FILTER (WHERE observed_status <> 'completed' AND due_at < :cutoff) overdue_tasks,
          COUNT(*) FILTER (WHERE observed_status IS NULL) unknown_status_tasks
        FROM visible_tasks
        WHERE (CAST(:department AS integer) IS NULL OR department_id=CAST(:department AS integer))
          AND (CAST(:employee AS integer) IS NULL OR owner_id=CAST(:employee AS integer))
    """,
    "incidents": """
        SELECT COUNT(*) total_incidents,
          COUNT(*) FILTER (WHERE closed_at IS NULL OR closed_at >= :cutoff) open_incidents
        FROM incidents WHERE created_at < :cutoff
    """,
}


def get(client, domain, params):
    response = client.get("/api/v1/analytics/" + domain, params=params)
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {}
    with (
        engine().begin() as db,
        httpx.Client(base_url="http://127.0.0.1:8001", timeout=15, trust_env=False) as client,
    ):
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        for name, start, end in (
            ("full", date(2025, 10, 1), date(2026, 9, 30)),
            ("august", date(2026, 8, 1), date(2026, 8, 31)),
        ):
            cutoff = datetime.combine(end + timedelta(days=1), time(), tzinfo=UTC)
            scope = {
                "start": start,
                "end": end,
                "cutoff": cutoff,
                "department": None,
                "employee": None,
            }
            query = {"start_date": start, "end_date": end, "as_of": end, "include_trends": "false"}
            result[name] = {}
            for domain, sql in SQL.items():
                expected = dict(db.execute(text(sql), scope).mappings().one())
                if domain == "procurement":
                    expected["on_time_rate"] = (
                        Decimal(100 * expected["on_time_orders"]) / expected["due_orders"]
                    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                actual = get(client, domain, query)
                assert actual["window"]["observation_start"] == str(start)
                assert actual["window"]["observation_end"] == actual["window"]["as_of"] == str(end)
                for key, value in expected.items():
                    metric = actual["metrics"][key]
                    assert Decimal(str(metric["value"])) == value, (
                        name,
                        domain,
                        key,
                        metric,
                        value,
                    )
                    if domain == "finance" or key.endswith("commitment"):
                        assert metric["unit"] == "GBP", (domain, key)
                result[name][domain] = expected
            for name_filter, key, api_name in (
                ("department_1", "department", "department_id"),
                ("employee_1", "employee", "employee_id"),
            ):
                expected = db.execute(text(SQL["workforce"]), {**scope, key: 1}).mappings().one()
                metrics = get(client, "workforce", {**query, api_name: 1})["metrics"]
                assert all(Decimal(str(metrics[k]["value"])) == v for k, v in expected.items())
                result[name][name_filter] = dict(expected)
        # An empty population is zero orders and an undefined rate, never zero percent.
        missing = get(client, "procurement", {"supplier_id": 999999})["metrics"]
        assert Decimal(str(missing["purchase_orders"]["value"])) == 0
        assert missing["on_time_rate"]["value"] is None
        assert missing["on_time_rate"]["status"] == "undefined"
        for params in (
            {"as_of": "2026-10-01"},
            {"start_date": "2026-09-30", "end_date": "2026-09-01"},
            {"as_of": "invalid"},
        ):
            assert client.get("/api/v1/analytics/overview", params=params).status_code == 422
    result["date_errors"] = 3
    result["empty_population_rate"] = "undefined"
    result["passed"] = True
    args.output.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print("Independent SQL matched both live reporting periods, workforce scope and date guards.")


if __name__ == "__main__":
    main()
