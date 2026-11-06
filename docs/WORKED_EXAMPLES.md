# Hand-verifiable analytics examples

The independent fixture in `backend/tests/analytics_fixtures.py` is hand-authored,
not generated from Northstar's random simulation. It is inserted only into a UUID
test database inside a rollback transaction. The real demo dataset is never reset.

## Supplier receipt and SLA

At 6 November 2025, supplier 1 has eleven orders. Ten are promised by 2 November:
eight fully received by 1 November, one received as 4 units on 1 November plus
6 on 4 November, and one still overdue. The eleventh promise is 20 November and
is immature at the cutoff.

Full-order on-time count = 8, completed late = 1, overdue incomplete = 1.
The denominator is **10 due orders**, so on-time rate is **80%**, not 8/11.
The contract's 95% target gives a **-15 percentage-point** operational concern.
The late order has two days of completed lateness; its early partial receipt does
not turn it into an on-time completed order.

At 2 November, eight orders are fully on time, two due orders remain incomplete
and one is partially received. Receipt-event punctuality is 100% then, while
full-order service is still 80%. These metrics have different grains.

All eleven orders were placed in October. For 1–6 November, order-date cohort
volume is zero, but completion-event throughput is **nine orders**. The report
and monthly trend preserve that distinction.

The first purchase order is 10 units at GBP 100; the other ten are 10 at GBP 10.
Order value is **GBP 2,000**, counted once per line despite split receipts. For
the same SKU, min/max prices are GBP 10/100 and weighted mean is GBP 18.18.
An unused supplier has zero orders and null/undefined on-time rate, never 0%.

## Inventory ledger

Warehouse 2 / product 2 has a documented opening adjustment of 20 units on
1 October, a receipt of 15 on 10 October, and dispatch of 25 on 15 October.

For a period beginning 2 October:

```text
opening 20 + receipts 15 - dispatches 25 + period adjustments 0 = closing 10
```

Stock as-of 1 October is 20, as-of 10 October 35, and as-of 15 October 10.
The final 10-unit balance is not substituted for earlier snapshots. All quantities
come from signed movements; reservations are not inferred.

## Invoice and cash flow

Invoice 1 is GBP 1,000. Two payments are GBP 400 on 3 October and GBP 350 on
4 October. At 6 November, **paid GBP 750 + outstanding GBP 250 = GBP 1,000**.
At 3 October the second payment is invisible: outstanding is GBP 600.

Selecting only 3–4 October gives invoice-cohort value zero (issue was 2 October),
but cash payments GBP 750. This legitimate scope difference is reported explicitly.
A second invoice has an unsupported GBP 25 discrepancy, recognized analytically
only once its finance-review incident opens on 5 November. Actual additional costs
are separate expense events: GBP 85 expediting and GBP 120 overtime. No cash value
is invented merely because a delay or dispute exists.

## Four tasks and historical incidents

Four tasks are due by 2 November at 12:00 UTC. Two complete before that timestamp,
one completes on 4 November, and one remains unfinished. At 6 November:

- completed on time: **2**;
- completed late: **1**;
- unfinished overdue: **1**;
- completion rate: **3/4 = 75%**.

At 1 November only one has completed, three remain open, and none is overdue yet.
A due timestamp exactly at the next day's midnight is excluded from the prior
as-of day's overdue population. Missing status history returns unavailable results.

An incident closed on 4 November remains unresolved in a 3 November snapshot.
New incidents during 4–6 November and all incidents still open at that cutoff are
separate incidence/prevalence counts. Historical escalation is null/unavailable,
because no escalation event history exists.

## Original Stage 1 scenarios, unchanged

Default dataset: 1 October 2025–30 September 2026, seed 20251001. These records are
regression cases, not forced rankings or hardcoded analytical endpoint responses.

| Scenario | Queryable evidence |
|---|---|
| Supplier delay to customer | Supplier/order 1 → receipt 185 → movement 332 → shortage 16 → customer order 1 → dispatch 149 → incident/task 16. Promise 8 Oct; receipt 20 Oct; customer promise 10 Oct; dispatch 20 Oct. The sole recorded replenishment source supports the simulated causal label. |
| Warehouse pressure | Incident/task 1729 → expense 104, explicit overtime **GBP 120**. No percentage capacity utilization is invented. |
| Contract concern | Supplier/contract 1: **24 of 72** due orders on time = **33.33%**, target **95%**. Legal breach is not established. |
| Finance review | Invoice 37: face value GBP 9,053.43 versus order lines GBP 9,028.43 → finance incident/task 1153. Explicit discrepancy **GBP 25**. |
| Corrective workload | Operations department 1 has **123** unfinished overdue tasks at the dataset cutoff; this is workload, not employee value. |

The default overall supplier on-time rate weights actual due orders rather than
averaging supplier percentages. Full live/in-process acceptance checks require
overview values to equal their corresponding domain metrics, and supplier detail
to equal comparison-row current-period metrics under the same comparison scope.

The persisted dataset fingerprint must remain:

```text
7ed73422d07ddb0528f0ce5641e1767cdef95aa698dfcddf8dc26aad68dae0b7
```

Tests independently assert the arithmetic, exact GBP values, historical boundaries,
source identifiers and absence of future evidence. The validation report records
freshly queried values; it never substitutes these examples into API output.
