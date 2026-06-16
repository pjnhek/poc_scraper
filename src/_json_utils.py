from __future__ import annotations

import json
from typing import Literal, overload


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return text


@overload
def parse_json(text: str, kind: Literal["object"]) -> dict[str, object] | None: ...


@overload
def parse_json(text: str, kind: Literal["array"]) -> list[dict[str, object]] | None: ...


def parse_json(
    text: str, kind: Literal["object", "array"]
) -> dict[str, object] | list[dict[str, object]] | None:
    """Best-effort JSON extraction from an LLM response.

    Strips markdown code fences and finds the first top-level brace/bracket
    pair. For arrays, also unwraps single-key objects whose value is a
    list (some models wrap arrays in `{"items": [...]}`).
    """
    text = _strip_code_fence(text)
    open_char, close_char = ("{", "}") if kind == "object" else ("[", "]")
    start = text.find(open_char)
    end = text.rfind(close_char)
    if start == -1 or end == -1 or end <= start:
        if kind == "array":
            wrapped = parse_json(text, "object")
            if wrapped is None:
                return None
            for value in wrapped.values():
                if isinstance(value, list):
                    return [v for v in value if isinstance(v, dict)]
        return None
    try:
        loaded = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if kind == "object":
        return loaded if isinstance(loaded, dict) else None
    if not isinstance(loaded, list):
        return None
    return [v for v in loaded if isinstance(v, dict)]


def parse_json_object(text: str) -> dict[str, object] | None:
    return parse_json(text, "object")


def parse_json_array(text: str) -> list[dict[str, object]] | None:
    return parse_json(text, "array")


def clip_score(value: object) -> float:
    """Coerce an LLM-emitted score to a float clamped to [1.0, 5.0].

    A non-numeric value degrades to the 1.0 floor rather than raising, so a
    sloppy writer/judge response yields a low score instead of crashing.
    """
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 1.0
    return max(1.0, min(5.0, f))
