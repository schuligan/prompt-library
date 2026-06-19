"""Structural tests over the prompt library itself: every prompt has valid
frontmatter and a 'Why it works' section, and the INDEX builder works."""

import pytest

from cli import build_index_rows, render_index
from evals.promptio import iter_prompts

REQUIRED_META = {"name", "version", "category", "intent"}
KNOWN_CATEGORIES = {
    "role-prompts",
    "structured-output",
    "agent-and-chain",
    "extraction",
    "classification",
    "rewriting",
    "eval-rubrics",
}

ALL_PROMPTS = list(iter_prompts())


def test_library_has_prompts():
    assert len(ALL_PROMPTS) >= 10


@pytest.mark.parametrize("prompt", ALL_PROMPTS, ids=lambda p: p.name)
def test_prompt_has_required_frontmatter(prompt):
    missing = REQUIRED_META - set(prompt.meta)
    assert not missing, f"{prompt.path} missing frontmatter keys: {missing}"


@pytest.mark.parametrize("prompt", ALL_PROMPTS, ids=lambda p: p.name)
def test_prompt_category_is_known(prompt):
    assert prompt.category in KNOWN_CATEGORIES


@pytest.mark.parametrize("prompt", ALL_PROMPTS, ids=lambda p: p.name)
def test_prompt_explains_why_it_works(prompt):
    assert "Why it works" in prompt.body, f"{prompt.path} lacks a 'Why it works' section"


@pytest.mark.parametrize("prompt", ALL_PROMPTS, ids=lambda p: p.name)
def test_prompt_version_is_semverish(prompt):
    parts = prompt.version.split(".")
    assert len(parts) == 3 and all(seg.isdigit() for seg in parts)


def test_index_builder_covers_all_prompts():
    rows = build_index_rows()
    assert len(rows) == len(ALL_PROMPTS)
    md = render_index(rows)
    assert "| Name | Category | Version | Intent |" in md
    assert md.count("\n|") >= len(rows)
