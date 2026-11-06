import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.db.session import engine, session
from app.main import app
from app.services.seeding import seed
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.tests.analytics_fixtures import small_db  # noqa: F401
from data.generator.company import generate


@pytest.fixture(scope="session")
def dataset():
    return generate()


@pytest.fixture(scope="session")
def postgres():
    original = os.environ.get("DATABASE_URL")
    url = make_url(settings().database_url.get_secret_value())
    name = "opspilot_test_" + uuid.uuid4().hex
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
    except Exception:
        pytest.fail(
            "PostgreSQL is required. Start the project database and configure DATABASE_URL.",
            pytrace=False,
        )
    test_url = url.set(database=name)
    os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
    settings.cache_clear()
    engine.cache_clear()
    test_engine = engine()
    try:
        command.upgrade(Config("alembic.ini"), "head")
        with Session(test_engine) as db, db.begin():
            seed(db)
        yield test_engine
    finally:
        test_engine.dispose()
        engine.cache_clear()
        settings.cache_clear()
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def db(postgres):
    with postgres.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
            yield db
        transaction.rollback()


@pytest.fixture
def client(db):
    app.dependency_overrides[session] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
