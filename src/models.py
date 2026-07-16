from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class AccountStatus(StrEnum):
    clean = "clean"
    low_groundedness = "low_groundedness"
    hook_suppressed = "hook_suppressed"
    judge_failed = "judge_failed"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Account(_Frozen):
    domain: str

    @field_validator("domain")
    @classmethod
    def _normalize_domain(cls, v: str) -> str:
        original = v

        def invalid() -> ValueError:
            return ValueError(f"invalid domain: {original!r}")

        if any(ord(char) <= 31 or ord(char) == 127 for char in original):
            raise invalid()

        value = original.strip()
        if not value:
            raise invalid()

        has_scheme = "://" in value
        if not has_scheme and value.startswith("//"):
            raise invalid()

        try:
            parsed = urlsplit(value if has_scheme else f"//{value}")
            hostname = parsed.hostname
            port = parsed.port
        except ValueError:
            raise invalid() from None

        if has_scheme and parsed.scheme.lower() not in {"http", "https"}:
            raise invalid()
        if not has_scheme and parsed.scheme:
            raise invalid()

        authority = parsed.netloc.rsplit("@", 1)[-1]
        if (
            hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or port is not None
            or ":" in authority
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise invalid()

        domain = hostname.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if domain.endswith(".") or len(domain) > 253 or "." not in domain:
            raise invalid()

        labels = domain.split(".")
        if any(not DNS_LABEL.fullmatch(label) for label in labels):
            raise invalid()
        return domain


class Citation(_Frozen):
    url: HttpUrl
    title: str | None = None
    snippet: str | None = None
    retrieved_at: datetime | None = None
    source: Literal["exa", "browserbase"]

    @classmethod
    def make(
        cls,
        url: str,
        source: Literal["exa", "browserbase"],
        *,
        title: str | None = None,
        snippet: str | None = None,
        retrieved_at: datetime | None = None,
    ) -> Citation:
        return cls.model_validate(
            {
                "url": url,
                "source": source,
                "title": title,
                "snippet": snippet,
                "retrieved_at": retrieved_at,
            }
        )


class NewsItem(_Frozen):
    headline: str
    summary: str
    citation: Citation
    published_at: datetime | None = None


class Justification(_Frozen):
    """One numbered piece of retrieved evidence shown to the writer and judge.

    The whole pipeline references retrievals by 1-based `index` so claims can
    cite "[1]" instead of pasting URLs. Both the writer prompt and the judge
    prompt see the same numbered list, which makes citation-checking
    deterministic instead of fuzzy URL matching.
    """

    index: int = Field(ge=1)
    summary: str
    citation: Citation


class Firmographics(_Frozen):
    name: str
    industry: str | None = None
    headcount_range: str | None = None
    tech_signals: tuple[str, ...] = ()
    citations: tuple[Citation, ...] = ()


class Enrichment(_Frozen):
    account: Account
    firmographics: Firmographics | None = None
    news: tuple[NewsItem, ...] = ()
    justifications: tuple[Justification, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return self.firmographics is None and not self.news


class RubricBreakdown(_Frozen):
    support_volume: float = Field(ge=1, le=5)
    ai_maturity: float = Field(ge=1, le=5)
    stage_fit: float = Field(ge=1, le=5)
    channel_breadth: float = Field(ge=1, le=5)
    support_volume_reason: str
    ai_maturity_reason: str
    stage_fit_reason: str
    channel_breadth_reason: str


class ICPScore(_Frozen):
    total: float = Field(ge=1, le=5)
    breakdown: RubricBreakdown
    justification: str
    verdict: str
    supporting_indices: tuple[int, ...] = ()


class Contact(_Frozen):
    role_title: str
    rationale: str


class OutreachHook(_Frozen):
    contact: Contact
    paragraph: str
    # 1-based justification indices the writer claims to have cited.
    # Validated against Enrichment.justifications before this hook is built,
    # so anything in this tuple is guaranteed to resolve.
    cited_indices: tuple[int, ...]


class EvalScore(_Frozen):
    groundedness: float = Field(ge=1, le=5)
    icp_relevance: float = Field(ge=1, le=5)
    personalization: float = Field(ge=1, le=5)
    specificity: float = Field(ge=1, le=5)
    recency: float = Field(ge=1, le=5)
    eval_failed: bool = False
    notes: str | None = None
    flag_threshold: float = Field(default=3.0, ge=1, le=5)

    @property
    def is_flagged(self) -> bool:
        return self.groundedness < self.flag_threshold


class ScoredAccount(_Frozen):
    account: Account
    status: AccountStatus
    enrichment: Enrichment
    score: ICPScore | None = None
    contacts: tuple[Contact, ...] = ()
    hooks: tuple[OutreachHook, ...] = ()
    eval_score: EvalScore | None = None
    error: str | None = None

    @classmethod
    def unscoreable(
        cls,
        account: Account,
        enrichment: Enrichment,
        reason: str,
        status: AccountStatus = AccountStatus.hook_suppressed,
    ) -> ScoredAccount:
        return cls(account=account, status=status, enrichment=enrichment, error=reason)


RetrievalStatus = Literal["ok", "thin", "empty"]


class EvidencePack(_Frozen):
    retrieval_status: RetrievalStatus
    about_text: str = ""
    justifications: tuple[Justification, ...] = ()
    news: tuple[NewsItem, ...] = ()

    @classmethod
    def from_context(
        cls,
        about_text: str,
        news_items: list[NewsItem],
        justifications: tuple[Justification, ...],
        *,
        about_text_min_chars: int,
    ) -> EvidencePack:
        has_news = bool(news_items)
        status: RetrievalStatus
        if not about_text and not has_news:
            status = "empty"
        elif len(about_text) < about_text_min_chars and not has_news:
            status = "thin"
        else:
            status = "ok"
        return cls(
            retrieval_status=status,
            about_text=about_text,
            justifications=justifications,
            news=tuple(news_items),
        )
