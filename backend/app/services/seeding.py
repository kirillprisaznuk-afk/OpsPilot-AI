import hashlib
from pathlib import Path

from app.knowledge.schema import metadata as knowledge_metadata
from app.models import Base, SeedRun
from app.services.integrity import validate
from sqlalchemy import func, select, text

from data.generator.company import END, SEED, VERSION, generate, stamp

ROOT = Path(__file__).resolve().parents[3]


def seed(db, seed_value=SEED):
    # Serialize competing seed/reset operations in this database only.
    db.execute(text("SELECT pg_advisory_xact_lock(741902511)"))
    for table in [*Base.metadata.sorted_tables, *knowledge_metadata.sorted_tables]:
        if db.scalar(select(func.count()).select_from(table)):
            raise ValueError(
                "Database is not empty. Refusing reseed; use the explicit reset command."
            )
    dataset = generate(seed_value)
    report = validate(dataset)
    for version in dataset.rows["document_versions"]:
        path = ROOT / version["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != version["sha256"]:
            raise ValueError(f"Document missing or changed: {version['path']}")
    for table in Base.metadata.sorted_tables:
        rows = dataset.rows.get(table.name)
        if rows:
            db.execute(table.insert(), rows)
    fingerprint = dataset.fingerprint()
    db.add(
        SeedRun(
            id=1,
            created_at=stamp(END),
            synthetic=True,
            seed=seed_value,
            generator_version=VERSION,
            fingerprint=fingerprint,
        )
    )
    db.flush()
    return {**report, "fingerprint": fingerprint}


def reset(db, confirmation):
    name = db.scalar(text("SELECT current_database()"))
    if name != "opspilot" and not name.startswith("opspilot_test_"):
        raise ValueError("Reset restricted to opspilot or isolated opspilot_test_* databases")
    if confirmation != f"DELETE SYNTHETIC DATA FROM {name}":
        raise ValueError(f'Reset requires --confirm "DELETE SYNTHETIC DATA FROM {name}"')
    db.execute(text("SELECT pg_advisory_xact_lock(741902511)"))
    tables = [*Base.metadata.sorted_tables, *knowledge_metadata.sorted_tables]
    if db.scalar(text("SELECT to_regclass('workflow_proposals')")):
        if not name.startswith("opspilot_test_"):
            raise ValueError("Reset refused: Stage 5 workflow governance depends on source data")
        from app.workflow.schema import metadata as workflow_metadata

        tables.extend(workflow_metadata.sorted_tables)
    names = ", ".join(f'"{t.name}"' for t in tables)
    # No CASCADE: unexpected external dependencies cause a safe failure.
    db.execute(text(f"TRUNCATE TABLE {names}"))
