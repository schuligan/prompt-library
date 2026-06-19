# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Continuous integration (GitHub Actions): `ruff` + `pytest` on Python 3.11 and 3.12, with a status badge.

## [0.1.0] - 2026-06-19

### Added
- Versioned prompt library: 15 prompts across 7 categories, each with frontmatter and a "why it works" rationale.
- Offline eval harness with scorers (exact-match, regex, JSON-schema, field, keyword) and an A/B variant comparison scoreboard.
- `prompt-improver`: diagnose → rewrite → explain for any weak prompt.
- Structured-output JSON Schemas with a matching pydantic mirror.
