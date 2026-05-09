from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
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

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CachedSynthesis:
    text: str
    cache_read_tokens: int
    cache_creation_tokens: int


@dataclass(frozen=True)
class GenerationParams:
    temperature: float = 0.6
    top_p: float = 0.7
    max_tokens: int = 4096
    # For reasoning models (e.g. Seed-OSS): -1 = unlimited budget, 0 =
    # disabled, positive = token cap. None means "don't pass the field"
    # so non-reasoning models stay unaffected.
    reasoning_budget: int | None = None


class NvidiaClient:
    """OpenAI-compatible client for the NVIDIA Build endpoint.

    Same `synthesize` shape as the rest of the codebase. NVIDIA's free
    tier rate-limits aggressively, so this client owns its own retry
    policy and an in-flight cap. The OpenAI SDK's built-in retries are
    disabled (max_retries=0) so we don't double-retry with two different
    backoff schedules.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        params: GenerationParams | None = None,
        max_in_flight: int = 2,
        client: Any = None,
    ) -> None:
        self._model = model
        self._params = params or GenerationParams()
        self._client = (
            client
            if client is not None
            else AsyncOpenAI(api_key=api_key, base_url=NVIDIA_BASE_URL, max_retries=0)
        )
        self._sem = asyncio.Semaphore(max(1, max_in_flight))

    async def synthesize(
        self,
        system: str,
        cached_context: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> CachedSynthesis:
        user_content = f"{cached_context}\n\n{user_prompt}" if cached_context else user_prompt
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
        if self._params.reasoning_budget is not None:
            kwargs["extra_body"] = {"thinking_budget": self._params.reasoning_budget}
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
        return CachedSynthesis(
            text=text,
            cache_read_tokens=0,
            cache_creation_tokens=0,
        )
