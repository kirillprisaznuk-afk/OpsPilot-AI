"""Bounded investigations following real foreign keys, with explicitly labelled evidence."""

from app.analytics import (
    finance,
    incidents,
    inventory,
    procurement,
    warehouses,
    workforce,
)
from app.analytics.common import AnalyticsInputError, metrics, one, rows, validate_query, window
from app.analytics.contracts import Investigation
from app.analytics.facts import EXPENSE_FACTS, INCIDENT_CTES, INVOICE_CTES, TASK_CTES
from app.analytics.order_queries import order_aggregates, order_ctes

ENTITIES = {
    "supplier": "suppliers",
    "purchase_order": "purchase_orders",
    "sales_order": "sales_orders",
    "shortage": "shortages",
    "warehouse": "warehouses",
    "incident": "incidents",
    "invoice": "supplier_invoices",
    "department": "departments",
    "task": "tasks",
    "product": "products",
}


def scope_ctes():
    return f"""
      {INCIDENT_CTES}, {TASK_CTES},
      root_incidents AS (
        SELECT i.* FROM incident_facts i WHERE
          (:root_type='incident' AND i.id=:root_id) OR
          (:root_type='department' AND (i.department_id=:root_id OR i.id IN
             (SELECT incident_id FROM task_facts WHERE department_id=:root_id))) OR
          (:root_type='warehouse' AND i.affected_warehouse_id=:root_id) OR
          (:root_type='invoice' AND i.invoice_id=:root_id) OR
          (:root_type='task' AND i.id IN (SELECT incident_id FROM task_facts WHERE id=:root_id))
      ),
      scope_po AS (
        SELECT po.* FROM purchase_orders po WHERE po.ordered_on<=:as_of AND (
          (:root_type='purchase_order' AND po.id=:root_id) OR
          (:root_type='supplier' AND po.supplier_id=:root_id) OR
          (:root_type='warehouse' AND po.warehouse_id=:root_id) OR
          (:root_type='product' AND EXISTS (SELECT 1 FROM purchase_order_lines l
             WHERE l.purchase_order_id=po.id AND l.product_id=:root_id)) OR
          (:root_type='invoice' AND po.id IN (SELECT purchase_order_id FROM supplier_invoices
             WHERE id=:root_id AND issued_on<=:as_of)) OR
          po.id IN (SELECT affected_purchase_order_id FROM root_incidents) OR
          po.id IN (SELECT pl.purchase_order_id FROM shortages sh
             JOIN sales_order_lines sl ON sl.id=sh.sales_order_line_id
             JOIN purchase_order_lines pl ON pl.id=sh.expected_purchase_line_id
             WHERE sh.detected_on<=:as_of AND ((:root_type='shortage' AND sh.id=:root_id)
                OR (:root_type='sales_order' AND sl.sales_order_id=:root_id)))
        )
      ),
      scope_shortages AS (
        SELECT sh.* FROM shortages sh JOIN sales_order_lines sl ON sl.id=sh.sales_order_line_id
        LEFT JOIN purchase_order_lines pl ON pl.id=sh.expected_purchase_line_id
        WHERE sh.detected_on<=:as_of AND (
          pl.purchase_order_id IN (SELECT id FROM scope_po) OR
          (:root_type='shortage' AND sh.id=:root_id) OR
          (:root_type='sales_order' AND sl.sales_order_id=:root_id) OR
          sh.id IN (SELECT shortage_id FROM root_incidents)
        )
      ),
      scope_so AS (
        SELECT so.* FROM sales_orders so WHERE so.ordered_on<=:as_of AND (
          (:root_type='sales_order' AND so.id=:root_id) OR
          (:root_type='warehouse' AND so.warehouse_id=:root_id) OR
          (:root_type='product' AND EXISTS (SELECT 1 FROM sales_order_lines sl
             WHERE sl.sales_order_id=so.id AND sl.product_id=:root_id)) OR
          so.id IN (SELECT affected_sales_order_id FROM root_incidents) OR
          so.id IN (SELECT sl.sales_order_id FROM sales_order_lines sl
             JOIN scope_shortages sh ON sh.sales_order_line_id=sl.id)
        )
      ),
      scope_incidents AS (
        SELECT i.* FROM incident_facts i WHERE i.id IN (SELECT id FROM root_incidents)
          OR i.purchase_order_id IN (SELECT id FROM scope_po)
          OR i.shortage_id IN (SELECT id FROM scope_shortages)
          OR i.sales_order_id IN (SELECT id FROM scope_so)
          OR i.invoice_id IN (SELECT id FROM supplier_invoices
                             WHERE purchase_order_id IN (SELECT id FROM scope_po) AND
                             issued_on<=:as_of)
      ),
      scope_tasks AS (
        SELECT t.* FROM task_facts t WHERE t.incident_id IN (SELECT id FROM scope_incidents)
          OR (:root_type='task' AND t.id=:root_id)
          OR (:root_type='department' AND t.department_id=:root_id)
          OR (:root_type='supplier' AND t.supplier_id=:root_id)
      )
    """


def edge(
    left_type,
    left_id,
    right_type,
    right_id,
    time,
    relation,
    source,
    source_id,
    from_sql,
    quantity="NULL::integer",
    amount="NULL::numeric",
    evidence="explicit_link",
):
    return f"""SELECT '{left_type}'::text AS entity_type, {left_id} AS entity_id,
      '{right_type}'::text AS related_entity_type, {right_id} AS related_entity_id,
      {time} AS event_time, '{relation}'::text AS relationship_type,
      '{evidence}'::text AS evidence_class, {quantity} AS quantity, {amount} AS amount_gbp,
      '{source}:'||{source_id}::text AS source_reference FROM {from_sql}"""


def day(column):
    return f"({column}::timestamp AT TIME ZONE 'UTC')"


def evidence_sql():
    fragments = [
        edge(
            "supplier",
            "po.supplier_id",
            "purchase_order",
            "po.id",
            day("po.ordered_on"),
            "commercial_counterparty",
            "purchase_orders",
            "po.id",
            "scope_po po",
        ),
        edge(
            "warehouse",
            "po.warehouse_id",
            "purchase_order",
            "po.id",
            day("po.ordered_on"),
            "receiving_location",
            "purchase_orders",
            "po.id",
            "scope_po po",
        ),
        edge(
            "purchase_order",
            "po.id",
            "contract",
            "po.contract_id",
            day("po.ordered_on"),
            "governed_by",
            "purchase_orders",
            "po.id",
            "scope_po po",
        ),
        edge(
            "supplier",
            "c.supplier_id",
            "contract",
            "c.id",
            "c.created_at",
            "agreement",
            "supplier_contracts",
            "c.id",
            "supplier_contracts c WHERE c.created_at<:cutoff "
            "AND c.effective_date<=:as_of AND ((:root_type='supplier' AND c.supplier_id=:root_id) "
            "OR c.id IN (SELECT contract_id FROM scope_po))",
        ),
        edge(
            "contract",
            "d.contract_id",
            "document_version",
            "v.id",
            "v.created_at",
            "documented_terms",
            "document_versions",
            "v.id",
            "documents d JOIN document_versions v ON v.document_id=d.id "
            "WHERE v.created_at<:cutoff AND v.effective_on<=:as_of AND "
            "(d.contract_id IN (SELECT contract_id FROM scope_po) OR "
            "(:root_type='supplier' AND d.contract_id IN "
            "(SELECT id FROM supplier_contracts WHERE supplier_id=:root_id)))",
        ),
        edge(
            "purchase_order",
            "l.purchase_order_id",
            "purchase_line",
            "l.id",
            "l.created_at",
            "contains_line",
            "purchase_order_lines",
            "l.id",
            "purchase_order_lines l WHERE l.purchase_order_id IN (SELECT id FROM scope_po) "
            "AND l.created_at<:cutoff",
            "l.quantity",
            "l.quantity*l.unit_price",
        ),
        edge(
            "purchase_line",
            "r.purchase_order_line_id",
            "receipt",
            "r.id",
            day("r.received_on"),
            "physically_received",
            "goods_receipts",
            "r.id",
            "goods_receipts r JOIN purchase_order_lines l ON l.id=r.purchase_order_line_id "
            "WHERE l.purchase_order_id IN (SELECT id FROM scope_po) AND r.received_on<=:as_of",
            "r.quantity",
        ),
        edge(
            "receipt",
            "m.receipt_id",
            "stock_movement",
            "m.id",
            day("m.occurred_on"),
            "posts_stock",
            "stock_movements",
            "m.id",
            "stock_movements m JOIN goods_receipts r ON r.id=m.receipt_id "
            "JOIN purchase_order_lines l ON l.id=r.purchase_order_line_id "
            "WHERE l.purchase_order_id IN (SELECT id FROM scope_po) AND m.occurred_on<=:as_of",
            "m.quantity",
        ),
        edge(
            "purchase_line",
            "sh.expected_purchase_line_id",
            "shortage",
            "sh.id",
            day("sh.detected_on"),
            "expected_replenishment_association",
            "shortages",
            "sh.id",
            "scope_shortages sh WHERE sh.expected_purchase_line_id IS NOT NULL",
            "sh.quantity",
        ),
        edge(
            "sales_order",
            "sl.sales_order_id",
            "sales_line",
            "sl.id",
            "sl.created_at",
            "contains_customer_demand",
            "sales_order_lines",
            "sl.id",
            "sales_order_lines sl WHERE sl.sales_order_id IN (SELECT id FROM scope_so) "
            "AND sl.created_at<:cutoff",
            "sl.quantity",
            "sl.quantity*sl.unit_price",
        ),
        edge(
            "sales_line",
            "sh.sales_order_line_id",
            "shortage",
            "sh.id",
            day("sh.detected_on"),
            "recorded_shortage",
            "shortages",
            "sh.id",
            "scope_shortages sh",
            "sh.quantity",
        ),
        edge(
            "sales_line",
            "f.sales_order_line_id",
            "fulfilment",
            "f.id",
            day("f.fulfilled_on"),
            "dispatched_quantity",
            "fulfilments",
            "f.id",
            "fulfilments f JOIN sales_order_lines sl ON sl.id=f.sales_order_line_id "
            "WHERE sl.sales_order_id IN (SELECT id FROM scope_so) AND f.fulfilled_on<=:as_of",
            "f.quantity",
        ),
        edge(
            "fulfilment",
            "m.fulfilment_id",
            "stock_movement",
            "m.id",
            day("m.occurred_on"),
            "consumes_stock",
            "stock_movements",
            "m.id",
            "stock_movements m JOIN fulfilments f ON f.id=m.fulfilment_id "
            "JOIN sales_order_lines sl ON sl.id=f.sales_order_line_id "
            "WHERE sl.sales_order_id IN (SELECT id FROM scope_so) AND m.occurred_on<=:as_of",
            "m.quantity",
        ),
        edge(
            "warehouse",
            "so.warehouse_id",
            "sales_order",
            "so.id",
            day("so.ordered_on"),
            "dispatch_location",
            "sales_orders",
            "so.id",
            "scope_so so",
        ),
        edge(
            "purchase_order",
            "inv.purchase_order_id",
            "invoice",
            "inv.id",
            day("inv.issued_on"),
            "supplier_invoice",
            "supplier_invoices",
            "inv.id",
            "supplier_invoices inv WHERE inv.purchase_order_id IN (SELECT id FROM scope_po) "
            "AND inv.issued_on<=:as_of",
            amount="inv.amount",
        ),
        edge(
            "invoice",
            "p.invoice_id",
            "payment",
            "p.id",
            day("p.paid_on"),
            "cash_payment",
            "payments",
            "p.id",
            "payments p JOIN supplier_invoices inv ON inv.id=p.invoice_id "
            "WHERE inv.purchase_order_id IN (SELECT id FROM scope_po) AND p.paid_on<=:as_of",
            amount="p.amount",
        ),
        edge(
            "incident",
            "i.id",
            "task",
            "t.id",
            "t.created_at",
            "corrective_action",
            "tasks",
            "t.id",
            "scope_tasks t JOIN scope_incidents i ON i.id=t.incident_id",
        ),
        edge(
            "department",
            "t.department_id",
            "task",
            "t.id",
            "t.created_at",
            "recorded_assignment",
            "tasks",
            "t.id",
            "scope_tasks t",
        ),
        edge(
            "task",
            "t.id",
            "employee",
            "t.owner_id",
            "t.created_at",
            "recorded_owner",
            "tasks",
            "t.id",
            "scope_tasks t",
        ),
        edge(
            "task",
            "h.task_id",
            "task_history",
            "h.id",
            "h.created_at",
            "status_" + "'||h.status||'",
            "task_status_history",
            "h.id",
            "task_status_history h WHERE "
            "h.task_id IN (SELECT id FROM scope_tasks) AND h.created_at<:cutoff",
        ),
        edge(
            "department",
            "i.department_id",
            "incident",
            "i.id",
            "i.created_at",
            "responsible_department",
            "incidents",
            "i.id",
            "scope_incidents i",
        ),
        edge(
            "warehouse",
            "i.affected_warehouse_id",
            "incident",
            "i.id",
            "i.created_at",
            "affected_location_via_evidence",
            "incidents",
            "i.id",
            "scope_incidents i WHERE i.affected_warehouse_id IS NOT NULL",
        ),
        edge(
            "incident",
            "e.incident_id",
            "expense",
            "e.id",
            day("e.incurred_on"),
            "explicit_recorded_cost",
            "operational_expenses",
            "e.id",
            "operational_expenses e WHERE e.incurred_on<=:as_of "
            "AND e.incident_id IN (SELECT id FROM scope_incidents)",
            amount="e.amount",
        ),
        edge(
            "warehouse",
            "e.warehouse_id",
            "expense",
            "e.id",
            day("e.incurred_on"),
            "recorded_location_cost",
            "operational_expenses",
            "e.id",
            "operational_expenses e WHERE :root_type='warehouse' AND e.warehouse_id=:root_id "
            "AND e.incurred_on<=:as_of",
            amount="e.amount",
        ),
        edge(
            "warehouse",
            "m.warehouse_id",
            "stock_movement",
            "m.id",
            day("m.occurred_on"),
            "physical_stock_event",
            "stock_movements",
            "m.id",
            "stock_movements m WHERE m.occurred_on<=:as_of AND "
            "((:root_type='warehouse' AND m.warehouse_id=:root_id) OR "
            "(:root_type='product' AND m.product_id=:root_id))",
            "m.quantity",
        ),
    ]
    for field, kind in [
        ("purchase_order_id", "purchase_order"),
        ("shortage_id", "shortage"),
        ("sales_order_id", "sales_order"),
        ("invoice_id", "invoice"),
    ]:
        fragments.append(
            edge(
                "incident",
                "i.id",
                kind,
                f"i.{field}",
                "i.created_at",
                "affected_entity",
                "incidents",
                "i.id",
                f"scope_incidents i WHERE i.{field} IS NOT NULL",
            )
        )
    # Stronger evidence is deliberately restricted to a sole recorded positive stock source.
    fragments.append(
        edge(
            "shortage",
            "sh.id",
            "fulfilment",
            "f.id",
            day("f.fulfilled_on"),
            "sole_recorded_late_replenishment",
            "goods_receipts",
            "r.id",
            """
        scope_shortages sh JOIN sales_order_lines sl ON sl.id=sh.sales_order_line_id
        JOIN scope_so so ON so.id=sl.sales_order_id
        JOIN purchase_order_lines pl ON pl.id=sh.expected_purchase_line_id AND
        pl.product_id=sl.product_id
        JOIN scope_po po ON po.id=pl.purchase_order_id AND po.warehouse_id=so.warehouse_id
        JOIN goods_receipts r ON r.purchase_order_line_id=pl.id
        JOIN fulfilments f ON f.sales_order_line_id=sl.id
        WHERE r.received_on<=:as_of AND f.fulfilled_on<=:as_of
          AND r.received_on>po.promised_on AND sh.detected_on<r.received_on
          AND f.fulfilled_on>=r.received_on AND f.fulfilled_on>so.promised_on
          AND NOT EXISTS (SELECT 1 FROM stock_movements m
            WHERE m.product_id=pl.product_id AND m.warehouse_id=po.warehouse_id
              AND m.quantity>0 AND m.occurred_on<=f.fulfilled_on
              AND m.receipt_id IS DISTINCT FROM r.id)
        """,
            quantity="f.quantity",
            evidence="simulated_causal_chain",
        )
    )
    return (
        f"WITH {scope_ctes()}, evidence AS ({' UNION ALL '.join(fragments)}) SELECT * FROM evidence"
    )


def root_metrics(db, kind, identifier, q):
    if kind == "supplier":
        return metrics(
            "procurement", procurement.compute(db, q.model_copy(update={"supplier_id": identifier}))
        )
    if kind == "warehouse":
        return warehouses.get_warehouses(
            db,
            q.model_copy(
                update={
                    "warehouse_id": identifier,
                    "include_trends": False,
                    "include_comparison": False,
                }
            ),
        ).metrics
    if kind == "product":
        return metrics(
            "inventory", inventory.compute(db, q.model_copy(update={"product_id": identifier}))
        )
    if kind == "department":
        return metrics(
            "workforce", workforce.compute(db, q.model_copy(update={"department_id": identifier}))
        )
    if kind in {"purchase_order", "sales_order"}:
        purchase = kind == "purchase_order"
        source = "purchase" if purchase else "sales"
        raw = one(
            db,
            f"WITH {order_ctes(source)} SELECT {order_aggregates(source)} "
            f"FROM {'po' if purchase else 'so'}_facts WHERE id=:root_id",
            q,
            root_id=identifier,
        )
        return metrics("procurement" if purchase else "fulfilment", raw)
    if kind == "invoice":
        return metrics(
            "finance",
            one(
                db,
                f"WITH {INVOICE_CTES} SELECT {finance.INVOICE_SUMS} "
                "FROM invoice_facts WHERE id=:root_id",
                q,
                root_id=identifier,
            ),
        )
    if kind == "incident":
        return metrics(
            "incidents",
            one(db, incidents.aggregate_sql() + " WHERE i.id=:root_id", q, root_id=identifier),
        )
    if kind == "task":
        return metrics(
            "workforce",
            one(
                db,
                f"WITH {workforce.ctes()} SELECT {workforce.SUMS} "
                "FROM workforce_facts WHERE id=:root_id",
                q,
                root_id=identifier,
            ),
        )
    raw = one(
        db,
        f"WITH {inventory.ctes()} SELECT {inventory.DEMAND_SUMS} "
        "FROM inventory_demand WHERE shortage_id=:root_id",
        q,
        root_id=identifier,
    )
    return metrics("inventory", raw)


def investigate(db, kind, identifier, q):
    validate_query(q, ())
    table = ENTITIES[kind]  # API Literal and internal whitelist, never caller SQL.
    found = one(
        db,
        f"SELECT count(*) AS n FROM {table} WHERE id=:root_id AND created_at<:cutoff",
        q,
        root_id=identifier,
    )
    if not found["n"]:
        return None
    evidence_kind = getattr(q, "evidence_kind", "all")
    open_tasks_only = getattr(q, "open_tasks_only", False)
    overdue_tasks_only = getattr(q, "overdue_tasks_only", False)
    if (open_tasks_only or overdue_tasks_only) and evidence_kind != "tasks":
        raise AnalyticsInputError("evidence_kind", "Task-state filters require evidence_kind=tasks")
    sql = selected_evidence_sql(kind, evidence_kind, open_tasks_only, overdue_tasks_only)
    extra = {"root_type": kind, "root_id": identifier}
    evidence = rows(
        db,
        f"SELECT e.*, count(*) OVER() AS total FROM ({sql}) e "
        "ORDER BY event_time,entity_type,entity_id,related_entity_type,"
        "related_entity_id,relationship_type "
        "LIMIT :limit OFFSET :offset",
        q,
        **extra,
    )
    total = (
        evidence[0]["total"]
        if evidence
        else one(db, f"SELECT count(*) AS n FROM ({sql}) e", q, **extra)["n"]
    )
    return Investigation(
        entity_type=kind,
        entity_id=identifier,
        window=window(q),
        metrics=root_metrics(db, kind, identifier, q),
        evidence=evidence,
        total=total,
        limit=q.limit,
        offset=q.offset,
        limitations=[
            (
                "Evidence follows recorded keys across the entity's history through "
                "as_of, including events before start_date."
            ),
            (
                "Metrics retain their documented cohort/snapshot basis; order-root "
                "metrics describe that whole order."
            ),
            (
                "Associations are not sole causes. Simulated chains require a sole "
                "recorded positive replenishment source."
            ),
            (
                "Original assignment metadata has no reassignment history. Financial "
                "consequences without expense records remain unknown."
            ),
            "Open-only task evidence requires historically confirmed unfinished state; "
            "unknown history is not imputed.",
        ],
    )


def selected_evidence_sql(kind, evidence_kind, open_tasks_only=False, overdue_tasks_only=False):
    if evidence_kind == "tasks":
        filters = {
            "supplier": "coalesce(t.supplier_id,i.supplier_id)=:root_id",
            "warehouse": "i.affected_warehouse_id=:root_id",
            "department": "t.department_id=:root_id",
            "incident": "t.incident_id=:root_id",
            "invoice": "i.invoice_id=:root_id",
            "shortage": "i.shortage_id=:root_id",
        }
        condition = filters.get(kind, "true")
        unfinished = (
            "AND t.observed_status IN ('open','active','escalated')"
            if open_tasks_only or overdue_tasks_only
            else ""
        )
        if overdue_tasks_only:
            unfinished += " AND t.due_at<:cutoff"
        return f"""
          WITH {scope_ctes()}
          SELECT 'task'::text AS entity_type,t.id AS entity_id,
            'employee'::text AS related_entity_type,t.owner_id AS related_entity_id,
            t.created_at AS event_time,'recorded_owner'::text AS relationship_type,
            'explicit_link'::text AS evidence_class,NULL::integer AS quantity,
            NULL::numeric AS amount_gbp,'tasks:'||t.id AS source_reference,
            t.observed_status,t.title,t.due_at,t.priority
          FROM scope_tasks t LEFT JOIN incident_facts i ON i.id=t.incident_id
          WHERE {condition} {unfinished}
        """
    if evidence_kind == "costs":
        condition = {
            "incident": "e.incident_id=:root_id",
            "supplier": "e.supplier_id=:root_id",
            "warehouse": "e.warehouse_id=:root_id",
        }.get(kind, "e.incident_id IN (SELECT id FROM scope_incidents)")
        return f"""
          WITH {scope_ctes()}, {EXPENSE_FACTS}
          SELECT 'expense'::text AS entity_type,e.id AS entity_id,
            CASE WHEN e.incident_id IS NULL THEN 'warehouse' ELSE 'incident'
              END AS related_entity_type,
            coalesce(e.incident_id,e.warehouse_id) AS related_entity_id,
            {day("e.incurred_on")} AS event_time,
            CASE WHEN e.incident_id IS NULL THEN 'recorded_location_cost'
              ELSE 'explicit_recorded_cost' END AS relationship_type,
            'explicit_link'::text AS evidence_class,NULL::integer AS quantity,
            e.amount AS amount_gbp,'operational_expenses:'||e.id AS source_reference,
            e.category AS cost_category,e.basis AS recorded_basis
          FROM expense_facts e WHERE {condition}
        """
    base = evidence_sql()
    if evidence_kind in {"receipts", "incidents"}:
        target = "receipt" if evidence_kind == "receipts" else "incident"
        narrow = ""
        if kind == "shortage" and target == "receipt":
            narrow = (
                "AND e.related_entity_id IN (SELECT r.id FROM goods_receipts r "
                "JOIN shortages sh ON sh.expected_purchase_line_id=r.purchase_order_line_id "
                "WHERE sh.id=:root_id)"
            )
        return (
            f"SELECT DISTINCT ON (related_entity_id) e.* FROM ({base}) e "
            f"WHERE related_entity_type='{target}' {narrow} "
            "ORDER BY related_entity_id,relationship_type,source_reference"
        )
    return base
