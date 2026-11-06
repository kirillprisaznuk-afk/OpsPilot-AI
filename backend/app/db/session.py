from functools import lru_cache

from app.core.config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


@lru_cache
def engine():
    return create_engine(settings().database_url.get_secret_value(), pool_pre_ping=True)


def session():
    with Session(engine()) as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        yield db
