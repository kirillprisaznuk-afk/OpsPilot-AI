from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    llm_provider: Literal["ollama", "openai"] = "ollama"
    llm_model: str | None = Field("qwen3.5:4b", min_length=1, max_length=100)
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_context_tokens: int = Field(32768, ge=8192, le=32768)
    ollama_compact_transport: bool = True
    ollama_reference_output: bool = False
    ollama_tool_selection: bool = False
    ollama_gpu_layers: int | None = Field(None, ge=0, le=99)
    ollama_batch_tokens: int | None = Field(None, ge=32, le=512)
    openai_api_key: SecretStr | None = None
    agent_max_rounds: int = Field(6, ge=1, le=6)
    agent_max_tools: int = Field(12, ge=1, le=12)
    agent_output_tokens: int = Field(2000, ge=256, le=4000)
    agent_usage_tokens: int = Field(64000, ge=1000, le=100000)
    agent_context_bytes: int = Field(120000, ge=4096, le=200000)
    agent_result_bytes: int = Field(48000, ge=2048, le=64000)
    agent_timeout_seconds: float = Field(90, ge=1, le=90)
    agent_tool_timeout_seconds: float = Field(10, ge=0.1, le=20)
    agent_provider_timeout_seconds: float = Field(30, ge=0.1, le=30)
    agent_retries: int = Field(0, ge=0, le=1)
    llm_price_model: str | None = None
    llm_input_usd_per_million: float | None = Field(None, ge=0)
    llm_output_usd_per_million: float | None = Field(None, ge=0)

    @field_validator(
        "llm_model",
        "llm_price_model",
        "llm_input_usd_per_million",
        "llm_output_usd_per_million",
        "ollama_gpu_layers",
        "ollama_batch_tokens",
        mode="before",
    )
    @classmethod
    def optional_environment(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def configured(self):
        if self.llm_provider == "ollama":
            return bool(self.llm_model)
        return bool(
            self.llm_model
            and self.openai_api_key
            and self.openai_api_key.get_secret_value().strip()
        )


@lru_cache
def agent_settings():
    return AgentSettings()
