"""Frequency-wordlist loader — the membership set behind validate's word-quality check.

Port of ``cleanup._get_word_set`` (cleanup.py:86-97): read a FrequencyWords/Morph-it style
wordlist (``word count`` per line) into a lowercased set for O(1) membership. The live code
used a function-attribute singleton bound to one hardcoded path; here the path comes from
``cfg.language.frequency_dictionary`` (resolved through ``asset_path``), so two books with
different dictionaries never collide — the cache is keyed by the resolved path, mirroring
the spaCy-pipeline cache in ``lang.base``.

Consumed by M2 ``validate`` now and by M4b ``cleanup`` later (the same word set drives both).
"""

from __future__ import annotations

from pathlib import Path

#: Process-wide cache: resolved path → frozen word set. Frozen so callers can't mutate the
#: shared set, and keyed by the absolute path so a different dictionary loads independently.
_WORD_SETS: dict[Path, frozenset[str]] = {}


def load_word_set(path: Path) -> frozenset[str]:
    """Load the frequency wordlist at ``path`` as a lowercased ``frozenset``.

    Each line is ``<word> <count>``; only the first token is kept. Raises
    ``FileNotFoundError`` if the wordlist is absent — a missing dictionary is a hard
    configuration error, not something to paper over with an empty set.
    """
    path = Path(path).resolve()
    cached = _WORD_SETS.get(path)
    if cached is not None:
        return cached

    words: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if parts:
                words.add(parts[0].lower())

    frozen = frozenset(words)
    _WORD_SETS[path] = frozen
    return frozen
