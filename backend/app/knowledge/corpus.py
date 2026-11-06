"""Registered corpus discovery, metadata/hash validation and safe source access."""

import hashlib
import json
import re
from pathlib import Path

from app.knowledge.embeddings import KnowledgeError
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "knowledge/synthetic_documents"
DOCUMENT_SQL = """
SELECT d.id document_id,d.code,d.title,d.document_type,d.department_id,
 dep.name department,d.contract_id,c.supplier_id,s.name supplier,c.reference contract_reference,
 v.id version_id,v.version,v.effective_on,v.path,v.sha256,
 v.created_at published_at
FROM documents d JOIN document_versions v ON v.document_id=d.id
JOIN departments dep ON dep.id=d.department_id
LEFT JOIN supplier_contracts c ON c.id=d.contract_id
LEFT JOIN suppliers s ON s.id=c.supplier_id
"""


def documents(db):
    return [dict(r) for r in db.execute(text(DOCUMENT_SQL + " ORDER BY d.id,v.version")).mappings()]


def source(meta, root=None):
    # The database registration is necessary, but never sufficient to permit a path.
    path = (ROOT / meta["path"]).resolve()
    allowed = Path(root or CORPUS).resolve()
    if not path.is_relative_to(allowed) or path.suffix.lower() != ".md":
        raise KnowledgeError(
            "source_unavailable", "Registered source is outside the synthetic corpus."
        )
    try:
        raw = path.read_bytes()
        value = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise KnowledgeError("source_unavailable", "Registered source cannot be read.") from exc
    if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
        raise KnowledgeError(
            "source_hash_mismatch", "Registered source hash does not match its content."
        )
    if len(raw) > 1_000_000:
        raise KnowledgeError(
            "source_too_large", "Registered Markdown exceeds the source size limit."
        )
    return value


def validate_metadata(meta, value):
    expected = {
        "Document ID": meta["code"],
        "Type": meta["document_type"],
        "Version": str(meta["version"]),
        "Effective date": str(meta["effective_on"]),
        "Department": meta["department"],
        "Contract ID": str(meta["contract_id"] or "N/A"),
    }
    fields = dict(re.findall(r"^- ([^:\r\n]+): ([^\r\n]+)\r?$", value, re.M))
    if (
        any(fields.get(k) != v for k, v in expected.items())
        or value.splitlines()[0] != "# " + meta["title"]
    ):
        raise KnowledgeError(
            "invalid_document_metadata", "Source metadata differs from the registered version."
        )
    if bool(meta["contract_id"]) != (meta["document_type"] == "supplier_agreement"):
        raise KnowledgeError(
            "invalid_document_metadata", "Document type and contract reference disagree."
        )


def public_metadata(meta):
    return {
        k: meta[k]
        for k in [
            "document_id",
            "code",
            "title",
            "document_type",
            "department_id",
            "department",
            "contract_id",
            "contract_reference",
            "supplier_id",
            "supplier",
            "version_id",
            "version",
            "effective_on",
            "sha256",
        ]
    }


def metadata_signature(meta):
    values = {
        k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in meta.items() if k != "path"
    }
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
