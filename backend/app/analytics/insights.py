from app.analytics import finance, incidents, inventory, suppliers, workforce
from app.analytics.common import metrics, validate_query, window
from app.analytics.contracts import Insight, InsightReport

SEVERITY_ORDER = {"critical": 0, "warning": 1, "opportunity": 2, "information": 3}


def get_insights(db, q):
    validate_query(q, ())
    items = []
    # Process bounded SQL aggregates (not transactional records); query count is
    # independent of employee, task and order populations.
    bounded = q.model_copy(
        update={"limit": 100, "offset": 0, "include_trends": False, "include_comparison": False}
    )
    supplier_report = suppliers.get_suppliers(db, bounded)
    assessments = sorted(
        supplier_report.contracts,
        key=lambda a: (
            a.gap_percentage_points is None,
            a.gap_percentage_points or 0,
            a.contract_id,
        ),
    )
    for contract in assessments:
        if (
            contract.due_orders < 5
            or contract.gap_percentage_points is None
            or contract.gap_percentage_points >= 0
        ):
            continue
        contract_metrics = metrics(
            "procurement",
            {"on_time_orders": contract.on_time_orders, "due_orders": contract.due_orders},
        )
        target_metrics = metrics(
            "suppliers",
            {
                "sla_target_percent": contract.target_percent,
                "sla_gap": contract.gap_percentage_points,
            },
        )
        items.append(
            Insight(
                rule_id="supplier_below_target",
                severity="warning" if contract.gap_percentage_points <= -10 else "information",
                statement=(
                    f"Supplier {contract.supplier_id}: {contract.observed_percent}% "
                    f"full-order on-time receipt is below contract {contract.contract_id} "
                    f"target {contract.target_percent}%."
                ),
                entity_type="supplier",
                entity_id=contract.supplier_id,
                evidence={"on_time_rate": contract_metrics["on_time_rate"], **target_metrics},
                source_reference=f"/api/v1/analytics/suppliers/{contract.supplier_id}",
            )
        )
        if sum(i.rule_id == "supplier_below_target" for i in items) == 3:
            break
    warehouse_report = inventory.get_inventory(
        db,
        bounded.model_copy(
            update={
                "group_by": "warehouse",
                "sort": "outstanding_shortage_units",
                "direction": "desc",
            }
        ),
    )
    if warehouse_report.breakdowns:
        largest = warehouse_report.breakdowns[0]
        missing = largest.metrics["outstanding_shortage_units"]
        if missing.value:
            items.append(
                Insight(
                    rule_id="warehouse_shortage",
                    severity="warning",
                    statement=(
                        f"Warehouse {largest.entity_id} has the highest observed outstanding "
                        f"shortage demand: {missing.value} units (ties ordered by ID)."
                    ),
                    entity_type="warehouse",
                    entity_id=largest.entity_id,
                    evidence={"outstanding_shortage_units": missing},
                    source_reference=f"/api/v1/analytics/investigations/warehouse/{largest.entity_id}",
                )
            )
    tasks = workforce.get_workforce(
        db, bounded.model_copy(update={"sort": "overdue_tasks", "direction": "desc"})
    )
    if tasks.breakdowns:
        largest = tasks.breakdowns[0]
        overdue = largest.metrics["overdue_tasks"]
        if overdue.value:
            items.append(
                Insight(
                    rule_id="overdue_corrective_work",
                    severity="warning" if overdue.value >= 20 else "information",
                    statement=(
                        f"{largest.label} has {overdue.value} unfinished overdue tasks at the "
                        f"selected cutoff."
                    ),
                    entity_type="department",
                    entity_id=largest.entity_id,
                    evidence={"overdue_tasks": overdue},
                    source_reference=f"/api/v1/analytics/workforce?department_id={largest.entity_id}",
                )
            )
    incident_metrics = metrics("incidents", incidents.compute(db, bounded))
    for severity in ("critical", "high"):
        metric = incident_metrics[f"{severity}_open_incidents"]
        if metric.value:
            items.append(
                Insight(
                    rule_id=f"{severity}_open_incidents",
                    severity="critical" if severity == "critical" else "warning",
                    statement=(
                        f"{metric.value} recorded {severity}-severity incidents remain unresolved "
                        f"at the cutoff."
                    ),
                    evidence={metric.metric: metric},
                    source_reference="/api/v1/analytics/incidents",
                )
            )
    financial = metrics("finance", finance.compute(db, bounded))
    discrepancies = financial["discrepancy_invoices"]
    if discrepancies.value:
        items.append(
            Insight(
                rule_id="invoice_review",
                severity="warning",
                statement=(
                    f"{discrepancies.value} invoices have explicitly recorded finance-review "
                    f"discrepancies."
                ),
                evidence={
                    "discrepancy_invoices": discrepancies,
                    "documented_discrepancy_amount": financial["documented_discrepancy_amount"],
                },
                source_reference="/api/v1/analytics/finance",
            )
        )
    overdue_commitment = supplier_report.metrics["overdue_commitment"]
    if overdue_commitment.value and overdue_commitment.value >= 1000:
        items.append(
            Insight(
                rule_id="overdue_purchase_commitments",
                severity="warning",
                statement=(
                    f"Recorded overdue unreceived purchase commitments total GBP "
                    f"{overdue_commitment.value}."
                ),
                evidence={"overdue_commitment": overdue_commitment},
                source_reference="/api/v1/analytics/procurement",
            )
        )
    previous_q = q.previous()
    if previous_q:
        previous = metrics("finance", finance.compute(db, previous_q))
        current_cost = financial["expediting_costs"]
        old_cost = previous["expediting_costs"]
        if current_cost.value > old_cost.value:
            items.append(
                Insight(
                    rule_id="expediting_increase",
                    severity="warning",
                    statement=(
                        f"Recorded expediting costs increased from GBP {old_cost.value} to GBP "
                        f"{current_cost.value} over the equivalent eligible periods."
                    ),
                    evidence={"current": current_cost, "previous": old_cost},
                    source_reference="/api/v1/analytics/finance",
                )
            )
    items.sort(key=lambda item: (SEVERITY_ORDER[item.severity], item.rule_id, item.entity_id or 0))
    return InsightReport(
        window=window(q),
        items=items[q.offset : q.offset + q.limit],
        total=len(items),
        limit=q.limit,
        offset=q.offset,
    )
