"""Read-only Windows evaluation admission for the measured local Qwen 4B profile."""

import ctypes
import os
import shutil
import subprocess

import httpx


def snapshot(model):
    result = {"model": model, "admitted": True, "reasons": []}
    if os.name != "nt":
        return {**result, "measurement": "Windows admission not applicable"}

    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong)
            for name in (
                "total_physical",
                "available_physical",
                "total_page",
                "available_page",
                "total_virtual",
                "available_virtual",
                "available_extended",
            )
        ]

    memory = Memory()
    memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise OSError("Could not measure available physical RAM")
    result["free_ram_gib"] = round(memory.available_physical / 1024**3, 3)
    result["total_ram_gib"] = round(memory.total_physical / 1024**3, 3)
    nvidia = shutil.which("nvidia-smi") or r"C:\Windows\System32\nvidia-smi.exe"
    try:
        output = subprocess.check_output(
            [
                nvidia,
                "--query-gpu=memory.free,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=10,
        )
        free, total = map(int, output.splitlines()[0].split(","))
        result.update(free_vram_mib=free, total_vram_mib=total)
    except (OSError, subprocess.SubprocessError, ValueError):
        result["reasons"].append("GPU free-memory measurement is unavailable for this benchmark")
        free = 0
    try:
        with httpx.Client(trust_env=False, timeout=5) as client:
            loaded = client.get("http://127.0.0.1:11434/api/ps").json().get("models", [])
    except (httpx.HTTPError, ValueError):
        loaded = []
        result["reasons"].append("Local Ollama API is unavailable")
    resident = next((m for m in loaded if m.get("name") == model), None)
    result["loaded_model"] = resident
    result["minimum_free_ram_gib"] = 1.5
    result["minimum_free_vram_mib"] = 512 if resident else 4096
    if result["free_ram_gib"] < result["minimum_free_ram_gib"]:
        result["reasons"].append("Free physical RAM is below the measured profile's RAM margin")
    if free < result["minimum_free_vram_mib"]:
        result["reasons"].append("Insufficient free GPU memory for the measured Qwen 4B profile")
    result["admitted"] = not result["reasons"]
    return result
