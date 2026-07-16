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

    # Cross-family calibration judge (EVAL-04 / D-08). The collusion signal
    # only needs the second judge to be a DIFFERENT model family than the
    # DeepSeek writer+judge; the specific provider is not load-bearing. The
    # free NVIDIA endpoint is unreliable for a 25-record batch (drops
    # connections, exhausts retries), so the cross-family judge is
    # overridable via env. When all three are empty, calibration falls back
    # to the NVIDIA judge (locked-matrix default). When set, any
    # OpenAI-compatible endpoint works (the generic NvidiaClient speaks the
    # OpenAI wire format). Vendor specifics live only in the gitignored .env;
    # no vendor name appears in code or committed config.
    calibration_judge_api_key: str = ""
    calibration_judge_base_url: str = ""
    calibration_judge_model: str = ""

    # DeepSeek defaults. Both on v4-flash for demo-friendly latency.
    # Writer runs without thinking; judge runs WITH thinking enabled
    # plus reasoning_effort="medium". The thinking-mode toggle creates
    # meaningful (not perfect) separation between writer and judge
    # outputs while keeping each call to ~5-10 sec.
    #
    # Set JUDGE_MODEL_DEEPSEEK=deepseek-v4-pro and JUDGE_REASONING_EFFORT_DEEPSEEK=high
    # for more rigorous reasoning (~30-60s per call, recommended for
    # offline analysis runs but too slow for a live demo).
    writer_model_deepseek: str = "deepseek-v4-flash"
    judge_model_deepseek: str = "deepseek-v4-flash"
    # Reasoning effort for the DeepSeek judge: "low" | "medium" | "high".
    # Sent as a top-level kwarg, separate from thinking-mode toggle.
    judge_reasoning_effort_deepseek: str = "medium"

    # Generation params (provider-agnostic). Current reasoning models
    # (DeepSeek v4, Kimi k2.x, and the o-series / Gemini families) are
    # tuned for temperature 1.0 and degrade if it is altered; the reasoning
    # trace, not a cold sampler, supplies judge consistency now. So both
    # roles run at 1.0.
    #
    # judge_max_tokens is the budget for the PRIMARY (DeepSeek production)
    # judge. 8192 = 2x the long-proven 4096, enough for a medium-effort
    # thinking trace plus the JSON answer WITHOUT runaway length: at 32768
    # the DeepSeek judge generated responses so long the connection timed
    # out (~2min/attempt x 6 retries, unusable). The cross-family
    # calibration judge sets its own larger budget on its override path
    # (it tolerates and needs more headroom); see build_nvidia_judge_client.
    writer_temperature: float = 1.0
    writer_top_p: float = 0.95
    writer_max_tokens: int = 8192

    judge_temperature: float = 1.0
    judge_top_p: float = 0.95
    judge_max_tokens: int = 8192
    # NVIDIA-specific reasoning budget. -1 = unlimited, 0 = disabled,
    # positive = cap. Only applies when llm_provider == "nvidia" and the
    # judge model is a reasoning model (Seed-OSS, Nemotron reasoning).
    # On DeepSeek, reasoning is toggled separately via the thinking-mode
    # extra_body (see clients/nvidia_client.py).
    judge_reasoning_budget: int = 0

    pipeline_concurrency: int = Field(default=5, ge=1, le=50)
    # Per-LLM-client cap on simultaneous in-flight requests. Prevents
    # rate-limiting on free-tier providers. DeepSeek tolerates higher
    # parallelism so the default is permissive; bump down for NVIDIA
    # if you hit 429s.
    llm_max_in_flight: int = Field(default=6, ge=1, le=50)
    # Optional: cap how many domains the pipeline processes from accounts.csv.
    # Useful for demos and free-tier rate-limit avoidance. Unset = process all.
    run_limit: int | None = Field(default=None, ge=1)

    accounts_csv: Path = Path("inputs/accounts.csv")

    # Replay mode (D-15): when set, build_deps swaps real Exa/Browserbase/LLM
    # clients for the ReplayExa/ReplayBrowserbase/ReplayLLM stubs in
    # src/clients/replay.py pointed at this directory. No live API calls;
    # require_for_pipeline skips the API-key checks in this mode.
    demo_bundle: Path | None = None
    # Recording mode (D-17): when set, build_deps wraps the real clients in
    # the tee wrappers in src/clients/replay.py that mirror each
    # request/response to this directory. Live API keys are still required
    # because the inner clients still call the live providers.
    record_bundle: Path | None = None

    # MCP server tier override (MCP-06): forces the thin (Exa-only) tier
    # regardless of which keys are present. Used by the hosted demo so a
    # misconfigured or leaked full-tier key never gets exercised there.
    mcp_demo_mode: bool = False

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

    @property
    def calibration_judge_overridden(self) -> bool:
        """True when an explicit cross-family calibration judge is configured.

        Requires all three of api_key, base_url, and model so a half-set
        override fails loud at config time rather than silently falling back
        to NVIDIA mid-run.
        """
        return bool(
            self.calibration_judge_api_key
            and self.calibration_judge_base_url
            and self.calibration_judge_model
        )

    def require_for_pipeline(self) -> None:
        # Replay mode reads from disk; no live API keys required. Recording
        # mode (record_bundle) still requires live keys because the wrappers
        # call the real clients, so there is no early-return for it (D-15).
        if self.demo_bundle is not None:
            return
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

    def mcp_tier(self) -> Literal["thin", "full"]:
        """Resolve the MCP server's capability tier once at startup.

        Thin = retrieval-only (Exa, optional Browserbase fallback). Full =
        adds writer/judge LLM tooling (registered in Phase 12). EXA_API_KEY
        is required for either tier, so its absence fails fast before the
        demo-mode early return.
        """
        if not self.exa_api_key:
            raise RuntimeError(
                "missing required env vars for MCP server: EXA_API_KEY. See .env.example."
            )
        if self.mcp_demo_mode:
            return "thin"
        provider = self.resolved_provider
        provider_key = self.deepseek_api_key if provider == "deepseek" else self.nvidia_api_key
        if provider_key and self.browserbase_api_key and self.browserbase_project_id:
            return "full"
        return "thin"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
