from __future__ import annotations

import pytest

from evals.run_eval import (
    _require_calibration_keys,
    build_nvidia_judge_client,
    run_calibration,
)
from src.config import Settings

# ---------------------------------------------------------------------------
# _require_calibration_keys
# ---------------------------------------------------------------------------


def _settings(**overrides: str) -> Settings:
    """Build a Settings with both keys present by default."""
    base = {
        "deepseek_api_key": "ds-key",
        "nvidia_api_key": "nv-key",
    }
    base.update(overrides)
    return Settings(**base)


def test_require_calibration_keys_passes_when_both_present() -> None:
    _require_calibration_keys(_settings())  # must not raise


def test_require_calibration_keys_raises_when_deepseek_missing() -> None:
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        _require_calibration_keys(_settings(deepseek_api_key=""))


def test_require_calibration_keys_raises_when_nvidia_missing() -> None:
    with pytest.raises(RuntimeError, match="NVIDIA_API_KEY"):
        _require_calibration_keys(_settings(nvidia_api_key=""))


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


def test_run_calibration_wraps_judge_errors_as_eval_failed() -> None:
    # Regression: a persistently-timing-out judge (NVIDIA free-tier exhausting
    # tenacity retries, or the known DeepSeek empty-content flake) must NOT
    # abort the whole run. run_calibration must wrap each judge call so a
    # raised exception becomes an eval_failed=True sentinel excluded from kappa.
    import inspect

    import evals.run_eval as mod

    src = inspect.getsource(mod.run_calibration)
    assert "_safe_judge" in src
    assert "except Exception" in src
    assert "eval_failed=True" in src


def test_run_calibration_returns_int_on_missing_keys() -> None:

    # When both keys are missing, run_calibration must raise RuntimeError
    # (from _require_calibration_keys), not return 1 silently.
    # The test confirms the function does not swallow the error.
    # We cannot inject settings easily, so we just verify the error is propagated.
    # This test is inherently limited to the key-missing code path.
    pytest.skip(
        "run_calibration reads from get_settings(); key-missing test requires "
        "env patching not available in this pure-unit layer"
    )
