"""Explicit opt-in live evaluation; default records configuration without paid calls."""

import argparse
import asyncio
import json
import statistics
import time
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx
from app.agent.config import agent_settings
from app.agent.contracts import AgentError


def at(value, path):
    for part in path.strip("/").split("/"):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def rendered_numeric(body, expected):
    """Check selected final metrics, independently from merely retrieved evidence."""
    evidence_ids = {
        e["evidence_id"] for e in body["evidence"] if e["tool_name"] == expected["tool"]
    }
    pointers = expected.get("rendered_paths", [expected["path"].removesuffix("/value")])
    for finding in body["key_findings"]:
        for metric in finding["metrics"]:
            if metric["evidence_id"] in evidence_ids and metric["pointer"] in pointers:
                try:
                    if Decimal(str(metric["value"])) == Decimal(str(expected["value"])):
                        return True
                except InvalidOperation:
                    pass
    return False


async def offline(cases, settings):
    from app.agent.execution import ToolExecutor, parse_arguments
    from app.agent.grounding import citation_map

    rows = []
    executor = ToolExecutor(settings)
    for case in cases:
        results = []
        errors = []
        elapsed = []
        for plan in case["calls"]:
            try:
                args = parse_arguments(
                    plan["tool"],
                    json.dumps(plan["arguments"]),
                    date.fromisoformat(case.get("as_of", "2026-09-30")),
                )
                payload, ms = await executor.run(
                    plan["tool"], args, settings.agent_tool_timeout_seconds
                )
                results.append({"tool": plan["tool"], "payload": payload})
                elapsed.append(ms)
            except AgentError as exc:
                errors.append(exc.code)
        numeric = []
        for expected in case.get("numeric", []):
            payload = next((r["payload"] for r in results if r["tool"] == expected["tool"]), None)
            numeric.append(
                payload is not None and str(at(payload, expected["path"])) == str(expected["value"])
            )
        codes = set()
        for r in results:
            for e in r["payload"].get("evidence", []):
                if "metadata" in e:
                    codes.add(e["metadata"]["code"])
        row = {
            "id": case["id"],
            "execution_mode": "offline_tools_only",
            "tool_errors": errors,
            "declared_tool_validation_passed": errors == [case["expected_error"]]
            if "expected_error" in case
            else not errors,
            "known_numerical_assertions": numeric,
            "required_document_codes_found": set(case.get("expected_codes", [])) <= codes,
            "source_citations": sum(len(citation_map(r["payload"])) for r in results),
            "tool_elapsed_ms": round(sum(elapsed), 3),
            "live_tool_selection": None,
            "final_answer_correctness": None,
        }
        rows.append(row)
    return {
        "mode": "offline_tools_only",
        "cases": rows,
        "known_numerical_assertions_passed": all(
            all(r["known_numerical_assertions"]) for r in rows
        ),
        "tool_and_source_checks_passed": all(
            r["declared_tool_validation_passed"] and r["required_document_codes_found"]
            for r in rows
        ),
        "live_selection_answer_metrics": None,
    }


def live(cases):
    rows = []
    with httpx.Client(base_url="http://127.0.0.1:8001", timeout=100) as client:
        for case in cases:
            begin = time.perf_counter()
            response = client.post(
                "/api/v1/agent/query",
                json={"question": case["question"], "as_of": case.get("as_of", "2026-09-30")},
            )
            response.raise_for_status()
            body = response.json()
            used = {t["tool"] for t in body["tool_trace"] if t["status"] == "success"}
            required = {
                p["tool"]
                for p in case["calls"]
                if p["tool"]
                in {
                    "get_supplier_performance",
                    "compare_suppliers",
                    "get_inventory_status",
                    "get_workforce_tasks",
                    "search_corporate_knowledge",
                    "investigate_business_entity",
                }
            }
            citations = []
            for citation in body["citations"]:
                r = client.get("/api/v1/knowledge/citations/" + citation["citation_id"])
                citations.append(r.status_code == 200 and r.json()["verified"])
            expected_numeric = []
            for expected in case.get("numeric", []):
                evidence = next(
                    (e for e in body["evidence"] if e["tool_name"] == expected["tool"]), None
                )
                expected_numeric.append(
                    evidence is not None
                    and str(at(evidence["payload"], expected["path"])) == str(expected["value"])
                )
            document_codes = set()
            cited_codes = set()
            cited_documents = {citation["document_id"] for citation in body["citations"]}

            def source_metadata(
                value,
                document_codes=document_codes,
                cited_codes=cited_codes,
                cited_documents=cited_documents,
            ):
                if isinstance(value, dict):
                    metadata = value.get("metadata", {})
                    if isinstance(metadata, dict) and {"code", "document_id", "version_id"} <= set(
                        metadata
                    ):
                        document_codes.add(metadata["code"])
                        if metadata["document_id"] in cited_documents:
                            cited_codes.add(metadata["code"])
                    for child in value.values():
                        source_metadata(child)
                elif isinstance(value, list):
                    for child in value:
                        source_metadata(child)

            for evidence in body["evidence"]:
                source_metadata(evidence["payload"])
            rows.append(
                {
                    "id": case["id"],
                    "status": body["status"],
                    "tool_selection_expected_subset": required <= used,
                    "valid_tool_argument_fraction": sum(
                        t["status"] == "success" for t in body["tool_trace"]
                    )
                    / len(body["tool_trace"])
                    if body["tool_trace"]
                    else None,
                    "citation_resolution": all(citations) if citations else None,
                    "known_numeric_evidence": expected_numeric,
                    "known_numeric_rendered": [
                        rendered_numeric(body, expected) for expected in case.get("numeric", [])
                    ],
                    "required_document_codes_found": set(case.get("expected_codes", []))
                    <= document_codes,
                    "required_document_codes_cited": set(case.get("expected_codes", []))
                    <= cited_codes,
                    "expected_status_matched": body["status"] == case["expected_status"]
                    if "expected_status" in case
                    else None,
                    "usage": body["usage"],
                    "elapsed_ms": round(1000 * (time.perf_counter() - begin), 3),
                    "response": body,
                }
            )
    return {
        "mode": "live",
        "cases": rows,
        "completed_investigation_fraction": statistics.mean(
            r["status"] == "completed" for r in rows
        ),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    modes = p.add_mutually_exclusive_group()
    modes.add_argument("--live", action="store_true")
    modes.add_argument("--offline", action="store_true")
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--output", default=None)
    p.add_argument("--cases", default=None, help="Comma-separated curated case IDs")
    args = p.parse_args()
    data = json.loads(Path("data/evaluation/agent.json").read_text())
    if not 1 <= args.limit <= 40:
        p.error("limit must be between one and forty")
    config = agent_settings()
    selected = data["cases"][: args.limit]
    if args.cases:
        identifiers = args.cases.split(",")
        selected = [case for case in data["cases"] if case["id"] in identifiers]
        if len(selected) != len(identifiers):
            p.error("Unknown or duplicate case IDs")
    if args.offline:
        result = asyncio.run(offline(data["cases"], config))
        target = "reports/stage4-offline-evaluation.json"
    elif not args.live or not config.configured:
        result = {
            "mode": "live",
            "status": "BLOCKED" if args.live else "NOT_RUN",
            "reason": "Selected provider is not configured locally."
            if not config.configured
            else "Explicit --live opt-in required.",
            "model": config.llm_model,
            "dataset_cases": len(data["cases"]),
            "paid_calls": 0,
            "tool_selection_correctness": None,
            "answer_accuracy": None,
            "actual_token_usage": None,
            "cost": None,
        }
        target = "reports/stage4-live-evaluation.json"
    else:
        result = live(selected)
        target = "reports/stage4-live-evaluation.json"
    result["provider"] = config.llm_provider
    result["model"] = config.llm_model
    target = args.output or target
    Path(target).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in result.items() if k != "cases"}, indent=2))


if __name__ == "__main__":
    main()
