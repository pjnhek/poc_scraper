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

    anthropic_api_key: str = ""
    exa_api_key: str = ""
    browserbase_api_key: str = ""
    browserbase_project_id: str = ""

    google_application_credentials: str = "./credentials.json"
    google_sheet_id: str = ""

    anthropic_model: str = "claude-sonnet-4-6"
    pipeline_concurrency: int = Field(default=5, ge=1, le=50)

    accounts_csv: Path = Path("inputs/accounts.csv")
    eval_groundedness_threshold: float = 6.0

    def require_for_pipeline(self) -> None:
        missing = [
            name
            for name, value in (
                ("ANTHROPIC_API_KEY", self.anthropic_api_key),
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
