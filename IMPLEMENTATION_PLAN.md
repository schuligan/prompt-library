# Implementation Plan

This document records the design of the prompt library and its eval harness:
the taxonomy, the scoring strategy, the trade-offs taken, and the phased build.
It is written as the plan I'd hand to a reviewer before writing code.

## 1. Goals and non-goals

**Goals**

- Treat prompts as versioned artifacts with an explicit rationale.
- Make prompt quality *measurable*: golden inputs + scorers + a scoreboard.
- Demonstrate A/B prompt evaluation (variant vs variant) with a declared winner.
- Help *author* better prompts, not just score them: a diagnose→rewrite→explain
  improver that turns a weak prompt into a structured one against the same rubric.
- Run fully offline in CI — no API key, no network — via a deterministic mock /
  rule-based path.
- Stay small and dependency-light so a reviewer can read the whole thing.

**Non-goals**

- Not a general prompt-ops platform (no DB, no UI, no experiment tracking).
- Not a benchmark of model quality — it benchmarks *prompts*, holding the model
  fixed.
- Not a constrained-decoding library; it documents where to pair with one.

## 2. Library taxonomy

Prompts are organised by **use case**, because that is how someone reaching for a
prompt actually searches ("I need to classify X", "I need structured output").

| Category            | What lives here                                              |
| ------------------- | ----------------------------------------------------------- |
| `role-prompts`      | Persona/role-primed system prompts (support triage, reviewer)|
| `structured-output` | JSON-schema-constrained outputs, function routing           |
| `agent-and-chain`   | Multi-step agents, plan/act loops, map-reduce chains         |
| `extraction`        | Pull structured fields from free text (incl. the A/B pair)   |
| `classification`    | Closed-set labelling, safety gates                          |
| `rewriting`         | Tone shifts, simplification — content-preserving transforms  |
| `eval-rubrics`      | LLM-as-judge rubrics (faithfulness, pairwise quality)        |

**File format.** Each prompt is a `.prompt.md` with YAML frontmatter
(`name`, `version`, `category`, `intent`, `model_notes`, `inputs`, optional
`schema`) followed by the prompt body and a mandatory `## Why it works` section.
Markdown keeps prompts readable on GitHub; frontmatter keeps them machine-indexable.

**Versioning.** Semantic-ish `MAJOR.MINOR.PATCH`. A wording change that alters
behaviour bumps MINOR; a tightening that fixes a bug bumps PATCH; a contract
change (output shape) bumps MAJOR. Versions make prompt diffs reviewable and let
the eval suite pin a variant.

## 3. Eval harness design

Five components, each small and single-purpose:

1. **`promptio.py`** — parse frontmatter/body; iterate the library.
2. **`model.py`** — model adapters. `MockModel` (default, deterministic) and
   `LiveModel` (only if `ANTHROPIC_API_KEY` + `anthropic` present).
3. **`scorers.py`** — pure functions: `(raw_output, expectation) -> ScoreResult`.
4. **`golden/*.yaml`** — declarative suites: variants + cases + per-case checks.
5. **`run.py`** — orchestrates model → scorers → aggregate → rich scoreboard.

### Why a mock model is the default

The hardest constraint is "must run in CI offline and deterministically." LLM
output is non-deterministic and gated behind a key, which makes it useless as a
*regression* signal. So the default backend is a hand-written deterministic
responder per prompt variant. This is honest about what it is — it is not
claiming model quality, it is exercising the *harness* and demonstrating the
*scoring and A/B logic* reproducibly. The live path exists for real evaluation
but is never required.

The mock deliberately encodes the *known failure modes* of an under-specified
prompt (markdown fences, dropped null keys, unnormalised phone numbers) for the
baseline variant, and clean behaviour for the hardened variant — so the A/B
result mirrors what real models do, while staying reproducible.

### Scoring strategy

A spectrum from cheapest/most-objective to richest/most-subjective:

| Scorer        | Signal                          | Cost | Used for                  |
| ------------- | ------------------------------- | ---- | ------------------------- |
| `exact_match` | strongest, brittlest            | tiny | canonical short outputs   |
| `regex`       | presence of a required token    | tiny | "did it emit P1?"         |
| `json_schema` | shape + parseability            | low  | all structured-output     |
| `json_fields` | per-field accuracy (partial)    | low  | extraction / classification |
| `keyword`     | rubric-keyword coverage         | low  | "did the rationale cite…" |

Design choices:

- **Partial credit** (`json_fields`, `keyword`) gives a smooth signal instead of
  pass/fail cliffs, so small prompt regressions show up as score *drops*.
- **`json_schema` penalises non-JSON-only output with half credit** rather than
  zero. This captures a real distinction: "valid but needed unwrapping" is worse
  than clean JSON but better than garbage — and it's exactly the axis the A/B
  pair turns on.
- **A hand-rolled mini JSON-Schema validator** (in `scorers.py`) covers only the
  keywords our schemas use (`type`, `enum`, `pattern`, `required`,
  `additionalProperties`, numeric bounds, `maxLength`, `items`). This avoids a
  `jsonschema` dependency to keep the footprint tiny; the trade-off is noted
  below.

### A/B evaluation

A suite with ≥2 `variants` runs the same `cases` through each, aggregates mean
score per variant, ranks them, and emits a winner with the margin and a reason.
Ties (equal means) are reported as ties. The `answer-quality-rubric` prompt
documents the *judge-side* protocol for pairwise comparison (including
position-bias mitigation) for when you A/B with an LLM judge rather than
deterministic scorers.

## 3a. Prompt improver

A complement to the eval harness: the harness *scores* prompts, the improver
helps *write* a better one. It is a thin, transparent pipeline under `improver/`:

1. **`rubric.py`** — the diagnostic criteria as declarative data: explicit role,
   sufficient context, clear task, output format/schema, constraints, examples,
   success criteria, safety/refusal. The set deliberately mirrors the techniques
   the prompt library teaches, so diagnosis, library, and rewrite share one
   vocabulary.
2. **`diagnose.py`** — one transparent heuristic detector per criterion returning
   `present` / `weak` / `missing` + a note, plus a 0..1 readiness score. Pattern/
   keyword heuristics (not a model call) keep it deterministic and offline.
3. **`rewrite.py`** — the default **rule-based** rewriter scaffolds a structured
   prompt (Role / Context / Task / Output / Constraints / Success / Refusal),
   preserving the user's instruction verbatim in Task and injecting checklist
   defaults elsewhere. An optional `rewrite_with_llm` uses the catalogued
   `prompt-improver` meta-prompt when a key is present.
4. **`improve.py`** — orchestrates diagnose → rewrite → explain, and reuses
   `evals.model.live_available` so the improver and harness agree on when a real
   model is in play (DRY). The explanation diffs the gaps the rewrite closed,
   each tied to its principle.
5. **`render.py` / `cli.py`** — a rich banner + diagnosis table + rewrite panel +
   rationale, and the `improve` subcommand (`improve "<text>"` / `--file` /
   `--plain` / `--rule-based`).

**Why rule-based as the default.** Same constraint as the harness: it must run
offline and deterministically. A rule-based rewriter is honest about what it is —
checklist-driven scaffolding, not a creative rewrite — and it is genuinely useful
because the highest-value fixes for weak prompts (a refusal/null policy, an output
spec, a primed role) are structural and don't need a model. The LLM path exists
for a richer rewrite but is never required.

## 4. Trade-offs

- **Mock vs live as default.** Chose mock-default for deterministic CI. Cost:
  the headline numbers are not "real" model scores. Mitigation: a loud banner,
  explicit docs, and a working live path.
- **Mini-validator vs `jsonschema`.** Chose a small in-repo validator for zero
  extra deps and full readability. Cost: it implements a subset of draft-07.
  Mitigation: it covers everything our schemas use and is unit-tested; swapping
  in `jsonschema` later is a one-function change.
- **Markdown prompts vs a prompt DSL.** Chose Markdown + frontmatter for GitHub
  legibility over a bespoke format. Cost: no compile-time validation of inputs.
  Mitigation: structural tests assert required frontmatter exists.
- **Per-variant mock responders.** Scorers are model-agnostic, but the mock must
  know how each prompt "tends" to answer. Cost: adding a live-only prompt needs a
  mock responder for offline tests. Mitigation: documented in the README's
  "add an eval" section; only prompts under eval need one.

## 5. Phased plan (as built)

- **Phase 0 — scaffolding.** Repo layout, license, `.gitignore`, `.env.example`,
  `requirements.txt`.
- **Phase 1 — the library.** 14 prompts across 7 categories, each with
  frontmatter and a "Why it works" section; JSON Schemas + a pydantic mirror for
  structured-output.
- **Phase 2 — the harness.** `promptio` → `model` (mock + live) → `scorers` →
  `run` with a rich scoreboard.
- **Phase 3 — golden data + A/B.** Contact-extraction A/B pair (baseline vs
  hardened) and a single-variant intent-classifier suite.
- **Phase 4 — tests + catalog.** pytest over scorers, harness, A/B logic, and
  prompt structure; `cli.py index` generates `prompts/INDEX.md`.
- **Phase 5 — docs.** README (hook, problem, Mermaid flow, quickstart, example
  scoreboard, About) and this plan.
- **Phase 6 — prompt improver.** `improver/` package (rubric → diagnose →
  rewrite → explain), the `improve` CLI subcommand, the catalogued
  `prompt-improver` meta-prompt for the live path, example inputs, and tests
  asserting the diagnosis flags a weak prompt's gaps and the rewrite emits every
  required section — all offline.

## 6. Verification

- `python -m evals.run` prints the scoreboard and declares the hardened variant
  the A/B winner, offline, on the mock model.
- `pytest -q` passes with the harness running in mock mode, asserting the
  scoreboard aggregation and the winner logic (hardened > baseline).
- `ruff check .` is clean.

## 7. Possible extensions

- Cost/latency columns in the scoreboard (live path).
- A `--json` report mode to diff two eval runs (true prompt regression CI).
- Wire `answer-quality-rubric` as a live LLM-judge scorer with the swap-pass
  position-bias control implemented in code.
- Snapshot prior scores per prompt version to flag regressions automatically.
