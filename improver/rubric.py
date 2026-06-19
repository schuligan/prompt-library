"""The diagnostic rubric.

Each criterion is one axis we check a raw prompt against. The set mirrors the
techniques the rest of the library teaches (role priming, explicit context,
schema-constrained output, null/refusal policies, few-shot, success criteria),
so the improver and the prompt library speak the same vocabulary.

A criterion is intentionally *data*, not code: the detectors live in
``diagnose.py`` and reference these by ``key``. Keeping the rubric declarative
makes it cheap to add a criterion and keeps the diagnosis logic readable.
"""

from __future__ import annotations

from dataclasses import dataclass

# Verdicts a criterion can receive, worst -> best. The numeric weight is used to
# turn the per-criterion verdicts into a single 0..1 readiness score.
VERDICT_SCORE = {"missing": 0.0, "weak": 0.5, "present": 1.0}


@dataclass(frozen=True)
class Criterion:
    key: str
    title: str
    # Why this matters, one line — surfaced in the diagnosis output.
    rationale: str
    # The library principle / prompt that teaches this, for the explanation.
    principle: str


RUBRIC: tuple[Criterion, ...] = (
    Criterion(
        key="role",
        title="Explicit role",
        rationale="A primed persona sets the model's frame, vocabulary, and bar.",
        principle="role priming (see role-prompts/)",
    ),
    Criterion(
        key="context",
        title="Sufficient context",
        rationale="State the audience, domain, and inputs so the model isn't guessing.",
        principle="context sufficiency",
    ),
    Criterion(
        key="task",
        title="Clear task / instruction",
        rationale="One unambiguous ask beats a vague wish; verbs over vibes.",
        principle="instruction clarity",
    ),
    Criterion(
        key="output_format",
        title="Explicit output format / schema",
        rationale="Name the shape (JSON, fields, bullets) or you'll get prose drift.",
        principle="schema-constrained output (see structured-output/)",
    ),
    Criterion(
        key="constraints",
        title="Constraints & guardrails",
        rationale="Length, scope, and 'do not' rules keep output inside the lines.",
        principle="bounded scope",
    ),
    Criterion(
        key="examples",
        title="Examples / few-shot",
        rationale="A worked example pins the format better than describing it.",
        principle="few-shot demonstration",
    ),
    Criterion(
        key="success_criteria",
        title="Success criteria",
        rationale="Say what 'good' looks like so the output is checkable.",
        principle="evaluable acceptance criteria (see eval-rubrics/)",
    ),
    Criterion(
        key="safety",
        title="Safety / refusal handling",
        rationale="A null/refusal policy stops confident guessing on missing or unsafe input.",
        principle="null & refusal policy (see classification/pii-redaction-gate)",
    ),
)

RUBRIC_BY_KEY = {c.key: c for c in RUBRIC}
