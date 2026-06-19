"""Orchestrate the full improve flow: diagnose -> rewrite -> explain.

    raw prompt
        |
        v
    diagnose (rubric)  --> Diagnosis (per-criterion findings + readiness score)
        |
        v
    rewrite (rule-based default, LLM optional) --> improved prompt
        |
        v
    explain (diff the gaps the rewrite addressed) --> rationale lines

Backend selection reuses ``evals.model.live_available`` so the improver and the
eval harness agree on when a real model is in play (DRY). The rule-based path is
the default and runs fully offline.
"""

from __future__ import annotations

from dataclasses import dataclass

from evals.model import live_available
from improver.diagnose import Diagnosis, diagnose
from improver.rewrite import rewrite_rule_based, rewrite_with_llm


@dataclass(frozen=True)
class ImproveResult:
    raw: str
    diagnosis: Diagnosis
    improved: str
    explanation: tuple[str, ...]
    backend: str  # "rule-based" | "llm"


def _explain(diag: Diagnosis) -> tuple[str, ...]:
    """One rationale line per gap the rewrite closed, tied to the principle."""
    lines = []
    for finding in diag.gaps:
        c = finding.criterion
        verb = "Added" if finding.verdict == "missing" else "Strengthened"
        lines.append(
            f"{verb} **{c.title.lower()}** — {c.rationale} "
            f"(principle: {c.principle})."
        )
    if not lines:
        lines.append(
            "The prompt already covered the rubric; the rewrite only reformats it "
            "into explicit sections for consistency and easier evaluation."
        )
    return tuple(lines)


def improve(raw: str, force_rule_based: bool = False) -> ImproveResult:
    """Diagnose ``raw``, rewrite it, and explain the changes.

    Uses the deterministic rule-based rewriter unless a live model is available
    and ``force_rule_based`` is False.
    """
    if not raw or not raw.strip():
        raise ValueError("Cannot improve an empty prompt.")

    diag = diagnose(raw)

    if not force_rule_based and live_available():
        improved = rewrite_with_llm(raw)
        backend = "llm"
    else:
        improved = rewrite_rule_based(raw)
        backend = "rule-based"

    return ImproveResult(
        raw=raw,
        diagnosis=diag,
        improved=improved,
        explanation=_explain(diag),
        backend=backend,
    )
