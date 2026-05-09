from __future__ import annotations

from typing import Protocol

from .browserbase_client import RenderedPage
from .exa_client import ExaResult
from .nvidia_client import LLMResponse


class ExaLike(Protocol):
    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]: ...

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]: ...


class BrowserbaseLike(Protocol):
    async def render(self, url: str) -> RenderedPage | None: ...


class LLMClient(Protocol):
    async def synthesize(
        self,
        system: str,
        context: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...
