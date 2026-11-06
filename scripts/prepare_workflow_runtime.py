"""Trusted maintenance only: scoped non-owner workflow login and non-login service roles."""

import re

from app.knowledge.schema import metadata as knowledge_metadata
from app.models import Base
from app.workflow import schema as s
from app.workflow.common import DB_ROLES
from psycopg import sql
from sqlalchemy import text


def prepare_runtime(db, login, password):
    name = db.scalar(text("SELECT current_database()"))
    if name != "opspilot" and not name.startswith("opspilot_test_"):
        raise ValueError("Workflow maintenance is restricted to the OpsPilot database.")
    if not re.fullmatch(r"opspilot_wf_[a-z0-9_]{3,45}", login):
        raise ValueError("Unexpected workflow login name")
    db.execute(text("SELECT pg_advisory_xact_lock(741902515)"))
    connection = db.connection().connection.driver_connection

    def command(template, *identifiers):
        connection.execute(sql.SQL(template).format(*(sql.Identifier(x) for x in identifiers)))

    for role in DB_ROLES.values():
        row = (
            db.execute(
                text(
                    "SELECT rolsuper,rolcreatedb,rolcreaterole,rolcanlogin,rolbypassrls "
                    "FROM pg_roles WHERE rolname=:role"
                ),
                {"role": role},
            )
            .mappings()
            .first()
        )
        if row is None:
            command(
                "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS",
                role,
            )
        elif any(row.values()):
            raise ValueError("Existing workflow service role has unexpected privileges")
        command("GRANT USAGE ON SCHEMA public TO {}", role)
    existing = (
        db.execute(
            text(
                "SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls "
                "FROM pg_roles WHERE rolname=:name"
            ),
            {"name": login},
        )
        .mappings()
        .first()
    )
    if existing is None:
        # Native SQL composition prevents credential interpolation and SQL error query printing.
        connection.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOINHERIT NOBYPASSRLS"
            ).format(sql.Identifier(login), sql.Literal(password))
        )
    elif any(existing.values()):
        raise ValueError("Existing runtime login has unexpected privileges")
    command("GRANT CONNECT ON DATABASE {} TO {}", name, login)
    for role in [*DB_ROLES.values(), "opspilot_agent_reader"]:
        command("GRANT {} TO {} WITH INHERIT FALSE, SET TRUE", role, login)

    workflow_tables = [t.name for t in s.metadata.tables.values() if t.name.startswith("workflow_")]
    business_tables = [
        t.name for t in [*Base.metadata.sorted_tables, *knowledge_metadata.sorted_tables]
    ]
    for role in DB_ROLES.values():
        for name in s.metadata.tables:
            command("REVOKE ALL PRIVILEGES ON TABLE {} FROM {}", name, role)
        for name in business_tables:
            command("REVOKE ALL PRIVILEGES ON TABLE {} FROM {}", name, role)
            command("GRANT SELECT ON TABLE {} TO {}", name, role)
    for name in s.metadata.tables:
        command("REVOKE ALL PRIVILEGES ON TABLE {} FROM PUBLIC", name)

    for role in DB_ROLES.values():
        command("GRANT INSERT ON TABLE workflow_audit_events TO {}", role)
        command(
            "GRANT SELECT (id,username,active,is_human,authz_version,employee_id,created_at) "
            "ON auth_principals TO {}",
            role,
        )
        command(
            "GRANT SELECT (id,principal_id,authz_version,expires_at,revoked_at) "
            "ON auth_sessions TO {}",
            role,
        )
        command("GRANT SELECT ON auth_role_assignments,auth_roles TO {}", role)
    for role in [DB_ROLES[k] for k in ("read", "review", "execute", "admin")]:
        for name in workflow_tables:
            command("GRANT SELECT ON TABLE {} TO {}", name, role)
    command(
        "GRANT SELECT ON auth_principals,auth_sessions,auth_login_buckets TO {}", DB_ROLES["auth"]
    )
    command("GRANT INSERT ON auth_sessions,auth_login_buckets TO {}", DB_ROLES["auth"])
    command("GRANT UPDATE (revoked_at) ON auth_sessions TO {}", DB_ROLES["auth"])
    command("GRANT UPDATE ON auth_login_buckets TO {}", DB_ROLES["auth"])
    command(
        "GRANT INSERT ON workflow_subjects,workflow_evidence,workflow_proposals,"
        "workflow_approvals,workflow_idempotency_records TO {}",
        DB_ROLES["review"],
    )
    for role in (DB_ROLES["review"], DB_ROLES["execute"]):
        command("GRANT UPDATE (status,updated_at) ON workflow_proposals TO {}", role)
    command(
        "GRANT INSERT ON workflow_executions,workflow_tasks,workflow_escalations,"
        "workflow_task_notes,workflow_task_assignments,workflow_idempotency_records TO {}",
        DB_ROLES["execute"],
    )
    command(
        "GRANT UPDATE ON workflow_tasks,workflow_escalations,workflow_executions TO {}",
        DB_ROLES["execute"],
    )
    command("GRANT INSERT,UPDATE ON auth_role_assignments TO {}", DB_ROLES["admin"])
    command("GRANT UPDATE (authz_version,active) ON auth_principals TO {}", DB_ROLES["admin"])
    command("GRANT INSERT ON workflow_policies TO {}", DB_ROLES["admin"])
    command("GRANT UPDATE ON workflow_policy_control TO {}", DB_ROLES["admin"])
    for name in ("workflow_audit_events", "workflow_policies"):
        column = "sequence" if name == "workflow_audit_events" else "id"
        sequence = db.scalar(
            text("SELECT pg_get_serial_sequence(:table,:column)"), {"table": name, "column": column}
        )
        for role in DB_ROLES.values():
            connection.execute(
                sql.SQL("GRANT USAGE,SELECT ON SEQUENCE {} TO {}").format(
                    sql.Identifier(*sequence.split(".")), sql.Identifier(role)
                )
            )
