"""Jinja2 ``StrictUndefined`` prompt templating — input-side prompt assembly.

The first consumer is the OCR prompt (M4a); every later book/language-aware prompt
(triage/cleanup/translate/refine in M4b/M4c; multi-eval/synthesis in M5) renders through the
same machinery and the same namespaced context. ``StrictUndefined`` makes a template that
references an absent context key a hard error at render time, not a silent empty string —
validate-bindings for prompts.

The boundary (D2/BR-008):

  - the rendering **machinery** is engine-package-owned (here);
  - the template **files** are book-neutral and live in the shared ``profiles/prompts/`` tree —
    reusable prompt knowledge that outlives any one book, not per-book;
  - the **book/language** supply only values, through a namespaced render context:
    ``{{ book.* }}`` is book identity (``manifest.prompt_context``) and ``{{ language.* }}`` is
    cross-title language facts (display name, accent inventory) from the language profile.

Keeping book identity out of both the engine core and the templates is the engine-agnostic
invariant the forward-fork rests on; the synthetic-render leakage test is its proof.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, StrictUndefined

from ..config.models import ResolvedConfig

# templating.py -> prompts -> engine(pkg) -> src -> engine/ (project root)
ENGINE_ROOT = Path(__file__).resolve().parents[3]

#: Shared, book-neutral prompt templates. A future book needing a structurally different prompt
#: would add a per-book override path; deferred until one does (BR-008 note).
PROMPTS_DIR = ENGINE_ROOT / "profiles" / "prompts"

#: One process-wide environment. ``autoescape=False`` because prompts are plain text, not HTML;
#: ``StrictUndefined`` turns any unbound ``{{ ... }}`` into a render-time error.
_ENV = Environment(undefined=StrictUndefined, autoescape=False)


class PromptTemplate:
    """A book-neutral prompt template, rendered on demand against a supplied context."""

    def __init__(self, source: str, *, name: str = "<string>") -> None:
        self.name = name
        self._template = _ENV.from_string(source)

    @classmethod
    def load(cls, name: str, *, prompts_dir: Path | None = None) -> PromptTemplate:
        """Load ``profiles/prompts/<name>.txt.j2`` (``name`` e.g. ``"ocr"``)."""
        base = prompts_dir or PROMPTS_DIR
        path = base / f"{name}.txt.j2"
        if not path.is_file():
            raise FileNotFoundError(f"prompt template not found: {path}")
        return cls(path.read_text(encoding="utf-8"), name=name)

    def render(self, **context) -> str:
        """Render with ``context``; an unbound variable raises ``jinja2.UndefinedError``."""
        return self._template.render(**context)


def build_prompt_context(cfg: ResolvedConfig) -> dict:
    """Assemble the namespaced render context (BR-008): book identity + language facts.

    Returns ``{"book": {...}, "language": {...}}`` — the two top-level namespaces every
    book/language-aware prompt renders. ``book`` is the manifest's free ``prompt_context``
    verbatim (book identity); ``language`` is the cross-title facts a prompt needs (the human
    display name + the accent inventory the model is asked to preserve). A template referencing a
    key absent from either namespace fails at render under ``StrictUndefined`` — so a forgotten
    ``prompt_context`` key surfaces immediately, not as silent empty text.
    """
    return {
        "book": dict(cfg.manifest.prompt_context),
        "language": {
            "display_name": cfg.language.display_name,
            "accent_inventory": list(cfg.language.accent_inventory),
        },
    }
