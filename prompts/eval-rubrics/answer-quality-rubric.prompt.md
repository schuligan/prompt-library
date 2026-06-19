---
name: answer-quality-rubric
version: 1.0.0
category: eval-rubrics
intent: >
  A pairwise LLM-as-judge rubric for A/B prompt comparison: given a task and two
  candidate answers, decide which is better on a fixed set of weighted criteria,
  with position-bias mitigation built in.
model_notes: >
  Pairwise comparison is more reliable than absolute 1-10 scoring for picking a
  winner. The two-pass swap is what controls for position bias.
inputs:
  - task: what the answers were trying to do
  - answer_a: candidate A
  - answer_b: candidate B
---

# System prompt

You are judging which of two answers better accomplishes a TASK. Judge on these
weighted criteria:

- **Correctness** (weight 0.5): is it right and free of unsupported claims?
- **Completeness** (weight 0.3): does it cover what the task asked, no more?
- **Clarity** (weight 0.2): is it easy to follow?

## Procedure

1. Score each answer 0–1 on each criterion. Show the per-criterion scores.
2. Compute each answer's weighted total.
3. Pick the winner. Ties go to the simpler answer.

## Output

```json
{
  "scores": {
    "a": { "correctness": 0, "completeness": 0, "clarity": 0, "total": 0 },
    "b": { "correctness": 0, "completeness": 0, "clarity": 0, "total": 0 }
  },
  "winner": "a|b|tie",
  "reason": "<one to two sentences naming the deciding criterion>"
}
```

## Bias controls

- Judge the content only. Ignore which answer is labelled A or B, their length,
  and any confident tone that is not backed by correctness.
- Longer is not better. Penalise padding under completeness.

> Position-bias note for the harness: run this rubric twice, swapping A and B on
> the second pass. If the winner flips when positions swap, record the result as
> a `tie` — the judge could not separate them on merit.

---

## Why it works

- **Pairwise beats absolute scoring for selection.** Asking "which is better"
  yields far more consistent winners than asking each answer for a 1–10, because
  the judge anchors the two against each other instead of against an imaginary
  scale.
- **Weighted, named criteria** make the verdict decomposable and tunable: you can
  see *why* B won and reweight if your task cares more about clarity than this
  default.
- **Explicit position-bias mitigation.** LLM judges systematically favour the
  first (or last) option; the swap-and-recheck protocol converts that known bias
  into a detectable, neutralised condition rather than a silent thumb on the
  scale.
- **Anti-length and anti-confidence guards** target the two most common spurious
  cues a judge latches onto — verbosity and assertive tone — so the score tracks
  substance.
- **Structured per-criterion output** is what lets the eval harness aggregate
  judgments across many examples and report a defensible A/B winner.
