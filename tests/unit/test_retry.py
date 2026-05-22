from __future__ import annotations

import httpx
import pytest
from tenacity import AsyncRetrying, RetryCallState, wait_exponential

from src.clients.retry import parse_retry_after, retry_after_aware_wait

# ---------------------------------------------------------------------------
# parse_retry_after: the D-08 case table (8 cases)
# ---------------------------------------------------------------------------


def test_parse_returns_integer_seconds() -> None:
    resp = httpx.Response(429, headers={"Retry-After": "30"})
    assert parse_retry_after(resp) == 30.0


def test_parse_returns_float_seconds() -> None:
    resp = httpx.Response(429, headers={"Retry-After": "2.5"})
    assert parse_retry_after(resp) == 2.5


def test_parse_returns_none_when_header_absent() -> None:
    resp = httpx.Response(429)
    assert parse_retry_after(resp) is None


def test_parse_returns_none_for_empty_header() -> None:
    resp = httpx.Response(429, headers={"Retry-After": ""})
    assert parse_retry_after(resp) is None


def test_parse_returns_none_for_non_numeric() -> None:
    resp = httpx.Response(429, headers={"Retry-After": "foo"})
    assert parse_retry_after(resp) is None


def test_parse_returns_none_for_negative_seconds() -> None:
    resp = httpx.Response(429, headers={"Retry-After": "-5"})
    assert parse_retry_after(resp) is None


def test_parse_returns_none_for_http_date_form() -> None:
    # D-06: seconds-only. RFC HTTP-date form is intentionally rejected.
    resp = httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2025 07:28:00 GMT"})
    assert parse_retry_after(resp) is None


def test_parse_tolerates_surrounding_whitespace() -> None:
    resp = httpx.Response(429, headers={"Retry-After": "  30  "})
    assert parse_retry_after(resp) == 30.0


# ---------------------------------------------------------------------------
# retry_after_aware_wait: delegation contract
# ---------------------------------------------------------------------------


def _state_with_exception(exc: BaseException) -> RetryCallState:
    """Build a RetryCallState whose outcome carries `exc` as the failure."""

    def _noop() -> None:
        return None

    retry_object = AsyncRetrying()
    state = RetryCallState(retry_object=retry_object, fn=_noop, args=(), kwargs={})
    try:
        raise exc
    except BaseException:
        import sys

        state.set_exception(sys.exc_info())  # type: ignore[arg-type]
    return state


def test_wait_returns_retry_after_when_httpstatuserror_carries_header() -> None:
    fallback = wait_exponential(multiplier=1, min=1, max=15)
    wait = retry_after_aware_wait(fallback=fallback)

    request = httpx.Request("POST", "https://example.invalid/x")
    response = httpx.Response(429, headers={"Retry-After": "2"}, request=request)
    exc = httpx.HTTPStatusError("rate limited", request=request, response=response)
    state = _state_with_exception(exc)

    assert wait(state) == 2.0


def test_wait_falls_back_when_http_status_error_has_no_retry_after() -> None:
    fallback = wait_exponential(multiplier=1, min=1, max=15)
    wait = retry_after_aware_wait(fallback=fallback)

    request = httpx.Request("POST", "https://example.invalid/x")
    response = httpx.Response(429, request=request)
    exc = httpx.HTTPStatusError("rate limited", request=request, response=response)
    state = _state_with_exception(exc)

    # Fallback is wait_exponential; on attempt_number=1 it returns multiplier*1 == 1.0.
    assert wait(state) == fallback(state)


def test_wait_falls_back_when_exception_is_not_http_status_error() -> None:
    fallback = wait_exponential(multiplier=1, min=1, max=15)
    wait = retry_after_aware_wait(fallback=fallback)

    request = httpx.Request("POST", "https://example.invalid/x")
    exc = httpx.ConnectError("boom", request=request)
    state = _state_with_exception(exc)

    assert wait(state) == fallback(state)


def test_wait_falls_back_for_malformed_retry_after() -> None:
    fallback = wait_exponential(multiplier=1, min=1, max=15)
    wait = retry_after_aware_wait(fallback=fallback)

    request = httpx.Request("POST", "https://example.invalid/x")
    response = httpx.Response(
        429, headers={"Retry-After": "Wed, 21 Oct 2025 07:28:00 GMT"}, request=request
    )
    exc = httpx.HTTPStatusError("rate limited", request=request, response=response)
    state = _state_with_exception(exc)

    assert wait(state) == fallback(state)


@pytest.mark.parametrize("retry_after_value, expected", [("30", 30.0), ("0", 0.0)])
def test_wait_returns_exact_retry_after_with_no_cap(
    retry_after_value: str, expected: float
) -> None:
    # D-05: no max, no min, no cap composition. Honor the header exactly.
    fallback = wait_exponential(multiplier=1, min=1, max=15)
    wait = retry_after_aware_wait(fallback=fallback)

    request = httpx.Request("POST", "https://example.invalid/x")
    response = httpx.Response(429, headers={"Retry-After": retry_after_value}, request=request)
    exc = httpx.HTTPStatusError("rate limited", request=request, response=response)
    state = _state_with_exception(exc)

    assert wait(state) == expected
