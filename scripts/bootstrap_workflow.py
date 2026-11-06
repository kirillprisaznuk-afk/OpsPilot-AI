"""Explicit local bootstrap; generated credentials are saved only in an ignored directory."""

import argparse
import json
import re
import secrets
import uuid
from pathlib import Path

from app.db.session import engine
from app.workflow import schema as s
from app.workflow.audit import event
from app.workflow.auth import password_hash
from app.workflow.permissions import ROLES
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import Session

from scripts.prepare_agent_reader import prepare_reader
from scripts.prepare_workflow_runtime import prepare_runtime


def create_principal(db, username, password, grants, *, employee_id=None, is_human=True):
    if not re.fullmatch(r"[a-z0-9_.-]{3,80}", username):
        raise ValueError("Invalid local username")
    if any(role not in ROLES for role, _ in grants):
        raise ValueError("Unknown application role")
    identifier = uuid.uuid4()
    db.execute(
        insert(s.principals).values(
            id=identifier,
            username=username,
            password_hash=password_hash(password),
            employee_id=employee_id,
            is_human=is_human,
            active=True,
        )
    )
    for role, department_id in grants:
        db.execute(
            insert(s.assignments).values(
                principal_id=identifier, role_code=role, department_id=department_id, active=True
            )
        )
    event(
        db,
        None,
        "identity.bootstrapped",
        request_id=uuid.uuid4(),
        object_type="principal",
        object_id=identifier,
        after={"username": username, "roles": grants, "is_human": is_human},
    )
    return identifier


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(".local-tools/stage5-demo"))
    args = parser.parse_args()
    directory = args.output_dir.resolve()
    if not directory.is_relative_to(Path(".local-tools").resolve()):
        parser.error("Keep generated credentials under ignored .local-tools")
    directory.mkdir(parents=True, exist_ok=True)
    credential_file = directory / "accounts.json"
    if credential_file.exists():
        print("Existing local bootstrap credentials preserved; no accounts or passwords changed.")
        return
    runtime_password = secrets.token_urlsafe(32)
    login = "opspilot_wf_app"
    accounts = []
    configurations = {
        "stage5.analyst": [("OPERATIONS_ANALYST", 1), ("WORKFLOW_OPERATOR", 1)],
        "stage5.operator": [("WORKFLOW_OPERATOR", 1)],
        "stage5.reviewer": [("WORKFLOW_APPROVER", 1)],
        "stage5.viewer": [("VIEWER", 1)],
        "stage5.admin": [("WORKFLOW_ADMIN", None)],
        "stage5.outsider": [("WORKFLOW_APPROVER", 2)],
    }
    with Session(engine()) as db, db.begin():
        name = db.scalar(select(s.principals.c.id).limit(1))
        if name is not None:
            raise SystemExit(
                "Workflow identities already exist; refusing to overwrite credentials."
            )
        prepare_reader(db)
        prepare_runtime(db, login, runtime_password)
        for username, grants in configurations.items():
            password = secrets.token_urlsafe(24)
            identifier = create_principal(db, username, password, grants)
            accounts.append(
                {
                    "username": username,
                    "password": password,
                    "principal_id": str(identifier),
                    "roles": grants,
                }
            )
    owner_url = engine().url
    runtime_url = owner_url.set(username=login, password=runtime_password)
    # Prove this is a non-owner login before writing project-local configuration.
    probe = create_engine(runtime_url, connect_args={"connect_timeout": 5})
    try:
        with probe.connect() as connection:
            from sqlalchemy import text

            assert connection.scalar(text("SELECT current_user")) == login
    finally:
        probe.dispose()
    env_file = Path(".env")
    content = env_file.read_text(encoding="utf-8")
    values = {
        "WORKFLOW_DATABASE_URL": runtime_url.render_as_string(hide_password=False),
        "WORKFLOW_DB_USER": login,
        "WORKFLOW_DB_PASSWORD": runtime_password,
    }
    for key, value in values.items():
        content = re.sub(r"(?m)^" + key + r"=.*\n?", "", content)
        content += f"\n{key}={value}\n"
    env_file.write_text(content, encoding="utf-8")
    credential_file.write_text(
        json.dumps({"accounts": accounts}, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Created {len(accounts)} demo principals. Credentials: {credential_file}.")
    print("No password or session token was printed. Existing business records were not modified.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Utility SQL may contain a generated role secret: never render raw driver statements.
        raise SystemExit(
            "Workflow bootstrap failed safely; inspect configuration and migration status."
        ) from None
