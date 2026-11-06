"""Stage 5 metadata is separate from the immutable seeded business schema."""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.models import Base

metadata = sa.MetaData(naming_convention=Base.metadata.naming_convention)


def uid(name="id", *, primary=False, target=None, nullable=False):
    args = [sa.ForeignKey(target)] if target else []
    return sa.Column(
        name,
        sa.Uuid(),
        *args,
        primary_key=primary,
        nullable=nullable,
        default=uuid.uuid4 if primary else None,
    )


def stamp(name="created_at", *, nullable=False, default=True):
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=sa.func.now() if default else None,
    )


def business_fk(name, table, nullable=True):
    return sa.Column(
        name, sa.Integer(), sa.ForeignKey(Base.metadata.tables[table].c.id), nullable=nullable
    )


def table(name, *columns):
    return sa.Table(name, metadata, *columns)


principals = table(
    "auth_principals",
    uid(primary=True),
    sa.Column("username", sa.String(80), unique=True, nullable=False),
    sa.Column("password_hash", sa.Text(), nullable=False),
    sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column("is_human", sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column("authz_version", sa.Integer(), nullable=False, server_default="1"),
    business_fk("employee_id", "employees"),
    stamp(),
    sa.CheckConstraint("authz_version>0", name="positive_version"),
)
roles = table(
    "auth_roles",
    sa.Column("code", sa.String(40), primary_key=True),
    sa.Column("description", sa.Text(), nullable=False),
)
assignments = table(
    "auth_role_assignments",
    uid(primary=True),
    uid("principal_id", target="auth_principals.id"),
    sa.Column("role_code", sa.String(40), sa.ForeignKey("auth_roles.code"), nullable=False),
    business_fk("department_id", "departments"),
    sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    stamp(),
    sa.UniqueConstraint(
        "principal_id", "role_code", "department_id", postgresql_nulls_not_distinct=True
    ),
)
sessions = table(
    "auth_sessions",
    uid(primary=True),
    uid("principal_id", target="auth_principals.id"),
    sa.Column("token_digest", sa.String(64), unique=True, nullable=False),
    sa.Column("authz_version", sa.Integer(), nullable=False),
    stamp(),
    stamp("expires_at", default=False),
    stamp("revoked_at", default=False, nullable=True),
    sa.CheckConstraint("expires_at>created_at", name="expiry"),
)
login_buckets = table(
    "auth_login_buckets",
    sa.Column("key", sa.String(64), primary_key=True),
    sa.Column("failures", sa.Integer(), nullable=False),
    stamp("window_start"),
    sa.CheckConstraint("failures>=0", name="nonnegative_failures"),
)

policies = table(
    "workflow_policies",
    sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
    sa.Column("max_validity_hours", sa.Integer(), nullable=False),
    sa.Column("approval_validity_minutes", sa.Integer(), nullable=False),
    uid("created_by", target="auth_principals.id", nullable=True),
    stamp(),
    sa.CheckConstraint("max_validity_hours BETWEEN 1 AND 168", name="validity"),
    sa.CheckConstraint("approval_validity_minutes BETWEEN 5 AND 1440", name="approval_validity"),
)
policy_control = table(
    "workflow_policy_control",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("policy_id", sa.Integer(), sa.ForeignKey("workflow_policies.id"), nullable=False),
    sa.CheckConstraint("id=1", name="singleton"),
)

SUBJECT_TABLES = {
    "supplier": "suppliers",
    "purchase_order": "purchase_orders",
    "sales_order": "sales_orders",
    "warehouse": "warehouses",
    "product": "products",
    "incident": "incidents",
    "department": "departments",
}
subjects = table(
    "workflow_subjects",
    uid(primary=True),
    sa.Column("kind", sa.String(30), nullable=False),
    *(business_fk(kind + "_id", target) for kind, target in SUBJECT_TABLES.items()),
    sa.Column(
        "entity_id",
        sa.Integer(),
        sa.Computed(
            "coalesce(" + ",".join(k + "_id" for k in SUBJECT_TABLES) + ")", persisted=True
        ),
    ),
    sa.CheckConstraint(
        "num_nonnulls("
        + ",".join(k + "_id" for k in SUBJECT_TABLES)
        + ")=1 AND ("
        + " OR ".join(f"(kind='{k}' AND {k}_id IS NOT NULL)" for k in SUBJECT_TABLES)
        + ")",
        name="typed_foreign_key",
    ),
    sa.UniqueConstraint("kind", "entity_id"),
)
evidence = table(
    "workflow_evidence",
    uid(primary=True),
    uid("created_by", target="auth_principals.id"),
    uid("subject_id", target="workflow_subjects.id"),
    business_fk("department_id", "departments", False),
    sa.Column("payload", JSONB(), nullable=False),
    sa.Column("digest", sa.String(64), nullable=False),
    stamp(),
    stamp("expires_at", default=False),
    sa.CheckConstraint("expires_at>created_at", name="expiry"),
)
proposals = table(
    "workflow_proposals",
    uid(primary=True),
    uid("proposer_id", target="auth_principals.id"),
    business_fk("department_id", "departments", False),
    uid("subject_id", target="workflow_subjects.id"),
    uid("evidence_id", target="workflow_evidence.id", nullable=True),
    uid("previous_id", target="workflow_proposals.id", nullable=True),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("action_type", sa.String(50), nullable=False),
    sa.Column("source_type", sa.String(40), nullable=False),
    sa.Column("material", JSONB(), nullable=False),
    sa.Column("digest", sa.String(64), nullable=False),
    sa.Column("status", sa.String(30), nullable=False),
    stamp(),
    stamp("updated_at"),
    stamp("expires_at", default=False),
    sa.CheckConstraint("version>0", name="positive_version"),
    sa.CheckConstraint("expires_at>created_at", name="expiry"),
    sa.CheckConstraint(
        "status IN ('DRAFT','PENDING_REVIEW','APPROVED','REJECTED','CANCELLED',"
        "'EXPIRED','EXECUTING','COMPLETED','FAILED')",
        name="status",
    ),
    sa.CheckConstraint(
        "source_type IN ('HUMAN','DETERMINISTIC_RECOMMENDATION','AI_DRAFT')", name="source"
    ),
)
approvals = table(
    "workflow_approvals",
    uid(primary=True),
    uid("proposal_id", target="workflow_proposals.id"),
    uid("actor_id", target="auth_principals.id"),
    sa.Column("proposal_version", sa.Integer(), nullable=False),
    sa.Column("digest", sa.String(64), nullable=False),
    sa.Column("decision", sa.String(20), nullable=False),
    sa.Column("authz_version", sa.Integer(), nullable=False),
    sa.Column("reason", sa.String(1000), nullable=True),
    stamp(),
    stamp("valid_until", default=False),
    sa.UniqueConstraint("proposal_id", "actor_id", "decision"),
    sa.CheckConstraint("decision IN ('APPROVE','REJECT','REVOKE')", name="decision"),
)
executions = table(
    "workflow_executions",
    uid(primary=True),
    uid("proposal_id", target="workflow_proposals.id"),
    uid("actor_id", target="auth_principals.id"),
    uid("approver_id", target="auth_principals.id"),
    sa.Column("status", sa.String(20), nullable=False),
    sa.Column("result", JSONB(), nullable=False),
    sa.Column("error_code", sa.String(80), nullable=True),
    stamp(),
    stamp("finished_at", nullable=True, default=False),
    sa.UniqueConstraint("proposal_id"),
    sa.CheckConstraint("status IN ('EXECUTING','COMPLETED','FAILED')", name="status"),
)
tasks = table(
    "workflow_tasks",
    uid(primary=True),
    sa.Column("title", sa.String(200), nullable=False),
    sa.Column("description", sa.String(4000), nullable=False),
    sa.Column("status", sa.String(20), nullable=False),
    sa.Column("priority", sa.String(20), nullable=False),
    business_fk("department_id", "departments", False),
    business_fk("employee_id", "employees"),
    uid("subject_id", target="workflow_subjects.id"),
    uid("created_by", target="auth_principals.id"),
    uid("proposal_id", target="workflow_proposals.id"),
    uid("execution_id", target="workflow_executions.id"),
    sa.Column("version", sa.Integer(), nullable=False),
    stamp(),
    stamp("updated_at"),
    stamp("due_at", default=False),
    stamp("completed_at", default=False, nullable=True),
    sa.UniqueConstraint("proposal_id"),
    sa.UniqueConstraint("execution_id"),
    sa.CheckConstraint("version>0", name="positive_version"),
    sa.CheckConstraint("due_at>=created_at", name="due"),
    sa.CheckConstraint(
        "status IN ('open','active','blocked','completed','cancelled')", name="status"
    ),
    sa.CheckConstraint("priority IN ('low','normal','high','urgent')", name="priority"),
    sa.CheckConstraint("(status='completed')=(completed_at IS NOT NULL)", name="completion"),
)
task_assignments = table(
    "workflow_task_assignments",
    uid(primary=True),
    uid("task_id", target="workflow_tasks.id"),
    business_fk("department_id", "departments", False),
    business_fk("employee_id", "employees"),
    uid("actor_id", target="auth_principals.id"),
    uid("execution_id", target="workflow_executions.id"),
    stamp(),
    sa.UniqueConstraint("execution_id"),
)
notes = table(
    "workflow_task_notes",
    uid(primary=True),
    uid("task_id", target="workflow_tasks.id"),
    uid("actor_id", target="auth_principals.id"),
    uid("execution_id", target="workflow_executions.id"),
    sa.Column("text", sa.String(4000), nullable=False),
    stamp(),
    sa.UniqueConstraint("execution_id"),
)
escalations = table(
    "workflow_escalations",
    uid(primary=True),
    sa.Column("title", sa.String(200), nullable=False),
    sa.Column("reason", sa.String(4000), nullable=False),
    sa.Column("status", sa.String(20), nullable=False),
    sa.Column("priority", sa.String(20), nullable=False),
    business_fk("department_id", "departments", False),
    uid("subject_id", target="workflow_subjects.id"),
    uid("task_id", target="workflow_tasks.id", nullable=True),
    uid("created_by", target="auth_principals.id"),
    uid("proposal_id", target="workflow_proposals.id"),
    uid("execution_id", target="workflow_executions.id"),
    sa.Column("version", sa.Integer(), nullable=False),
    stamp(),
    stamp("updated_at"),
    stamp("due_at", default=False),
    stamp("closed_at", default=False, nullable=True),
    sa.Column("resolution", sa.String(4000), nullable=True),
    sa.UniqueConstraint("proposal_id"),
    sa.UniqueConstraint("execution_id"),
    sa.CheckConstraint("version>0", name="positive_version"),
    sa.CheckConstraint("due_at>=created_at", name="due"),
    sa.CheckConstraint("status IN ('open','closed')", name="status"),
    sa.CheckConstraint("priority IN ('low','normal','high','urgent')", name="priority"),
    sa.CheckConstraint(
        "(status='closed')=(closed_at IS NOT NULL AND resolution IS NOT NULL)", name="closure"
    ),
)
audit = table(
    "workflow_audit_events",
    uid(primary=True),
    sa.Column("sequence", sa.BigInteger(), sa.Identity(), unique=True, nullable=False),
    uid("actor_id", target="auth_principals.id", nullable=True),
    business_fk("department_id", "departments"),
    sa.Column("action", sa.String(80), nullable=False),
    sa.Column("object_type", sa.String(40), nullable=False),
    uid("object_id", nullable=True),
    uid("proposal_id", target="workflow_proposals.id", nullable=True),
    uid("execution_id", target="workflow_executions.id", nullable=True),
    sa.Column("before_state", JSONB(), nullable=False),
    sa.Column("after_state", JSONB(), nullable=False),
    sa.Column("reason", sa.String(1000), nullable=True),
    sa.Column("result", sa.String(20), nullable=False),
    uid("request_id"),
    stamp(),
    sa.CheckConstraint("result IN ('SUCCESS','DENIED','FAILED')", name="result"),
)
idempotency = table(
    "workflow_idempotency_records",
    uid("key", primary=True),
    uid("actor_id", target="auth_principals.id"),
    sa.Column("operation", sa.String(80), nullable=False),
    sa.Column("request_digest", sa.String(64), nullable=False),
    sa.Column("response", JSONB(), nullable=False),
    sa.Column("http_status", sa.Integer(), nullable=False),
    stamp(),
    sa.CheckConstraint("http_status BETWEEN 200 AND 599", name="http_status"),
)

for obj, columns in (
    (assignments, ["principal_id"]),
    (sessions, ["principal_id", "expires_at"]),
    (evidence, ["department_id", "created_at"]),
    (proposals, ["department_id", "status", "created_at"]),
    (approvals, ["proposal_id"]),
    (tasks, ["department_id", "status", "due_at"]),
    (notes, ["task_id"]),
    (task_assignments, ["task_id"]),
    (escalations, ["department_id", "status", "due_at"]),
    (audit, ["department_id", "sequence"]),
    (audit, ["proposal_id"]),
    (tasks, ["subject_id"]),
    (escalations, ["subject_id"]),
):
    sa.Index("ix_" + obj.name + "_" + "_".join(columns), *(obj.c[n] for n in columns))
