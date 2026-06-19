"""Tests for the prompt improver: diagnosis flags missing pieces, the rewrite
contains the required sections, and everything runs offline (rule-based) with
no API key."""

import pytest

from improver import diagnose, improve
from improver.rewrite import rewrite_rule_based

WEAK_PROMPT = "pull out the contact details from this email"

REQUIRED_SECTIONS = (
    "Role",
    "Context",
    "Task",
    "Output format",
    "Constraints",
    "Success criteria",
    "If you are unsure",
)


# --- diagnosis -------------------------------------------------------------


def test_diagnosis_flags_weak_prompt_gaps():
    diag = diagnose(WEAK_PROMPT)
    # A bare one-liner has no role, no output format, and no refusal policy.
    assert diag.by_key("role").verdict == "missing"
    assert diag.by_key("output_format").verdict == "missing"
    assert diag.by_key("safety").verdict == "missing"
    # It does have a real instruction verb ("pull out" -> find/extract style).
    assert diag.by_key("task").verdict != "missing"


def test_diagnosis_readiness_is_low_for_weak_prompt():
    diag = diagnose(WEAK_PROMPT)
    assert 0.0 <= diag.readiness <= 0.5


def test_diagnosis_credits_a_well_specified_prompt():
    strong = (
        "You are a meticulous data-extraction assistant. Given the customer email "
        "below, extract the contact fields. Return JSON only with keys name, email, "
        "phone. Do not add prose. For example, input 'call Dana at d@a.io' -> "
        '{"name": "Dana", "email": "d@a.io", "phone": null}. A good answer includes '
        "every key. If a field is not present, use null and do not guess."
    )
    diag = diagnose(strong)
    assert diag.by_key("role").verdict == "present"
    assert diag.by_key("output_format").verdict == "present"
    assert diag.by_key("safety").verdict == "present"
    assert diag.by_key("examples").verdict == "present"
    assert diag.readiness > 0.7


def test_every_criterion_gets_a_finding():
    diag = diagnose(WEAK_PROMPT)
    assert len(diag.findings) == 8
    assert all(f.verdict in {"present", "weak", "missing"} for f in diag.findings)


def test_gaps_are_sorted_worst_first():
    diag = diagnose(WEAK_PROMPT)
    scores = [f.score for f in diag.gaps]
    assert scores == sorted(scores)
    assert all(f.verdict != "present" for f in diag.gaps)


# --- rewrite ---------------------------------------------------------------


def test_rewrite_contains_all_required_sections():
    rewritten = rewrite_rule_based(WEAK_PROMPT)
    for section in REQUIRED_SECTIONS:
        assert f"## {section}" in rewritten, f"rewrite missing '{section}' section"


def test_rewrite_is_deterministic():
    a = rewrite_rule_based(WEAK_PROMPT)
    b = rewrite_rule_based(WEAK_PROMPT)
    assert a == b


def test_rewrite_preserves_the_task_intent():
    rewritten = rewrite_rule_based("summarize this support thread for my manager")
    assert "summarize" in rewritten.lower()


def test_rewrite_injects_refusal_policy_when_missing():
    rewritten = rewrite_rule_based(WEAK_PROMPT)
    low = rewritten.lower()
    assert "null" in low or "unknown" in low
    assert "guess" in low


# --- improve orchestration (offline) ---------------------------------------


def test_improve_runs_offline_rule_based(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = improve(WEAK_PROMPT)
    assert result.backend == "rule-based"
    assert result.improved.startswith("# System prompt")
    assert result.diagnosis.readiness < 1.0


def test_improve_force_rule_based_ignores_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    result = improve(WEAK_PROMPT, force_rule_based=True)
    assert result.backend == "rule-based"


def test_improve_explains_each_gap():
    result = improve(WEAK_PROMPT, force_rule_based=True)
    # One explanation line per gap the diagnosis found.
    assert len(result.explanation) == len(result.diagnosis.gaps)
    joined = " ".join(result.explanation).lower()
    assert "principle" in joined


def test_improve_rejects_empty_input():
    with pytest.raises(ValueError):
        improve("   ")


def test_improve_result_for_strong_prompt_still_rewrites():
    strong = (
        "You are a classifier. Classify the message into {a,b}. Return JSON with "
        "key label. If unsure use unknown and do not guess. Example: 'hi' -> "
        '{"label": "a"}.'
    )
    result = improve(strong, force_rule_based=True)
    assert "## Task" in result.improved
    assert result.explanation  # never empty
