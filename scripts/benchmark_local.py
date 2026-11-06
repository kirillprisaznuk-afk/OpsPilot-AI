"""Bounded Windows benchmark of authenticated, read-only OpsPilot gateway requests."""

import argparse
import json
import platform
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from scripts.evaluate_monitored import memory

GATEWAY = "/api/backend/api/v1/"
SAMPLES = 20
GIB = 1024**3


def check_memory(minimum_ram=1):
    current = memory()
    free = {
        "ram_gib": round(current.free / GIB, 3),
        "commit_gib": round(current.commit_free / GIB, 3),
    }
    if current.free < minimum_ram * GIB or current.commit_free < 2 * GIB:
        raise RuntimeError("Benchmark stopped at the Windows RAM or commit safety threshold")
    return free


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--origin", default="http://127.0.0.1:3106")
    args = parser.parse_args()
    if (
        not args.origin.startswith("http://127.0.0.1:")
        or not args.origin.rsplit(":", 1)[1].isdigit()
    ):
        parser.error("Use the configured loopback frontend origin.")
    account = next(
        x
        for x in json.loads(
            Path(".local-tools/stage5-demo/accounts.json").read_text(encoding="utf-8")
        )["accounts"]
        if x["username"] == "stage5.operator"
    )
    before = check_memory()
    workers = 4 if before["ram_gib"] >= 1.5 else 2
    minimum_ram = 1.5 if workers == 4 else 1
    report = {
        "environment": platform.system() + " " + platform.release(),
        "target": "authenticated production Compose gateway on Windows loopback",
        "samples_per_operation": SAMPLES,
        "maximum_concurrency": workers,
        "ram_stop_threshold_gib": minimum_ram,
        "warmup_excluded": True,
        "memory_before": before,
        "operations": {},
    }
    limits = httpx.Limits(max_connections=workers, max_keepalive_connections=workers)
    with httpx.Client(base_url=args.origin, limits=limits, timeout=15, trust_env=False) as client:
        start = time.perf_counter()
        login = client.post(
            "/api/session",
            headers={"Origin": args.origin},
            json={key: account[key] for key in ("username", "password")},
        )
        login.raise_for_status()
        report["login_ms_single_sample"] = round((time.perf_counter() - start) * 1000, 1)
        session = client.get("/api/session")
        session.raise_for_status()
        headers = {"Origin": args.origin, "X-CSRF-Token": session.json()["csrf"]}
        operations = {
            "dashboard_overview": ("GET", "analytics/overview", None),
            "supplier_detail": ("GET", "analytics/suppliers/1?include_trends=false", None),
            "warehouse_analytics": ("GET", "analytics/inventory?warehouse_id=3", None),
            "knowledge_hybrid": (
                "POST",
                "knowledge/search",
                {
                    "query": "procurement missed receipts escalation interval",
                    "mode": "hybrid",
                    "top_k": 5,
                },
            ),
            "deterministic_investigation": (
                "POST",
                "hybrid/query",
                {
                    "question": (
                        "Compare Supplier 1 delivery performance against its contractual SLA "
                        "and escalation policy."
                    ),
                    "mode": "DETERMINISTIC",
                    "as_of": "2026-09-30",
                },
            ),
            "scoped_tasks": ("GET", "workflows/tasks?limit=20", None),
            "scoped_audit_paged": ("GET", "workflows/audit?limit=20&offset=20", None),
        }

        def timed(operation):
            method, endpoint, payload = operation
            begin = time.perf_counter()
            try:
                response = client.request(method, GATEWAY + endpoint, headers=headers, json=payload)
                duration = (time.perf_counter() - begin) * 1000
                if response.is_error:
                    return duration, f"http_{response.status_code}"
                body = response.json()
                if endpoint == "hybrid/query" and (
                    body["status"] != "completed" or body["usage"]["llm_calls"] != 0
                ):
                    return duration, "unexpected_deterministic_result"
                return duration, None
            except (httpx.HTTPError, ValueError, KeyError) as error:
                return (time.perf_counter() - begin) * 1000, type(error).__name__

        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for name, operation in operations.items():
                    _, warmup_failure = timed(operation)
                    values, failures = [], []
                    for _ in range(SAMPLES // workers):
                        check_memory(minimum_ram)
                        for duration, failure in pool.map(timed, [operation] * workers):
                            if failure:
                                failures.append(failure)
                            else:
                                values.append(duration)
                    report["operations"][name] = {
                        "samples": SAMPLES,
                        "successes": len(values),
                        "failures": failures,
                        "warmup_failure": warmup_failure,
                        "median_ms": round(statistics.median(values), 1) if values else None,
                        "p95_ms": round(
                            statistics.quantiles(values, n=100, method="inclusive")[94], 1
                        )
                        if len(values) >= 20
                        else None,
                        "max_ms": round(max(values), 1) if values else None,
                    }
        finally:
            client.request("DELETE", "/api/session", headers=headers, json={})
    report["memory_after"] = check_memory(minimum_ram)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    assert all(
        not row["failures"] and not row["warmup_failure"] for row in report["operations"].values()
    )


if __name__ == "__main__":
    main()
