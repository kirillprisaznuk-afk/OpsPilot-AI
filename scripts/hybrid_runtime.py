"""Windows host measurements for the hybrid API. No downloads or global settings."""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import httpx

from scripts.evaluate_monitored import memory
from scripts.local_resources import snapshot

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".local-tools/hybrid/resources.json"
MODEL = "qwen3.5:2b-q4_K_M"


def owner():
    if os.name != "nt":
        return False
    try:
        pid = int((ROOT / ".local-tools/ollama/server.pid").read_text(encoding="utf-8").strip())
        executable = str(ROOT / ".local-tools/ollama/ollama.exe").replace("'", "''")
        check = (
            f"$taskServer=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}'; "
            f"if ($taskServer.ExecutablePath -ne '{executable}') {{ exit 2 }}"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", check],
            check=True,
            capture_output=True,
            timeout=10,
        )
        return True
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def measure():
    sample = snapshot(MODEL)
    if os.name == "nt":
        sample["free_commit_gib"] = round(memory().commit_free / 1024**3, 3)
        if sample["free_commit_gib"] < 2:
            sample["admitted"] = False
            sample["reasons"].append("Free commit headroom is below 2 GiB")
    sample.update(measured_at=time.time(), owner_verified=owner())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(sample, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    return sample


def warmup():
    sample = measure()
    if not sample["admitted"] or not sample["owner_verified"]:
        return {"status": "BLOCKED", "measurement": sample}
    # Launcher controls only the portable project-owned process and existing weights.
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-File",
            str(ROOT / "scripts/start_ollama.ps1"),
            "-Model",
            MODEL,
            "-ContextTokens",
            "8192",
            "-BatchTokens",
            "128",
        ],
        check=True,
        timeout=240,
    )
    return {"status": "warmup_executed", "measurement": measure()}


def watch():
    while True:
        sample = measure()
        if (
            sample.get("loaded_model")
            and sample.get("owner_verified")
            and (sample.get("free_ram_gib", 0) < 0.5 or sample.get("free_commit_gib", 0) < 2)
        ):
            # Emergency unloading touches the selected OpsPilot model only. No cold load.
            try:
                with httpx.Client(trust_env=False, timeout=2) as client:
                    client.post(
                        "http://127.0.0.1:11434/api/generate",
                        json={
                            "model": MODEL,
                            "keep_alive": 0,
                        },
                    ).raise_for_status()
            except httpx.HTTPError:
                pass
            (OUTPUT.parent / "pressure-event.json").write_text(
                json.dumps(sample, indent=2), encoding="utf-8"
            )
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--warmup", action="store_true")
    args = parser.parse_args()
    if args.watch:
        watch()
    else:
        print(json.dumps(warmup() if args.warmup else measure(), indent=2))


if __name__ == "__main__":
    main()
