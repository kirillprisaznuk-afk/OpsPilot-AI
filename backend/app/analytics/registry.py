"""Central definitions; response construction and documentation share this registry."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Definition:
    name: str
    unit: str
    definition: str
    time_basis: str
    grain: str
    numerator: str | None = None
    denominator: str | None = None
    inclusion: str = "Persisted synthetic records visible at the UTC end-of-day cutoff."
    exclusion: str = "Events after as_of; records outside the documented population."
    null_behavior: str = "Zero for empty additive populations; null for empty averages/rates."
    limitations: str = "No modelled or unrecorded losses, capacity or productivity assumptions."


REGISTRY: dict[str, Definition] = {}


def register(domain, entries, time_basis, grain):
    for field, unit, meaning in entries:
        name = f"{domain}.{field}"
        REGISTRY[name] = Definition(name, unit, meaning, time_basis, grain)


def rate(domain, field, numerator, denominator, meaning, time_basis, grain):
    name = f"{domain}.{field}"
    REGISTRY[name] = Definition(name, "percent", meaning, time_basis, grain, numerator, denominator)


register(
    "procurement",
    [
        (
            "completed_in_period",
            "count",
            "Full-receipt completion events during the period, regardless of order date.",
        )
    ],
    "Completion-event flow in selected period",
    "purchase order",
)
register(
    "procurement",
    [
        ("purchase_orders", "count", "Distinct purchase orders in the order-date cohort."),
        (
            "order_value",
            "GBP",
            "Sum of selected purchase-line quantity times exact unit price, once per line.",
        ),
        ("ordered_units", "units", "Selected purchase-line units ordered."),
        (
            "received_units",
            "units",
            (
                "Selected-line units received by cutoff, including receipts outside the "
                "order-date window."
            ),
        ),
        ("outstanding_units", "units", "Selected ordered units minus received units at cutoff."),
        (
            "completed_orders",
            "count",
            "Cohort orders with every original line fully received by cutoff.",
        ),
        (
            "due_orders",
            "count",
            "Cohort orders whose original receiving promise is at or before as_of.",
        ),
        (
            "on_time_orders",
            "count",
            "Due orders fully received on or before their original promise.",
        ),
        ("late_orders", "count", "Orders fully received after promise, by cutoff."),
        (
            "overdue_outstanding_orders",
            "count",
            "Due orders still missing any original line quantity at cutoff.",
        ),
        ("open_orders", "count", "Cohort orders not fully received, including immature promises."),
        ("partial_orders", "count", "Incomplete orders with some physical receipts by cutoff."),
        (
            "split_receipt_orders",
            "count",
            "Orders with at least one line received in multiple events by cutoff.",
        ),
        (
            "open_commitment",
            "GBP",
            "Unreceived selected line quantities times their purchase unit prices.",
        ),
        ("overdue_commitment", "GBP", "Open selected-line value for overdue incomplete orders."),
        (
            "average_lateness",
            "days",
            "Mean positive lateness of completed late orders; excludes open orders.",
        ),
        (
            "median_lateness",
            "days",
            "Interpolated median positive lateness of completed late orders.",
        ),
        ("average_overdue_age", "days", "Mean days past promise for overdue incomplete orders."),
        (
            "average_lead_time",
            "days",
            "Mean calendar days from order to full completion; completed orders only.",
        ),
        ("receipt_events", "count", "Receipt events for cohort orders, visible by cutoff."),
        (
            "punctual_receipts",
            "count",
            "Receipt events dated on/before the order promise; distinct from order completion.",
        ),
    ],
    "Order-date cohort; outcomes censored at as_of",
    "purchase order (money/units: selected lines)",
)
rate(
    "procurement",
    "on_time_rate",
    "on_time_orders",
    "due_orders",
    "Full-quantity on-time orders / due orders; overdue outstanding orders stay in denominator.",
    "Order-date cohort; mature promises at as_of",
    "purchase order",
)
rate(
    "procurement",
    "receipt_punctuality_rate",
    "punctual_receipts",
    "receipt_events",
    "Punctual individual receipt events / observed receipt events, not supplier full-order SLA.",
    "Order-date cohort; receipts visible at as_of",
    "receipt event",
)
register(
    "suppliers",
    [
        (
            "additional_linked_costs",
            "GBP",
            (
                "Explicit expediting/overtime expenses linked through purchase order or "
                "incident; never inferred loss."
            ),
        )
    ],
    "Expense events within selected period",
    "expense event",
)
register(
    "suppliers",
    [
        (
            "sla_target_percent",
            "percent",
            (
                "Contract on-time target when applicable contracts share one target; "
                "otherwise unavailable."
            ),
        ),
        (
            "sla_gap",
            "percentage_points",
            "Observed full-order on-time percent minus the common contractual target.",
        ),
    ],
    "Order cohort and effective contracts; no legal breach determination",
    "supplier",
)
register(
    "inventory",
    [
        ("opening_stock", "units", "Signed ledger balance strictly before start_date."),
        ("closing_stock", "units", "Signed ledger balance through end_date."),
        (
            "stock_on_hand",
            "units",
            "Physical signed ledger balance through as_of; no reservations exist.",
        ),
        ("received_units", "units", "Positive receipt movements within selected period."),
        ("dispatched_units", "units", "Absolute issue movements within selected period."),
        ("adjusted_units", "units", "Signed documented adjustments within selected period."),
        (
            "stock_positions",
            "count",
            "Product/warehouse positions with at least one movement visible by cutoff.",
        ),
        (
            "positive_stock_positions",
            "count",
            (
                "Observed positions with positive physical stock at as_of; not a "
                "fill-rate or availability percentage."
            ),
        ),
        (
            "open_shortages",
            "count",
            "Shortage records detected by cutoff with sales line demand still outstanding.",
        ),
        (
            "outstanding_shortage_units",
            "units",
            "Remaining unfulfilled units on shortage-associated sales lines, at as_of.",
        ),
        (
            "outstanding_demand_units",
            "units",
            "All sales-line ordered minus dispatched units, at as_of.",
        ),
        (
            "shortage_occurrences",
            "count",
            "Shortage detections within selected period; distinct from open shortage prevalence.",
        ),
        (
            "shortage_incidents",
            "count",
            "Incidents with explicit shortage links opened within selected period.",
        ),
    ],
    "Ledger flows in period; snapshots explicitly at end_date or as_of",
    "movement or sales line / shortage",
)
register(
    "fulfilment",
    [
        ("sales_orders", "count", "Distinct sales orders in the order-date cohort."),
        ("ordered_units", "units", "Selected customer sales-line ordered quantities."),
        (
            "dispatched_units",
            "units",
            "Selected-line physical dispatch quantities visible by cutoff.",
        ),
        ("outstanding_units", "units", "Selected ordered minus dispatched quantities at cutoff."),
        (
            "completed_orders",
            "count",
            "Orders with all original line quantities dispatched by cutoff.",
        ),
        ("partial_orders", "count", "Incomplete orders with some recorded dispatch."),
        ("open_orders", "count", "Customer orders with any outstanding quantity."),
        (
            "due_orders",
            "count",
            "Cohort sales orders whose original dispatch promise is mature at cutoff.",
        ),
        ("on_time_orders", "count", "Due sales orders fully dispatched on/before promise."),
        ("late_orders", "count", "Sales orders fully dispatched late by cutoff."),
        (
            "overdue_outstanding_orders",
            "count",
            "Due customer orders not fully dispatched at cutoff.",
        ),
        (
            "backorder_units",
            "units",
            "Outstanding selected-line units; reservations are not implemented.",
        ),
        ("average_lateness", "days", "Mean positive delay of fully dispatched late orders."),
        (
            "shortage_linked_delays",
            "count",
            (
                "Distinct delayed orders with an explicit shortage record; association, "
                "not sole-cause proof."
            ),
        ),
        (
            "late_supply_linked_delays",
            "count",
            "Delayed orders linked via shortage to an inbound order past its promise; association.",
        ),
        (
            "capacity_linked_delays",
            "count",
            "Delayed orders with explicit capacity incidents visible by cutoff.",
        ),
    ],
    "Sales order-date cohort; dispatch outcomes censored at as_of",
    "sales order (units: selected lines)",
)
rate(
    "fulfilment",
    "on_time_rate",
    "on_time_orders",
    "due_orders",
    "Fully on-time dispatched due orders / all due sales orders; not carrier-arrival punctuality.",
    "Order-date cohort; mature dispatch promises",
    "sales order",
)
register(
    "finance",
    [
        ("invoices", "count", "Invoices issued within selected period."),
        (
            "invoice_value",
            "GBP",
            "Exact face value of invoice-issue cohort, including documented disputed charges.",
        ),
        ("paid_amount", "GBP", "Payments by as_of against the selected invoice cohort."),
        (
            "outstanding_amount",
            "GBP",
            "Invoice-cohort face value less its payments by cutoff; not cash spent.",
        ),
        ("overdue_invoices", "count", "Unsettled cohort invoices with mature due dates at cutoff."),
        ("overdue_amount", "GBP", "Remaining liability on overdue cohort invoices."),
        (
            "fully_paid_invoices",
            "count",
            "Cohort invoices fully settled by observed payments, not final status.",
        ),
        (
            "partially_paid_invoices",
            "count",
            "Cohort invoices with positive but incomplete payment by cutoff.",
        ),
        ("unpaid_invoices", "count", "Cohort invoices with no observed payment by cutoff."),
        (
            "discrepancy_invoices",
            "count",
            (
                "Cohort invoices with a visible finance-review incident and face value "
                "differing from purchase-line value."
            ),
        ),
        (
            "documented_discrepancy_amount",
            "GBP",
            (
                "Signed invoice-minus-order value for visible discrepancy incidents; "
                "disputed exposure, not operating expense."
            ),
        ),
        (
            "payments_made",
            "GBP",
            (
                "Cash payment events dated within selected period, independently of "
                "invoice issue cohort."
            ),
        ),
        (
            "average_payment_days",
            "days",
            (
                "Mean days from issue to individual payment events within period; not "
                "full settlement time."
            ),
        ),
        (
            "operating_expenses",
            "GBP",
            "Explicit operating expense events within selected period, net of VAT.",
        ),
        ("additional_costs", "GBP", "Explicit expediting and overtime expense events only."),
        ("expediting_costs", "GBP", "Recorded expediting expense events."),
        ("overtime_costs", "GBP", "Recorded overtime expense events."),
    ],
    "Invoice cohort, payment flows and expense flows labelled separately",
    "invoice, payment event or expense event",
)
register(
    "workforce",
    [
        (
            "total_tasks",
            "count",
            "Tasks created by cutoff under the selected assignment dimensions.",
        ),
        ("tasks_created", "count", "New tasks within selected period."),
        (
            "open_tasks",
            "count",
            (
                "Tasks with observed non-completed history state at cutoff; null if any "
                "history is unavailable."
            ),
        ),
        ("completed_tasks", "count", "Tasks with completion timestamps at/before cutoff."),
        ("completed_in_period", "count", "Completion events within selected period."),
        (
            "overdue_tasks",
            "count",
            "Tasks due by cutoff and not completed by it; null if history is unavailable.",
        ),
        (
            "completed_late",
            "count",
            "Completed tasks whose completion timestamp exceeds due timestamp.",
        ),
        (
            "completed_on_time",
            "count",
            "Completed tasks whose completion timestamp is at/before due timestamp.",
        ),
        ("unknown_status_tasks", "count", "Tasks without reliable status evidence at cutoff."),
        ("average_open_age", "days", "Mean calendar-date age of observed non-completed tasks."),
        (
            "average_completion_days",
            "days",
            "Mean elapsed days from creation to observed completion.",
        ),
    ],
    "Snapshot at as_of; creation/completion flows in selected period",
    "task",
)
rate(
    "workforce",
    "completion_rate",
    "completed_tasks",
    "total_tasks",
    (
        "Observed completed tasks / all tasks created by cutoff; assignment "
        "workload, not employee value."
    ),
    "Snapshot at as_of",
    "task",
)
register(
    "incidents",
    [
        ("total_incidents", "count", "Incidents opened by cutoff."),
        ("new_incidents", "count", "Incidents opened within selected period (incidence)."),
        (
            "open_incidents",
            "count",
            "Incidents not closed by cutoff (unresolved prevalence, all operational statuses).",
        ),
        ("resolved_incidents", "count", "Incidents with explicit closure by cutoff."),
        ("resolved_in_period", "count", "Closure events within selected period."),
        (
            "escalated_incidents",
            "count",
            "Final-cutoff unresolved escalated incidents; earlier escalation status unavailable.",
        ),
        (
            "critical_open_incidents",
            "count",
            "Unresolved incidents classified critical in the recorded severity field.",
        ),
        (
            "high_open_incidents",
            "count",
            "Unresolved incidents classified high in the recorded severity field.",
        ),
        ("average_open_age", "days", "Mean calendar-date age of unresolved incidents."),
        (
            "average_resolution_days",
            "days",
            "Mean elapsed creation-to-closure days for incidents closed by cutoff.",
        ),
        (
            "corrective_tasks",
            "count",
            "Distinct tasks created by cutoff with a link to selected incidents.",
        ),
        (
            "open_corrective_tasks",
            "count",
            "Linked tasks with observed unfinished status by cutoff.",
        ),
    ],
    "Snapshot prevalence at as_of; opening/closure incidence in period",
    "incident (actions: task)",
)
