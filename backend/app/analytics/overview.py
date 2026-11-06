from app.analytics import finance, fulfilment, incidents, inventory, procurement, workforce
from app.analytics.common import metrics, validate_query, window
from app.analytics.contracts import AnalyticsReport

HEADLINES = [
    (
        "procurement",
        procurement,
        {"purchase_orders", "on_time_rate", "open_commitment", "overdue_commitment"},
    ),
    (
        "inventory",
        inventory,
        {
            "stock_on_hand",
            "positive_stock_positions",
            "open_shortages",
            "outstanding_shortage_units",
        },
    ),
    (
        "fulfilment",
        fulfilment,
        {"sales_orders", "on_time_rate", "outstanding_units", "overdue_outstanding_orders"},
    ),
    ("finance", finance, {"outstanding_amount", "overdue_amount", "additional_costs"}),
    ("workforce", workforce, {"open_tasks", "overdue_tasks"}),
    ("incidents", incidents, {"open_incidents", "critical_open_incidents"}),
]


def get_overview(db, q):
    validate_query(q, ())
    result = {}
    previous_q = q.previous() if q.include_comparison else None
    for domain, module, selected in HEADLINES:
        current = module.compute(db, q)
        previous = module.compute(db, previous_q) if previous_q else None
        computed = metrics(domain, current, previous, previous_q, q.include_comparison)
        result.update(
            {f"{domain}.{key}": metric for key, metric in computed.items() if key in selected}
        )
    return AnalyticsReport(
        domain="overview",
        window=window(q),
        filters={},
        metrics=result,
        limit=q.limit,
        offset=q.offset,
        limitations=[
            (
                "Each headline retains its domain population: order/invoice cohorts, "
                "event expenses or all-history snapshots."
            ),
            (
                "Monthly trends and segmentation are available from the corresponding "
                "domain endpoints."
            ),
        ],
    )
