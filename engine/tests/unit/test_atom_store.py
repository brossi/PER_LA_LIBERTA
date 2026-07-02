"""S1.5 — the persisted atom store, synthetic floor (ENGINE_STRUCTURE_PLAN §3.5/§3.6/§11.1; D21).

Three tiers, the S1.5 done-when (PLAN §9), each proven red by ``scratchpad/mutate_atom_store.py``:

- **serialization-invariance** — ``load(save(s)) == s`` over every addressing field (``raw_span``,
  ``raw_source_hash``, ``geom`` present *and* absent, ``derived_from``) and the witness ``GapRecord``
  stream, incl. a mixed-whitespace gap that proves gaps are *persisted bytes*, not width-derived;
- **schema/version fail-loud** — a stale version, wrong stale class, missing key, unknown kind, or a
  wrapped model-invariant each raise ``StaleArtifactError`` at the load boundary;
- **integrity** — the anchored round-trip self-check catches a persisted text drift / dropped gap;
  reference-integrity resolves every canonical back-link.

``test_atom_store_real_input`` runs the same store over the committed PLL witnesses.
"""

from __future__ import annotations

import dataclasses

import pytest

from engine.errors import CaptureError, MissingInputError, RoundTripError, StaleArtifactError
from engine.paths import BookWorkspace
from engine.structure.atom_store import (
    CANONICAL,
    WITNESS,
    AtomStream,
    assert_atom_hashes,
    assert_reference_integrity,
    assert_stream_roundtrip,
    from_json,
    load_stream,
    save_stream,
    stream_path,
    to_json,
)
from engine.structure.atoms import (
    PROCESSING_SCOPE_EXCLUDED,
    PROCESSING_SCOPE_INCLUDED,
    Atom,
    AtomDerivation,
    Geom,
)
from engine.structure.capture import build_canonical, capture_witness
from engine.structure.roundtrip import hash_raw
from engine.structure.roundtrip_gate import GapRecord, gap_records
from engine.util.jsonio import atomic_write_json, read_json

# A present, matched word-box geom (the field axis capture_witness never produces — it emits absent).
GEOM = Geom.matched(
    page=12,
    bbox=(72.0, 118.4, 523.1, 134.8),
    geometry_engine="pymupdf-ocr",
    matched_witness_id="copy1",
    match_method="token-bbox",
    match_confidence=0.97,
)


def _ws(tmp_path) -> BookWorkspace:
    return BookWorkspace.for_book("testbook", tmp_path).ensure()


def _witness_stream(source: str, witness: str = "copy1", **kw) -> AtomStream:
    """Capture ``source`` and wrap it as a witness :class:`AtomStream` (real atoms + real gaps)."""
    atoms = capture_witness(source, witness, **kw)
    return AtomStream.witness(witness, atoms, gap_records(atoms, source), source)


def _furniture(line: str) -> str | None:
    return "page-furniture" if line.strip() == "###" else None


# --- serialization-invariance ---------------------------------------------------------------- #


def test_witness_stream_round_trips_through_json_and_disk(tmp_path):
    # A source with a furniture line → both included body atoms AND an excluded furniture atom, plus
    # leading/inter/trailing gaps. Every field must survive json + disk byte-for-byte.
    source = "\nAlpha line\n\n###\n\nBeta line\n\n"
    stream = _witness_stream(source, classify_line=_furniture)
    assert any(a.processing_scope == PROCESSING_SCOPE_EXCLUDED for a in stream.atoms)
    assert any(a.processing_scope == PROCESSING_SCOPE_INCLUDED for a in stream.atoms)
    assert stream.gaps, "source has inter-atom whitespace to persist"

    assert from_json(to_json(stream)) == stream            # envelope round-trip
    ws = _ws(tmp_path)
    save_stream(ws, stream)
    assert load_stream(ws, "copy1") == stream              # disk round-trip


def test_present_geom_round_trips_exact(tmp_path):
    ws = _ws(tmp_path)
    src = "word"
    atom = Atom(
        atom_id="copy1_00000", text=src, raw_span=(0, 4), raw_source_hash=hash_raw(src),
        page_range=(12, 12), norm_layer="raw", geom=GEOM, capture_provenance_class="body",
        witness="copy1", processing_scope=PROCESSING_SCOPE_INCLUDED,
    )
    stream = AtomStream.witness("copy1", [atom], [], src)
    save_stream(ws, stream)
    loaded = load_stream(ws, "copy1")
    g = loaded.atoms[0].geom
    assert g == GEOM and g.present and g.bbox == (72.0, 118.4, 523.1, 134.8)
    assert isinstance(g.bbox, tuple) and g.match_confidence == 0.97 and g.page == 12


def test_absent_geom_round_trips_as_absent(tmp_path):
    ws = _ws(tmp_path)
    stream = _witness_stream("plain body line\n")
    save_stream(ws, stream)
    loaded = load_stream(ws, "copy1")
    assert all(not a.geom.present for a in loaded.atoms)
    assert all(a.geom.bbox is None and a.geom.page is None for a in loaded.atoms)  # never invented


def test_mixed_whitespace_gap_persists_bytes_not_width(tmp_path):
    # The carried S1.4-audit decision in one assertion: a width-3 gap of "\t \n" is NOT recoverable
    # from the span width alone. The store must persist the gap *bytes*; an atoms-only / width-only
    # store would round-trip vacuously on a newline-only witness and silently lie here.
    ws = _ws(tmp_path)
    source = "AA\n \t\nBB"        # blank middle line " \t" flushes → inter-atom gap "\n \t\n" (mixed ws)
    stream = _witness_stream(source)
    assert any("\t" in g.text and " " in g.text for g in stream.gaps), "expected a mixed-ws gap"
    save_stream(ws, stream)
    loaded = load_stream(ws, "copy1")
    assert [g.text for g in loaded.gaps] == [g.text for g in stream.gaps]  # exact bytes, not widths


def test_canonical_stream_round_trips_with_derivations(tmp_path):
    ws = _ws(tmp_path)
    t1, t2 = "Alpha\n\nBeta\n", "Alpha\n\nBeta\n"
    canon = AtomStream.canonical(
        build_canonical(
            {"copy1": capture_witness(t1, "copy1"), "copy2": capture_witness(t2, "copy2")},
            ["copy1", "copy2"],
        )
    )
    assert canon.atoms and all(a.derived_from for a in canon.atoms)
    assert from_json(to_json(canon)) == canon
    save_stream(ws, canon)
    loaded = load_stream(ws, "canonical")
    assert loaded == canon
    assert all(a.witness is None for a in loaded.atoms)               # canonical is no single witness
    assert isinstance(loaded.atoms[0].derived_from[0], AtomDerivation)


def test_canonical_envelope_carries_no_gaps_or_source_hash(tmp_path):
    canon = AtomStream.canonical(
        build_canonical(
            {"copy1": capture_witness("X\n", "copy1"), "copy2": capture_witness("X\n", "copy2")},
            ["copy1", "copy2"],
        )
    )
    env = to_json(canon)
    assert "gaps" not in env and "source_hash" not in env             # tiles no single source
    assert env["kind"] == CANONICAL and env["stale_class"] == "atom-stream"


# --- persistence path ------------------------------------------------------------------------ #


def test_save_writes_under_data_atoms_creating_the_dir(tmp_path):
    ws = _ws(tmp_path)
    stream = _witness_stream("body\n")
    path = save_stream(ws, stream)
    assert path == ws.root / "data" / "atoms" / "copy1.json"
    assert path.is_file() and path == stream_path(ws, "copy1")


def test_load_missing_file_raises_missing_input(tmp_path):
    ws = _ws(tmp_path)
    with pytest.raises(MissingInputError, match="not found"):
        load_stream(ws, "copy1")


# --- schema / version fail-loud -------------------------------------------------------------- #


def test_from_json_rejects_stale_schema_version(tmp_path):
    env = to_json(_witness_stream("body\n"))
    env["schema_version"] = 999
    with pytest.raises(StaleArtifactError, match="schema version"):
        from_json(env)


def test_from_json_rejects_wrong_stale_class():
    env = to_json(_witness_stream("body\n"))
    env["stale_class"] = "structure-map"
    with pytest.raises(StaleArtifactError, match="stale_class"):
        from_json(env)


def test_from_json_rejects_missing_required_key():
    env = to_json(_witness_stream("body\n"))
    del env["atoms"]
    with pytest.raises(StaleArtifactError, match="missing required key"):
        from_json(env)


def test_from_json_rejects_unknown_kind():
    env = to_json(_witness_stream("body\n"))
    env["kind"] = "relations"
    with pytest.raises(StaleArtifactError, match="kind"):
        from_json(env)


def test_from_json_wraps_model_invariant_as_stale(tmp_path):
    # A persisted atom with a length-3 raw_span violates the S1.1 model invariant. In memory that is a
    # ValueError (programming error); through the load boundary it is corrupt data → StaleArtifactError.
    env = to_json(_witness_stream("body\n"))
    env["atoms"][0]["raw_span"] = [0, 1, 2]
    with pytest.raises(StaleArtifactError, match="malformed"):
        from_json(env)


# --- integrity: anchored round-trip self-check ----------------------------------------------- #


def test_load_detects_persisted_text_drift(tmp_path):
    # The whole-artifact value of S1.4, now anchored in the store: drift one atom's text on disk
    # without touching its span. The reconstructed source no longer hashes to the stored anchor.
    ws = _ws(tmp_path)
    save_stream(ws, _witness_stream("Alpha\n\nBeta\n"))
    path = stream_path(ws, "copy1")
    env = read_json(path)
    env["atoms"][0]["text"] = env["atoms"][0]["text"] + "X"
    atomic_write_json(path, env)
    with pytest.raises(RoundTripError, match="round-trip failed"):
        load_stream(ws, "copy1")


def test_load_detects_dropped_gap(tmp_path):
    ws = _ws(tmp_path)
    save_stream(ws, _witness_stream("Alpha\n\nBeta\n"))
    path = stream_path(ws, "copy1")
    env = read_json(path)
    assert env["gaps"], "stream had a gap to drop"
    env["gaps"] = env["gaps"][:-1]                          # a hole opens in the tiling
    atomic_write_json(path, env)
    with pytest.raises(RoundTripError):
        load_stream(ws, "copy1")


def test_load_rejects_id_filename_mismatch(tmp_path):
    ws = _ws(tmp_path)
    stream = _witness_stream("body\n", witness="copy1")        # envelope stream_id == "copy1"
    save_stream(ws, stream)                                    # creates data/atoms/ + copy1.json
    atomic_write_json(stream_path(ws, "copy2"), to_json(stream))  # same envelope, written as copy2.json
    with pytest.raises(StaleArtifactError, match="id mismatch"):
        load_stream(ws, "copy2")


def test_assert_stream_roundtrip_is_noop_for_canonical():
    canon = AtomStream.canonical(
        build_canonical(
            {"copy1": capture_witness("X\n", "copy1"), "copy2": capture_witness("X\n", "copy2")},
            ["copy1", "copy2"],
        )
    )
    assert_stream_roundtrip(canon)                          # no source to anchor → no-op, no raise


# --- construction guards (in-memory ValueError) ---------------------------------------------- #


def test_canonical_with_gaps_raises():
    atoms = build_canonical(
        {"copy1": capture_witness("X\n", "copy1"), "copy2": capture_witness("X\n", "copy2")},
        ["copy1", "copy2"],
    )
    with pytest.raises(ValueError, match="no gap records"):
        AtomStream(stream_id="canonical", kind=CANONICAL, atoms=tuple(atoms), gaps=(GapRecord((0, 1), " "),))


def test_canonical_with_source_hash_raises():
    with pytest.raises(ValueError, match="source_hash must be None"):
        AtomStream(stream_id="canonical", kind=CANONICAL, atoms=(), source_hash="sha256:x")


def test_witness_without_source_hash_raises():
    with pytest.raises(ValueError, match="must carry a source_hash"):
        AtomStream(stream_id="copy1", kind=WITNESS, atoms=())


def test_bad_kind_raises():
    with pytest.raises(ValueError, match="kind must be"):
        AtomStream(stream_id="copy1", kind="relations", atoms=(), source_hash="sha256:x")


@pytest.mark.parametrize("bad", ["", "../escape", "a/b", ".", ".."])
def test_bad_stream_id_raises(bad):
    with pytest.raises(ValueError, match="flat filename stem"):
        AtomStream.witness(bad, [], [], "src")


# --- integrity: reference-integrity ---------------------------------------------------------- #


def _canon_and_witnesses():
    t1, t2 = "Alpha\n\nBeta\n", "Alpha\n\nBeta\n"
    w1, w2 = capture_witness(t1, "copy1"), capture_witness(t2, "copy2")
    canon = AtomStream.canonical(build_canonical({"copy1": w1, "copy2": w2}, ["copy1", "copy2"]))
    witnesses = {
        "copy1": AtomStream.witness("copy1", w1, gap_records(w1, t1), t1),
        "copy2": AtomStream.witness("copy2", w2, gap_records(w2, t2), t2),
    }
    return canon, witnesses


def test_reference_integrity_passes_when_all_resolve():
    canon, witnesses = _canon_and_witnesses()
    assert_reference_integrity(canon, witnesses)            # every derived_from resolves


def test_reference_integrity_unknown_witness_raises():
    canon, witnesses = _canon_and_witnesses()
    bad = dataclasses.replace(canon.atoms[0], derived_from=(AtomDerivation("copyX", "copy1_00000"),))
    broken = AtomStream.canonical((bad,) + canon.atoms[1:])
    with pytest.raises(CaptureError, match="unknown witness"):
        assert_reference_integrity(broken, witnesses)


def test_reference_integrity_unknown_atom_id_raises():
    canon, witnesses = _canon_and_witnesses()
    bad = dataclasses.replace(canon.atoms[0], derived_from=(AtomDerivation("copy1", "copy1_99999"),))
    broken = AtomStream.canonical((bad,) + canon.atoms[1:])
    with pytest.raises(CaptureError, match="resolves to no atom"):
        assert_reference_integrity(broken, witnesses)


def test_reference_integrity_requires_canonical_kind():
    _canon, witnesses = _canon_and_witnesses()
    with pytest.raises(ValueError, match="expects a 'canonical'"):
        assert_reference_integrity(witnesses["copy1"], witnesses)


def test_reference_integrity_rejects_empty_derivation():
    # The S1.3a property "every canonical atom has >=1 witness derivation" is vacuously true for an
    # empty derived_from — the store is the persistence-boundary enforcer (5-lens audit, agent C).
    canon, witnesses = _canon_and_witnesses()
    orphan = dataclasses.replace(canon.atoms[0], derived_from=())
    broken = AtomStream.canonical((orphan,) + canon.atoms[1:])
    with pytest.raises(CaptureError, match="no derived_from"):
        assert_reference_integrity(broken, witnesses)


# === 5-lens adversarial-audit hardening (S1.5) ================================================= #
# Each test below pins a defect the overlapping-subagent audit surfaced; each is mutation-proven by
# scratchpad/mutate_atom_store.py.


def _atom(text, start, end, *, witness="copy1", aid=None, hash_=None, geom=None, derived=()):
    return Atom(
        atom_id=aid or f"{witness}_{start:05d}",
        text=text,
        raw_span=(start, end),
        raw_source_hash=hash_ if hash_ is not None else hash_raw(text),
        page_range=(1, 1),
        norm_layer="raw",
        geom=geom or Geom.absent(),
        capture_provenance_class="body",
        witness=witness,
        derived_from=derived,
    )


# --- D1: from_json / load_stream is a TOTAL contract (no raw TypeError / JSONDecodeError leak) ---- #


@pytest.mark.parametrize("doc", [None, 5, 1.5, True])
def test_from_json_rejects_non_object_document(doc):
    # A valid-JSON-but-non-object document used to TypeError out of the first membership test.
    with pytest.raises(StaleArtifactError, match="must be a JSON object"):
        from_json(doc)


@pytest.mark.parametrize("field,bad", [("raw_span", 5), ("derived_from", 7), ("page_range", 9)])
def test_from_json_wraps_wrong_typed_field_as_stale(field, bad):
    # A wrong-TYPE (scalar where a list is expected) lands on tuple()/`for` → TypeError, which the
    # contract must wrap — the failure branch the length-3-LIST fixture never exercised.
    env = to_json(_witness_stream("body\n"))
    env["atoms"][0][field] = bad
    with pytest.raises(StaleArtifactError, match="malformed"):
        from_json(env)


@pytest.mark.parametrize("garbage", ["", "   ", "not json {{{", "[1, 2,", "null"])
def test_load_rejects_non_json_or_non_object_file(tmp_path, garbage):
    ws = _ws(tmp_path)
    save_stream(ws, _witness_stream("body\n"))           # create data/atoms/
    path = stream_path(ws, "copy1")
    path.write_text(garbage, encoding="utf-8")           # clobber with garbage (test-only direct write)
    with pytest.raises(StaleArtifactError):              # clean engine error, never a bare traceback
        load_stream(ws, "copy1")


# --- D2: per-atom address check makes raw_source_hash load-bearing (compensated drift / canonical) - #


def test_load_detects_compensated_drift(tmp_path):
    # Two directly-adjacent atoms; on disk move a byte across the boundary so the CONCATENATION is
    # unchanged. The whole-artifact anchor (it checks the concatenation) passes — only the per-atom
    # address check catches it. The "address drift" message proves it was the per-atom tier, not the
    # anchor ("round-trip failed"), that fired — i.e. the per-atom check is non-redundant.
    ws = _ws(tmp_path)
    stream = AtomStream.witness("copy1", [_atom("A", 0, 1), _atom("B", 1, 2, aid="copy1_00001")], [], "AB")
    save_stream(ws, stream)
    path = stream_path(ws, "copy1")
    env = read_json(path)
    env["atoms"][0]["text"] = "AB"                        # 'B' moved left across the atom boundary
    env["atoms"][1]["text"] = ""                          # concatenation "AB" unchanged → anchor blind
    atomic_write_json(path, env)
    with pytest.raises(RoundTripError, match="address drift"):
        load_stream(ws, "copy1")


def test_load_detects_canonical_text_corruption(tmp_path):
    # Canonical streams have no whole-artifact anchor; before this tier a corrupt canonical atom loaded
    # GREEN. The per-atom address check is canonical's load-time text-integrity tier.
    ws = _ws(tmp_path)
    canon = AtomStream.canonical(
        build_canonical(
            {"copy1": capture_witness("Alpha\n", "copy1"), "copy2": capture_witness("Alpha\n", "copy2")},
            ["copy1", "copy2"],
        )
    )
    save_stream(ws, canon)
    path = stream_path(ws, "canonical")
    env = read_json(path)
    env["atoms"][0]["text"] = env["atoms"][0]["text"] + "X"
    atomic_write_json(path, env)
    with pytest.raises(RoundTripError, match="address drift"):
        load_stream(ws, "canonical")


def test_load_detects_stale_raw_source_hash(tmp_path):
    # The dual of text drift: text intact, the stored hash stale → still a broken address.
    ws = _ws(tmp_path)
    save_stream(ws, _witness_stream("Alpha\n\nBeta\n"))
    path = stream_path(ws, "copy1")
    env = read_json(path)
    env["atoms"][0]["raw_source_hash"] = "sha256:" + "0" * 64
    atomic_write_json(path, env)
    with pytest.raises(RoundTripError, match="address drift"):
        load_stream(ws, "copy1")


def test_assert_atom_hashes_passes_on_valid_capture():
    atoms = capture_witness("Alpha\n\nBeta\n", "copy1")
    assert_atom_hashes(atoms)                             # by-construction valid → no raise


# --- D3: atom_id uniqueness enforced (the store is the documented enforcer) ----------------------- #


def test_duplicate_atom_ids_rejected_in_memory():
    dup = [_atom("A", 0, 1, aid="copy1_DUP"), _atom("B", 1, 2, aid="copy1_DUP")]
    with pytest.raises(ValueError, match="duplicate atom_id"):
        AtomStream.witness("copy1", dup, [], "AB")


def test_persisted_duplicate_atom_ids_rejected(tmp_path):
    ws = _ws(tmp_path)
    stream = AtomStream.witness("copy1", [_atom("A", 0, 1), _atom("B", 1, 2, aid="copy1_00001")], [], "AB")
    save_stream(ws, stream)
    path = stream_path(ws, "copy1")
    env = read_json(path)
    env["atoms"][1]["atom_id"] = env["atoms"][0]["atom_id"]   # collide ids on disk
    atomic_write_json(path, env)
    with pytest.raises(StaleArtifactError, match="duplicate atom_id"):
        load_stream(ws, "copy1")


# --- D4: a non-finite geom float fails loud at save (RFC-JSON + equality safety) ------------------ #


@pytest.mark.parametrize("bad_conf", [float("nan"), float("inf")])
def test_non_finite_geom_fails_loud_at_save(tmp_path, bad_conf):
    ws = _ws(tmp_path)
    bad_geom = Geom.matched(
        page=1, bbox=(0.0, 0.0, 1.0, 1.0), geometry_engine="e", matched_witness_id="copy1",
        match_method="m", match_confidence=bad_conf,
    )
    stream = AtomStream.witness("copy1", [_atom("w", 0, 1, geom=bad_geom)], [], "w")
    with pytest.raises(ValueError, match="JSON compliant"):   # allow_nan=False fails loud at write
        save_stream(ws, stream)


# --- J3: the read path rejects a non-flat stream_id (not only the constructor) ------------------- #


@pytest.mark.parametrize("bad", ["../evil", "a/b", "", "."])
def test_load_stream_rejects_non_flat_id(tmp_path, bad):
    ws = _ws(tmp_path)
    with pytest.raises(ValueError, match="flat filename stem"):
        load_stream(ws, bad)


def test_stream_path_rejects_non_flat_id(tmp_path):
    ws = _ws(tmp_path)
    with pytest.raises(ValueError, match="flat filename stem"):
        stream_path(ws, "../evil")


# --- J6: an invented-coords-on-absent geom fails loud at load (not silently normalized) ---------- #


def test_geom_invented_coords_on_absent_rejected():
    env = to_json(_witness_stream("body\n"))
    env["atoms"][0]["geom"] = {"present": False, "page": 99, "bbox": [1.0, 2.0, 3.0, 4.0]}
    with pytest.raises(StaleArtifactError, match="malformed"):
        from_json(env)
