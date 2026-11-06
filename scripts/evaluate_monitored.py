"""Windows-only guarded evaluation; touches only the verified project Ollama tree.

This is an empirical resource trial, not a business-quality acceptance assertion.
"""

import argparse
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes as w
from pathlib import Path


class Memory(ctypes.Structure):
    _fields_ = [("length", w.DWORD), ("load", w.DWORD)] + [
        (name, ctypes.c_ulonglong)
        for name in (
            "total",
            "free",
            "commit_limit",
            "commit_free",
            "virtual",
            "virtual_free",
            "extra",
        )
    ]


class Value(ctypes.Structure):
    _fields_ = [("status", w.DWORD), ("value", ctypes.c_double)]


def memory():
    value = Memory()
    value.length = ctypes.sizeof(value)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
        raise OSError("Cannot measure available RAM")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases")
    parser.add_argument("--prepared-oracles", default="reports/stage4b-oracles.json")
    parser.add_argument("--output", default="reports/stage4b-monitored-evaluation.json")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This measured resource trial supports Windows only")
    root = Path(__file__).resolve().parents[1]
    server = int((root / ".local-tools/ollama/server.pid").read_text().strip())
    executable = str(root / ".local-tools/ollama/ollama.exe").replace("'", "''")
    runtime = str(root / ".local-tools/ollama").replace("'", "''")
    ownership = (
        f"$taskServer=Get-CimInstance Win32_Process -Filter 'ProcessId={server}'; "
        f"if ($taskServer.ExecutablePath -ne '{executable}') {{ exit 2 }}; "
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ownership], check=True)
    stop_command = (
        ownership
        + "Get-CimInstance Win32_Process | Where-Object { "
        + f"$_.ParentProcessId -eq {server} -and $_.ExecutablePath.StartsWith('{runtime}\\') "
        + "} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; "
        + f"Stop-Process -Id {server} -Force"
    )
    pdh = ctypes.WinDLL("pdh")
    query = w.HANDLE()
    pdh.PdhOpenQueryW.argtypes = [w.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(w.HANDLE)]
    pdh.PdhAddEnglishCounterW.argtypes = [
        w.HANDLE,
        w.LPCWSTR,
        ctypes.c_size_t,
        ctypes.POINTER(w.HANDLE),
    ]
    pdh.PdhCollectQueryData.argtypes = [w.HANDLE]
    pdh.PdhGetFormattedCounterValue.argtypes = [
        w.HANDLE,
        w.DWORD,
        ctypes.POINTER(w.DWORD),
        ctypes.POINTER(Value),
    ]
    pdh.PdhCloseQuery.argtypes = [w.HANDLE]
    if pdh.PdhOpenQueryW(None, 0, ctypes.byref(query)):
        raise OSError("Cannot initialize paging observation")
    counters = {}
    for name in ("Pages Input/sec", "Pages Output/sec"):
        handle = w.HANDLE()
        if pdh.PdhAddEnglishCounterW(query, "\\Memory\\" + name, 0, ctypes.byref(handle)) == 0:
            counters[name] = handle
    pdh.PdhCollectQueryData(query)
    initial = memory()
    if initial.free < 1.5 * 1024**3 or initial.commit_free < 2 * 1024**3:
        parser.error("Insufficient measured reserve for a resident-model trial")
    samples, unsafe = [], []
    done = threading.Event()
    begin = time.monotonic()

    def observe():
        while not done.wait(0.25):
            try:
                current = memory()
            except OSError as exc:
                unsafe.append({"measurement_error": str(exc)})
                subprocess.run(["powershell", "-NoProfile", "-Command", stop_command], check=True)
                return
            row = {
                "seconds": round(time.monotonic() - begin, 3),
                "free_ram_mib": round(current.free / 1024**2, 3),
                "commit_free_gib": round(current.commit_free / 1024**3, 3),
            }
            pdh.PdhCollectQueryData(query)
            for name, handle in counters.items():
                value = Value()
                if (
                    pdh.PdhGetFormattedCounterValue(handle, 0x200, None, ctypes.byref(value)) == 0
                    and value.status == 0
                ):
                    row[name] = value.value
            samples.append(row)
            if current.free < 512 * 1024**2 or current.commit_free < 2 * 1024**3:
                unsafe.append(row)
                subprocess.run(["powershell", "-NoProfile", "-Command", stop_command], check=True)
                return

    thread = threading.Thread(target=observe, daemon=True)
    thread.start()
    command = [
        sys.executable,
        "-m",
        "scripts.evaluate_reliability",
        "--prepared-oracles",
        args.prepared_oracles,
        "--output",
        args.output,
    ]
    if args.cases:
        command.extend(["--cases", args.cases])
    try:
        result = subprocess.run(command, cwd=root, check=False)
    finally:
        done.set()
        thread.join(timeout=10)
        pdh.PdhCloseQuery(query)
        report = {
            "purpose": "Empirical memory trial, not semantic acceptance",
            "server_pid": server,
            "initial_free_ram_mib": round(initial.free / 1024**2, 3),
            "minimum_free_ram_mib": min((s["free_ram_mib"] for s in samples), default=None),
            "abort_floor_mib": 512,
            "aborted": bool(unsafe),
            "unsafe_samples": unsafe,
            "elapsed_seconds": round(time.monotonic() - begin, 3),
            "samples": samples,
        }
        Path(args.output).with_suffix(".memory.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
