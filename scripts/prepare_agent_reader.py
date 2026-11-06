"""Explicit local maintenance: provision a non-login reader for OpsPilot only."""

from app.db.session import engine
from app.knowledge.schema import metadata
from app.models import Base
from sqlalchemy import text
from sqlalchemy.orm import Session


def prepare_reader(db):
    name = db.scalar(text("SELECT current_database()"))
    if name != "opspilot" and not name.startswith("opspilot_test_"):
        raise ValueError("Reader setup is restricted to OpsPilot databases.")
    db.execute(text("SELECT pg_advisory_xact_lock(741902513)"))
    row = (
        db.execute(
            text(
                "SELECT rolsuper,rolcreaterole,rolcreatedb,rolcanlogin FROM "
                "pg_roles WHERE rolname='opspilot_agent_reader'"
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        db.execute(
            text(
                "CREATE ROLE opspilot_agent_reader NOLOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOINHERIT"
            )
        )
    elif any(row.values()):
        raise ValueError("Existing reader role has unexpected privileges; refusing to modify it.")
    db.execute(text("GRANT USAGE ON SCHEMA public TO opspilot_agent_reader"))
    names = ", ".join(
        '"' + t.name + '"' for t in [*Base.metadata.sorted_tables, *metadata.sorted_tables]
    )
    db.execute(text(f"GRANT SELECT ON TABLE {names} TO opspilot_agent_reader"))


if __name__ == "__main__":
    with Session(engine()) as db, db.begin():
        prepare_reader(db)
    print("Prepared the fixed OpsPilot non-login SELECT-only reader role.")
