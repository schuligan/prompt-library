"""Model adapters.

Two backends:

* ``MockModel`` — fully deterministic, no network, no key. It is the DEFAULT and
  is what CI and ``pytest`` run against. It does not call an LLM; instead it
  contains a small hand-written "responder" per prompt variant so the harness can
  demonstrate scoring and A/B comparison reproducibly. The mock deliberately
  makes the *baseline* contact-extraction prompt behave worse than the *hardened*
  one (markdown fences, dropped nulls) so the A/B result mirrors what a real
  model tends to do.

* ``LiveModel`` — used only when ``ANTHROPIC_API_KEY`` is set AND the ``anthropic``
  package is installed. Sends the prompt body as the system prompt and the input
  as the user turn. Never required for tests.

Select with :func:`get_model`.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Deterministic mock responders, keyed by prompt `name`.
# Each responder takes the example's input dict and returns a raw string,
# imitating how that specific prompt variant tends to respond.
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
# A name is a capitalised word that directly follows a "to/at/reach/contact"
# style trigger, so we don't grab the capitalised first word of a sentence.
_NAME_RE = re.compile(
    r"\b(?:contact|reach|call|email|to|with)\s+([A-Z][a-z]+)\b", re.IGNORECASE
)
_NAME_CAP_RE = re.compile(r"([A-Z][a-z]+)")


def _clean_phone(raw: str) -> str | None:
    """Strip separators; keep a leading + only if present in the source."""
    has_plus = raw.lstrip().startswith("+")
    bare = re.sub(r"[^\d]", "", raw)
    if not (7 <= len(bare) <= 15):
        return None
    return ("+" + bare) if has_plus else bare


def _extract_name(text: str) -> str | None:
    m = _NAME_RE.search(text)
    if m:
        return m.group(1)
    # Fallback: first capitalised word that is not a common sentence opener.
    openers = {"Please", "You", "Call", "Reach", "Contact", "Email", "The"}
    for cand in _NAME_CAP_RE.findall(text):
        if cand not in openers:
            return cand
    return None


def _extract_fields(text: str) -> dict:
    email = _EMAIL_RE.search(text)
    phone = _PHONE_RE.search(text)
    return {
        "name": _extract_name(text),
        "email": email.group(0) if email else None,
        "phone": _clean_phone(phone.group(0)) if phone else None,
        "company": None,
    }


def _respond_contact_baseline(inp: dict) -> str:
    """Baseline: drops null keys and wraps in a markdown fence (the bad habits)."""
    text = inp.get("text", "")
    fields = _extract_fields(text)
    # Baseline pathology #1: omit keys whose value is null instead of emitting null.
    trimmed = {k: v for k, v in fields.items() if v is not None}
    # Baseline pathology #2: phone left unnormalised.
    raw_phone = _PHONE_RE.search(text)
    if raw_phone and "phone" in trimmed:
        trimmed["phone"] = raw_phone.group(0).strip()
    # Baseline pathology #3: wrap in a markdown code fence + a prose line.
    return "Here is the contact info:\n```json\n" + json.dumps(trimmed) + "\n```"


def _respond_contact_hardened(inp: dict) -> str:
    """Hardened: strict JSON object, all keys present, phone normalised."""
    text = inp.get("text", "")
    return json.dumps(_extract_fields(text))


def _respond_intent(inp: dict) -> str:
    msg = inp.get("message", "").lower()
    table = [
        ("track", "track_order"),
        ("where is my order", "track_order"),
        ("cancel", "cancel_order"),
        ("refund", "return_or_refund"),
        ("return", "return_or_refund"),
        ("how do", "product_question"),
        ("does it", "product_question"),
        ("terrible", "complaint"),
        ("angry", "complaint"),
    ]
    label = next((lbl for kw, lbl in table if kw in msg), "unknown")
    conf = 0.9 if label != "unknown" else 0.4
    return json.dumps(
        {"label": label, "confidence": conf, "rationale": f"matched cue for {label}"}
    )


_RESPONDERS = {
    "contact-extraction-v1-baseline": _respond_contact_baseline,
    "contact-extraction-v2-hardened": _respond_contact_hardened,
    "intent-classifier": _respond_intent,
}


@dataclass
class MockModel:
    """Deterministic, offline. The default backend."""

    name: str = "mock"

    def complete(self, prompt_name: str, system: str, inp: dict) -> str:
        responder = _RESPONDERS.get(prompt_name)
        if responder is None:
            raise KeyError(
                f"No mock responder registered for prompt '{prompt_name}'. "
                "Add one in evals/model.py or run a registered variant."
            )
        return responder(inp)


@dataclass
class LiveModel:
    """Real Anthropic model. Only used when a key is present."""

    name: str
    _client: object = None

    def complete(self, prompt_name: str, system: str, inp: dict) -> str:  # pragma: no cover - network
        if self._client is None:
            import anthropic  # imported lazily so the package stays optional

            self._client = anthropic.Anthropic()
        user = json.dumps(inp, ensure_ascii=False)
        resp = self._client.messages.create(
            model=self.name,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")


def live_available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def get_model(force_mock: bool = False):
    """Return the active model. Mock unless a key + SDK are present and not forced."""
    if force_mock or not live_available():
        return MockModel()
    model_id = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    return LiveModel(name=model_id)
