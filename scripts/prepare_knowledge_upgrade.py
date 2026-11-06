"""Capture a preservation baseline and backup without changing services or records."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import httpx
from app.db.session import engine
from app.services.integrity import load_dataset, validate
from sqlalchemy import text
from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(".local-tools"))
    args = parser.parse_args()
    directory = args.output_dir.resolve()
    if not directory.is_relative_to(Path(".local-tools").resolve()):
        raise ValueError("Keep backup and machine-specific baseline inside ignored .local-tools.")
    directory.mkdir(parents=True, exist_ok=True)
    baseline_path = directory / "stage3-baseline.json"
    backup_path = directory / "stage3-before.dump"
    if baseline_path.exists() or backup_path.exists():
        raise ValueError("Preserved baseline/backup already exists; choose a fresh --output-dir.")
    record = {}
    with Session(engine()) as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        dataset = load_dataset(db)
        record["integrity"] = validate(dataset)
        for version in dataset.rows["document_versions"]:
            raw = Path(version["path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == version["sha256"]
            dataset.documents[version["path"]] = raw.decode("utf-8")
        record["fingerprint"] = dataset.fingerprint()
        accepted = json.loads(Path("reports/stage2-validation.json").read_text())
        assert record["fingerprint"] == accepted["final_fingerprint"]
        record["migration"] = db.scalar(text("SELECT version_num FROM alembic_version"))
    ids = subprocess.check_output(["docker", "ps", "-aq"], text=True).split()
    record["containers"] = []
    for current in json.loads(subprocess.check_output(["docker", "inspect", *ids])):
        state = current["State"]
        record["containers"].append(
            dict(
                id=current["Id"],
                name=current["Name"],
                image=current["Image"],
                status=state["Status"],
                started_at=state["StartedAt"],
                finished_at=state["FinishedAt"],
                mounts=current["Mounts"],
            )
        )
    record["volumes"] = subprocess.check_output(
        ["docker", "volume", "ls", "--format", "{{.Name}}"], text=True
    ).splitlines()
    record["networks"] = subprocess.check_output(
        ["docker", "network", "ls", "--format", "{{.ID}} {{.Name}}"], text=True
    ).splitlines()
    with httpx.Client(base_url="http://127.0.0.1:8001", timeout=60) as client:
        record["analytics"] = {}
        for domain in [
            "overview",
            "procurement",
            "suppliers",
            "inventory",
            "warehouses",
            "fulfilment",
            "finance",
            "workforce",
            "incidents",
            "insights",
        ]:
            response = client.get("/api/v1/analytics/" + domain)
            response.raise_for_status()
            record["analytics"][domain] = response.json()
    backup = subprocess.check_output(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "pg_dump",
            "-U",
            "opspilot",
            "-d",
            "opspilot",
            "-Fc",
        ]
    )
    assert backup.startswith(b"PGDMP")
    backup_path.write_bytes(backup)
    baseline_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "fingerprint": record["fingerprint"],
                "migration": record["migration"],
                "backup_bytes": len(backup),
                "output_directory": str(directory),
            }
        )
    )


if __name__ == "__main__":
    main()
