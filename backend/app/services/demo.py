from app.models import Base, SeedRun
from app.repositories.orders import timeline
from sqlalchemy import func, select, text

from data.generator.company import END, START


def summary(db):
    counts = {
        table.name: db.scalar(select(func.count()).select_from(table))
        for table in Base.metadata.sorted_tables
        if table.name != "seed_runs"
    }
    run = db.get(SeedRun, 1)
    return {
        "company": "Northstar Supply (fictional)",
        "synthetic": True,
        "currency": "GBP",
        "observation_start": START,
        "observation_end": END,
        "counts": counts,
        "fingerprint": run.fingerprint if run else None,
    }


def readiness(db):
    revision = db.scalar(text("SELECT version_num FROM alembic_version"))
    return revision == "0004" and db.get(SeedRun, 1) is not None


def order_timeline(db, order_id, kind):
    return timeline(db, order_id, kind)
