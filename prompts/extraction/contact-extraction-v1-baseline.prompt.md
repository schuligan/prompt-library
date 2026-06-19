---
name: contact-extraction-v1-baseline
version: 1.0.0
category: extraction
intent: >
  Baseline variant. Extract contact details (name, email, phone, company) from
  free text into JSON. Minimal instructions — used as the control in the A/B
  eval against the hardened v2.
model_notes: >
  Intentionally underspecified to demonstrate, via the eval harness, how a thin
  prompt drifts: it tends to omit nulls and occasionally adds prose.
inputs:
  - text: free-form text possibly containing contact details
schema: ../../schemas/contact.schema.json
---

# System prompt

Extract the contact information from the text below and return it as JSON with
the fields: name, email, phone, company.

---

## Why it works (and where it falls short)

- It works *often enough* to look fine in a demo, which is exactly the trap.
- It has **no null policy**, so absent fields get dropped or invented depending
  on the run — non-deterministic shape.
- It has **no "JSON only" guard**, so the model sometimes wraps output in a
  markdown fence or adds a sentence, breaking `json.loads`.
- It does **not normalise phone numbers or constrain email shape**.

This file exists to be *beaten*. See `contact-extraction-v2-hardened` and the
`evals/` harness, which scores both variants on the same golden inputs and shows
the hardened version winning on schema-validity and field accuracy.
