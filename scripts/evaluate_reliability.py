"""Sequential real-provider evaluation with independent Stage 2/3 oracle plans.

Fixtures/oracles are evaluation-only. Only question, cutoff and validated
conversation identity are sent to the production API. Results persist per case.
"""

import argparse
import asyncio
import copy
import hashlib
import json
import subprocess
import sys
import time
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx
from app.agent.config import agent_settings
from app.agent.contracts import AgentError

from scripts.evaluate_agent import at, rendered_numeric
from scripts.local_resources import snapshot


async def oracle(case, settings):
    from app.agent.execution import ToolExecutor, parse_arguments

    results = []
    for plan in case.get("calls", []):
        try:
            args = parse_arguments(
                plan["tool"],
                json.dumps(plan["arguments"]),
                date.fromisoformat(case.get("as_of", "2026-09-30")),
            )
        except AgentError as exc:
            if exc.code != case.get("expected_error"):
                raise
            results.append({"tool": plan["tool"], "expected_error": exc.code})
            continue
        payload, ms = await ToolExecutor(settings).run(plan["tool"], args, 20)
        results.append(
            {
                "tool": plan["tool"],
                "arguments": args.model_dump(mode="json"),
                "payload": payload,
                "elapsed_ms": ms,
            }
        )
    return results


def isolated_oracle(case):
    """Release the oracle's native embedding session before real LLM inference."""
    result = subprocess.run(
        [sys.executable, "-m", "scripts.evaluate_reliability", "--oracle-worker"],
        input=json.dumps(case),
        text=True,
        capture_output=True,
        timeout=240,
        check=True,
    )
    return json.loads(result.stdout)


def equal_number(left, right):
    if left is None or right is None:
        return left is right
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except InvalidOperation:
        return left == right


def flatten_arguments(values):
    nested = values.get("query")
    return {**values, **nested} if isinstance(nested, dict) else dict(values)


def document_codes(body):
    cited_ids = {c["document_id"] for c in body["citations"]}
    found, cited = set(), set()

    def walk(value):
        if isinstance(value, dict):
            metadata = value.get("metadata", {})
            if isinstance(metadata, dict) and "code" in metadata:
                found.add(metadata["code"])
                if metadata.get("document_id") in cited_ids:
                    cited.add(metadata["code"])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for evidence in body["evidence"]:
        walk(evidence["payload"])
    return found, cited


def checks(case, body, truth):
    used = {t["tool"] for t in body["tool_trace"] if t["status"] == "success"}
    required = (
        set() if "expected_error" in case else {plan["tool"] for plan in case.get("calls", [])}
    )
    errors = [
        {"tool": t["tool"], "code": t["error_code"], "fields": t.get("error_details")}
        for t in body["tool_trace"]
        if t["status"] != "success"
    ]
    window_ok = all(
        e["payload"].get("window") == expected["payload"].get("window")
        for expected in truth
        if "window" in expected.get("payload", {})
        for e in body["evidence"]
        if e["tool_name"] == expected["tool"]
    )
    metrics = [m for f in body["key_findings"] for m in f["metrics"]]
    final_entities = [
        (e["entity_type"], e["entity_id"])
        for f in body["key_findings"]
        for e in f.get("entities", [])
    ]
    metric_checks = []
    for assertion in case.get("metric_checks", []):
        expected = next(p for p in truth if p["tool"] == assertion["tool"])
        source = at(expected["payload"], assertion["path"])
        wanted = source["value"] if isinstance(source, dict) else source
        candidates = [m for m in metrics if equal_number(m["value"], wanted)]
        if isinstance(source, dict):
            candidates = [
                m
                for m in candidates
                if m["metric"] == source["metric"]
                and m["unit"] == source["unit"]
                and m.get("denominator") == source.get("denominator")
            ]
        relevant = []
        for m in candidates:
            evidence = next(e for e in body["evidence"] if e["evidence_id"] == m["evidence_id"])
            actual_args = flatten_arguments(evidence["arguments"])
            wanted_args = flatten_arguments(expected["arguments"])
            scope_keys = {"supplier_id", "warehouse_id", "department_id", "as_of"}
            if evidence["tool_name"] == assertion["tool"] and all(
                actual_args.get(key) == wanted_args.get(key) for key in scope_keys
            ):
                relevant.append(m)
        metric_checks.append(
            {"assertion": assertion, "oracle_value": wanted, "passed": bool(relevant)}
        )
    ranking = None
    if "ranking" in case:
        query = case["ranking"]
        source = next(p for p in truth if p["tool"] == "compare_suppliers")
        expected = [
            r["entity_id"] for r in source["payload"]["breakdowns"][: query["minimum_rows"]]
        ]
        actual = list(dict.fromkeys(e[1] for e in final_entities if e[0] == "supplier"))
        correct_query = any(
            t["tool"] == "compare_suppliers"
            and t["status"] == "success"
            and t["arguments"]["sort"] == query["sort"]
            and t["arguments"]["direction"] == query["direction"]
            for t in body["tool_trace"]
        )
        selected_metric = all(
            any(
                m["metric"].rsplit(".", 1)[-1] == query["sort"]
                for f in body["key_findings"]
                if any(e["entity_id"] == identifier for e in f.get("entities", []))
                for m in f["metrics"]
            )
            for identifier in expected
        )
        ranking = {
            "expected": expected,
            "actual": actual,
            "query_correct": correct_query,
            "criterion_rendered": selected_metric,
            "passed": actual[: len(expected)] == expected and correct_query and selected_metric,
        }
    found, cited = document_codes(body)
    expected_entities = {
        (kind, identifier)
        for kind, ids in case.get("required_entities", {}).items()
        for identifier in ids
    }
    allowed_statuses = case.get("expected_statuses", [case.get("expected_status", "completed")])
    status_ok = body["status"] in allowed_statuses
    zero = not case.get("zero_inference") or (
        body["usage"]["llm_calls"] == body["usage"]["tool_calls"] == 0 and not body["tool_trace"]
    )
    known = [rendered_numeric(body, assertion) for assertion in case.get("numeric", [])]
    alternatives = {"search_corporate_knowledge": {"build_knowledge_context"}}
    capability_match = all(
        tool in used or bool(alternatives.get(tool, set()) & used) for tool in required
    )
    automatic = {
        "observation_window": window_ok,
        "status": status_ok,
        "required_tools": capability_match,
        "required_entities": expected_entities <= set(final_entities),
        "numeric_references": all(known),
        "independent_metrics": all(m["passed"] for m in metric_checks),
        "required_sources_cited": set(case.get("expected_codes", [])) <= cited,
        "argument_errors_within_limit": len(errors) <= case.get("max_tool_errors", 1),
        "prompt_refusal": zero,
        "ranking": ranking is None or ranking["passed"],
        "not_false_refusal": not case.get("must_not_refuse") or body["status"] != "refused",
    }
    return {
        "deterministic_checks": automatic,
        "deterministic_checks_passed": all(automatic.values()),
        "tool_errors": errors,
        "actual_tools": sorted(used),
        "required_tools": sorted(required),
        "required_numeric_references": known,
        "independent_metrics": metric_checks,
        "ranking": ranking,
        "found_document_codes": sorted(found),
        "cited_document_codes": sorted(cited),
        "final_entities": final_entities,
        "tool_success_fraction": 1 - len(errors) / len(body["tool_trace"])
        if body["tool_trace"]
        else None,
        "invalid_argument_attempts": sum(e["code"] == "invalid_arguments" for e in errors),
        "argument_valid_fraction": 1
        - sum(e["code"] == "invalid_arguments" for e in errors) / len(body["tool_trace"])
        if body["tool_trace"]
        else None,
        "semantic_review": {
            "status": "pending",
            "instruction": case.get("semantic_review"),
            "model_findings": [f["text"] for f in body["key_findings"]],
            "verified_quotations": [q for f in body["key_findings"] for q in f["quotations"]],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=None)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--check-resources", action="store_true")
    parser.add_argument("--output", default="reports/stage4b-live-evaluation.json")
    parser.add_argument("--prepared-oracles", type=Path)
    parser.add_argument("--oracle-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.oracle_worker:
        print(json.dumps(asyncio.run(oracle(json.load(sys.stdin), agent_settings()))))
        return
    original = json.loads(Path("data/evaluation/agent.json").read_text(encoding="utf-8"))["cases"]
    ids = {"A01", "A02", "A03", "A06", "A22", "A23", "A25", "A27"}
    selected = [c for c in original if c["id"] in ids]
    for case in selected:
        if case["id"] in {"A25", "A27"}:
            case.update(expected_status="refused", zero_inference=True)
        if case["id"] == "A23":
            case["max_tool_errors"] = 0
        if case["id"] == "A02":
            case["ranking"] = {"sort": "on_time_rate", "direction": "asc", "minimum_rows": 3}
        if case["id"] == "A03":
            case["required_entities"] = {"sales_order": [1]}
    selected += json.loads(
        Path("data/evaluation/agent_reliability.json").read_text(encoding="utf-8")
    )["cases"]
    if args.cases:
        wanted = args.cases.split(",")
        selected = [c for c in selected if c["id"] in wanted]
        if len(selected) != len(wanted):
            parser.error("Unknown/duplicate case IDs")
    settings = agent_settings()
    if settings.llm_provider != "ollama":
        parser.error("This evaluator permits local Ollama only")
    result = {
        "mode": "offline_oracles" if args.prepare_only else "live_local",
        "cases": [],
        "ready_for_stage5": False,
        "semantic_review_required": True,
    }
    prepared = {}
    if args.prepared_oracles:
        raw = args.prepared_oracles.read_bytes()
        source = json.loads(raw)
        if source.get("mode") != "offline_oracles":
            parser.error("Use a separately prepared real SQL/RAG oracle report")
        prepared = {row["id"]: row for row in source["cases"]}
        result["prepared_oracles"] = {
            "path": str(args.prepared_oracles),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "requirement": "Dataset/corpus must match the independently verified oracle baseline.",
        }
    rows = {}
    provider_missing = False
    with httpx.Client(base_url="http://127.0.0.1:8001", timeout=100, trust_env=False) as client:
        result["runtime_status"] = client.get("/api/v1/agent/status").json()
        if result["runtime_status"]["provider"] != "ollama":
            parser.error("Running API is not using local Ollama")
        if not args.prepare_only:
            result["hardware"] = snapshot(result["runtime_status"]["model"])
            if args.check_resources or not result["hardware"]["admitted"]:
                result["live_status"] = (
                    "READY" if result["hardware"]["admitted"] else "BLOCKED_RESOURCE_PRESSURE"
                )
                result["cases"] = [
                    {
                        "id": c["id"],
                        "execution": "NOT_RUN",
                        "reason": "Resource check only"
                        if args.check_resources
                        else result["live_status"],
                    }
                    for c in selected
                ]
                Path(args.output).write_text(
                    json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
                )
                print(result["live_status"], result["hardware"], flush=True)
                return
        for case in selected:
            row = {
                "id": case["id"],
                "question": case["question"],
                "as_of": case.get("as_of", "2026-09-30"),
            }
            rows[case["id"]] = row
            try:
                if provider_missing and not case.get("zero_inference"):
                    row.update(
                        execution="NOT_RUN", reason="Local provider unavailable after prior case"
                    )
                    raise ValueError("Local provider unavailable; no further inference attempted")
                previous = None
                if "followup_to" in case and not args.prepare_only:
                    previous = rows.get(case["followup_to"], {})
                    if not previous.get("deterministic_checks_passed") or not previous.get(
                        "response", {}
                    ).get("conversation_id"):
                        raise ValueError("Follow-up blocked: preceding ranking was not verified")
                    expected_ids = previous["ranking"]["expected"][:2]
                    case = {
                        **case,
                        "as_of": previous["as_of"],
                        "required_entities": {"supplier": expected_ids},
                        "calls": [
                            {"tool": "get_supplier_performance", "arguments": {"supplier_id": i}}
                            for i in expected_ids
                        ],
                    }
                    row["as_of"] = previous["as_of"]
                    row["expected_followup_supplier_ids"] = expected_ids
                cached = prepared.get(case["id"]) if previous is None else None
                if cached:
                    if (
                        cached["question"] != case["question"]
                        or cached["as_of"] != row["as_of"]
                        or "evaluation_error" in cached
                    ):
                        raise ValueError("Prepared oracle identity/window does not match")
                    row["oracle"] = copy.deepcopy(cached["oracle"])
                    row["oracle_origin"] = "Independent prepared PostgreSQL/RAG snapshot"
                else:
                    row["oracle"] = isolated_oracle(case)
                if previous is not None:
                    references = list(
                        dict.fromkeys(
                            contract["reference"]
                            for output in row["oracle"]
                            for contract in output["payload"].get("contracts", [])
                        )
                    )
                    source_plans = [
                        {"tool": "search_corporate_knowledge", "arguments": {"query": ref}}
                        for ref in references
                    ]
                    extra = isolated_oracle({"calls": source_plans, "as_of": row["as_of"]})
                    row["oracle"].extend(extra)
                    case["calls"] = case["calls"] + source_plans
                    case["expected_codes"] = sorted(
                        {
                            entry["metadata"]["code"]
                            for output in extra
                            for entry in output["payload"].get("evidence", [])
                        }
                    )
                if not args.prepare_only:
                    request = {"question": case["question"], "as_of": row["as_of"]}
                    if "followup_to" in case:
                        request["conversation_id"] = previous["response"]["conversation_id"]
                        request.pop("as_of")
                        row["as_of"] = previous["as_of"]
                    begin = time.perf_counter()
                    response = client.post("/api/v1/agent/query", json=request)
                    row["elapsed_ms"] = round(1000 * (time.perf_counter() - begin), 3)
                    response.raise_for_status()
                    row["response"] = response.json()
                    if row["response"]["termination_reason"] == "provider_connection_error":
                        try:
                            probe = httpx.get(
                                settings.ollama_base_url + "/api/version",
                                timeout=2,
                                trust_env=False,
                            )
                            provider_missing = probe.status_code != 200
                        except httpx.HTTPError:
                            provider_missing = True
                    row.update(checks(case, row["response"], row["oracle"]))
                    row["citation_resolution"] = all(
                        client.get("/api/v1/knowledge/citations/" + c["citation_id"])
                        .json()
                        .get("verified")
                        for c in row["response"]["citations"]
                    )
                    if not row["citation_resolution"]:
                        row["deterministic_checks_passed"] = False
            except Exception as exc:
                row["evaluation_error"] = type(exc).__name__ + ": " + str(exc)
                row["deterministic_checks_passed"] = False
            result["cases"].append(row)
            Path(args.output).write_text(
                json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8", newline="\n"
            )
            print(
                case["id"],
                row.get("response", {}).get("status", "oracle/blocked"),
                row.get("deterministic_checks_passed"),
                flush=True,
            )


if __name__ == "__main__":
    main()
