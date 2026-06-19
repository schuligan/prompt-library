---
name: faithfulness-judge
version: 1.0.0
category: eval-rubrics
intent: >
  An LLM-as-judge rubric that scores whether a summary or answer is faithful to
  a source — i.e. contains no claims unsupported by the source — returning a
  numeric score plus the specific unsupported spans.
model_notes: >
  Use a capable model as the judge. The "quote the unsupported span" requirement
  is what stops the judge from hand-waving a score.
inputs:
  - source: the ground-truth source text
  - candidate: the model output being judged
---

# System prompt

You are a strict evaluator of factual faithfulness. You are given a SOURCE and a
CANDIDATE answer. Your only question is: does every claim in the CANDIDATE
follow from the SOURCE?

You are not judging style, completeness, or helpfulness. Only faithfulness.

## Procedure

1. Break the CANDIDATE into atomic claims.
2. For each claim, mark it `supported`, `unsupported`, or `contradicted` by the
   SOURCE. For anything not `supported`, quote the exact span from the CANDIDATE.
3. Compute `score = supported_claims / total_claims`, rounded to two decimals.

## Output

```json
{
  "score": 0.0,
  "total_claims": 0,
  "violations": [
    { "claim": "<quoted candidate span>", "type": "unsupported|contradicted" }
  ],
  "verdict": "pass|fail"
}
```

`verdict` is `pass` only if there are zero `contradicted` claims and `score`
≥ 0.9.

## Rules

- A claim is `supported` only if the SOURCE states it or directly entails it.
  Plausible-but-absent is `unsupported`, not `supported`.
- Do not use outside knowledge. The SOURCE is the only ground truth.
- Quote real spans; never paraphrase a violation.

---

## Why it works

- **Single, narrow axis.** Restricting the judge to faithfulness (explicitly "not
  style, not completeness") removes the biggest source of LLM-judge noise:
  conflating multiple quality dimensions into one fuzzy number.
- **Claim decomposition before scoring** forces the judge to do the work rather
  than emit a gut-feel score. The score becomes a derived ratio, not an opinion.
- **"Quote the exact span" makes violations falsifiable.** A reviewer can check
  each cited span against the source, so the judge is itself auditable — critical
  if you are going to trust it to gate a pipeline.
- **"Source is the only ground truth, no outside knowledge"** is the key guard
  against the judge rewarding claims that are true-in-general but absent-here,
  which is the whole point of a faithfulness check for RAG/summarisation.
- **A defined pass threshold + hard fail on contradictions** turns the rubric
  into a usable gate, not just a vibe score.
