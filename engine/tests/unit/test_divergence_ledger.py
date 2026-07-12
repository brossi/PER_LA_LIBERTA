"""Invariant I3 (mechanizable sliver) — divergence-ledger coherence.

Port fidelity rests on two things: deterministic steps reproduce the frozen-from-live goldens,
and *any* change to a golden is licensed by a ledger entry citing ground truth (the anti-cheat
rule, ``port_discipline.md`` §5). The hard half — proving a golden was not quietly re-baselined
to launder an unlicensed divergence — needs human git-diff-vs-ledger review and ground-truth
judgement; it is a documented probe, not a unit test (``engine/docs/invariants.md``, I3 residual
risk). What *is* mechanizable, and guarded here: the ledger stays machine-parseable and every
entry is well-formed, so a malformed or partial divergence record cannot slip in silently.

The real ledger is empty today, so the structural assertion on it is forward-looking. The inline
fixtures below give the validator teeth *now* — they exercise the accept and reject branches the
empty ledger never would (the single-fixture-blind-spot rule).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

LEDGER = Path(__file__).resolve().parents[2] / "docs" / "decisions" / "divergence_ledger.md"
# A real entry header: digits after the dash. The format-template lines in the doc use the
# literal "DL-NNN"/"RF-NNN" (letters), so they are correctly not parsed as entries.
_ENTRY_RE = re.compile(r"^## (DL|RF)-(\d+)\b", re.MULTILINE)


def _validate_ledger(text: str) -> list[tuple[str, int]]:
    """Raise ``ValueError`` on an incoherent ledger; return the parsed ``(kind, number)`` entries.

    Coherence = ids sequential from 1 within each kind, and each entry carries the cite its kind
    requires (a DL entry names the ``Golden:`` it moves; an RF entry names what it ``Re-froze:``).
    """
    matches = list(_ENTRY_RE.finditer(text))
    parsed: list[tuple[str, int]] = []
    for i, m in enumerate(matches):
        kind, number = m.group(1), int(m.group(2))
        body = text[m.end() : (matches[i + 1].start() if i + 1 < len(matches) else len(text))]
        required = "Golden:" if kind == "DL" else "Re-froze:"
        if required not in body:
            raise ValueError(f"{kind}-{number:03d} is missing its required {required!r} line")
        parsed.append((kind, number))

    for kind in ("DL", "RF"):
        nums = sorted(n for k, n in parsed if k == kind)
        if nums != list(range(1, len(nums) + 1)):
            raise ValueError(f"{kind} ids must be sequential from 1, got {nums}")
    return parsed


def test_real_ledger_is_coherent():
    # Forward-guard: the moment a real DL/RF entry lands, it must be well-formed. Empty today.
    assert LEDGER.is_file(), f"divergence ledger missing at {LEDGER}"
    _validate_ledger(LEDGER.read_text(encoding="utf-8"))


def test_format_template_lines_are_not_counted_as_entries():
    # The doc shows the entry shape with "DL-NNN"/"RF-NNN" (letters, not digits); those lines must
    # not be read as entries-with-no-cite. Validated in isolation, not via `== []` on the full doc,
    # so this stays green when a first legitimate DL/RF entry lands (#55); the non-vacuity guard
    # keeps the fixture bound to the templates the doc actually carries.
    doc = LEDGER.read_text(encoding="utf-8")
    templates = [line for line in doc.splitlines() if "DL-NNN" in line or "RF-NNN" in line]
    assert templates, f"format templates (DL-NNN/RF-NNN) missing from {LEDGER}"
    assert _validate_ledger("\n".join(templates) + "\n") == []


def test_validator_accepts_a_well_formed_dl_entry():
    good = "## DL-001 — render hardening (2026-06-23, ocr)\n- Why better: x\n- Golden: ocr_x (a → b)\n"
    assert _validate_ledger(good) == [("DL", 1)]


def test_validator_rejects_a_dl_entry_missing_its_golden_cite():
    bad = "## DL-001 — title (2026-06-23, ocr)\n- Why better: x but no fixture named\n"
    with pytest.raises(ValueError, match="Golden:"):
        _validate_ledger(bad)


def test_validator_rejects_non_sequential_ids():
    bad = "## DL-002 — skipped DL-001 (2026-06-23, ocr)\n- Golden: g (a → b)\n"
    with pytest.raises(ValueError, match="sequential"):
        _validate_ledger(bad)
