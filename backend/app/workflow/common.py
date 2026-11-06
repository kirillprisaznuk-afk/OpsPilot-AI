import hashlib
import json
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache

from fastapi.encoders import jsonable_encoder
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DB_ROLES = {
    "auth": "opspilot_wf_auth",
    "read": "opspilot_wf_read",
    "review": "opspilot_wf_review",
    "execute": "opspilot_wf_executor",
    "admin": "opspilot_wf_admin",
}


class WorkflowSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WORKFLOW_", env_file=".env", extra="ignore")
    database_url: SecretStr | None = None
    session_hours: int = Field(4, ge=1, le=12)
    statement_timeout_ms: int = Field(5000, ge=100, le=15000)


class WorkflowError(Exception):
    def __init__(self, code, message, status=409, *, details=None):
        super().__init__(message)
        self.code, self.status, self.details = code, status, details


@dataclass(frozen=True)
class Actor:
    id: uuid.UUID
    session_id: uuid.UUID
    authz_version: int
    username: str


@dataclass
class Result:
    data: dict | None = None
    error: WorkflowError | None = None
    status: int = 200
    transaction_ms: float | None = None

    def unwrap(self):
        if self.error:
            raise self.error
        return self.data


def now():
    return datetime.now(UTC)


def canonical(value):
    return json.dumps(
        jsonable_encoder(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def lock(db, namespace, identifier, *, shared=False):
    value = int.from_bytes(
        hashlib.sha256(f"{namespace}:{identifier}".encode()).digest()[:8], "big", signed=True
    )
    function = "pg_advisory_xact_lock_shared" if shared else "pg_advisory_xact_lock"
    db.execute(text("SELECT " + function + "(:key)"), {"key": value})


def principal_locks(db, identifiers):
    for identifier in sorted(set(identifiers), key=str):
        lock(db, "workflow-principal", identifier)


@lru_cache
def workflow_engine():
    settings = WorkflowSettings()
    if not settings.database_url or not settings.database_url.get_secret_value().strip():
        raise WorkflowError("workflow_not_configured", "Run project-local workflow bootstrap.", 503)
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
        pool_size=5,
        max_overflow=5,
    )


@contextmanager
def transaction(role, bind=None):
    if role not in DB_ROLES:
        raise ValueError("Unknown internal database role")
    with Session(bind or workflow_engine()) as db, db.begin():
        unsafe = db.execute(
            text(
                "SELECT r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolbypassrls OR "
                "pg_get_userbyid(d.datdba)=session_user FROM pg_roles r,pg_database d "
                "WHERE r.rolname=session_user AND d.datname=current_database()"
            )
        ).scalar_one()
        if unsafe:
            raise WorkflowError(
                "unsafe_workflow_connection",
                "Workflow requests require the restricted runtime login.",
                503,
            )
        db.execute(text("SET LOCAL ROLE " + DB_ROLES[role]))
        db.execute(
            text("SELECT set_config('statement_timeout',:timeout,true)"),
            {"timeout": str(WorkflowSettings().statement_timeout_ms)},
        )
        db.execute(text("SET LOCAL lock_timeout='3s'"))
        yield db
