"""SymSpell loader — the edit-distance speller behind cleanup's dictionary correction.

Port of ``cleanup._get_spellchecker`` (cleanup.py:50-59): build a ``SymSpell`` index from a
FrequencyWords/Morph-it style wordlist (``word count`` per line). The live code used a
function-attribute singleton bound to one hardcoded path; here the path comes from
``cfg.language.frequency_dictionary`` (resolved through ``asset_path``), and the cache is keyed by
the resolved path — mirroring ``dictionaries.frequency.load_word_set`` and the spaCy-pipeline cache
in ``lang.base``, so two books with different dictionaries never collide.

``symspellpy`` is imported lazily inside ``load_symspell`` so importing this module needs no native
dependency; the tuning (edit-distance 2, prefix length 7) is the verbatim live default, kept a code
default because it is engine-processing tuning, not a per-book language fact.
"""

from __future__ import annotations

from pathlib import Path

_MAX_EDIT_DISTANCE = 2
_PREFIX_LENGTH = 7

#: Process-wide cache: resolved wordlist path → loaded SymSpell. Keyed by the absolute path so a
#: different dictionary builds its own index; loading the 708K-entry list once per process keeps
#: the test suite fast.
_SPELLERS: dict[Path, object] = {}


def load_symspell(path: Path):
    """Load the frequency wordlist at ``path`` into a ``SymSpell`` index (cached by path).

    Each line is ``<word> <count>`` (``term_index=0``, ``count_index=1``), exactly as the live
    ``_get_spellchecker``. Raises ``FileNotFoundError`` if the wordlist is absent — a missing
    dictionary is a hard configuration error, not something to paper over with an empty index.
    """
    path = Path(path).resolve()
    cached = _SPELLERS.get(path)
    if cached is not None:
        return cached

    if not path.is_file():
        raise FileNotFoundError(f"frequency dictionary not found: {path}")

    from symspellpy import SymSpell

    sym = SymSpell(max_dictionary_edit_distance=_MAX_EDIT_DISTANCE, prefix_length=_PREFIX_LENGTH)
    sym.load_dictionary(str(path), term_index=0, count_index=1)
    _SPELLERS[path] = sym
    return sym
