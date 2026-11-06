from alembic import context
from app.db.session import engine
from app.knowledge.schema import metadata as knowledge_metadata
from app.models import Base
from app.workflow.schema import metadata as workflow_metadata

target_metadata = [Base.metadata, knowledge_metadata, workflow_metadata]

if context.is_offline_mode():
    context.configure(
        url="postgresql+psycopg://",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:

    def migrate(connection):
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

    provided = context.config.attributes.get("connection")
    if provided is not None:
        migrate(provided)
    else:
        with engine().connect() as connection:
            migrate(connection)
