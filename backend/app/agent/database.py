"""Fixed, non-login SELECT-only role and read-only transaction for every tool."""

from contextlib import contextmanager

from app.agent.contracts import AgentError
from app.db.session import engine
from sqlalchemy import text
from sqlalchemy.orm import Session

ROLE = "opspilot_agent_reader"


@contextmanager
def agent_session(timeout_seconds=10, cancellation=None, bind=None):
    with Session(bind or engine()) as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        try:
            db.execute(text("SET LOCAL ROLE opspilot_agent_reader"))
            db.execute(
                text("SELECT set_config('statement_timeout',:timeout,true)"),
                {"timeout": str(max(1, int(timeout_seconds * 1000)))},
            )
            if cancellation:
                cancellation.connection = db.connection().connection.driver_connection
            yield db
        finally:
            if cancellation:
                cancellation.connection = None
            db.rollback()


def verify_reader(db):
    row = (
        db.execute(
            text(
                "SELECT rolname,rolsuper,rolcreaterole,rolcreatedb,rolcanlogin "
                "FROM pg_roles WHERE rolname=current_user"
            )
        )
        .mappings()
        .one()
    )
    if row["rolname"] != ROLE or any(
        row[k] for k in ["rolsuper", "rolcreaterole", "rolcreatedb", "rolcanlogin"]
    ):
        raise AgentError(
            "unsafe_database_role", "Agent requires the prepared SELECT-only reader role."
        )
    if db.scalar(text("SHOW transaction_read_only")) != "on":
        raise AgentError("unsafe_database_transaction", "Agent transactions must be read-only.")
