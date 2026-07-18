"""LanguagePlugin registry: language id → implementation.

A manifest names its language by id (``"it"``); the orchestrator resolves it here.
New languages register by adding an entry — the core never imports a concrete plugin.
"""

from __future__ import annotations

from .base import LanguagePlugin
from .italian import ItalianLanguagePlugin

class UnknownLanguageError(Exception):
    """A manifest names a language id with no registered ``LanguagePlugin``.

    A plain ``Exception`` (not ``KeyError``) so its ``str`` is the bare message — the CLI
    surfaces it as a clean exit-1 config error rather than a quote-wrapped traceback.
    """


_REGISTRY: dict[str, type[LanguagePlugin]] = {
    ItalianLanguagePlugin.language_id: ItalianLanguagePlugin,
}


def get_language_plugin(language_id: str) -> LanguagePlugin:
    """Instantiate the plugin registered for ``language_id``."""
    try:
        cls = _REGISTRY[language_id]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise UnknownLanguageError(
            f"no LanguagePlugin registered for language id {language_id!r}; known: {known}"
        ) from None
    return cls()


def available_languages() -> list[str]:
    return sorted(_REGISTRY)
