from app.analytics.common import (
    one,
    optional,
    paged,
    report,
    rows,
    segments,
    trends,
    validate_query,
)
from app.analytics.facts import INCIDENT_CTES, TASK_CTES

ALLOWED = {"department_id", "incident_category", "supplier_id", "warehouse_id"}
SORTS = {"id": "entity_id", "open_incidents": "open_incidents", "new_incidents": "new_incidents"}
GROUPS = {
    "department": ("i.department_id", "d.name"),
    "warehouse": ("i.affected_warehouse_id", "coalesce(w.name,'Unlinked warehouse')"),
    "category": ("NULL::integer", "i.category"),
    "severity": ("NULL::integer", "i.severity"),
}


def ctes():
    return f"""
      {INCIDENT_CTES}, {TASK_CTES},
      corrective_counts AS (
        SELECT incident_id, count(*) AS corrective_tasks,
          count(*) FILTER (WHERE observed_status<>'completed') AS open_corrective_tasks,
          count(*) FILTER (WHERE observed_status IS NULL) AS unknown_status
        FROM task_facts GROUP BY incident_id
      ),
      incident_scope AS (
        SELECT i.*, coalesce(t.corrective_tasks,0) AS corrective_tasks,
          coalesce(t.open_corrective_tasks,0) AS open_corrective_tasks,
          coalesce(t.unknown_status,0) AS unknown_corrective_status
        FROM incident_facts i LEFT JOIN corrective_counts t ON t.incident_id=i.id
        WHERE {optional("i.department_id", "department_id")}
          AND {optional("i.category", "incident_category", "text")}
          AND {optional("i.supplier_id", "supplier_id")}
          AND {optional("i.affected_warehouse_id", "warehouse_id")}
      )
    """


SUMS = """
 count(*) AS total_incidents,
 count(*) FILTER (WHERE i.created_at>=:begin AND i.created_at<:finish) AS new_incidents,
 count(*) FILTER (WHERE i.closed_at IS NULL OR i.closed_at>=:cutoff) AS open_incidents,
 count(*) FILTER (WHERE i.closed_at<:cutoff) AS resolved_incidents,
 count(*) FILTER (WHERE i.closed_at>=:begin AND i.closed_at<:finish) AS resolved_in_period,
 CASE WHEN CAST(:as_of AS date)=DATE '2026-09-30' THEN
   count(*) FILTER (WHERE i.status='escalated' AND (i.closed_at IS NULL OR i.closed_at>=:cutoff))
   ELSE NULL END AS escalated_incidents,
 count(*) FILTER (WHERE i.severity='critical' AND (i.closed_at IS NULL OR
 i.closed_at>=:cutoff)) AS critical_open_incidents,
 count(*) FILTER (WHERE i.severity='high' AND (i.closed_at IS NULL OR i.closed_at>=:cutoff)) AS
 high_open_incidents,
 avg(CAST(:as_of AS date)-(i.created_at AT TIME ZONE 'UTC')::date)
   FILTER (WHERE i.closed_at IS NULL OR i.closed_at>=:cutoff) AS average_open_age,
 avg(extract(epoch FROM (i.closed_at-i.created_at))/86400)
   FILTER (WHERE i.closed_at<:cutoff) AS average_resolution_days,
 coalesce(sum(i.corrective_tasks),0) AS corrective_tasks,
 coalesce(sum(i.open_corrective_tasks),0) AS open_corrective_tasks,
 coalesce(sum(i.unknown_corrective_status),0) AS unknown_corrective_status
"""


def aggregate_sql(group=None):
    fields, suffix = "", ""
    if group:
        identifier, label = GROUPS[group]
        fields = f"{identifier} AS entity_id, {label} AS label,"
        suffix = f"GROUP BY {identifier},{label}"
    return f"""WITH {ctes()} SELECT {fields} {SUMS} FROM incident_scope i
      JOIN departments d ON d.id=i.department_id LEFT JOIN warehouses w ON
      w.id=i.affected_warehouse_id
      {suffix}"""


def compute(db, q):
    return one(db, aggregate_sql(), q)


def monthly(db, q):
    sql = f"""
      WITH {ctes()}, months AS (
        SELECT m::date AS month, greatest(m::date,CAST(:start AS date)) AS start_on,
          least((m+interval '1 month')::date,CAST(:end AS date)+1) AS end_exclusive
        FROM generate_series(date_trunc('month',CAST(:start AS date)),
                             date_trunc('month',CAST(:end AS date)),interval '1 month') m
      )
      SELECT month,
        count(i.id) FILTER (WHERE i.created_at>=x.start_on AND i.created_at<x.end_exclusive) AS
        new_incidents,
        count(i.id) FILTER (WHERE i.closed_at>=x.start_on AND i.closed_at<x.end_exclusive) AS
        resolved_in_period
      FROM months x LEFT JOIN incident_scope i ON true GROUP BY month ORDER BY month
    """
    return trends("incidents", q, rows(db, sql, q))


def get_incidents(db, q):
    validate_query(q, ALLOWED, GROUPS, SORTS)
    raw = compute(db, q)
    previous = compute(db, q.previous()) if q.include_comparison and q.previous() else None
    group = q.group_by or "category"
    grouped, total = paged(db, aggregate_sql(group), q, SORTS)
    return report(
        "incidents",
        q,
        raw,
        previous,
        segments("incidents", group, grouped),
        monthly(db, q) if q.include_trends else [],
        total,
        limitations=[
            (
                "Historical open/resolved state follows timestamps. Earlier operational "
                "escalation/investigation states are unavailable."
            ),
            "Recorded severity and responsible department have no revision history.",
        ],
    )
