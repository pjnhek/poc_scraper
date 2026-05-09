from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    nvidia_api_key: str = ""
    exa_api_key: str = ""
    browserbase_api_key: str = ""
    browserbase_project_id: str = ""

    google_application_credentials: str = "./credentials.json"
    google_sheet_id: str = ""

    # Two different model families on purpose: writer is hot for creativity,
    # judge is cold for consistency, and a different family avoids the
    # self-grading bias that shows up when the same model writes and judges.
    writer_model: str = "minimaxai/minimax-m2.7"
    writer_temperature: float = 1.0
    writer_top_p: float = 0.95
    writer_max_tokens: int = 8192

    judge_model: str = "bytedance/seed-oss-36b-instruct"
    judge_temperature: float = 0.3
    judge_top_p: float = 0.95
    judge_max_tokens: int = 4096
    # Bounded reasoning budget keeps room in max_tokens for the final JSON.
    # -1 = unlimited reasoning (only safe with a much larger max_tokens),
    # 0 = disabled, positive int = cap. Only applied if the judge model
    # supports the thinking_budget extra (Seed-OSS, Nemotron reasoning).
    judge_reasoning_budget: int = 1024

    pipeline_concurrency: int = Field(default=5, ge=1, le=50)

    accounts_csv: Path = Path("inputs/accounts.csv")

    def require_for_pipeline(self) -> None:
        missing = [
            name
            for name, value in (
                ("NVIDIA_API_KEY", self.nvidia_api_key),
                ("EXA_API_KEY", self.exa_api_key),
                ("BROWSERBASE_API_KEY", self.browserbase_api_key),
                ("BROWSERBASE_PROJECT_ID", self.browserbase_project_id),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"missing required env vars for live pipeline: {', '.join(missing)}. "
                "See .env.example."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
