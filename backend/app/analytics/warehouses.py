from app.analytics import finance, fulfilment, incidents, inventory
from app.analytics.common import metrics, rows, validate_query


def get_warehouses(db, q):
    validate_query(q, inventory.ALLOWED, ("warehouse",), inventory.SORTS)
    q = q.model_copy(update={"group_by": "warehouse"})
    result = inventory.get_inventory(db, q)
    result.domain = "warehouses"
    # Each domain aggregates all selected warehouses once, never once per warehouse.
    sources = [
        ("fulfilment", fulfilment, {"late_orders", "overdue_outstanding_orders"}),
        ("incidents", incidents, {"new_incidents", "open_incidents", "escalated_incidents"}),
        ("finance", finance, {"additional_costs", "overtime_costs", "expediting_costs"}),
    ]
    for domain, module, selected in sources:
        scoped = q.model_copy(update={"product_id": None, "product_category": None})
        if q.product_id or q.product_category:
            # Inventory/product demand can be segmented; warehouse incident/expense attribution
            # cannot be proportionally allocated to products without inventing a model.
            if domain in {"incidents", "finance"}:
                continue
            scoped = q
        raw = module.compute(db, scoped)
        previous = (
            module.compute(db, scoped.previous())
            if q.include_comparison and scoped.previous()
            else None
        )
        computed = metrics(domain, raw, previous, scoped.previous(), q.include_comparison)
        result.metrics.update({f"{domain}_{k}": v for k, v in computed.items() if k in selected})
        grouped = rows(db, module.aggregate_sql("warehouse"), scoped)
        by_id = {r["entity_id"]: r for r in grouped}
        for segment in result.breakdowns:
            if segment.entity_id in by_id:
                computed = metrics(domain, by_id[segment.entity_id])
                segment.metrics.update(
                    {f"{domain}_{k}": v for k, v in computed.items() if k in selected}
                )
    result.limitations.append(
        "Warehouse pressure is an observed incident category; no capacity "
        "denominator or utilization percentage exists."
    )
    if q.product_id or q.product_category:
        result.limitations.append(
            "Product-specific expense/incident attribution is unavailable; those "
            "warehouse-wide metrics are omitted."
        )
    return result
