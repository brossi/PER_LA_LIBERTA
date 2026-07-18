"""TranslationProvider abstraction (Anthropic/Gemini/OpenAI) + TranslationResult.
Small port of the top-level providers.py: retry helpers import from engine.util,
the dictionary-context fragment becomes a neutral hook driven by
LanguageProfile.period_dictionaries. Scaffold stub (M5)."""

from __future__ import annotations
