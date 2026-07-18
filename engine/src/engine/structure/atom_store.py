"""S1.5 — the persisted L1 atom store (ENGINE_STRUCTURE_PLAN §3.5/§3.6/§11.1; D21).

S1.3a builds the per-witness atom streams + the canonical reconciled projection in memory; S1.4
proves a single-witness stream reconstructs its source byte-exact. This module makes those streams
**durable**: one JSON file per stream under ``books/<id>/work/data/atoms/`` (§11.1), each carrying an
**independent** schema version and stale class (M3) so a lineage stale-check can name *which* layer
changed and route the right migration (§3.6). It is the read/write path S1.4's closure and every L2
consumer (S10.2) reach the atoms through — never a private helper, never re-reading the raw witness.

Three guarantees, the S1.5 done-when (PLAN §9):

- **Serialization-invariance.** :func:`to_json` / :func:`from_json` round-trip an :class:`AtomStream`
  byte-for-byte — every addressing field (``raw_span``, ``raw_source_hash``, ``geom``,
  ``derived_from``), not just ``text``, and the per-witness :class:`~engine.structure.roundtrip_gate.GapRecord`
  stream. ``load_stream(save_stream(s)) == s``.
- **Two-tier round-trip self-check on load.** *(a) Whole-artifact anchor* — a witness stream persists
  its inter-atom **gap records** *and* a ``source_hash`` (the hash of the true witness source it tiles,
  fixed at capture); :func:`assert_stream_roundtrip` rebuilds the source from stored atom + gap **text**
  and checks its hash against that anchor. Persisting the gap *bytes* is load-bearing — gap whitespace
  is *not* recoverable from span widths (a width-N gap is any mix of spaces / tabs / newlines), so an
  atoms-only store could not rebuild the witness without re-reading the raw file (the back-door S1.4
  forbids) and would round-trip **vacuously** green on PLL's newline-only copies (S1.4 5-lens audit,
  carried decision). *(b) Per-atom address check* — :func:`assert_atom_hashes` checks each atom's
  ``hash_raw(text) == raw_source_hash`` (otherwise the persisted per-atom hash is *inert* at load). It
  catches what the anchor cannot: a **compensated drift** (bytes moved across an atom boundary, leaving
  the concatenation — and the anchor — unchanged), and corruption of a **canonical** atom (which has no
  whole-artifact anchor, so this is its only load-time text tier). Both run in :func:`load_stream`.
- **Reference-integrity.** :func:`assert_reference_integrity` checks every canonical atom derives from
  ≥1 witness (the S1.3a property, never vacuously zero) and that every ``derived_from`` back-link
  resolves to a real atom in the named witness stream, else fails loud.

**Scope split, from S1.4's audit.** A *witness* stream tiles one source → it carries gaps + a
``source_hash`` and gets both round-trip tiers (anchor + per-atom). The *canonical* stream tiles no
single source (its atoms adopt their ``derived_from[0]`` witness's address, pointing into different
witness sources) → it carries **no** gaps and **no** ``source_hash``, so it skips the whole-artifact
anchor; its load-time integrity is the per-atom address check + reference-integrity here (+ the per-atom
S1.2 floor against each ``derived_from`` witness, elsewhere).

**Failure-mode split.** :class:`~engine.errors.StaleArtifactError` is the *load-boundary* contract:
:func:`from_json` returns a valid stream or raises it — a non-object document, a stale ``schema_version``,
wrong ``stale_class``, missing envelope key, a wrong-*typed* field (a ``TypeError`` from reconstruction),
or any deeper model ``ValueError`` is wrapped here; :func:`load_stream` also maps a non-JSON file to it.
The model's own ``__post_init__`` guards (an out-of-vocab ``processing_scope``, a half-built ``geom``, a
canonical stream handed gaps, a duplicate ``atom_id``) raise ``ValueError`` for an **in-memory** caller —
a programming error, not stale data. A persisted text/address drift is
:class:`~engine.errors.RoundTripError`; a *missing* file is :class:`~engine.errors.MissingInputError`.

This departs from the §11.1 sketch's bare JSON *array* by design: the envelope header (version, stale
class, the witness ``source_hash`` + gap stream) is exactly what the carried S1.4 decision requires for
a non-back-door, non-vacuous store. Pure persistence of neutral atoms: no language, ordinal, or
book-structure opinion lives here (the S0.2 neutrality guard scans this module) — stream ids and capture
classes are caller-supplied strings.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from engine.errors import CaptureError, MissingInputError, RoundTripError, StaleArtifactError
from engine.paths import BookWorkspace
from engine.structure.artifacts import (
    ATOM_STORE_SCHEMA_VERSION,
    ATOM_STORE_STALE_CLASS,
    ATOMS_AREA,
    ATOMS_SUBDIR,
    atoms_dir,
)
from engine.structure.atoms import (
    Atom,
    AtomDerivation,
    Geom,
    duplicate_atom_ids,
)
from engine.structure.roundtrip import hash_raw
from engine.structure.roundtrip_gate import GapRecord, reconstruct_source
from engine.util.jsonio import atomic_write_json, read_json

#: The two stream flavours (§11.1). A ``witness`` stream tiles one source (carries gaps + a
#: ``source_hash`` anchor); a ``canonical`` stream is the reconciled projection (no single source).
WITNESS = "witness"
CANONICAL = "canonical"

#: A stream id is a flat filename stem, not a path — it names one ``<stream_id>.json`` file. The
#: containment guard in ``BookWorkspace.resolve`` blocks a *workspace* escape (``../../..``), but it
#: still permits an in-workspace ``../evil`` (→ ``data/evil.json``) or a nested ``a/b``; this pattern
#: keeps the id a single flat component so a stream is exactly one file under ``data/atoms/``.
_STREAM_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _check_stream_id(stream_id: str) -> None:
    """Raise ``ValueError`` unless ``stream_id`` is a flat filename stem (the one chokepoint both the
    constructor and :func:`stream_path` route through, so an id like ``../evil`` / ``a/b`` is rejected
    on **read** as well as on construct — not only blocked from escaping the workspace)."""
    if not isinstance(stream_id, str) or not _STREAM_ID.fullmatch(stream_id):
        raise ValueError(
            f"stream_id must be a flat filename stem matching {_STREAM_ID.pattern!r}, got "
            f"{stream_id!r} — a stream is one <stream_id>.json file, never a nested path"
        )


@dataclass(frozen=True, slots=True)
class AtomStream:
    """One persisted L1 atom stream — the durable unit of the atom store (§11.1).

    ``kind`` is :data:`WITNESS` or :data:`CANONICAL`. A witness stream tiles one source, so it carries
    its inter-atom ``gaps`` (:class:`~engine.structure.roundtrip_gate.GapRecord`) and a ``source_hash``
    (the :func:`~engine.structure.roundtrip.hash_raw` of that source — the round-trip anchor). A
    canonical stream tiles no single source, so it carries **no** gaps and **no** ``source_hash``; its
    integrity is reference-integrity + the per-atom S1.2 floor. ``schema_version`` is the independent
    per-layer version (M3). Build via the :meth:`witness` / :meth:`canonical` factories so the anchor is
    derived, not hand-passed.
    """

    stream_id: str
    kind: str
    atoms: tuple[Atom, ...]
    gaps: tuple[GapRecord, ...] = ()
    source_hash: str | None = None
    schema_version: int = ATOM_STORE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "atoms", tuple(self.atoms))
        object.__setattr__(self, "gaps", tuple(self.gaps))
        _check_stream_id(self.stream_id)
        if self.kind not in (WITNESS, CANONICAL):
            raise ValueError(f"AtomStream.kind must be {WITNESS!r} or {CANONICAL!r}, got {self.kind!r}")
        dups = duplicate_atom_ids(self.atoms)
        if dups:
            # atom_id is L1 identity (atoms.py); the store is the documented enforcer of its
            # uniqueness, so a stream with a repeated id is malformed — caught at construction so an
            # in-memory build fails ValueError and a persisted dup fails StaleArtifactError (from_json
            # wraps this). Else assert_reference_integrity's id set collapses the dup silently.
            raise ValueError(
                f"atom stream {self.stream_id!r} has duplicate atom_id(s) {dups[:5]} — atom_id is L1 "
                f"identity and must be unique within a stream"
            )
        if self.kind == CANONICAL:
            if self.gaps:
                raise ValueError(
                    "a canonical stream tiles no single source — it carries no gap records (its atoms "
                    "adopt different witnesses' addresses; verified per-atom by the S1.2 floor, not the "
                    "whole-artifact round-trip)"
                )
            if self.source_hash is not None:
                raise ValueError(
                    "a canonical stream has no single source — source_hash must be None (there is no one "
                    "witness source to anchor a whole-artifact round-trip against)"
                )
        elif not self.source_hash:
            # `not` (not `is None`): an empty-string anchor is as anchor-less as a missing one, and
            # it would ride into the S4.4 lineage manifest as {"hash": ""} — reject both at the model.
            raise ValueError(
                "a witness stream must carry a non-empty source_hash anchor (hash_raw of the witness "
                "source it tiles) — the non-vacuous round-trip self-check resolves against it; use "
                "AtomStream.witness()"
            )

    @classmethod
    def witness(
        cls,
        stream_id: str,
        atoms: Sequence[Atom],
        gaps: Sequence[GapRecord],
        source: str,
    ) -> "AtomStream":
        """A per-witness stream anchored to ``source`` (``source_hash = hash_raw(source)``).

        ``atoms`` + ``gaps`` are the S1.3a capture of ``source`` (the gaps from
        :func:`~engine.structure.roundtrip_gate.gap_records`); the anchor is derived from the true
        source here so :func:`assert_stream_roundtrip` can later catch a drift in either.
        """
        return cls(
            stream_id=stream_id,
            kind=WITNESS,
            atoms=tuple(atoms),
            gaps=tuple(gaps),
            source_hash=hash_raw(source),
        )

    @classmethod
    def canonical(cls, atoms: Sequence[Atom], *, stream_id: str = "canonical") -> "AtomStream":
        """The reconciled projection stream (no single source → no gaps, no anchor)."""
        return cls(stream_id=stream_id, kind=CANONICAL, atoms=tuple(atoms))


# --- serialization (envelope ⇄ AtomStream) ---------------------------------------------------- #


def _require(data: Mapping, key: str, ctx: str):
    """Fetch ``data[key]`` or fail loud as a malformed envelope (the load-boundary contract)."""
    if key not in data:
        raise StaleArtifactError(f"malformed atom-store {ctx}: missing required key {key!r}")
    return data[key]


def _geom_to_json(geom: Geom) -> dict:
    if not geom.present:
        return {"present": False}
    return {
        "present": True,
        "page": geom.page,
        "bbox": list(geom.bbox),
        "geometry_engine": geom.geometry_engine,
        "matched_witness_id": geom.matched_witness_id,
        "match_method": geom.match_method,
        "match_confidence": geom.match_confidence,
    }


def _geom_from_json(data: Mapping) -> Geom:
    # Reconstruct faithfully from whatever fields are present and let ``Geom.__post_init__`` enforce
    # coherence — so a corrupt *absent* geom that carries coordinates (invented geometry) raises at the
    # load boundary instead of being silently flattened to a clean absent geom; a present geom missing
    # a provenance field likewise fails the model's "full provenance" guard. (The raising ValueError is
    # wrapped as StaleArtifactError by ``from_json``.)
    bbox = data.get("bbox")
    return Geom(
        present=_require(data, "present", "geom"),
        page=data.get("page"),
        bbox=tuple(bbox) if bbox is not None else None,
        geometry_engine=data.get("geometry_engine"),
        matched_witness_id=data.get("matched_witness_id"),
        match_method=data.get("match_method"),
        match_confidence=data.get("match_confidence"),
    )


def _atom_to_json(atom: Atom) -> dict:
    return {
        "atom_id": atom.atom_id,
        "text": atom.text,
        "raw_span": list(atom.raw_span),
        "raw_source_hash": atom.raw_source_hash,
        "page_range": list(atom.page_range),
        "norm_layer": atom.norm_layer,
        "geom": _geom_to_json(atom.geom),
        "capture_provenance_class": atom.capture_provenance_class,
        "witness": atom.witness,
        "derived_from": [{"witness": d.witness, "atom_id": d.atom_id} for d in atom.derived_from],
        "processing_scope": atom.processing_scope,
    }


def _atom_from_json(data: Mapping) -> Atom:
    return Atom(
        atom_id=_require(data, "atom_id", "atom"),
        text=_require(data, "text", "atom"),
        raw_span=tuple(_require(data, "raw_span", "atom")),
        raw_source_hash=_require(data, "raw_source_hash", "atom"),
        page_range=tuple(_require(data, "page_range", "atom")),
        norm_layer=_require(data, "norm_layer", "atom"),
        geom=_geom_from_json(_require(data, "geom", "atom")),
        capture_provenance_class=_require(data, "capture_provenance_class", "atom"),
        witness=_require(data, "witness", "atom"),
        derived_from=tuple(
            AtomDerivation(
                witness=_require(d, "witness", "derived_from"),
                atom_id=_require(d, "atom_id", "derived_from"),
            )
            for d in _require(data, "derived_from", "atom")
        ),
        processing_scope=_require(data, "processing_scope", "atom"),
    )


def _gap_to_json(gap: GapRecord) -> dict:
    return {"raw_span": list(gap.raw_span), "text": gap.text}


def _gap_from_json(data: Mapping) -> GapRecord:
    return GapRecord(tuple(_require(data, "raw_span", "gap")), _require(data, "text", "gap"))


def to_json(stream: AtomStream) -> dict:
    """The persisted envelope for ``stream`` (header + atoms, plus gaps/anchor for a witness)."""
    envelope: dict = {
        "schema_version": stream.schema_version,
        "stale_class": ATOM_STORE_STALE_CLASS,
        "stream_id": stream.stream_id,
        "kind": stream.kind,
        "atoms": [_atom_to_json(a) for a in stream.atoms],
    }
    if stream.kind == WITNESS:
        envelope["source_hash"] = stream.source_hash
        envelope["gaps"] = [_gap_to_json(g) for g in stream.gaps]
    return envelope


def from_json(data: Mapping) -> AtomStream:
    """Parse + validate a persisted envelope into an :class:`AtomStream`, or fail loud.

    Validates the registered ``schema_version`` and the ``stale_class`` discriminator first (the
    genuinely *stale* / wrong-artifact cases route to migration, M3/S8.1), then reconstructs the
    stream. Any deeper malformation — a non-object document, a missing key, a wrong-*typed* field
    (a scalar where a list is expected → ``TypeError``), or a model-invariant ``ValueError`` from
    ``Atom``/``Geom``/``GapRecord`` reconstruction — is wrapped as
    :class:`~engine.errors.StaleArtifactError`, so this has a **total** contract: a valid stream or that
    error, never a bare traceback. Raises :class:`~engine.errors.StaleArtifactError`.
    """
    if not isinstance(data, Mapping):
        # A valid-JSON-but-non-object document (null / number / bool / list) is not an atom-store
        # envelope; without this gate the first `key not in data` membership test would TypeError.
        raise StaleArtifactError(
            f"atom-store envelope must be a JSON object, got {type(data).__name__}"
        )
    version = _require(data, "schema_version", "envelope")
    if version != ATOM_STORE_SCHEMA_VERSION:
        raise StaleArtifactError(
            f"atom-store schema version {version!r} != current {ATOM_STORE_SCHEMA_VERSION!r} "
            f"(stale class {ATOM_STORE_STALE_CLASS!r}) — refresh or migrate the stream"
        )
    stale_class = _require(data, "stale_class", "envelope")
    if stale_class != ATOM_STORE_STALE_CLASS:
        raise StaleArtifactError(
            f"stale_class {stale_class!r} != {ATOM_STORE_STALE_CLASS!r} — not an atom-store stream "
            f"(a different persisted layer, or a malformed file)"
        )
    kind = _require(data, "kind", "envelope")
    if kind not in (WITNESS, CANONICAL):
        raise StaleArtifactError(
            f"atom-store kind {kind!r} is neither {WITNESS!r} nor {CANONICAL!r} (malformed envelope)"
        )
    try:
        atoms = tuple(_atom_from_json(a) for a in _require(data, "atoms", "envelope"))
        if kind == WITNESS:
            gaps = tuple(_gap_from_json(g) for g in _require(data, "gaps", "envelope"))
            return AtomStream(
                stream_id=_require(data, "stream_id", "envelope"),
                kind=WITNESS,
                atoms=atoms,
                gaps=gaps,
                source_hash=_require(data, "source_hash", "envelope"),
                schema_version=version,
            )
        return AtomStream(
            stream_id=_require(data, "stream_id", "envelope"),
            kind=CANONICAL,
            atoms=atoms,
            schema_version=version,
        )
    except StaleArtifactError:
        raise
    except (ValueError, TypeError) as exc:
        # A model-invariant violation (bad raw_span, half-built geom, canonical-with-gaps → ValueError)
        # OR a wrong-typed field (a scalar where a list/dict is expected → TypeError from tuple()/`for`)
        # in a *persisted* stream is corrupt data, not an in-memory programming error: surface it
        # through the load-boundary contract, never as a bare traceback.
        raise StaleArtifactError(f"malformed atom-store stream: {exc}") from exc


# --- persistence (atomic JSON under data/atoms/) ---------------------------------------------- #


def stream_path(workspace: BookWorkspace, stream_id: str) -> Path:
    """The containment-checked path to ``<work>/data/atoms/<stream_id>.json``.

    Validates ``stream_id`` is a flat stem (:func:`_check_stream_id`) *before* resolving — so a raw id
    like ``../evil`` or ``a/b`` is rejected on the read path too, not only blocked from escaping the
    workspace by ``resolve``'s containment (which would still let ``../evil`` land in ``data/``)."""
    _check_stream_id(stream_id)
    return workspace.resolve(ATOMS_AREA, ATOMS_SUBDIR, f"{stream_id}.json")


def save_stream(workspace: BookWorkspace, stream: AtomStream) -> Path:
    """Persist ``stream`` atomically to ``<work>/data/atoms/<stream_id>.json``; return the path.

    Creates ``data/atoms/`` (the store owns that, per :func:`~engine.structure.artifacts.atoms_dir`)
    and writes through :func:`~engine.util.jsonio.atomic_write_json`, so a present store file is never
    half-written (invariant I8).
    """
    atoms_dir(workspace).mkdir(parents=True, exist_ok=True)
    path = stream_path(workspace, stream.stream_id)
    atomic_write_json(path, to_json(stream))
    return path


def stream_ids(workspace: BookWorkspace) -> list[str]:
    """The ids of every persisted atom stream in ``workspace`` — the **witness-iteration** read path.

    Sorted stems of ``data/atoms/*.json`` (empty if the dir is absent — ``glob`` yields nothing for a
    missing directory, so no existence guard is needed). The one enumeration primitive a consumer needs
    to iterate the streams a workspace holds *without already knowing their ids* (then :func:`load_stream`
    each and filter by ``.kind`` — the canonical stream is named ``"canonical"``, the rest are
    witnesses). Names only; it does not read or validate the files.
    """
    return sorted(path.stem for path in atoms_dir(workspace).glob("*.json"))


def load_stream(workspace: BookWorkspace, stream_id: str) -> AtomStream:
    """Read + validate the stream at ``<work>/data/atoms/<stream_id>.json``, round-trip self-checked.

    Fails loud on a missing file (:class:`~engine.errors.MissingInputError`), a non-JSON / stale /
    malformed envelope (:class:`~engine.errors.StaleArtifactError`), an id that disagrees with the
    filename, or a persisted text/address drift — both the whole-artifact anchor
    (:func:`assert_stream_roundtrip`, witness-only) **and** the per-atom address self-check
    (:func:`assert_atom_hashes`, every stream incl. canonical) catch it
    (:class:`~engine.errors.RoundTripError`).
    """
    path = stream_path(workspace, stream_id)
    if not path.is_file():
        raise MissingInputError(f"atom stream {stream_id!r} not found at {path}")
    try:
        data = read_json(path)
    except json.JSONDecodeError as exc:
        # An empty / truncated / non-JSON store file is a malformed envelope, not a Python bug — give
        # the load-boundary's clean error, not the bare json traceback that escapes the CLI handler.
        raise StaleArtifactError(f"atom stream {stream_id!r} at {path} is not valid JSON: {exc}") from exc
    stream = from_json(data)
    if stream.stream_id != stream_id:
        raise StaleArtifactError(
            f"atom-store id mismatch: file {stream_id!r} carries stream_id {stream.stream_id!r}"
        )
    # Anchor first (its message names whole-artifact drift), then the per-atom address self-check —
    # which also gives the canonical stream, with no whole-artifact anchor, a load-time text tier.
    assert_stream_roundtrip(stream)
    assert_atom_hashes(stream.atoms)
    return stream


# --- integrity tiers -------------------------------------------------------------------------- #


def assert_stream_roundtrip(stream: AtomStream) -> None:
    """Anchored whole-artifact round-trip self-check for a witness stream (no-op for canonical).

    Rebuilds the source from the stored atom + gap **text** and checks its hash against the stream's
    ``source_hash`` anchor. A persisted ``atom.text`` (or gap) drifted off its span yields a different
    source → a different hash → loud failure — the whole-artifact coverage the per-atom hash floor
    cannot see (it re-slices the source). Non-vacuous because the anchor was fixed from the *true*
    source at capture, independent of the stored text. Raises :class:`~engine.errors.RoundTripError`.
    """
    if stream.kind != WITNESS:
        return
    recovered = reconstruct_source(stream.atoms, stream.gaps)
    actual = hash_raw(recovered)
    if actual != stream.source_hash:
        raise RoundTripError(
            f"atom-store round-trip failed for stream {stream.stream_id!r}: reconstructed source hash "
            f"{actual} != stored source_hash {stream.source_hash} — a persisted atom.text/gap drifted "
            f"off its span (the whole-artifact drift the per-atom hash re-slices past)"
        )


def assert_atom_hashes(atoms: Sequence[Atom]) -> None:
    """Per-atom address self-check: every atom's ``hash_raw(text)`` matches its stored ``raw_source_hash``.

    The per-atom complement of :func:`assert_stream_roundtrip`'s whole-artifact anchor, and the tier
    that makes the persisted ``raw_source_hash`` actually load-bearing (it is otherwise *inert* at
    load). It catches two drifts the anchor cannot:

    - a **compensated drift** — bytes re-attributed across an atom boundary so the concatenation, and
      thus the anchor, is unchanged (the anchor checks the whole reconstruction, not each atom);
    - a corrupted **canonical** atom — canonical streams have no whole-artifact anchor, so this is
      their only load-time text-integrity tier.

    Relies on the store's raw/verbatim-text invariant (``text`` *is* the raw slice the span addresses,
    so ``hash_raw(text) == raw_source_hash`` by construction) — the same invariant the anchor assumes;
    a future normalized layer (S3), where ``text`` diverges from the raw slice, revisits both together.
    Raises :class:`~engine.errors.RoundTripError`.
    """
    for atom in atoms:
        expected = hash_raw(atom.text)
        if expected != atom.raw_source_hash:
            raise RoundTripError(
                f"atom {atom.atom_id!r} address drift: hash_raw(text) {expected} != stored "
                f"raw_source_hash {atom.raw_source_hash} — the atom's text no longer matches the raw "
                f"slice its span addresses (a per-atom drift the whole-artifact anchor cannot see)"
            )


def assert_reference_integrity(
    canonical: AtomStream,
    witnesses: Mapping[str, AtomStream],
) -> None:
    """Every canonical atom derives from ≥1 witness, and every ``derived_from`` back-link resolves.

    The reference-integrity tier (§3.6/§9): a canonical projection with a dangling back-link — or with
    a canonical atom that derives from *nothing* (violating the S1.3a property "every canonical atom
    has ≥1 witness derivation", which is vacuously true with an empty ``derived_from``) — is a broken
    store, caught here rather than discovered as a silent mis-alignment downstream. Raises
    :class:`~engine.errors.CaptureError` naming the first offender (no derivation, unknown witness, or
    known witness but unknown ``atom_id``).
    """
    if canonical.kind != CANONICAL:
        raise ValueError(
            f"assert_reference_integrity expects a {CANONICAL!r} stream, got kind {canonical.kind!r}"
        )
    ids_by_witness = {w: {a.atom_id for a in s.atoms} for w, s in witnesses.items()}
    for atom in canonical.atoms:
        if not atom.derived_from:
            raise CaptureError(
                f"canonical atom {atom.atom_id!r} has no derived_from back-links — every canonical "
                f"atom must derive from ≥1 witness (S1.3a property), never zero"
            )
        for deriv in atom.derived_from:
            if deriv.witness not in ids_by_witness:
                raise CaptureError(
                    f"canonical atom {atom.atom_id!r} derives from unknown witness {deriv.witness!r} "
                    f"(have {sorted(ids_by_witness)}) — back-link does not resolve"
                )
            if deriv.atom_id not in ids_by_witness[deriv.witness]:
                raise CaptureError(
                    f"canonical atom {atom.atom_id!r} back-link {deriv.witness}:{deriv.atom_id!r} "
                    f"resolves to no atom in that witness stream — reference integrity violated"
                )


# --- store-backed loading of a whole workspace (S4.6a reader glue) ----------------------------- #


def load_workspace_streams(
    workspace: BookWorkspace, *, canonical_stream_id: str = "canonical"
) -> dict[str, AtomStream]:
    """Load **every** persisted stream in ``workspace``, reference-integrity asserted (S4.6a).

    The store half of the reader glue (runway §3 item 2): each stream comes through
    :func:`load_stream` (its per-stream round-trip + hash tiers), then the cross-stream
    :func:`assert_reference_integrity` tier runs over the set — a persisted canonical stream with
    a dangling ``derived_from`` back-link reds here (``CaptureError``), never rides silently into
    a reader. One canonical anchor per workspace: the stream named ``canonical_stream_id`` must be
    canonical-kind and every other stream witness-kind — either fault is a stale substrate
    (:class:`~engine.errors.StaleArtifactError`), since a map cannot anchor on an ambiguous
    canonical. An absent substrate (no streams, or no stream under the canonical id) is
    :class:`~engine.errors.MissingInputError` — absent, not stale.
    """
    ids = stream_ids(workspace)
    if not ids:
        raise MissingInputError(
            f"no persisted atom streams under {atoms_dir(workspace)} — capture and save the "
            f"streams first (the S4.6-pre freeze step for a real book)"
        )
    if canonical_stream_id not in ids:
        raise MissingInputError(
            f"canonical stream {canonical_stream_id!r} is not among the persisted streams {ids} "
            f"— the substrate has witnesses but no canonical projection to anchor on"
        )
    streams = {stream_id: load_stream(workspace, stream_id) for stream_id in ids}
    canonical = streams[canonical_stream_id]
    if canonical.kind != CANONICAL:
        raise StaleArtifactError(
            f"stream {canonical_stream_id!r} is kind {canonical.kind!r}, not {CANONICAL!r} — the "
            f"named canonical stream must be the canonical projection"
        )
    rogue = sorted(
        stream_id
        for stream_id, stream in streams.items()
        if stream_id != canonical_stream_id and stream.kind != WITNESS
    )
    if rogue:
        raise StaleArtifactError(
            f"streams {rogue} are canonical-kind but not the named canonical "
            f"({canonical_stream_id!r}) — one canonical anchor per workspace; a second is an "
            f"ambiguous substrate, not a witness"
        )
    witnesses = {sid: s for sid, s in streams.items() if sid != canonical_stream_id}
    assert_reference_integrity(canonical, witnesses)
    return streams
