from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["deepseek", "nvidia"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    nvidia_api_key: str = ""
    deepseek_api_key: str = ""
    exa_api_key: str = ""
    browserbase_api_key: str = ""
    browserbase_project_id: str = ""

    google_application_credentials: str = "./credentials.json"
    google_sheet_id: str = ""

    # Provider for writer + judge. Defaults to "deepseek" because the free
    # NVIDIA Build endpoint drops connections during reasoning calls. Set
    # to "nvidia" to use the original free-preview models. Picked
    # automatically: if DEEPSEEK_API_KEY is set, deepseek wins; otherwise
    # falls back to nvidia.
    llm_provider: LLMProvider | None = None

    # NVIDIA defaults. Used when llm_provider == "nvidia".
    writer_model_nvidia: str = "minimaxai/minimax-m2.7"
    judge_model_nvidia: str = "bytedance/seed-oss-36b-instruct"

    # DeepSeek defaults. Writer = v4-flash (cheaper, no thinking).
    # Judge = v4-pro with thinking + reasoning_effort=high (currently 75%
    # off until 2026/05/31; even after the discount, the reasoning lift
    # is worth ~$0.40 on a 10-domain run).
    writer_model_deepseek: str = "deepseek-v4-flash"
    judge_model_deepseek: str = "deepseek-v4-pro"
    # Reasoning effort for the DeepSeek judge: "low" | "medium" | "high".
    # Sent as a top-level kwarg, separate from thinking-mode toggle.
    judge_reasoning_effort_deepseek: str = "high"

    # Generation params (provider-agnostic). Writer hot for creativity,
    # judge cold for consistency.
    writer_temperature: float = 1.0
    writer_top_p: float = 0.95
    writer_max_tokens: int = 8192

    judge_temperature: float = 0.3
    judge_top_p: float = 0.95
    judge_max_tokens: int = 4096
    # NVIDIA-specific reasoning budget. -1 = unlimited, 0 = disabled,
    # positive = cap. Only applies when llm_provider == "nvidia" and the
    # judge model is a reasoning model (Seed-OSS, Nemotron reasoning).
    # On DeepSeek, reasoning is toggled separately via the thinking-mode
    # extra_body (see clients/nvidia_client.py).
    judge_reasoning_budget: int = 0

    pipeline_concurrency: int = Field(default=5, ge=1, le=50)
    # Optional: cap how many domains the pipeline processes from accounts.csv.
    # Useful for demos and free-tier rate-limit avoidance. Unset = process all.
    run_limit: int | None = Field(default=None, ge=1)

    accounts_csv: Path = Path("inputs/accounts.csv")

    @property
    def resolved_provider(self) -> LLMProvider:
        if self.llm_provider:
            return self.llm_provider
        if self.deepseek_api_key:
            return "deepseek"
        return "nvidia"

    @property
    def writer_model(self) -> str:
        if self.resolved_provider == "deepseek":
            return self.writer_model_deepseek
        return self.writer_model_nvidia

    @property
    def judge_model(self) -> str:
        if self.resolved_provider == "deepseek":
            return self.judge_model_deepseek
        return self.judge_model_nvidia

    def require_for_pipeline(self) -> None:
        provider = self.resolved_provider
        missing: list[str] = []
        if provider == "deepseek" and not self.deepseek_api_key:
            missing.append("DEEPSEEK_API_KEY")
        if provider == "nvidia" and not self.nvidia_api_key:
            missing.append("NVIDIA_API_KEY")
        for name, value in (
            ("EXA_API_KEY", self.exa_api_key),
            ("BROWSERBASE_API_KEY", self.browserbase_api_key),
            ("BROWSERBASE_PROJECT_ID", self.browserbase_project_id),
        ):
            if not value:
                missing.append(name)
        if missing:
            raise RuntimeError(
                f"missing required env vars for live pipeline: {', '.join(missing)}. "
                "See .env.example."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
