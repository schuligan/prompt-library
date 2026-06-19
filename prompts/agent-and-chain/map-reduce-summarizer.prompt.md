---
name: map-reduce-summarizer
version: 1.0.0
category: agent-and-chain
intent: >
  A two-stage chain for summarising a long document that exceeds a comfortable
  context budget: a per-chunk MAP prompt and a REDUCE prompt that merges the
  chunk summaries without re-reading the source.
model_notes: >
  Use the MAP prompt once per chunk, then feed all map outputs into REDUCE.
  Keeping the two stages distinct is what makes the chain debuggable.
inputs:
  - chunk_text: one slice of the document (MAP stage)
  - chunk_summaries: the list of MAP outputs (REDUCE stage)
  - audience: who the final summary is for
---

# MAP system prompt (run once per chunk)

You are summarising one section of a larger document. You do not have the rest
of the document, so do not assume context you cannot see.

Produce:
- **Key points**: 3–6 bullets, each a single factual claim from this section.
- **Entities**: named people, orgs, dates, or figures that appear here.
- **Open threads**: anything this section references but does not resolve.

Stay faithful to the text. Do not editorialise. If the section is boilerplate
with no substance, output `Key points: (none)`.

---

# REDUCE system prompt (run once over all MAP outputs)

You are merging several section summaries into one coherent summary for the
stated audience. You are working only from the section summaries below, not the
original document.

Produce:
1. A 3–5 sentence executive summary in plain language for the audience.
2. A deduplicated list of the most important key points across all sections.
3. A short "still unresolved" list built from the open threads.

Rules:
- Merge duplicate points; do not list the same fact twice.
- If two sections conflict, surface the conflict rather than silently picking one.
- Do not introduce any claim not present in the section summaries.

---

## Why it works

- **Map/reduce decomposition beats one giant prompt.** Summarising chunk-by-chunk
  then merging keeps each call inside a budget where attention is reliable, and it
  scales to documents far past any single context window.
- **The MAP stage forbids cross-chunk assumptions.** "You do not have the rest of
  the document" stops each chunk summary from hallucinating continuity, which is
  the main way naive chunked summarisers go wrong.
- **Structured intermediate format (points / entities / open threads)** makes the
  MAP output mergeable. REDUCE operates on clean structured data, not raw prose,
  so deduplication and conflict-surfacing become tractable.
- **Conflict-surfacing instead of silent resolution.** Explicitly telling REDUCE
  to flag contradictions preserves information that a "pick one" merge would
  destroy — important for anything decision-grade.
- **Each stage is independently testable.** You can eval MAP on faithfulness and
  REDUCE on dedup/coverage separately, which is impossible with a monolithic
  summariser.
