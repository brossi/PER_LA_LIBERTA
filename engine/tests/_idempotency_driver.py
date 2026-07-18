"""I9 idempotency driver — NOT a pytest test (no ``test_`` prefix, never collected).

Run by ``test_invariants_controls`` in two subprocesses under different ``PYTHONHASHSEED`` values; it
prints a stable SHA-256 of the M4b deterministic surfaces' output (triage's pure resolution passes +
cleanup's deterministic text/flag generation). Two identical hashes prove no set/dict iteration order
leaked into written output. Heavy models are stubbed: the dictionary-correction path has no
set→output leak (``proper_indices`` is membership-only), and its determinism is separately
underwritten by the detcore golden's stability — this driver targets the cheap set-bearing paths
(``seen_flig``, the flag scans) without a 40 s model load per process.
"""

from __future__ import annotations

import hashlib
import json


def _verdict(category, proposed, confidence, needs_human):
    return {
        "category": category, "proposed_reading": proposed, "confidence": confidence,
        "reasoning": "x", "needs_human": needs_human,
    }


class _Tok:
    def __init__(self, i, text, ws):
        self.i, self.text, self.whitespace_, self.pos_ = i, text, ws, "X"


class _Doc:
    ents = ()

    def __init__(self, line):
        toks = line.split(" ")
        self._t = [_Tok(i, t, " " if i < len(toks) - 1 else "") for i, t in enumerate(toks)]

    def __iter__(self):
        return iter(self._t)


class _Sym:
    def lookup(self, *a, **k):
        return []


def main() -> None:
    from engine.config.loader import load_book
    from engine.steps import cleanup, triage

    reviewed = [
        {"chapter": "c", "paragraph": 0, "chosen": "comuni",
         "triage": _verdict("ocr_confusion", "comune", "high", False)},
        {"chapter": "c", "paragraph": 1, "chosen": "foo",
         "triage": _verdict("alignment_drift", "zzzzzzzz", "high", False)},
        {"chapter": "c", "paragraph": 2, "chosen": "bar",
         "triage": _verdict("unknown", "bar", "low", True)},
    ]
    resolved, stats = triage.apply_resolution_passes(reviewed)

    cfg = load_book("per_la_liberta")
    rules = cleanup.build_rules(cfg)
    word_set = frozenset({"comune", "gatto", "nero", "libertà", "prova", "testo"})
    sample = (
        "Il gatto-nero corre 165 3E:\n\n"
        "una prova com-une di testo con parole strane\n\n"
        "Parola^parola e altre cose"
    )
    text, flags, punct = cleanup.clean_text(sample, word_set, rules, sym=_Sym(), nlp=lambda s: _Doc(s))

    payload = {"triage": [resolved, stats], "cleanup": [text, flags, punct]}
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode("utf-8")).hexdigest()
    print(digest)


if __name__ == "__main__":
    main()
