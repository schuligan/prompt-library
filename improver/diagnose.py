"""Rule-based diagnosis of a raw prompt against the rubric.

Each criterion has a detector that returns a verdict in
{``present``, ``weak``, ``missing``} plus a short note. The detectors are
deliberately simple, transparent heuristics (keyword / pattern presence) rather
than a model call — so the diagnosis is deterministic and offline by default,
matching the eval harness's mock-first design. They are tuned to be useful on
the kind of under-specified prompts people actually paste in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from improver.rubric import RUBRIC, VERDICT_SCORE, Criterion

# --- signal vocabularies ---------------------------------------------------

_ROLE_CUES = (
    "you are",
    "act as",
    "your role",
    "as a ",
    "as an ",
    "you're a",
    "you are a",
    "behave as",
)
_OUTPUT_CUES = (
    "json",
    "yaml",
    "markdown",
    "table",
    "bullet",
    "list",
    "format",
    "schema",
    "fields",
    "csv",
    "return only",
    "respond with",
    "output:",
)
_CONSTRAINT_CUES = (
    "do not",
    "don't",
    "never",
    "must",
    "only",
    "at most",
    "no more than",
    "limit",
    "max ",
    "maximum",
    "fewer than",
    "avoid",
    "within",
    "exactly",
)
_EXAMPLE_CUES = (
    "example",
    "for instance",
    "e.g.",
    "such as",
    "input:",
    "output:",
    "sample",
)
_SUCCESS_CUES = (
    "success",
    "must include",
    "is correct when",
    "acceptance",
    "criteria",
    "evaluate",
    "good answer",
    "definition of done",
    "check that",
)
_SAFETY_CUES = (
    "if unknown",
    "if you don't know",
    "if not present",
    "null",
    "refuse",
    "decline",
    "out of scope",
    "do not guess",
    "don't guess",
    "uncertain",
    "n/a",
    "unsure",
    "cannot determine",
)
_CONTEXT_CUES = (
    "context",
    "audience",
    "background",
    "the following",
    "given",
    "based on",
    "the user",
    "customer",
    "the text",
    "the document",
    "domain",
)
# Imperative verbs that signal an actual task rather than a vague wish.
_TASK_VERBS = (
    "classify",
    "extract",
    "summarize",
    "summarise",
    "rewrite",
    "translate",
    "generate",
    "write",
    "list",
    "identify",
    "analyze",
    "analyse",
    "draft",
    "explain",
    "label",
    "score",
    "review",
    "convert",
    "produce",
    "return",
    "find",
)


@dataclass(frozen=True)
class Finding:
    """One criterion's diagnosis."""

    criterion: Criterion
    verdict: str  # "present" | "weak" | "missing"
    note: str

    @property
    def score(self) -> float:
        return VERDICT_SCORE[self.verdict]


@dataclass(frozen=True)
class Diagnosis:
    raw: str
    findings: tuple[Finding, ...]

    @property
    def readiness(self) -> float:
        """Mean criterion score, 0..1 — a single 'how ready is this prompt' number."""
        if not self.findings:
            return 0.0
        return round(sum(f.score for f in self.findings) / len(self.findings), 3)

    @property
    def gaps(self) -> tuple[Finding, ...]:
        """Findings that need attention (missing or weak), worst first."""
        ranked = sorted(self.findings, key=lambda f: f.score)
        return tuple(f for f in ranked if f.verdict != "present")

    def by_key(self, key: str) -> Finding:
        return next(f for f in self.findings if f.criterion.key == key)


# --- detector helpers ------------------------------------------------------


def _has_any(text: str, cues: tuple[str, ...]) -> bool:
    return any(cue in text for cue in cues)


def _verdict(strong: bool, weak: bool, present_note: str, weak_note: str, missing_note: str):
    if strong:
        return "present", present_note
    if weak:
        return "weak", weak_note
    return "missing", missing_note


# --- per-criterion detectors -----------------------------------------------


def _diag_role(text: str) -> tuple[str, str]:
    return _verdict(
        strong=_has_any(text, _ROLE_CUES),
        weak=False,
        present_note="a role/persona is primed",
        weak_note="",
        missing_note="no role primed — the model has to infer who it should be",
    )


def _diag_context(text: str) -> tuple[str, str]:
    hits = sum(1 for cue in _CONTEXT_CUES if cue in text)
    return _verdict(
        strong=hits >= 2,
        weak=hits == 1,
        present_note="audience/inputs are described",
        weak_note="only a thin sense of context — name the audience, domain, and inputs",
        missing_note="no context — the model can't tell who this is for or what it's given",
    )


def _diag_task(text: str) -> tuple[str, str]:
    verbs = [v for v in _TASK_VERBS if re.search(rf"\b{v}\b", text)]
    word_count = len(text.split())
    return _verdict(
        strong=bool(verbs) and word_count >= 4,
        weak=bool(verbs) or word_count >= 8,
        present_note=f"clear instruction (verb: {verbs[0]})" if verbs else "instruction present",
        weak_note="the ask is vague — lead with a concrete action verb",
        missing_note="no actionable instruction — it reads as a wish, not a task",
    )


def _diag_output_format(text: str) -> tuple[str, str]:
    schema_like = "json" in text or "schema" in text or "fields" in text
    return _verdict(
        strong=schema_like,
        weak=_has_any(text, _OUTPUT_CUES),
        present_note="an explicit output shape/schema is requested",
        weak_note="output shape is gestured at but not pinned — name JSON/fields/sections",
        missing_note="no output format — expect free-form prose that's hard to parse or score",
    )


def _diag_constraints(text: str) -> tuple[str, str]:
    hits = sum(1 for cue in _CONSTRAINT_CUES if cue in text)
    return _verdict(
        strong=hits >= 2,
        weak=hits == 1,
        present_note="constraints/guardrails are stated",
        weak_note="only one constraint — add scope, length, or 'do not' rules",
        missing_note="no constraints — nothing bounds length, scope, or behaviour",
    )


def _diag_examples(text: str) -> tuple[str, str]:
    return _verdict(
        strong=_has_any(text, _EXAMPLE_CUES),
        weak=False,
        present_note="at least one example / few-shot cue is present",
        weak_note="",
        missing_note="no example — a worked input→output pins the format far better than prose",
    )


def _diag_success(text: str) -> tuple[str, str]:
    return _verdict(
        strong=_has_any(text, _SUCCESS_CUES),
        weak=False,
        present_note="success criteria are stated",
        weak_note="",
        missing_note="no success criteria — there's no checkable bar for a 'good' answer",
    )


def _diag_safety(text: str) -> tuple[str, str]:
    return _verdict(
        strong=_has_any(text, _SAFETY_CUES),
        weak=False,
        present_note="a null/refusal/uncertainty policy is present",
        weak_note="",
        missing_note="no refusal/null policy — the model will guess on missing or unsafe input",
    )


_DETECTORS = {
    "role": _diag_role,
    "context": _diag_context,
    "task": _diag_task,
    "output_format": _diag_output_format,
    "constraints": _diag_constraints,
    "examples": _diag_examples,
    "success_criteria": _diag_success,
    "safety": _diag_safety,
}


def diagnose(raw: str) -> Diagnosis:
    """Run every rubric detector over ``raw`` and return a :class:`Diagnosis`."""
    text = raw.lower()
    findings = []
    for criterion in RUBRIC:
        verdict, note = _DETECTORS[criterion.key](text)
        findings.append(Finding(criterion=criterion, verdict=verdict, note=note))
    return Diagnosis(raw=raw, findings=tuple(findings))
