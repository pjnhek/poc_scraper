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

    judge_model: str = "mistralai/mistral-nemotron"
    judge_temperature: float = 0.6
    judge_top_p: float = 0.7
    judge_max_tokens: int = 4096

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
