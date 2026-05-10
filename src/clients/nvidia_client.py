from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from openai import APIError, APIStatusError, AsyncOpenAI, RateLimitError
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
# Free-tier hosted endpoints sometimes silently drop idle connections
# during long reasoning calls. Without an explicit per-call timeout the
# SDK's default lets a single call hang for 5+ minutes before tenacity
# retries. 120s is bounded but generous for typical reasoning calls.
DEFAULT_REQUEST_TIMEOUT_S = 120.0

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResponse:
    text: str


@dataclass(frozen=True)
class GenerationParams:
    temperature: float = 0.6
    top_p: float = 0.7
    max_tokens: int = 4096
    # For NVIDIA reasoning models (e.g. Seed-OSS) that expose a
    # `thinking_budget` extra: -1 = unlimited budget, 0 = disabled,
    # positive = token cap. None means "don't pass the field" so
    # non-reasoning models stay unaffected.
    reasoning_budget: int | None = None
    # OpenAI o-series / DeepSeek pro reasoning effort: "low", "medium",
    # "high", or None. Sent as a top-level kwarg, not in extra_body.
    reasoning_effort: str | None = None
    # When True, ask the provider for guaranteed JSON output via
    # response_format={"type": "json_object"}. Removes code-fence
    # wrapping and prose-around-JSON failure modes on supported endpoints.
    json_mode: bool = False
    # Provider-agnostic extra_body merged into every request. DeepSeek's
    # thinking mode toggles via extra_body={"thinking": {"type": "enabled"}}.
    extra_body: dict[str, Any] = field(default_factory=dict)


class NvidiaClient:
    """OpenAI-compatible client. Despite the name, works for any provider
    that speaks the OpenAI chat-completions wire format (NVIDIA Build,
    DeepSeek, Anthropic via DeepSeek's compat shim, OpenAI itself).

    The class owns its own retry policy and an in-flight cap. The OpenAI
    SDK's built-in retries are disabled (max_retries=0) so we don't
    double-retry with two different backoff schedules.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = NVIDIA_BASE_URL,
        params: GenerationParams | None = None,
        max_in_flight: int = 2,
        client: Any = None,
    ) -> None:
        self._model = model
        self._params = params or GenerationParams()
        self._client = (
            client
            if client is not None
            else AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                max_retries=0,
                timeout=DEFAULT_REQUEST_TIMEOUT_S,
            )
        )
        self._sem = asyncio.Semaphore(max(1, max_in_flight))

    async def synthesize(
        self,
        system: str,
        context: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        user_content = f"{context}\n\n{user_prompt}" if context else user_prompt
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            "temperature": self._params.temperature,
            "top_p": self._params.top_p,
            "max_tokens": max_tokens or self._params.max_tokens,
        }
        if self._params.reasoning_effort is not None:
            kwargs["reasoning_effort"] = self._params.reasoning_effort
        if self._params.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        extra: dict[str, Any] = dict(self._params.extra_body)
        if self._params.reasoning_budget is not None:
            extra["thinking_budget"] = self._params.reasoning_budget
        if extra:
            kwargs["extra_body"] = extra
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(6),
            wait=wait_random_exponential(multiplier=4, max=60),
            retry=retry_if_exception_type((RateLimitError, APIStatusError, APIError)),
            before_sleep=before_sleep_log(log, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                async with self._sem:
                    response = await self._client.chat.completions.create(**kwargs)

        choice = response.choices[0]
        text = choice.message.content or ""
        return LLMResponse(text=text)
