"""Fail closed on missing/stale host measurements; inference never cold-loads a model."""

import json
import time
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.agent.contracts import AgentError


class HybridSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HYBRID_", env_file=".env", extra="ignore")
    llm_enabled: bool = True
    model: str = "qwen3.5:2b-q4_K_M"
    resource_file: str = ".local-tools/hybrid/resources.json"
    model_timeout_seconds: float = Field(8, ge=1, le=15)
    max_model_calls: int = Field(2, ge=1, le=2)
    allow_legacy: bool = False


def admission(settings, *, model=None, context=8192):
    try:
        sample = json.loads(Path(settings.resource_file).read_text(encoding="utf-8"))
        age = time.time() - sample["measured_at"]
        resident = sample.get("loaded_model") or {}
        valid = (
            0 <= age <= 8
            and sample.get("owner_verified") is True
            and sample["free_ram_gib"] >= 1.5
            and sample["free_commit_gib"] >= 2
            and sample["free_vram_mib"] >= 512
            and resident.get("name") == (model or settings.model)
            and resident.get("context_length") == context
            and resident.get("size", 0) > 0
            and resident.get("size_vram") == resident.get("size")
        )
    except (OSError, ValueError, KeyError, TypeError):
        valid = False
    if not valid:
        raise AgentError(
            "resource_admission_blocked",
            "Fresh host measurements and a fully GPU-resident local model are required; "
            "free RAM must be at least 1.5 GiB, commit 2 GiB and free VRAM 512 MiB.",
        )
    return sample
