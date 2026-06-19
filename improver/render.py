"""Rich rendering for the improver, styled to match the eval scoreboard.

Layout:
    * a backend banner (mock/rule-based vs live), like the eval harness's;
    * a diagnosis table (criterion | verdict | note) with a readiness score;
    * the rewritten prompt in a syntax-highlighted panel;
    * an explanation panel listing what changed and why.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from improver.improve import ImproveResult

_VERDICT_STYLE = {
    "present": "green",
    "weak": "yellow",
    "missing": "red",
}
_VERDICT_GLYPH = {
    "present": "present",
    "weak": "weak",
    "missing": "missing",
}


def _banner(result: ImproveResult) -> Panel:
    if result.backend == "llm":
        text = "[bold red]LIVE MODEL[/] — rewrite via Anthropic (ANTHROPIC_API_KEY detected)"
    else:
        text = (
            "[bold yellow]RULE-BASED[/] — deterministic, offline, no API key used"
        )
    return Panel(text, title="prompt improver", border_style="blue")


def _diagnosis_table(result: ImproveResult) -> Table:
    diag = result.diagnosis
    table = Table(
        title=f"Diagnosis (readiness {diag.readiness:.3f} / 1.000)",
        title_style="bold",
    )
    table.add_column("Criterion", style="cyan", no_wrap=True)
    table.add_column("Verdict", no_wrap=True)
    table.add_column("Note")
    for finding in diag.findings:
        style = _VERDICT_STYLE[finding.verdict]
        table.add_row(
            finding.criterion.title,
            f"[{style}]{_VERDICT_GLYPH[finding.verdict]}[/]",
            finding.note,
        )
    return table


def render(result: ImproveResult, console: Console | None = None) -> None:
    console = console or Console()
    console.print(_banner(result))
    console.print(_diagnosis_table(result))
    console.print(
        Panel(
            Syntax(result.improved, "markdown", theme="ansi_dark", word_wrap=True),
            title="Improved prompt",
            border_style="green",
        )
    )
    body = "\n".join(f"- {line}" for line in result.explanation)
    console.print(
        Panel(body, title="What changed & why", border_style="magenta")
    )
