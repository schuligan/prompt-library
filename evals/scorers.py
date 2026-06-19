"""Scorers turn a (raw model output, expectation) pair into a 0..1 score.

Each scorer returns a ``ScoreResult`` with the numeric score and a short note so
the scoreboard can explain *why* a variant lost, not just that it did.

Available scorer kinds (selected by the golden file's ``scorer`` field):

* ``exact_match``      — output, trimmed, equals ``expected`` exactly.
* ``regex``            — ``expected`` (a regex) matches somewhere in the output.
* ``json_schema``      — output parses as JSON and validates against a schema.
* ``json_fields``      — output parses as JSON and the listed fields equal the
                          expected values (partial-credit per field).
* ``keyword``          — all required keywords appear (case-insensitive).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"


@dataclass(frozen=True)
class ScoreResult:
    score: float  # 0.0 .. 1.0
    note: str


# --- helpers ---------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _try_parse_json(raw: str) -> tuple[dict | list | None, bool]:
    """Parse JSON. Returns (value, was_clean).

    ``was_clean`` is False if we had to strip a markdown fence or surrounding
    prose to find the JSON — a signal the output was not pipeline-ready.
    """
    raw = raw.strip()
    try:
        return json.loads(raw), True
    except json.JSONDecodeError:
        pass
    m = _FENCE_RE.search(raw)
    if m:
        try:
            return json.loads(m.group(1)), False
        except json.JSONDecodeError:
            pass
    # last resort: first {...} or [...] span
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = raw.find(opener), raw.rfind(closer)
        if 0 <= start < end:
            try:
                return json.loads(raw[start : end + 1]), False
            except json.JSONDecodeError:
                continue
    return None, False


# Minimal draft-07 validator covering the keywords our schemas use. Avoids a
# third-party dependency so the harness stays light and offline.
def _validate(instance, schema: dict) -> tuple[bool, str]:
    t = schema.get("type")
    if t:
        types = t if isinstance(t, list) else [t]
        if not _type_ok(instance, types):
            return False, f"expected type {types}, got {type(instance).__name__}"
    if instance is None:
        return True, ""
    if "enum" in schema and instance not in schema["enum"]:
        return False, f"{instance!r} not in enum"
    if "pattern" in schema and isinstance(instance, str):
        if not re.search(schema["pattern"], instance):
            return False, f"{instance!r} fails pattern"
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            return False, "below minimum"
        if "maximum" in schema and instance > schema["maximum"]:
            return False, "above maximum"
    if isinstance(instance, str) and "maxLength" in schema:
        if len(instance) > schema["maxLength"]:
            return False, "exceeds maxLength"
    if isinstance(instance, dict) and schema.get("type") == "object" or (
        isinstance(instance, dict) and "properties" in schema
    ):
        for key in schema.get("required", []):
            if key not in instance:
                return False, f"missing required key '{key}'"
        if schema.get("additionalProperties") is False:
            extra = set(instance) - set(schema.get("properties", {}))
            if extra:
                return False, f"unexpected keys {sorted(extra)}"
        for key, subschema in schema.get("properties", {}).items():
            if key in instance:
                ok, why = _validate(instance[key], subschema)
                if not ok:
                    return False, f"{key}: {why}"
    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            ok, why = _validate(item, schema["items"])
            if not ok:
                return False, f"[{i}]: {why}"
    return True, ""


def _type_ok(instance, types: list[str]) -> bool:
    checks = {
        "object": lambda x: isinstance(x, dict),
        "array": lambda x: isinstance(x, list),
        "string": lambda x: isinstance(x, str),
        "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
        "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
        "boolean": lambda x: isinstance(x, bool),
        "null": lambda x: x is None,
    }
    return any(checks.get(t, lambda _: False)(instance) for t in types)


# --- scorers ---------------------------------------------------------------


def score_exact_match(raw: str, expected: str, **_) -> ScoreResult:
    ok = raw.strip() == expected.strip()
    return ScoreResult(1.0 if ok else 0.0, "exact match" if ok else "mismatch")


def score_regex(raw: str, expected: str, **_) -> ScoreResult:
    ok = re.search(expected, raw) is not None
    return ScoreResult(1.0 if ok else 0.0, "regex matched" if ok else "no match")


def score_json_schema(raw: str, schema: str, **_) -> ScoreResult:
    obj, clean = _try_parse_json(raw)
    if obj is None:
        return ScoreResult(0.0, "output is not valid JSON")
    schema_obj = json.loads((SCHEMAS_DIR / schema).read_text())
    valid, why = _validate(obj, schema_obj)
    if not valid:
        return ScoreResult(0.0, f"schema invalid ({why})")
    # Penalise outputs that were not directly parseable (fence/prose wrapped).
    if not clean:
        return ScoreResult(0.5, "valid but needed unwrapping (not JSON-only)")
    return ScoreResult(1.0, "schema-valid, JSON-only")


def score_json_fields(raw: str, expected: dict, **_) -> ScoreResult:
    obj, _clean = _try_parse_json(raw)
    if not isinstance(obj, dict):
        return ScoreResult(0.0, "output is not a JSON object")
    hits = sum(1 for k, v in expected.items() if obj.get(k) == v)
    total = len(expected) or 1
    missing = [k for k, v in expected.items() if obj.get(k) != v]
    note = "all fields correct" if not missing else f"wrong/missing: {missing}"
    return ScoreResult(round(hits / total, 3), note)


def score_keyword(raw: str, expected: list[str], **_) -> ScoreResult:
    low = raw.lower()
    present = [k for k in expected if k.lower() in low]
    total = len(expected) or 1
    missing = [k for k in expected if k.lower() not in low]
    note = "all keywords present" if not missing else f"missing: {missing}"
    return ScoreResult(round(len(present) / total, 3), note)


SCORERS = {
    "exact_match": score_exact_match,
    "regex": score_regex,
    "json_schema": score_json_schema,
    "json_fields": score_json_fields,
    "keyword": score_keyword,
}


def run_scorer(kind: str, raw: str, expectation, **extra) -> ScoreResult:
    if kind not in SCORERS:
        raise KeyError(f"Unknown scorer '{kind}'. Known: {sorted(SCORERS)}")
    # The expectation key in the golden file is named per scorer for readability.
    return SCORERS[kind](raw, expectation, **extra)
