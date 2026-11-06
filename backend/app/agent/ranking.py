"""Agent presentation ordering of existing Stage 2 supplier metrics, no new KPIs."""

from decimal import Decimal

from app.agent.contracts import AgentError
from app.analytics import suppliers

EXTRA_SORTS = {"overdue_outstanding_orders", "sla_gap", "open_commitment"}


def compare_suppliers(db, query):
    if query.sort not in EXTRA_SORTS:
        return suppliers.get_suppliers(db, query)
    # A controlled, complete snapshot is needed to rank a metric that Stage 2
    # exposes but does not offer as a public SQL sort. Public endpoints stay intact.
    snapshot_query = query.model_copy(
        update={"sort": "id", "direction": "asc", "limit": 100, "offset": 0}
    )
    snapshot = suppliers.get_suppliers(db, snapshot_query)
    if snapshot.total_segments > 100:
        raise AgentError(
            "ranking_population_limit",
            "Narrow the scope: a complete ranking "
            "cannot exceed the existing hundred-record snapshot ceiling.",
        )
    if any(query.sort not in row.metrics for row in snapshot.breakdowns):
        raise AgentError("ranking_metric_unavailable", "This ranking metric is unavailable.")

    def ordering(row):
        value = row.metrics[query.sort].value
        number = Decimal(str(value)) if value is not None else Decimal(0)
        return value is None, number if query.direction == "asc" else -number, row.entity_id

    ordered = sorted(snapshot.breakdowns, key=ordering)
    chosen = ordered[query.offset : query.offset + query.limit]
    identities = {row.entity_id for row in chosen}
    snapshot.breakdowns = chosen
    snapshot.contracts = [c for c in snapshot.contracts if c.supplier_id in identities]
    snapshot.limit, snapshot.offset = query.limit, query.offset
    snapshot.limitations.append(
        f"Agent presentation orders the existing Stage 2 {query.sort} metric across the "
        f"complete scoped supplier population ({snapshot.total_segments}); unavailable values "
        "are last. No new score or financial amount was calculated."
    )
    return snapshot
