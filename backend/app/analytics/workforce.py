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

ALLOWED = {
    "department_id",
    "employee_id",
    "priority",
    "incident_category",
    "supplier_id",
    "warehouse_id",
}
SORTS = {"id": "entity_id", "overdue_tasks": "overdue_tasks", "total_tasks": "total_tasks"}
GROUPS = {
    "department": ("department_id", "department_name"),
    "employee": ("owner_id", "employee_name"),
    "priority": (None, "priority"),
    "incident_category": (None, "incident_category"),
}


def ctes():
    return f"""
      {TASK_CTES}, {INCIDENT_CTES},
      workforce_facts AS (
        SELECT t.*, d.name AS department_name, e.name AS employee_name,
               coalesce(i.category,'unlinked') AS incident_category
        FROM task_facts t JOIN departments d ON d.id=t.department_id
        JOIN employees e ON e.id=t.owner_id LEFT JOIN incident_facts i ON i.id=t.incident_id
        WHERE {optional("t.department_id", "department_id")} AND
        {optional("t.owner_id", "employee_id")}
          AND {optional("t.priority", "priority", "text")} AND
          {optional("i.category", "incident_category", "text")}
          AND {optional("coalesce(t.supplier_id,i.supplier_id)", "supplier_id")}
          AND {optional("i.affected_warehouse_id", "warehouse_id")}
      )
    """


SUMS = """
 count(*) AS total_tasks,
 count(*) FILTER (WHERE created_at>=:begin AND created_at<:finish) AS tasks_created,
 CASE WHEN count(*) FILTER (WHERE observed_status IS NULL)>0 THEN NULL ELSE
   count(*) FILTER (WHERE observed_status<>'completed') END AS open_tasks,
 count(*) FILTER (WHERE observed_completed_at IS NOT NULL) AS completed_tasks,
 count(*) FILTER (WHERE observed_completed_at>=:begin AND observed_completed_at<:finish) AS
 completed_in_period,
 CASE WHEN count(*) FILTER (WHERE observed_status IS NULL)>0 THEN NULL ELSE
   count(*) FILTER (WHERE observed_status<>'completed' AND due_at<:cutoff) END AS overdue_tasks,
 count(*) FILTER (WHERE observed_completed_at>due_at) AS completed_late,
 count(*) FILTER (WHERE observed_completed_at<=due_at) AS completed_on_time,
 count(*) FILTER (WHERE observed_status IS NULL) AS unknown_status_tasks,
 avg(CAST(:as_of AS date)-(created_at AT TIME ZONE 'UTC')::date)
   FILTER (WHERE observed_status<>'completed') AS average_open_age,
 avg(extract(epoch FROM (observed_completed_at-created_at))/86400)
   FILTER (WHERE observed_completed_at IS NOT NULL) AS average_completion_days
"""


def aggregate_sql(group=None):
    fields, suffix = "", ""
    if group:
        identifier, label = GROUPS[group]
        fields = f"{identifier or 'NULL::integer'} AS entity_id, {label} AS label,"
        suffix = f"GROUP BY {identifier + ',' if identifier else ''}{label}"
    return f"WITH {ctes()} SELECT {fields} {SUMS} FROM workforce_facts {suffix}"


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
        count(t.id) FILTER (WHERE t.created_at>=x.start_on AND t.created_at<x.end_exclusive) AS
        tasks_created,
        count(t.id) FILTER (WHERE t.observed_completed_at>=x.start_on AND
        t.observed_completed_at<x.end_exclusive) AS completed_in_period
      FROM months x LEFT JOIN workforce_facts t ON true GROUP BY month ORDER BY month
    """
    return trends("workforce", q, rows(db, sql, q))


def get_workforce(db, q):
    validate_query(q, ALLOWED, GROUPS, SORTS)
    raw = compute(db, q)
    previous = compute(db, q.previous()) if q.include_comparison and q.previous() else None
    group = q.group_by or "department"
    grouped, total = paged(db, aggregate_sql(group), q, SORTS)
    return report(
        "workforce",
        q,
        raw,
        previous,
        segments("workforce", group, grouped),
        monthly(db, q) if q.include_trends else [],
        total,
        limitations=[
            (
                "Assignment, department and priority revision histories are unavailable; "
                "dimensions use recorded assignments."
            ),
            "Task workload is not an employee productivity/value score.",
        ],
    )
