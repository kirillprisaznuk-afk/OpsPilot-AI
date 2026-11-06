# Metric registry
Percentages use **0–100**. Money is exact **GBP net of VAT**.
Every metric below inherits these defaults unless its definition narrows the scope:
- Inclusion: persisted synthetic records visible by UTC end of as_of.
- Exclusion: future events and records outside the metric's population.
- Empty behavior: additive metrics are zero; empty averages and ratios are null.
- Limitations: no unrecorded losses, capacity denominators, employee scores or legal findings.
- Entity labels and assignment dimensions have no revision history; historical reassignment is unavailable.

Order promises mature at UTC end of their promised date. Full completion requires every original line. Product filters select line values/units but never redefine full-order service completion. Incidence flows and all-history snapshot prevalence are labelled separately.

Invoice exposure and payments must not be added as two costs. Shortage units are remaining sales demand, not the initial missing-quantity snapshot. Reservations and carrier arrival are unavailable.

## Procurement
| Metric | Unit | Definition | Numerator / denominator | Time basis | Grain |
|---|---|---|---|---|---|
| `procurement.completed_in_period` | count | Full-receipt completion events during the period, regardless of order date. | Not a ratio | Completion-event flow in selected period | purchase order |
| `procurement.purchase_orders` | count | Distinct purchase orders in the order-date cohort. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.order_value` | GBP | Sum of selected purchase-line quantity times exact unit price, once per line. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.ordered_units` | units | Selected purchase-line units ordered. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.received_units` | units | Selected-line units received by cutoff, including receipts outside the order-date window. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.outstanding_units` | units | Selected ordered units minus received units at cutoff. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.completed_orders` | count | Cohort orders with every original line fully received by cutoff. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.due_orders` | count | Cohort orders whose original receiving promise is at or before as_of. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.on_time_orders` | count | Due orders fully received on or before their original promise. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.late_orders` | count | Orders fully received after promise, by cutoff. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.overdue_outstanding_orders` | count | Due orders still missing any original line quantity at cutoff. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.open_orders` | count | Cohort orders not fully received, including immature promises. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.partial_orders` | count | Incomplete orders with some physical receipts by cutoff. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.split_receipt_orders` | count | Orders with at least one line received in multiple events by cutoff. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.open_commitment` | GBP | Unreceived selected line quantities times their purchase unit prices. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.overdue_commitment` | GBP | Open selected-line value for overdue incomplete orders. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.average_lateness` | days | Mean positive lateness of completed late orders; excludes open orders. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.median_lateness` | days | Interpolated median positive lateness of completed late orders. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.average_overdue_age` | days | Mean days past promise for overdue incomplete orders. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.average_lead_time` | days | Mean calendar days from order to full completion; completed orders only. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.receipt_events` | count | Receipt events for cohort orders, visible by cutoff. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.punctual_receipts` | count | Receipt events dated on/before the order promise; distinct from order completion. | Not a ratio | Order-date cohort; outcomes censored at as_of | purchase order (money/units: selected lines) |
| `procurement.on_time_rate` | percent | Full-quantity on-time orders / due orders; overdue outstanding orders stay in denominator. | on_time_orders / due_orders | Order-date cohort; mature promises at as_of | purchase order |
| `procurement.receipt_punctuality_rate` | percent | Punctual individual receipt events / observed receipt events, not supplier full-order SLA. | punctual_receipts / receipt_events | Order-date cohort; receipts visible at as_of | receipt event |

## Suppliers
| Metric | Unit | Definition | Numerator / denominator | Time basis | Grain |
|---|---|---|---|---|---|
| `suppliers.additional_linked_costs` | GBP | Explicit expediting/overtime expenses linked through purchase order or incident; never inferred loss. | Not a ratio | Expense events within selected period | expense event |
| `suppliers.sla_target_percent` | percent | Contract on-time target when applicable contracts share one target; otherwise unavailable. | Not a ratio | Order cohort and effective contracts; no legal breach determination | supplier |
| `suppliers.sla_gap` | percentage_points | Observed full-order on-time percent minus the common contractual target. | Not a ratio | Order cohort and effective contracts; no legal breach determination | supplier |

## Inventory
| Metric | Unit | Definition | Numerator / denominator | Time basis | Grain |
|---|---|---|---|---|---|
| `inventory.opening_stock` | units | Signed ledger balance strictly before start_date. | Not a ratio | Ledger flows in period; snapshots explicitly at end_date or as_of | movement or sales line / shortage |
| `inventory.closing_stock` | units | Signed ledger balance through end_date. | Not a ratio | Ledger flows in period; snapshots explicitly at end_date or as_of | movement or sales line / shortage |
| `inventory.stock_on_hand` | units | Physical signed ledger balance through as_of; no reservations exist. | Not a ratio | Ledger flows in period; snapshots explicitly at end_date or as_of | movement or sales line / shortage |
| `inventory.received_units` | units | Positive receipt movements within selected period. | Not a ratio | Ledger flows in period; snapshots explicitly at end_date or as_of | movement or sales line / shortage |
| `inventory.dispatched_units` | units | Absolute issue movements within selected period. | Not a ratio | Ledger flows in period; snapshots explicitly at end_date or as_of | movement or sales line / shortage |
| `inventory.adjusted_units` | units | Signed documented adjustments within selected period. | Not a ratio | Ledger flows in period; snapshots explicitly at end_date or as_of | movement or sales line / shortage |
| `inventory.stock_positions` | count | Product/warehouse positions with at least one movement visible by cutoff. | Not a ratio | Ledger flows in period; snapshots explicitly at end_date or as_of | movement or sales line / shortage |
| `inventory.positive_stock_positions` | count | Observed positions with positive physical stock at as_of; not a fill-rate or availability percentage. | Not a ratio | Ledger flows in period; snapshots explicitly at end_date or as_of | movement or sales line / shortage |
| `inventory.open_shortages` | count | Shortage records detected by cutoff with sales line demand still outstanding. | Not a ratio | Ledger flows in period; snapshots explicitly at end_date or as_of | movement or sales line / shortage |
| `inventory.outstanding_shortage_units` | units | Remaining unfulfilled units on shortage-associated sales lines, at as_of. | Not a ratio | Ledger flows in period; snapshots explicitly at end_date or as_of | movement or sales line / shortage |
| `inventory.outstanding_demand_units` | units | All sales-line ordered minus dispatched units, at as_of. | Not a ratio | Ledger flows in period; snapshots explicitly at end_date or as_of | movement or sales line / shortage |
| `inventory.shortage_occurrences` | count | Shortage detections within selected period; distinct from open shortage prevalence. | Not a ratio | Ledger flows in period; snapshots explicitly at end_date or as_of | movement or sales line / shortage |
| `inventory.shortage_incidents` | count | Incidents with explicit shortage links opened within selected period. | Not a ratio | Ledger flows in period; snapshots explicitly at end_date or as_of | movement or sales line / shortage |

## Fulfilment
| Metric | Unit | Definition | Numerator / denominator | Time basis | Grain |
|---|---|---|---|---|---|
| `fulfilment.sales_orders` | count | Distinct sales orders in the order-date cohort. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.ordered_units` | units | Selected customer sales-line ordered quantities. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.dispatched_units` | units | Selected-line physical dispatch quantities visible by cutoff. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.outstanding_units` | units | Selected ordered minus dispatched quantities at cutoff. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.completed_orders` | count | Orders with all original line quantities dispatched by cutoff. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.partial_orders` | count | Incomplete orders with some recorded dispatch. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.open_orders` | count | Customer orders with any outstanding quantity. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.due_orders` | count | Cohort sales orders whose original dispatch promise is mature at cutoff. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.on_time_orders` | count | Due sales orders fully dispatched on/before promise. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.late_orders` | count | Sales orders fully dispatched late by cutoff. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.overdue_outstanding_orders` | count | Due customer orders not fully dispatched at cutoff. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.backorder_units` | units | Outstanding selected-line units; reservations are not implemented. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.average_lateness` | days | Mean positive delay of fully dispatched late orders. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.shortage_linked_delays` | count | Distinct delayed orders with an explicit shortage record; association, not sole-cause proof. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.late_supply_linked_delays` | count | Delayed orders linked via shortage to an inbound order past its promise; association. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.capacity_linked_delays` | count | Delayed orders with explicit capacity incidents visible by cutoff. | Not a ratio | Sales order-date cohort; dispatch outcomes censored at as_of | sales order (units: selected lines) |
| `fulfilment.on_time_rate` | percent | Fully on-time dispatched due orders / all due sales orders; not carrier-arrival punctuality. | on_time_orders / due_orders | Order-date cohort; mature dispatch promises | sales order |

## Finance
| Metric | Unit | Definition | Numerator / denominator | Time basis | Grain |
|---|---|---|---|---|---|
| `finance.invoices` | count | Invoices issued within selected period. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.invoice_value` | GBP | Exact face value of invoice-issue cohort, including documented disputed charges. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.paid_amount` | GBP | Payments by as_of against the selected invoice cohort. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.outstanding_amount` | GBP | Invoice-cohort face value less its payments by cutoff; not cash spent. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.overdue_invoices` | count | Unsettled cohort invoices with mature due dates at cutoff. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.overdue_amount` | GBP | Remaining liability on overdue cohort invoices. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.fully_paid_invoices` | count | Cohort invoices fully settled by observed payments, not final status. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.partially_paid_invoices` | count | Cohort invoices with positive but incomplete payment by cutoff. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.unpaid_invoices` | count | Cohort invoices with no observed payment by cutoff. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.discrepancy_invoices` | count | Cohort invoices with a visible finance-review incident and face value differing from purchase-line value. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.documented_discrepancy_amount` | GBP | Signed invoice-minus-order value for visible discrepancy incidents; disputed exposure, not operating expense. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.payments_made` | GBP | Cash payment events dated within selected period, independently of invoice issue cohort. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.average_payment_days` | days | Mean days from issue to individual payment events within period; not full settlement time. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.operating_expenses` | GBP | Explicit operating expense events within selected period, net of VAT. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.additional_costs` | GBP | Explicit expediting and overtime expense events only. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.expediting_costs` | GBP | Recorded expediting expense events. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |
| `finance.overtime_costs` | GBP | Recorded overtime expense events. | Not a ratio | Invoice cohort, payment flows and expense flows labelled separately | invoice, payment event or expense event |

## Workforce
| Metric | Unit | Definition | Numerator / denominator | Time basis | Grain |
|---|---|---|---|---|---|
| `workforce.total_tasks` | count | Tasks created by cutoff under the selected assignment dimensions. | Not a ratio | Snapshot at as_of; creation/completion flows in selected period | task |
| `workforce.tasks_created` | count | New tasks within selected period. | Not a ratio | Snapshot at as_of; creation/completion flows in selected period | task |
| `workforce.open_tasks` | count | Tasks with observed non-completed history state at cutoff; null if any history is unavailable. | Not a ratio | Snapshot at as_of; creation/completion flows in selected period | task |
| `workforce.completed_tasks` | count | Tasks with completion timestamps at/before cutoff. | Not a ratio | Snapshot at as_of; creation/completion flows in selected period | task |
| `workforce.completed_in_period` | count | Completion events within selected period. | Not a ratio | Snapshot at as_of; creation/completion flows in selected period | task |
| `workforce.overdue_tasks` | count | Tasks due by cutoff and not completed by it; null if history is unavailable. | Not a ratio | Snapshot at as_of; creation/completion flows in selected period | task |
| `workforce.completed_late` | count | Completed tasks whose completion timestamp exceeds due timestamp. | Not a ratio | Snapshot at as_of; creation/completion flows in selected period | task |
| `workforce.completed_on_time` | count | Completed tasks whose completion timestamp is at/before due timestamp. | Not a ratio | Snapshot at as_of; creation/completion flows in selected period | task |
| `workforce.unknown_status_tasks` | count | Tasks without reliable status evidence at cutoff. | Not a ratio | Snapshot at as_of; creation/completion flows in selected period | task |
| `workforce.average_open_age` | days | Mean calendar-date age of observed non-completed tasks. | Not a ratio | Snapshot at as_of; creation/completion flows in selected period | task |
| `workforce.average_completion_days` | days | Mean elapsed days from creation to observed completion. | Not a ratio | Snapshot at as_of; creation/completion flows in selected period | task |
| `workforce.completion_rate` | percent | Observed completed tasks / all tasks created by cutoff; assignment workload, not employee value. | completed_tasks / total_tasks | Snapshot at as_of | task |

## Incidents
| Metric | Unit | Definition | Numerator / denominator | Time basis | Grain |
|---|---|---|---|---|---|
| `incidents.total_incidents` | count | Incidents opened by cutoff. | Not a ratio | Snapshot prevalence at as_of; opening/closure incidence in period | incident (actions: task) |
| `incidents.new_incidents` | count | Incidents opened within selected period (incidence). | Not a ratio | Snapshot prevalence at as_of; opening/closure incidence in period | incident (actions: task) |
| `incidents.open_incidents` | count | Incidents not closed by cutoff (unresolved prevalence, all operational statuses). | Not a ratio | Snapshot prevalence at as_of; opening/closure incidence in period | incident (actions: task) |
| `incidents.resolved_incidents` | count | Incidents with explicit closure by cutoff. | Not a ratio | Snapshot prevalence at as_of; opening/closure incidence in period | incident (actions: task) |
| `incidents.resolved_in_period` | count | Closure events within selected period. | Not a ratio | Snapshot prevalence at as_of; opening/closure incidence in period | incident (actions: task) |
| `incidents.escalated_incidents` | count | Final-cutoff unresolved escalated incidents; earlier escalation status unavailable. | Not a ratio | Snapshot prevalence at as_of; opening/closure incidence in period | incident (actions: task) |
| `incidents.critical_open_incidents` | count | Unresolved incidents classified critical in the recorded severity field. | Not a ratio | Snapshot prevalence at as_of; opening/closure incidence in period | incident (actions: task) |
| `incidents.high_open_incidents` | count | Unresolved incidents classified high in the recorded severity field. | Not a ratio | Snapshot prevalence at as_of; opening/closure incidence in period | incident (actions: task) |
| `incidents.average_open_age` | days | Mean calendar-date age of unresolved incidents. | Not a ratio | Snapshot prevalence at as_of; opening/closure incidence in period | incident (actions: task) |
| `incidents.average_resolution_days` | days | Mean elapsed creation-to-closure days for incidents closed by cutoff. | Not a ratio | Snapshot prevalence at as_of; opening/closure incidence in period | incident (actions: task) |
| `incidents.corrective_tasks` | count | Distinct tasks created by cutoff with a link to selected incidents. | Not a ratio | Snapshot prevalence at as_of; opening/closure incidence in period | incident (actions: task) |
| `incidents.open_corrective_tasks` | count | Linked tasks with observed unfinished status by cutoff. | Not a ratio | Snapshot prevalence at as_of; opening/closure incidence in period | incident (actions: task) |

## Comparisons and limitations
Previous periods have the same number of calendar days and the same post-period observation lag. A previous window crossing 1 October 2025 is unavailable, not shortened. Relative change is null at a zero baseline; absolute change remains available. Rate differences additionally report percentage points.

Earlier escalation counts are unavailable because incident status history does not exist. Task state uses the latest history entry before the exclusive next-day UTC cutoff. Missing task history makes open/overdue results unavailable, never inferred from final status.

Monthly order trends use the report's as_of for outcomes and disclose mature denominators. Inventory trend snapshots use each month's end. The selected current period can be partial; comparisons preserve its actual length. A below-target supplier result is an operational concern, not a legally established contract violation.
