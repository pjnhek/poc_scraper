from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from anthropic import APIError, APIStatusError, AsyncAnthropic
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


@dataclass(frozen=True)
class CachedSynthesis:
    text: str
    cache_read_tokens: int
    cache_creation_tokens: int


class AnthropicClient:
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 1024,
        client: Any = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._client = client if client is not None else AsyncAnthropic(api_key=api_key)

    @property
    def messages(self) -> Any:
        return self._client.messages

    async def synthesize(
        self,
        system: str,
        cached_context: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> CachedSynthesis:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=1, min=1, max=20),
            retry=retry_if_exception_type((APIStatusError, APIError)),
            reraise=True,
        ):
            with attempt:
                response = await self.messages.create(
                    model=self._model,
                    max_tokens=max_tokens or self._max_tokens,
                    system=[
                        {"type": "text", "text": system},
                    ],
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": cached_context,
                                    "cache_control": {"type": "ephemeral"},
                                },
                                {"type": "text", "text": user_prompt},
                            ],
                        }
                    ],
                )

        text_blocks = [b.text for b in response.content if getattr(b, "type", "") == "text"]
        usage = response.usage
        return CachedSynthesis(
            text="".join(text_blocks),
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )
