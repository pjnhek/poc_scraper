from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openai import APIError, APIStatusError, AsyncOpenAI
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


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


class NvidiaClient:
    """OpenAI-compatible client for the NVIDIA Build endpoint.

    Same `synthesize` shape as the rest of the codebase: a system prompt,
    a cached_context block, a user prompt, and an optional max_tokens
    override. NVIDIA does not expose Anthropic-style explicit cache
    control; the cached_context arg is just concatenated into the user
    message. We keep the field names so the protocol stays uniform.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        params: GenerationParams | None = None,
        client: Any = None,
    ) -> None:
        self._model = model
        self._params = params or GenerationParams()
        self._client = (
            client if client is not None else AsyncOpenAI(api_key=api_key, base_url=NVIDIA_BASE_URL)
        )

    async def synthesize(
        self,
        system: str,
        cached_context: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> CachedSynthesis:
        user_content = f"{cached_context}\n\n{user_prompt}" if cached_context else user_prompt
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=1, min=1, max=20),
            retry=retry_if_exception_type((APIStatusError, APIError)),
            reraise=True,
        ):
            with attempt:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=self._params.temperature,
                    top_p=self._params.top_p,
                    max_tokens=max_tokens or self._params.max_tokens,
                )

        choice = response.choices[0]
        text = choice.message.content or ""
        return CachedSynthesis(
            text=text,
            cache_read_tokens=0,
            cache_creation_tokens=0,
        )
