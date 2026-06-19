"""Unit tests for the scorer primitives."""

import json

import pytest

from evals.scorers import (
    run_scorer,
    score_exact_match,
    score_json_fields,
    score_json_schema,
    score_keyword,
    score_regex,
)


def test_exact_match_trims_and_compares():
    assert score_exact_match("  hello \n", "hello").score == 1.0
    assert score_exact_match("hello", "world").score == 0.0


def test_regex_matches_substring():
    assert score_regex("status: P1 urgent", r"\bP1\b").score == 1.0
    assert score_regex("status: P3", r"\bP1\b").score == 0.0


def test_keyword_partial_credit():
    res = score_keyword("the cat sat", ["cat", "dog"])
    assert res.score == 0.5
    assert "dog" in res.note


def test_json_schema_clean_object_scores_full():
    raw = json.dumps({"name": "Dana", "email": "d@a.io", "phone": "+15550100", "company": None})
    res = score_json_schema(raw, "contact.schema.json")
    assert res.score == 1.0


def test_json_schema_penalises_fenced_output():
    raw = "```json\n" + json.dumps(
        {"name": "Dana", "email": "d@a.io", "phone": "+15550100", "company": None}
    ) + "\n```"
    res = score_json_schema(raw, "contact.schema.json")
    # Valid but not JSON-only -> partial credit, demonstrating the baseline's penalty.
    assert res.score == 0.5


def test_json_schema_rejects_missing_required_key():
    raw = json.dumps({"name": "Dana"})  # missing required keys
    res = score_json_schema(raw, "contact.schema.json")
    assert res.score == 0.0


def test_json_schema_rejects_bad_pattern():
    raw = json.dumps(
        {"name": "Dana", "email": "not-an-email", "phone": None, "company": None}
    )
    res = score_json_schema(raw, "contact.schema.json")
    assert res.score == 0.0


def test_json_fields_partial_credit():
    raw = json.dumps({"label": "track_order", "confidence": 0.9, "rationale": "x"})
    res = score_json_fields(raw, {"label": "track_order"})
    assert res.score == 1.0
    res2 = score_json_fields(raw, {"label": "cancel_order"})
    assert res2.score == 0.0


def test_run_scorer_unknown_kind_raises():
    with pytest.raises(KeyError):
        run_scorer("nope", "x", "y")
