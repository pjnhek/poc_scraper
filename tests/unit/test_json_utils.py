from __future__ import annotations

from src._json_utils import parse_json_object


def test_parses_plain_json() -> None:
    assert parse_json_object('{"a": 1}') == {"a": 1}


def test_parses_json_with_surrounding_prose() -> None:
    text = 'Here is your answer:\n{"a": 1, "b": "hi"}\nLet me know if that helps.'
    assert parse_json_object(text) == {"a": 1, "b": "hi"}


def test_parses_json_in_code_fence() -> None:
    text = '```json\n{"a": 1}\n```'
    assert parse_json_object(text) == {"a": 1}


def test_parses_json_in_unlabeled_code_fence() -> None:
    text = '```\n{"a": 1}\n```'
    assert parse_json_object(text) == {"a": 1}


def test_returns_none_for_garbage() -> None:
    assert parse_json_object("just words, no braces") is None
    assert parse_json_object("") is None


def test_returns_none_for_array_top_level() -> None:
    assert parse_json_object("[1, 2, 3]") is None


def test_returns_none_for_invalid_json() -> None:
    assert parse_json_object('{"a": ,}') is None


def test_picks_outer_object_with_nested_braces() -> None:
    text = '{"a": {"b": 1}, "c": 2}'
    result = parse_json_object(text)
    assert result is not None
    assert result["c"] == 2
