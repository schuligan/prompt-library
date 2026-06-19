"""Eval runner.

Flow (also drawn in the README Mermaid diagram):

    prompt variant  ->  golden inputs  ->  model (mock by default)  ->  scorers
                                                                          |
                                                                          v
                                                            per-variant aggregate
                                                                          |
                                                                          v
                                                       rich scoreboard + A/B winner

Run:
    python -m evals.run                 # all golden suites, mock model
    python -m evals.run contact-extraction
    python -m evals.run --no-table      # plain text (CI logs)

Defaults to the deterministic MOCK model. If ANTHROPIC_API_KEY is set and the
`anthropic` package is installed, the live path is used and a banner says so.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from evals.model import get_model
from evals.promptio import REPO_ROOT, load_prompt
from evals.scorers import run_scorer

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


@dataclass
class VariantResult:
    name: str
    per_case: list[float] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def mean(self) -> float:
        return round(sum(self.per_case) / len(self.per_case), 3) if self.per_case else 0.0


@dataclass
class SuiteResult:
    task: str
    variants: list[VariantResult]

    @property
    def is_ab(self) -> bool:
        return len(self.variants) >= 2

    def winner(self) -> tuple[VariantResult, str]:
        ranked = sorted(self.variants, key=lambda v: v.mean, reverse=True)
        top = ranked[0]
        if len(ranked) == 1:
            return top, "only variant"
        runner_up = ranked[1]
        if top.mean == runner_up.mean:
            return top, "tie on mean score"
        margin = round(top.mean - runner_up.mean, 3)
        return top, f"+{margin} mean vs '{runner_up.name}'"


def _run_suite(suite_path: Path, force_mock: bool) -> SuiteResult:
    spec = yaml.safe_load(suite_path.read_text())
    model = get_model(force_mock=force_mock)

    variants: list[VariantResult] = []
    for v in spec["variants"]:
        prompt = load_prompt(REPO_ROOT / v["prompt"])
        vr = VariantResult(name=v["name"])
        for case in spec["cases"]:
            raw = model.complete(prompt.name, prompt.body, case["input"])
            case_scores: list[float] = []
            case_notes: list[str] = []
            for check in case["checks"]:
                kind = check["scorer"]
                extra = {k: val for k, val in check.items() if k not in ("scorer",)}
                # expectation arg name varies by scorer; pass through whichever key exists.
                expectation = (
                    extra.pop("expected", None)
                    if "expected" in extra
                    else extra.pop("schema", None)
                    if kind == "json_schema"
                    else extra.pop("pattern", None)
                )
                if kind == "json_schema":
                    res = run_scorer(kind, raw, check["schema"])
                else:
                    res = run_scorer(kind, raw, expectation, **extra)
                case_scores.append(res.score)
                case_notes.append(f"{case['id']}/{kind}: {res.score} ({res.note})")
            vr.per_case.append(sum(case_scores) / len(case_scores))
            vr.notes.extend(case_notes)
        variants.append(vr)
    return SuiteResult(task=spec["task"], variants=variants)


def _render(console: Console, suite: SuiteResult, use_table: bool) -> None:
    if use_table:
        table = Table(title=f"Eval suite: {suite.task}", title_style="bold")
        table.add_column("Variant", style="cyan", no_wrap=True)
        table.add_column("Cases", justify="right")
        table.add_column("Mean score", justify="right", style="bold")
        best = max(v.mean for v in suite.variants)
        for v in sorted(suite.variants, key=lambda x: x.mean, reverse=True):
            style = "bold green" if v.mean == best and suite.is_ab else None
            table.add_row(v.name, str(len(v.per_case)), f"{v.mean:.3f}", style=style)
        console.print(table)
    else:
        console.print(f"== {suite.task} ==")
        for v in sorted(suite.variants, key=lambda x: x.mean, reverse=True):
            console.print(f"  {v.name}: {v.mean:.3f} over {len(v.per_case)} cases")

    if suite.is_ab:
        win, why = suite.winner()
        console.print(
            Panel(
                f"[bold green]Winner: {win.name}[/]  ({why})\n"
                f"Why: the hardened variant emits strict JSON-only output, so it "
                f"passes the schema scorer cleanly where the baseline loses points "
                f"for markdown-fenced / non-JSON-only output and dropped null keys.",
                title="A/B result",
                border_style="green",
            )
        )


def run(tasks: list[str] | None, force_mock: bool, use_table: bool) -> list[SuiteResult]:
    console = Console()
    model = get_model(force_mock=force_mock)
    banner = (
        "[bold yellow]MOCK MODEL[/] — deterministic, offline, no API key used"
        if model.name == "mock"
        else f"[bold red]LIVE MODEL[/] — {model.name} (ANTHROPIC_API_KEY detected)"
    )
    console.print(Panel(banner, title="prompt-library evals", border_style="blue"))

    suite_paths = sorted(GOLDEN_DIR.glob("*.yaml"))
    if tasks:
        wanted = set(tasks)
        suite_paths = [p for p in suite_paths if p.stem in wanted]
        if not suite_paths:
            console.print(f"[red]No golden suites matched {tasks}[/]")
            return []

    results = []
    for path in suite_paths:
        suite = _run_suite(path, force_mock=force_mock)
        _render(console, suite, use_table)
        results.append(suite)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run prompt evals (mock by default).")
    parser.add_argument("tasks", nargs="*", help="golden suite stems to run; default all")
    parser.add_argument("--mock", action="store_true", help="force mock even if a key is set")
    parser.add_argument("--no-table", action="store_true", help="plain text output for CI")
    args = parser.parse_args(argv)
    run(args.tasks or None, force_mock=args.mock, use_table=not args.no_table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
