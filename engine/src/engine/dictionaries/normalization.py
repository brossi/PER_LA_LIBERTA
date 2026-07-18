"""S3.0 normalization policy — the pre-lookup fold, built from the language profile.

The membership-oracle / segmentation **fold path** made an explicit, versionable object (S3.0
R2; ``docs/s3_0_plan.md`` D-A/D-F). There is no single "the normalization" in the live code:
``load_word_set`` lowercases only, ``normalize_for_comparison`` is lower→NFKD→drop-``[^a-z]``,
and ``DictionaryOracle`` folds the first char for chunk selection then probes two accent forms.
This policy owns **only** the oracle fold path — the membership path S3.1 oracle-gates on — reading
**exactly** ``{case_fold, accent_fold}`` from the profile and nothing else.

Two operations, each with a live ``steps.adjudicate.DictionaryOracle`` referent the S3.0 test
battery binds against (``test_resource_lineage`` invariant 8):

- :meth:`chunk_key` — first-char case+accent fold → which letter chunk to load (the oracle's
  ``word[0].lower().translate(fold)``). The case axis is ``case_fold`` (the literal ``.lower()``
  the live oracle bakes), so a case-sensitive or non-Latin book sources ``"none"``/``"casefold"``
  instead of inheriting a hardcoded lower.
- :meth:`probe_forms` — the ordered, de-duplicated ``[original, accent-folded]`` forms the legacy
  oracle boundary-searches (the oracle's ``word`` then ``word.translate(fold)``, the second only
  when it differs). Case is **not** applied here (the live oracle searches case-insensitively via a
  regex flag — a *search* concern, S3.1 — not by folding the probe form).

:meth:`descriptor` emits ``{case_fold, accent_fold}`` — exactly the two axes the ops read, so the
normalizer version (``structure.lineage``) hashes precisely what is applied: a field hashed-but-
unused or used-but-unhashed is a contract break the battery catches (invariant 17). The *single
canonical membership key* (full-token fold) S3.1's Zipf-DP consumer will need is **deferred to
S3.1** — it has no live oracle op to bind against here (D-F).

The tokenizer identity (``spacy_model``) and the boundary-search predicate (``word_letter_class``)
are **not** this policy's — they belong to S3.1's segmentation/search version. This module carries
no language literal: the fold axes are data read from the profile (``case_fold`` /
``accent_fold``), never baked here.

The fold ops land in S3.0.4 (#26); the normalizer-version hash over :meth:`descriptor` is
``structure.lineage``'s (S3.0.5 / #27).
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.util.text import build_fold_table


@dataclass(frozen=True, slots=True)
class NormalizationPolicy:
    """The pre-lookup fold over ``{case_fold, accent_fold}``, built from a language profile.

    Construct directly from the two profile axes (``NormalizationPolicy(case_fold=…,
    accent_fold=…)``); ``structure.lineage.ResourceLineage.build`` does exactly that from
    ``cfg.language``. ``case_fold`` is one of ``"lower" | "casefold" | "none"``; ``accent_fold`` is
    the profile's ``{"from", "to"}`` fold table (the same table ``util.text.build_fold_table``
    turns into a ``str.translate`` map). The object is a pure value — equal axes ⇒ equal policy ⇒
    equal version.
    """

    case_fold: str
    accent_fold: dict  # the profile's fixed {"from": ..., "to": ...} accented->base fold table

    def chunk_key(self, token: str) -> str:
        """The folded first-character chunk key for ``token`` (case+accent fold of ``token[0]``).

        Reproduces ``DictionaryOracle``'s ``word[0].lower().translate(fold)`` with ``.lower()``
        generalised to ``case_fold`` — case first, then the accent fold, so a case-folded base
        char still routes through the same accent table the live oracle uses for chunk selection.
        Precondition: ``token`` is non-empty (``token[0]``); the live oracle never folds an
        empty/sub-3-char word (it short-circuits before the fold), so the caller owns that guard.
        """
        return self._fold_case(token[0]).translate(build_fold_table(self.accent_fold))

    def probe_forms(self, token: str) -> list[str]:
        """The ordered, de-duplicated probe forms ``[token, accent-folded token]``.

        Reproduces the legacy oracle's ``word`` then ``word.translate(fold)`` search forms — the
        folded form is appended only when it differs from the original (so an unaccented token
        yields a single form). Case is **not** applied: the live oracle searches case-insensitively
        via a regex flag, a *search* concern (S3.1), not by folding the probe form here.
        """
        folded = token.translate(build_fold_table(self.accent_fold))
        return [token] if folded == token else [token, folded]

    def descriptor(self) -> dict:
        """The versionable descriptor — ``{case_fold, accent_fold}``, exactly the ops' inputs.

        The normalizer version is a hash of this descriptor (``structure.lineage``); its key set
        equals the profile fields the fold ops actually read (invariant 17).
        """
        return {"case_fold": self.case_fold, "accent_fold": self.accent_fold}

    def _fold_case(self, char: str) -> str:
        """Apply the ``case_fold`` axis to ``char`` — the generalised ``.lower()`` chunk_key bakes.

        The schema enum-bounds ``case_fold`` to these three modes, so an unknown value can only mean
        a schema/policy drift (a new mode added without an op): fail loud rather than silently
        leaving the case un-folded, which would mis-route the chunk key.
        """
        if self.case_fold == "lower":
            return char.lower()
        if self.case_fold == "casefold":
            return char.casefold()
        if self.case_fold == "none":
            return char
        raise ValueError(
            f"unknown case_fold mode {self.case_fold!r} (expected 'lower' | 'casefold' | 'none')"
        )
