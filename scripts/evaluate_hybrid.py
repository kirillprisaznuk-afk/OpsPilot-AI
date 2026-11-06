"""Sequential HTTP acceptance. Fixture answers/oracles never enter production prompts."""

import argparse
import hashlib
import json
import statistics
import threading
import time
from pathlib import Path

import httpx

from scripts.evaluate_agent import at
from scripts.evaluate_reliability import checks, flatten_arguments, isolated_oracle
from scripts.hybrid_runtime import measure
from scripts.local_resources import snapshot


def cases():
    original = json.loads(Path("data/evaluation/agent.json").read_text(encoding="utf-8"))["cases"]
    selected = [
        c for c in original if c["id"] in {"A01", "A02", "A03", "A06", "A22", "A23", "A25", "A27"}
    ]
    for case in selected:
        if case["id"] in {"A25", "A27"}:
            case.update(expected_status="refused", zero_inference=True)
        if case["id"] == "A02":
            case["ranking"] = {"sort": "on_time_rate", "direction": "asc", "minimum_rows": 3}
        if case["id"] == "A03":
            case["required_entities"] = {"sales_order": [1]}
    selected += json.loads(
        Path("data/evaluation/agent_reliability.json").read_text(encoding="utf-8")
    )["cases"]
    selected += json.loads(Path("data/evaluation/hybrid.json").read_text(encoding="utf-8"))["cases"]
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=["DETERMINISTIC", "HYBRID_LOCAL"], default="DETERMINISTIC"
    )
    parser.add_argument("--output", default="reports/stage4c-deterministic-evaluation.json")
    parser.add_argument("--cases")
    parser.add_argument("--api-url", default="http://127.0.0.1:8001")
    args = parser.parse_args()
    selected = cases()
    if args.cases:
        selected = [c for c in selected if c["id"] in args.cases.split(",")]
    oracle_path = Path("reports/stage4b-oracles.json")
    prepared = {
        c["id"]: c["oracle"] for c in json.loads(oracle_path.read_text(encoding="utf-8"))["cases"]
    }
    report = {
        "mode": args.mode,
        "endpoint": "/api/v1/hybrid/query",
        "mocked": False,
        "prior_oracle_sha256": hashlib.sha256(oracle_path.read_bytes()).hexdigest(),
        "hardware_before": measure(),
        "cases": [],
    }
    conversations = {}
    samples, stop = [], threading.Event()

    def monitor():
        while not stop.is_set():
            try:
                samples.append(
                    {"measured_at": time.time(), **snapshot(report["hardware_before"]["model"])}
                )
            except (OSError, ValueError):
                samples.append({"measured_at": time.time(), "measurement_failed": True})
            stop.wait(2)

    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    with httpx.Client(base_url=args.api_url, trust_env=False, timeout=100) as client:
        # Container creation is asynchronous. Readiness must precede measured requests.
        for attempt in range(30):
            try:
                client.get("/ready").raise_for_status()
                break
            except httpx.HTTPError:
                if attempt == 29:
                    raise
                time.sleep(1)
        for case in selected:
            payload = {
                "question": case["question"],
                "mode": args.mode,
                "as_of": case.get("as_of", "2026-09-30"),
            }
            if case["id"] == "B15":
                payload.pop("as_of")
                payload["conversation_id"] = conversations.get("B02")
            if case.get("request"):
                payload.update(case["request"])
            started = time.perf_counter()
            response = client.post("/api/v1/hybrid/query", json=payload)
            response.raise_for_status()
            body = response.json()
            elapsed_ms = (time.perf_counter() - started) * 1000
            conversations[case["id"]] = body["conversation_id"]
            truth = prepared.get(case["id"])
            if truth is None:
                truth = isolated_oracle(case)
            result = checks(case, body, truth)
            extra = {
                "every_graph_fact_verified": all(
                    f["verified"] for f in body["evidence_graph"]["facts"]
                ),
                "tool_budget": body["usage"]["tool_calls"] <= 12,
                "mode_honest": args.mode != "DETERMINISTIC" or body["usage"]["llm_calls"] == 0,
                "expected_status": not case.get("hybrid_status")
                or body["status"] in case["hybrid_status"],
            }
            source_map = {e["evidence_id"]: e for e in body["evidence"]}
            comparisons = []
            for fact in body["evidence_graph"]["facts"]:
                if fact["kind"] != "metric":
                    continue
                source = source_map[fact["evidence_id"]]
                actual_scope = flatten_arguments(source["arguments"]) | {
                    k: v for k, v in source["arguments"].items() if k != "query"
                }
                for expected in truth:
                    if expected["tool"] != source["tool_name"] or "payload" not in expected:
                        continue
                    wanted = flatten_arguments(expected["arguments"]) | {
                        k: v for k, v in expected["arguments"].items() if k != "query"
                    }
                    keys = {
                        "as_of",
                        "start_date",
                        "end_date",
                        "supplier_id",
                        "warehouse_id",
                        "product_id",
                        "department_id",
                        "employee_id",
                        "entity_type",
                        "entity_id",
                    }
                    if any(actual_scope.get(k) != wanted.get(k) for k in keys):
                        continue
                    canonical = at(expected["payload"], fact["pointer"])
                    selected_value = (
                        fact["value"]["value"]
                        if fact["pointer"].startswith("/contracts/")
                        else fact["value"]
                    )
                    comparisons.append(
                        {"fact_id": fact["fact_id"], "passed": canonical == selected_value}
                    )
            extra["fresh_oracle_metrics"] = all(c["passed"] for c in comparisons)
            if case.get("expected_scopes"):
                actual = {
                    e["arguments"].get(case["scope_field"])
                    for e in body["evidence"]
                    if e["tool_name"] == case["scope_tool"]
                }
                extra["comparison_scopes"] = actual == set(case["expected_scopes"])
            result.update(hybrid_checks=extra, oracle=truth, oracle_metric_comparisons=comparisons)
            result["passed"] = result["deterministic_checks_passed"] and all(extra.values())
            report["cases"].append(
                {
                    "id": case["id"],
                    "response": body,
                    **result,
                    "http_elapsed_ms": elapsed_ms,
                }
            )
            Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(
                case["id"],
                body["status"],
                result["passed"],
                [k for k, v in result["deterministic_checks"].items() if not v],
                flush=True,
            )
    rows = report["cases"]
    stop.set()
    watcher.join(timeout=15)
    report["hardware_samples"] = samples
    report["hardware_after"] = measure()
    report["summary"] = {
        "cases": len(rows),
        "automatic_passed": sum(c["passed"] for c in rows),
        "llm_calls": sum(c["response"]["usage"]["llm_calls"] for c in rows),
        "reported_tokens": sum(c["response"]["usage"]["total_tokens"] or 0 for c in rows),
        "median_http_ms": statistics.median(c["http_elapsed_ms"] for c in rows),
        "max_http_ms": max(c["http_elapsed_ms"] for c in rows),
        "real_model_interpretations": sum(
            c["response"]["execution"]["model_state"] == "validated" for c in rows
        ),
        "semantic_review": "pending_human_or_agent_source_review",
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
