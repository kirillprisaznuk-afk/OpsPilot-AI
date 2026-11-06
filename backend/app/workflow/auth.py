import hashlib
import secrets
import threading
import uuid
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.workflow import schema as s
from app.workflow.audit import event
from app.workflow.common import (
    Actor,
    Result,
    WorkflowError,
    WorkflowSettings,
    lock,
    now,
    principal_locks,
    transaction,
)
from app.workflow.permissions import member, memberships, require, session_valid

HASHER = PasswordHasher()
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(32))
HASH_SLOTS = threading.BoundedSemaphore(2)


def password_hash(password):
    if not 12 <= len(password) <= 200:
        raise WorkflowError(
            "invalid_password", "Use a password between twelve and two hundred characters.", 422
        )
    return HASHER.hash(password)


def token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def login(body, remote, request_id, bind=None):
    outcome = Result()
    with transaction("auth", bind) as db:
        # Both account and origin budgets are persisted, locked and shared by workers.
        keys = [token_digest("account:" + body.username), token_digest("origin:" + remote)]
        buckets = []
        for key in sorted(keys):
            lock(db, "workflow-login", key)
            db.execute(
                pg_insert(s.login_buckets)
                .values(key=key, failures=0, window_start=now())
                .on_conflict_do_nothing()
            )
            row = (
                db.execute(select(s.login_buckets).where(s.login_buckets.c.key == key))
                .mappings()
                .one()
            )
            if row["window_start"] < now() - timedelta(minutes=15):
                db.execute(
                    update(s.login_buckets)
                    .where(s.login_buckets.c.key == key)
                    .values(failures=0, window_start=now())
                )
                row = dict(row, failures=0)
            buckets.append(row)
        if any(b["failures"] >= 8 for b in buckets):
            outcome.error = WorkflowError("login_throttled", "Login temporarily throttled.", 429)
        else:
            principal = (
                db.execute(select(s.principals).where(s.principals.c.username == body.username))
                .mappings()
                .first()
            )
            valid = False
            if HASH_SLOTS.acquire(timeout=0.25):
                try:
                    try:
                        valid = HASHER.verify(
                            principal["password_hash"] if principal else DUMMY_HASH,
                            body.password.get_secret_value(),
                        )
                    except (VerificationError, InvalidHashError):
                        valid = False
                finally:
                    HASH_SLOTS.release()
            else:
                outcome.error = WorkflowError("login_throttled", "Authentication is busy.", 429)
            if not outcome.error and (
                not valid or not principal or not principal["active"] or not principal["is_human"]
            ):
                outcome.error = WorkflowError("invalid_credentials", "Invalid credentials.", 401)
            if not outcome.error:
                principal_locks(db, [principal["id"]])
                # Re-read after the lock: revocation/deactivation may have raced password hashing.
                fresh = member(db, principal["id"])
                if not fresh["active"] or not fresh["is_human"]:
                    outcome.error = WorkflowError(
                        "invalid_credentials", "Invalid credentials.", 401
                    )
                else:
                    raw = secrets.token_urlsafe(32)
                    identifier = uuid.uuid4()
                    expiry = now() + timedelta(hours=WorkflowSettings().session_hours)
                    db.execute(
                        insert(s.sessions).values(
                            id=identifier,
                            principal_id=principal["id"],
                            token_digest=token_digest(raw),
                            authz_version=fresh["authz_version"],
                            expires_at=expiry,
                        )
                    )
                    db.execute(
                        update(s.login_buckets)
                        .where(s.login_buckets.c.key == keys[0])
                        .values(failures=0, window_start=now())
                    )
                    actor = Actor(
                        principal["id"], identifier, fresh["authz_version"], body.username
                    )
                    event(
                        db,
                        actor,
                        "auth.login",
                        request_id=request_id,
                        object_type="session",
                        object_id=identifier,
                    )
                    outcome.data = {
                        "access_token": raw,
                        "token_type": "bearer",
                        "expires_at": expiry,
                    }
        if outcome.error:
            if outcome.error.code != "login_throttled":
                db.execute(
                    update(s.login_buckets)
                    .where(s.login_buckets.c.key.in_(keys))
                    .values(failures=s.login_buckets.c.failures + 1)
                )
            event(
                db,
                None,
                "auth.login_denied",
                request_id=request_id,
                result="DENIED",
                after={"code": outcome.error.code},
            )
    return outcome.unwrap()


def authenticate(token, request_id, bind=None):
    actor, failure = None, None
    with transaction("auth", bind) as db:
        if token and 40 <= len(token) <= 100:
            row = (
                db.execute(
                    select(
                        s.sessions.c.id,
                        s.sessions.c.principal_id,
                        s.sessions.c.authz_version,
                        s.principals.c.username,
                    )
                    .join(s.principals, s.principals.c.id == s.sessions.c.principal_id)
                    .where(s.sessions.c.token_digest == token_digest(token))
                )
                .mappings()
                .first()
            )
            if row:
                actor = Actor(row["principal_id"], row["id"], row["authz_version"], row["username"])
                try:
                    session_valid(db, actor)
                except WorkflowError as exc:
                    failure = exc
        if actor is None or failure:
            event(db, None, "auth.session_denied", request_id=request_id, result="DENIED")
            failure = WorkflowError(
                "authentication_required", "A valid bearer session is required.", 401
            )
    if failure:
        raise failure
    return actor


def me(actor, bind=None):
    with transaction("auth", bind) as db:
        principal = dict(session_valid(db, actor))
        principal["roles"] = [dict(m) for m in memberships(db, actor.id)]
        return principal


def logout(actor, request_id, bind=None):
    with transaction("auth", bind) as db:
        principal_locks(db, [actor.id])
        session_valid(db, actor)
        db.execute(
            update(s.sessions).where(s.sessions.c.id == actor.session_id).values(revoked_at=now())
        )
        event(
            db,
            actor,
            "auth.logout",
            request_id=request_id,
            object_type="session",
            object_id=actor.session_id,
        )
    return {"revoked": True}


def change_role(actor, principal_id, body, request_id, bind=None):
    failure = None
    with transaction("admin", bind) as db:
        principal_locks(db, [actor.id, principal_id])
        try:
            require(db, actor, "admin", [body.department_id])
            if not member(db, principal_id):
                raise WorkflowError("principal_not_found", "Principal not found.", 404)
            if principal_id == actor.id and not body.active:
                raise WorkflowError(
                    "self_role_revocation", "Use a distinct administrator to revoke your role.", 403
                )
            if body.department_id is not None:
                from app.models import Base

                if not db.execute(
                    select(Base.metadata.tables["departments"].c.id).where(
                        Base.metadata.tables["departments"].c.id == body.department_id
                    )
                ).first():
                    raise WorkflowError("invalid_department", "Department does not exist.", 422)
            db.execute(
                pg_insert(s.assignments)
                .values(
                    principal_id=principal_id,
                    role_code=body.role,
                    department_id=body.department_id,
                    active=body.active,
                )
                .on_conflict_do_update(
                    index_elements=[
                        s.assignments.c.principal_id,
                        s.assignments.c.role_code,
                        s.assignments.c.department_id,
                    ],
                    set_={"active": body.active},
                )
            )
            event(
                db,
                actor,
                "permission.changed",
                request_id=request_id,
                object_type="principal",
                object_id=principal_id,
                department_id=body.department_id,
                after={"role": body.role, "active": body.active},
                reason=body.reason,
            )
        except WorkflowError as exc:
            failure = exc
            event(
                db,
                actor,
                "permission.denied",
                request_id=request_id,
                result="DENIED",
                after={"code": exc.code},
            )
    if failure:
        raise failure
    return {"changed": True, "sessions_revoked": True, "prior_approvals_invalidated": True}
