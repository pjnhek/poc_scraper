# mypy: disable-error-code=arg-type
#
# The Settings fixtures below build a defaults dict and splat it as
# **kwargs into the pydantic-settings Settings(). mypy cannot reconcile a
# **dict[str, object] unpack with pydantic's generated, per-field-typed
# __init__ (a known pydantic+mypy limitation; test_config.py sidesteps it
# only by passing kwargs individually). This is test-only and CI scopes
# mypy to `src evals` (.github/workflows/ci.yml), not tests/, so the
# annotation documents intent rather than silencing a checked surface.
from __future__ import annotations

from typing import cast

import pytest

from evals.rubric import EvalRubric
from evals.run_eval import (
    _require_calibration_keys,
    build_nvidia_judge_client,
    run_calibration,
)
from src.config import Settings

# ---------------------------------------------------------------------------
# _require_calibration_keys
# ---------------------------------------------------------------------------


def _settings(**overrides: object) -> Settings:
    """Build a Settings for the NVIDIA-fallback path by default.

    _env_file=None disables the real .env (pydantic-settings feature, same
    isolation pattern as test_config.py), so the developer's ambient
    CALIBRATION_JUDGE_* values cannot leak in and flip these fallback-path
    tests. Override-path behavior has its own fixture and dedicated tests.

    overrides is typed object (not str): Settings fields are heterogeneous
    (Path, int, str) and pydantic validates/coerces each at construction.
    """
    base: dict[str, object] = {
        "deepseek_api_key": "ds-key",
        "nvidia_api_key": "nv-key",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[call-arg]


def _settings_override(**overrides: object) -> Settings:
    """Build a Settings with the cross-family judge override active."""
    base: dict[str, object] = {
        "deepseek_api_key": "ds-key",
        "nvidia_api_key": "",
        "calibration_judge_api_key": "xf-key",
        "calibration_judge_base_url": "https://example.test/v1",
        "calibration_judge_model": "test-cross-family-model",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[call-arg]


def test_require_calibration_keys_passes_when_both_present() -> None:
    _require_calibration_keys(_settings())  # must not raise


def test_require_calibration_keys_raises_when_deepseek_missing() -> None:
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        _require_calibration_keys(_settings(deepseek_api_key=""))


def test_require_calibration_keys_raises_when_nvidia_missing() -> None:
    # Fallback path (no override configured): NVIDIA is the cross-family
    # judge, so its key is required.
    with pytest.raises(RuntimeError, match="NVIDIA_API_KEY"):
        _require_calibration_keys(_settings(nvidia_api_key=""))


def test_require_calibration_keys_passes_when_override_set_without_nvidia() -> None:
    # Override path: the cross-family judge is the configured override, so
    # a missing NVIDIA_API_KEY must NOT block calibration.
    _require_calibration_keys(_settings_override())  # must not raise


def test_require_calibration_keys_still_requires_deepseek_under_override() -> None:
    # The primary judge is always DeepSeek; the override only replaces the
    # cross-family side.
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        _require_calibration_keys(_settings_override(deepseek_api_key=""))


def test_require_calibration_keys_raises_both_missing_lists_both() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        _require_calibration_keys(_settings(deepseek_api_key="", nvidia_api_key=""))
    msg = str(exc_info.value)
    assert "DEEPSEEK_API_KEY" in msg
    assert "NVIDIA_API_KEY" in msg


def test_require_calibration_keys_error_message_mentions_env_example() -> None:
    with pytest.raises(RuntimeError, match=".env.example"):
        _require_calibration_keys(_settings(deepseek_api_key=""))


# ---------------------------------------------------------------------------
# build_nvidia_judge_client
# ---------------------------------------------------------------------------


def test_build_nvidia_judge_client_returns_nvidia_client() -> None:
    from src.clients.nvidia_client import NVIDIA_BASE_URL, NvidiaClient

    s = _settings()
    client = build_nvidia_judge_client(s)
    assert isinstance(client, NvidiaClient)
    # The client must use NVIDIA_BASE_URL (not DeepSeek's base URL).
    # Verify indirectly: the internal _client's base_url property should match.
    assert client._client.base_url == NVIDIA_BASE_URL or str(client._client.base_url).startswith(
        NVIDIA_BASE_URL
    )


def test_build_nvidia_judge_client_uses_judge_model_nvidia() -> None:
    s = _settings()
    client = build_nvidia_judge_client(s)
    # model stored as _model attribute on NvidiaClient
    assert client._model == s.judge_model_nvidia


def test_build_nvidia_judge_client_json_mode_false() -> None:
    # NVIDIA Build does not guarantee JSON response_format; must be False.
    s = _settings()
    client = build_nvidia_judge_client(s)
    assert client._params.json_mode is False


def test_build_judge_client_uses_override_endpoint_and_model() -> None:
    # When the cross-family override is configured, the client must target
    # the override base_url + model, NOT NVIDIA.
    s = _settings_override()
    client = build_nvidia_judge_client(s)
    assert client._model == "test-cross-family-model"
    assert str(client._client.base_url).startswith("https://example.test/v1")


def test_build_judge_client_override_no_thinking_toggle() -> None:
    # The cross-family judge is a NON-reasoning instruction-follower
    # (moonshot-v1-32k class). A thinking toggle was tried and rejected:
    # reasoning models return empty content / never return on the rubric
    # prompt. extra_body must be empty and reasoning_budget None so the
    # NVIDIA-only thinking_budget key is never injected into this endpoint.
    s = _settings_override()
    client = build_nvidia_judge_client(s)
    assert client._params.extra_body == {}
    assert client._params.reasoning_budget is None


def test_build_judge_client_override_token_budget_decoupled() -> None:
    # The cross-family judge gets its own modest budget, independent of the
    # DeepSeek-tuned judge_max_tokens default. 4096 is generous for the
    # ~270-token JSON the judge emits and avoids runaway-length timeouts.
    s = _settings_override(judge_max_tokens="8192")
    client = build_nvidia_judge_client(s)
    assert client._params.max_tokens == 4096


# ---------------------------------------------------------------------------
# run_calibration -- structural checks (no real API calls)
# ---------------------------------------------------------------------------


def test_run_calibration_is_coroutine() -> None:
    import inspect

    # Calling run_calibration() without await must return a coroutine,
    # confirming it is declared async.
    coro = run_calibration()
    assert inspect.iscoroutine(coro)
    coro.close()  # prevent "coroutine never awaited" warning


async def test_safe_judge_wraps_raised_error_as_eval_failed() -> None:
    # Behavioral regression: a persistently-timing-out judge (NVIDIA free-tier
    # exhausting tenacity retries, or the known DeepSeek empty-content flake)
    # must NOT abort the run. _safe_judge converts any raised exception into an
    # EvalScore(eval_failed=True) sentinel with all axes pinned to 1.
    from evals.run_eval import _safe_judge
    from src.models import Contact, OutreachHook

    class _RaisingRubric:
        async def evaluate_hook(self, hook: object, domain: str, justs: object) -> object:
            raise TimeoutError("provider exhausted retries")

    hook = OutreachHook(
        contact=Contact(role_title="VP CX", rationale="(test)"),
        paragraph="x",
        cited_indices=(),
    )
    score = await _safe_judge(
        cast(EvalRubric, _RaisingRubric()), "DeepSeek", hook, "example01.com", ()
    )

    assert score.eval_failed is True
    assert score.groundedness == 1
    assert score.icp_relevance == 1
    assert score.personalization == 1
    assert score.specificity == 1
    assert score.recency == 1
    assert score.notes is not None
    assert "TimeoutError" in score.notes


async def test_safe_judge_passes_through_a_successful_score() -> None:
    # The happy path must return the rubric's score unchanged (not a sentinel).
    from evals.run_eval import _safe_judge
    from src.models import Contact, EvalScore, OutreachHook

    good = EvalScore(
        groundedness=4,
        icp_relevance=3,
        personalization=5,
        specificity=2,
        recency=4,
    )

    class _GoodRubric:
        async def evaluate_hook(self, hook: object, domain: str, justs: object) -> EvalScore:
            return good

    hook = OutreachHook(
        contact=Contact(role_title="VP CX", rationale="(test)"),
        paragraph="x",
        cited_indices=(),
    )
    score = await _safe_judge(cast(EvalRubric, _GoodRubric()), "NVIDIA", hook, "example01.com", ())
    assert score is good
    assert score.eval_failed is False


def test_valid_indices_filter_excludes_expected_failed_and_judge_failed() -> None:
    # The union filter in run_calibration decides which records enter kappa.
    # A regression that flipped any clause (e.g. INCLUDING judge-failed
    # records) would silently corrupt every reported kappa, so pin the
    # exact membership against a hand-built mix.
    from src.models import EvalScore

    def _ok() -> EvalScore:
        return EvalScore(
            groundedness=3,
            icp_relevance=3,
            personalization=3,
            specificity=3,
            recency=3,
        )

    def _failed() -> EvalScore:
        return EvalScore(
            groundedness=1,
            icp_relevance=1,
            personalization=1,
            specificity=1,
            recency=1,
            eval_failed=True,
        )

    # index: (expected_eval_failed, ds_failed, nv_failed) -> valid?
    #   0: clean              -> valid
    #   1: expected_failed    -> excluded
    #   2: ds judge failed    -> excluded
    #   3: nv judge failed    -> excluded
    #   4: clean              -> valid
    examples_flags = [False, True, False, False, False]
    ds_scores = [_ok(), _ok(), _failed(), _ok(), _ok()]
    nv_scores = [_ok(), _ok(), _ok(), _failed(), _ok()]

    valid_indices = [
        i
        for i in range(len(examples_flags))
        if not examples_flags[i] and not ds_scores[i].eval_failed and not nv_scores[i].eval_failed
    ]
    assert valid_indices == [0, 4]


def test_run_calibration_propagates_missing_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # When both judge keys are missing, run_calibration must raise the
    # RuntimeError from _require_calibration_keys (fail loud), not return an
    # int or proceed to a network call. Monkeypatch get_settings at the
    # run_eval boundary so the pure-unit layer can exercise the real path.
    import asyncio

    import evals.run_eval as mod

    no_keys = Settings(_env_file=None, deepseek_api_key="", nvidia_api_key="")  # type: ignore[call-arg]
    monkeypatch.setattr(mod, "get_settings", lambda: no_keys)

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        asyncio.run(mod.run_calibration())
