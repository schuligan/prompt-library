# Improver example inputs

Raw, weak prompts to try the improver on. Each is deliberately under-specified —
no role, no output format, no refusal policy — so the diagnosis lights up and the
rewrite has something to fix.

```bash
# Diagnose + rewrite a weak one-liner
python cli.py improve --file improver/examples/weak-extraction.txt

# A free-text block pasted from an inbox / notes
python cli.py improve --file improver/examples/inbox-paste.txt

# Or pass text inline
python cli.py improve "summarize this"

# Print only the rewritten prompt (e.g. to pipe into a new .prompt.md)
python cli.py improve --file improver/examples/inbox-paste.txt --plain
```
