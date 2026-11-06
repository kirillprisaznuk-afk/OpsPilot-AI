"""Constrained decoding mirrors (and never replaces) server grounding validation."""

import re
import string
from functools import lru_cache
from typing import Annotated, Literal

from app.agent.contracts import AgentError, Draft, Strict
from app.agent.grounding import NUMBER
from pydantic import Field


@lru_cache
def qualitative_pattern():
    """Regular grammar for English prose excluding the server's numeric words.

    A trie complement avoids unsupported regex lookahead. Complete words use
    single separators and terminal punctuation. Quotes, backslashes, digits and
    control characters are absent, keeping the runtime's JSON grammar safe.
    """
    words = re.search(r"\(\?:([^)]*)\)", NUMBER.pattern).group(1).split("|")
    trie = {}
    for word in words:
        node = trie
        for letter in word:
            node = node.setdefault(letter, {})
        node[""] = True

    def branch(node, root=False):
        letters = sorted(key for key in node if key)
        other = "".join(c + c.upper() for c in string.ascii_lowercase if c not in letters)
        choices = ["[" + other + "][A-Za-z]*"] if other else []
        choices.extend(
            "[" + c + c.upper() + "]" + branch(node[c]) for c in letters if "" not in node[c]
        )
        expression = "(" + "|".join(choices) + ")"
        return expression if root or "" in node else expression + "?"

    word = branch(trie, root=True)
    return "^" + word + "(([ '-]|[,;:] )" + word + "){0,31}[.!?]$"


class EvidenceSupport(Strict):
    kind: Literal["evidence"]
    evidence_id: str


class MetricSupport(Strict):
    kind: Literal["metric"]
    evidence_id: str
    pointer: str


class SourceSupport(Strict):
    kind: Literal["source"]
    evidence_id: str
    citation_id: str
    document_code: str | None = Field(
        description="Copy the exact registered code from citation_source_codes. "
        "Select the requested document itself, not a different valid source."
    )
    quote: bool


Support = Annotated[EvidenceSupport | MetricSupport | SourceSupport, Field(discriminator="kind")]
Prose = Annotated[str, Field(pattern=qualitative_pattern())]


class LocalFinding(Strict):
    qualitative_assessment: Prose = Field(
        min_length=1,
        max_length=240,
        description="A short complete qualitative sentence ending in punctuation, "
        "without amounts or numeric IDs. "
        "The application separately renders selected metric values and source passages. "
        "Never write a quantitative sentence with blank quantities.",
    )
    supports: list[Support] = Field(min_length=1, max_length=3)


class LocalDraft(Draft):
    findings: list[LocalFinding] = Field(max_length=3)
    limitations: list[Prose] = Field(max_length=1)
    follow_up_questions: list[Prose] = Field(max_length=1)


def ollama_final_schema(index=None):
    schema = LocalDraft.model_json_schema()
    if index is None:
        return schema
    options = []
    for item in index:
        identifier = {"type": "string", "const": item["evidence_id"]}
        options.append(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {"kind": {"const": "evidence"}, "evidence_id": identifier},
                "required": ["kind", "evidence_id"],
            }
        )
        if item["metric_pointers"]:
            options.append(
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "kind": {"const": "metric"},
                        "evidence_id": identifier,
                        "pointer": {"type": "string", "enum": item["metric_pointers"]},
                    },
                    "required": ["kind", "evidence_id", "pointer"],
                }
            )
        for citation_id in item["citation_ids"]:
            options.append(
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "kind": {"const": "source"},
                        "evidence_id": identifier,
                        "citation_id": {"type": "string", "const": citation_id},
                        "document_code": {
                            "const": item.get("citation_source_codes", {}).get(citation_id)
                        },
                        "quote": {"type": "boolean"},
                    },
                    "required": ["kind", "evidence_id", "citation_id", "document_code", "quote"],
                }
            )
    if options:
        schema["$defs"]["LocalFinding"]["properties"]["supports"]["items"] = {"oneOf": options}
    else:
        schema["properties"]["findings"]["maxItems"] = 0
        schema["properties"]["status"]["enum"].remove("completed")
    return schema


def prompt_schema():
    def clean(value):
        if isinstance(value, dict):
            return {
                key: clean(child)
                for key, child in value.items()
                if key not in {"pattern", "title", "discriminator"}
            }
        if isinstance(value, list):
            return [clean(child) for child in value]
        return value

    return clean(LocalDraft.model_json_schema())


def canonical_draft(raw, index):
    try:
        local = LocalDraft.model_validate_json(raw, strict=True)
    except ValueError as exc:
        raise AgentError("malformed_final_output", "Invalid local structured response.") from exc
    known = {item["evidence_id"]: item for item in index}
    findings = []
    for finding in local.findings:
        identifiers, metrics, citations, quotes = [], [], [], []
        for support in finding.supports:
            evidence = known.get(support.evidence_id)
            if evidence is None:
                raise AgentError(
                    "invalid_evidence_reference", "Local support was not returned by a tool."
                )
            identifiers.append(support.evidence_id)
            if support.kind == "metric":
                if support.pointer not in evidence["metric_pointers"]:
                    raise AgentError(
                        "invalid_metric_reference", "Local metric support is not in its evidence."
                    )
                metrics.append({"evidence_id": support.evidence_id, "pointer": support.pointer})
            if support.kind == "source":
                if support.citation_id not in evidence["citation_ids"] or (
                    support.document_code
                    != evidence.get("citation_source_codes", {}).get(support.citation_id)
                ):
                    raise AgentError(
                        "invalid_citation_reference", "Local source is not in its evidence."
                    )
                citations.append(support.citation_id)
                if support.quote:
                    quotes.append(support.citation_id)
        findings.append(
            {
                "text": finding.qualitative_assessment,
                "evidence_ids": list(dict.fromkeys(identifiers)),
                "metric_refs": metrics,
                "citation_ids": list(dict.fromkeys(citations)),
                "quote_citation_ids": list(dict.fromkeys(quotes)),
            }
        )
    try:
        return Draft.model_validate(
            {
                "status": local.status,
                "findings": findings,
                "limitations": local.limitations,
                "follow_up_questions": local.follow_up_questions,
            },
            strict=True,
        ).model_dump_json()
    except ValueError as exc:
        raise AgentError(
            "malformed_final_output", "Local response exceeds canonical bounds."
        ) from exc
