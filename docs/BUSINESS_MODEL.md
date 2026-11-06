# Fictional business model

Northstar Supply is a synthetic UK distributor of office, industrial and technology
units. Six departments coordinate the company: Operations, Procurement, Warehouse
& Logistics, Finance, Customer Operations and Management. Forty-eight fictional
colleagues use only reserved `.example` email addresses. No login accounts exist.

Purchase orders are commitments to suppliers; sales orders are customer demand.
Their tables, lines, statuses and dates are distinct. Supplier contracts specify
effective dates, payment terms, an on-time receiving target and escalation days.
Promised dates are original receiving/dispatch commitments. A partial purchase
receipt does not imply that the commercial order is complete.

Stock is physical available stock, derived by product/warehouse from signed
movements. There are no reservations in Stage 1. Goods receipts add units and
fulfilments dispatch them. Shortages record missing units at order entry, with
an optional expected replenishment line for the same product and warehouse.
Resolution records full customer line dispatch, not a promise of replenishment.

Sales outstanding quantity is ordered quantity minus recorded fulfilments.
Delivery status is a lightweight synthetic dispatched/delivered indicator;
there is no carrier tracking or customer arrival timestamp. Customer promises
refer to dispatch. The Midlands warehouse applies a declared three-day handling
queue during November, December and June.

All money uses Decimal/NUMERIC in GBP, net of VAT. Purchase value is quantity
times unit price summed across lines, never a separately stored order total.
Invoices represent full purchase-line commercial value, including for staged
deliveries; a documented synthetic GBP 25 unsupported surcharge creates a dispute.
Payments can be partial or outstanding. Disputed invoices remain unpaid.
This is an operational cost model, not double-entry accounting or financial statements.

Additional costs exist only as explicit events: approved carrier rebooking GBP 85,
four overtime hours at GBP 30/hour, and monthly warehouse occupancy charges.
These are declared scenario assumptions, not estimates of every late delivery's loss.
Do not sum invoices and payments as two separate costs, or treat procurement
inventory purchases as a complete profit-and-loss statement.

Incidents retain typed links to operational evidence. Corrective tasks have owners,
departments, due dates and histories. Operations handles disproportionate triage
workload. Some tasks remain overdue at the fixed observation cutoff. Severity and
priority are constrained qualitative classifications; no fabricated supplier
performance score is stored.
