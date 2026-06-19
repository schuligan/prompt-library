"""Prompt improver.

Takes a raw / weak prompt (or a block of free text pasted from notes, an inbox,
a ticket, …) and returns:

* a **diagnosis** against a prompt-engineering rubric (per-criterion
  present / weak / missing findings), and
* a **rewrite** into a stronger, structured prompt (role, context, task,
  output spec, constraints), and
* an **explanation** tying each change back to the principle it fixes.

The default rewriter is **deterministic and rule-based** — it runs fully
offline, with no API key, so the CLI and tests behave reproducibly (mirroring
the eval harness's mock-model-first philosophy). An optional LLM-backed rewrite
is used only when ``ANTHROPIC_API_KEY`` and the ``anthropic`` package are both
present.
"""

from __future__ import annotations

from improver.diagnose import Diagnosis, Finding, diagnose
from improver.improve import ImproveResult, improve
from improver.rewrite import rewrite_rule_based

__all__ = [
    "Diagnosis",
    "Finding",
    "ImproveResult",
    "diagnose",
    "improve",
    "rewrite_rule_based",
]
