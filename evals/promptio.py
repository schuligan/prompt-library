"""Load `.prompt.md` files: split YAML frontmatter from the prompt body."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "prompts"


@dataclass(frozen=True)
class Prompt:
    """A parsed prompt file."""

    path: Path
    meta: dict = field(default_factory=dict)
    body: str = ""

    @property
    def name(self) -> str:
        return str(self.meta.get("name", self.path.stem))

    @property
    def category(self) -> str:
        return str(self.meta.get("category", self.path.parent.name))

    @property
    def version(self) -> str:
        return str(self.meta.get("version", "0.0.0"))

    @property
    def intent(self) -> str:
        return " ".join(str(self.meta.get("intent", "")).split())


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (meta, body). Frontmatter is a leading `---` fenced YAML block."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = yaml.safe_load(parts[1]) or {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, parts[2].lstrip("\n")


def load_prompt(path: str | Path) -> Prompt:
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    meta, body = _split_frontmatter(raw)
    return Prompt(path=p, meta=meta, body=body)


def iter_prompts(root: Path = PROMPTS_DIR):
    """Yield every parsed `.prompt.md` under `root`, sorted for stability."""
    for path in sorted(root.rglob("*.prompt.md")):
        yield load_prompt(path)
