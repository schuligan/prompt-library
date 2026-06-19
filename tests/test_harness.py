"""Integration tests: run the eval harness in mock mode and assert the
scoreboard + A/B winner logic behave correctly and offline."""


from evals.model import MockModel, get_model
from evals.run import GOLDEN_DIR, _run_suite, run

CONTACT_SUITE = GOLDEN_DIR / "contact-extraction.yaml"
INTENT_SUITE = GOLDEN_DIR / "intent-classifier.yaml"


def test_default_model_is_mock_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    model = get_model()
    assert isinstance(model, MockModel)
    assert model.name == "mock"


def test_force_mock_overrides_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    assert isinstance(get_model(force_mock=True), MockModel)


def test_contact_suite_runs_and_is_ab():
    suite = _run_suite(CONTACT_SUITE, force_mock=True)
    assert suite.task == "contact-extraction"
    assert suite.is_ab
    assert len(suite.variants) == 2
    # every case produced a score
    for v in suite.variants:
        assert len(v.per_case) == 3


def test_hardened_variant_beats_baseline():
    """The whole point of the A/B demo: v2 must win on the mock model."""
    suite = _run_suite(CONTACT_SUITE, force_mock=True)
    by_name = {v.name: v for v in suite.variants}
    baseline = by_name["contact-extraction-v1-baseline"]
    hardened = by_name["contact-extraction-v2-hardened"]
    assert hardened.mean > baseline.mean
    winner, why = suite.winner()
    assert winner.name == "contact-extraction-v2-hardened"
    assert "vs" in why  # margin string


def test_hardened_variant_is_schema_clean():
    """Hardened variant should reach a perfect mean on the mock (JSON-only + correct)."""
    suite = _run_suite(CONTACT_SUITE, force_mock=True)
    hardened = next(
        v for v in suite.variants if v.name == "contact-extraction-v2-hardened"
    )
    assert hardened.mean == 1.0


def test_intent_suite_single_variant():
    suite = _run_suite(INTENT_SUITE, force_mock=True)
    assert not suite.is_ab
    winner, why = suite.winner()
    assert why == "only variant"
    # mock classifier should get all four golden cases right
    assert winner.mean == 1.0


def test_run_all_suites_offline(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    results = run(tasks=None, force_mock=True, use_table=False)
    tasks = {s.task for s in results}
    assert {"contact-extraction", "intent-classifier"} <= tasks


def test_winner_margin_is_positive():
    suite = _run_suite(CONTACT_SUITE, force_mock=True)
    winner, _ = suite.winner()
    others = [v.mean for v in suite.variants if v.name != winner.name]
    assert all(winner.mean >= m for m in others)
