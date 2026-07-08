"""S5.1 — the ``rebind_anchors`` store-and-rebind mechanism (D33 Option A, R2; s4_plan §1.4.1b).

A durable ``node_id`` is **opaque and stored** (D33): re-extraction never recomputes it — it
**re-binds** the stored id to the freshly regenerated canonical atom stream through the node's
:class:`~engine.structure.projection.RebindAnchors` checkpoints. This module is that re-bind engine.
Given a stored :class:`~engine.structure.structure_map.StructureMap` (durable ids + anchors) and a
freshly regenerated canonical stream, it re-attaches each stored node to the fresh atoms it now owns:

- **unique + above-threshold + globally consistent** → **bind**, and mechanically re-stamp the node's
  *extent* authoring-evidence (the atoms are new ids but the same content);
- **ambiguous / below-threshold / no legal signal / a global ownership conflict / a changed decision
  digest** → **fail loud** into a typed :class:`RebindReport`, never a silent mis-bind (the
  ``corrections.json`` 40-char exact-substring tombstone this whole design exists to not repeat, R2).

Three anchors, three modes, one joint assignment (all Ben-ruled 2026-07-08, s5_1_plan §1):

- **region seed** — a single ``{page, bbox_region}`` (the node's first present own-atom box), a hard
  **pin** for the assignment where present; **content fingerprint** — a per-slot fuzzy shingle-set,
  the assignment **cost**; **structural-path** — derived at re-bind time, a residual tie-break.
- modes ``geometry-primary | geometry-tie-break | no-geometry`` (from
  ``manifest.segmentation.geometry_mode``; PLL = ``geometry-tie-break``, #30): geometry leads /
  corroborates / is discarded. **No rescue** — geometry and path only disambiguate among candidates
  already ≥ τ; they never lift a sub-τ fingerprint over τ (geometry is a pin, never a cost term).
- one **joint monotone DP** partitions the fresh included-atom stream into the old atom-owning slots
  in reading order (a fingerprint-scored analogue of ``geom_match.locate_pages``' banded monotone
  partition); the whole rebound projection then validates globally before any bind counts.

**Fingerprint required for auto-bind** (all modes): a node lacking the fingerprint its mode needs is
``missing-anchor``, never bound on geometry/path alone (optional-at-schema ≠ permissive-at-rebind).

**Threshold posture (S5.1 vs S5.2):** the per-mode τ here are a **default** — named, high, and
**uncalibrated**. S5.1 ships the default + the fail-loud mechanism; **S5.2** calibrates τ on a labeled
truth set and measures the three rate classes. The default-ordering ``τ(no-geometry) ≥ τ(tie-break) ≥
τ(primary)`` (weaker geometry ⇒ stricter fingerprint bar) is enforced structurally here so the S5.2
monotone-strictness property stays reachable; no real-data rate is claimed.

Neutral core (inv 15): no language/book/typeface literal — the S0.2 scan globs this module. The mode
is a **string parameter** (the caller reads ``geometry_mode`` from the book manifest); PLL's
``geometry-tie-break`` is asserted in a fixture, never here.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from engine.errors import EngineError, StaleArtifactError
from engine.structure.atom_store import CANONICAL, AtomStream, assert_reference_integrity
from engine.structure.atoms import PROCESSING_SCOPE_INCLUDED
from engine.structure.errors import StructureValidationError
from engine.structure.evidence import (
    AuthoringEvidence,
    EvidenceEntry,
    decision_digest,
    extent_digest,
    extent_payload,
)
from engine.structure.geom_match import normalize_tokens
from engine.structure.geom_regate import MODE_NO_GEOMETRY, MODE_PRIMARY, MODE_TIE_BREAK
from engine.structure.projection import (
    ContainerNode,
    Node,
    ProjectionMap,
    Region,
    SlotFingerprint,
    validate_projection,
    validate_reference_integrity,
)
from engine.structure.structure_map import (
    StreamAtomReader,
    StructureMap,
    canonical_content_hash,
    canonical_geometry_hash,
    structure_map_from_json,
)

# --- fingerprint producer + similarity (§2.2) ------------------------------------------------------ #

#: The fingerprint algorithm + normalizer ids stamped into every produced :class:`SlotFingerprint`.
#: They make an algorithm or normalizer change **detectable** — a change flips the id, so a stored
#: fingerprint computed under a different rule never silently compares equal (R2, §2.2). The
#: normalizer is ``geom_match.normalize_tokens`` reused verbatim (DT-8); its accent/apostrophe
#: tolerance is an S5.2 *calibration* question, made detectable here, never silently swapped.
FINGERPRINT_ALGO_ID = "shingle-jaccard@v1"
FINGERPRINT_NORMALIZER_ID = "geom_match.normalize_tokens@v1"

#: Default shingle size (a build detail, §2.2). A slot shorter than ``k`` falls back to
#: ``k' = min(k, token_count)`` down to unigrams — a slot too short to fingerprint reliably binds
#: only with geometry/path corroboration or fails loud, **never on an empty shingle set**.
DEFAULT_SHINGLE_K = 3


def normalized_slot_tokens(texts: Sequence[str]) -> list[str]:
    """The normalized token stream for a slot: ``normalize_tokens`` (the shared DT-8 normalizer) over
    each owned atom's text, concatenated in atom order. One place computes slot tokens, so the stored
    fingerprint and a fresh window are always normalized the same way."""
    tokens: list[str] = []
    for text in texts:
        tokens.extend(normalize_tokens(text))
    return tokens


def fingerprint_slot(tokens: Sequence[str], *, k: int = DEFAULT_SHINGLE_K) -> SlotFingerprint | None:
    """Compute a :class:`SlotFingerprint` over **already-normalized** ``tokens`` (a shingle **set**),
    or ``None`` when ``tokens`` is empty.

    ``None`` — never an empty-shingle fingerprint — is how a slot too short to fingerprint is
    represented: the caller routes it to geometry/path corroboration or fails loud, so an empty window
    can never score a spurious 1.0 against another empty window (the short-slot invariant). ``k`` is
    the requested shingle size; the effective size is ``k' = min(k, len(tokens))`` (the short-slot
    fallback down to unigrams), and ``k'`` is what the fingerprint records — so a comparison recomputes
    the fresh side at the *stored* ``k'`` and stays apples-to-apples."""
    toks = list(tokens)
    if not toks:
        return None
    k_eff = min(k, len(toks)) if k >= 1 else 1
    shingles = sorted({" ".join(toks[i : i + k_eff]) for i in range(len(toks) - k_eff + 1)})
    return SlotFingerprint(
        algo_id=FINGERPRINT_ALGO_ID,
        normalizer_id=FINGERPRINT_NORMALIZER_ID,
        k=k_eff,
        token_count=len(toks),
        shingles=tuple(shingles),
    )


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard similarity ``|a ∩ b| / |a ∪ b|`` — the primary ``[0, 1]`` fingerprint score. Two empty
    sets never reach here (the producer returns ``None`` for an empty slot, and the scorer guards a
    ``None`` fresh side), so a ``0/0`` vacuous-1.0 cannot arise."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def slot_similarity(stored: SlotFingerprint, window_tokens: Sequence[str]) -> float:
    """The ``[0, 1]`` similarity of a candidate window's normalized ``window_tokens`` to a ``stored``
    slot fingerprint: Jaccard over the shingle sets, the fresh side recomputed at the **stored** ``k``
    (short-slot fallback included) so the two shingle vocabularies line up. An empty window scores 0
    (the short-slot guard: it never binds on an empty set). Fuzzy by construction — a locally edited
    window scores strictly between 0 and 1, never the exact-substring all-or-nothing R2 tombstoned."""
    fresh = fingerprint_slot(window_tokens, k=stored.k)
    if fresh is None:
        return 0.0
    return _jaccard(frozenset(stored.shingles), frozenset(fresh.shingles))


# --- operating modes + threshold policy (§1.2, D-4) ------------------------------------------------ #

#: The three DP operating modes, re-exported from :mod:`engine.structure.geom_regate` (the ONE home
#: of the ``MODE_*`` vocabulary, bound to the manifest enum by ``test_geom_regate``) so re-bind and the
#: re-gate can never disagree on the tokens.
GEOMETRY_MODES = (MODE_PRIMARY, MODE_TIE_BREAK, MODE_NO_GEOMETRY)

#: The reported label + DP behavior when a book's ``geometry_mode`` is **unruled** (``None`` — the
#: re-gate has not run). The mode is *reported* as ``conditional-primary`` with ``source="fallback"``
#: (weaker provenance, never silently invented — §1.2), and its DP behavior is the **conservative**
#: ``geometry-tie-break`` (unvalidated geometry corroborates, never leads).
FALLBACK_REPORTED_MODE = "conditional-primary"

#: The named, high, **uncalibrated** default fingerprint threshold (D-4). S5.1 ships this + the
#: fail-loud mechanism; S5.2 calibrates on a labeled truth set. It is the ``geometry-tie-break``
#: (PLL) bar; the other modes derive from it by :data:`_DEFAULT_MODE_MARGIN`.
DEFAULT_FINGERPRINT_THRESHOLD = 0.75
#: How much stricter/looser the no-geometry / primary bars sit around the tie-break base (a default,
#: not calibrated). Weaker geometry ⇒ stricter fingerprint bar (the monotone-strictness direction).
_DEFAULT_MODE_MARGIN = 0.05


def resolve_mode(geometry_mode: str | None) -> tuple[str, str, str]:
    """Resolve a book's ``geometry_mode`` to ``(dp_mode, reported_mode, source)``.

    - a known token (:data:`GEOMETRY_MODES`) → ``(mode, mode, "manifest")``;
    - ``None`` (unruled) → ``(MODE_TIE_BREAK, "conditional-primary", "fallback")`` — the conservative
      fallback with honestly weaker provenance (§1.2), never a silently invented mode;
    - anything else → :class:`ValueError` (a bad ``geometry_mode`` is a config error, the
      ``mint_node_id`` unknown-authority precedent; never guessed).
    """
    if geometry_mode is None:
        return (MODE_TIE_BREAK, FALLBACK_REPORTED_MODE, "fallback")
    if geometry_mode in GEOMETRY_MODES:
        return (geometry_mode, geometry_mode, "manifest")
    raise ValueError(
        f"unknown geometry_mode {geometry_mode!r} — expected one of {GEOMETRY_MODES} or None "
        f"(unruled). A re-bind never invents a mode (§1.2)."
    )


@dataclass(frozen=True, slots=True)
class RebindPolicy:
    """Per-mode fingerprint thresholds τ (D-4). The defaults derive from
    :data:`DEFAULT_FINGERPRINT_THRESHOLD` and satisfy the **default-ordering** ``τ(no-geometry) ≥
    τ(tie-break) ≥ τ(primary)`` — weaker geometry ⇒ stricter fingerprint bar — which is enforced at
    construction, so an inverted default (the mutant) cannot be built and the S5.2 monotone-strictness
    property stays reachable. Uncalibrated: S5.1 ships a default; S5.2 calibrates."""

    tau_primary: float = DEFAULT_FINGERPRINT_THRESHOLD - _DEFAULT_MODE_MARGIN
    tau_tie_break: float = DEFAULT_FINGERPRINT_THRESHOLD
    tau_no_geometry: float = DEFAULT_FINGERPRINT_THRESHOLD + _DEFAULT_MODE_MARGIN

    def __post_init__(self) -> None:
        if not (self.tau_no_geometry >= self.tau_tie_break >= self.tau_primary):
            raise ValueError(
                f"RebindPolicy violates the default-ordering τ(no-geometry) >= τ(tie-break) >= "
                f"τ(primary): got no-geometry={self.tau_no_geometry}, tie-break={self.tau_tie_break}, "
                f"primary={self.tau_primary} — weaker geometry must never lower the fingerprint bar "
                f"(monotone-strictness, feedback_no_cheating_results)"
            )

    def threshold(self, dp_mode: str) -> float:
        """The fingerprint threshold τ for a resolved DP mode."""
        if dp_mode == MODE_PRIMARY:
            return self.tau_primary
        if dp_mode == MODE_TIE_BREAK:
            return self.tau_tie_break
        if dp_mode == MODE_NO_GEOMETRY:
            return self.tau_no_geometry
        raise ValueError(f"RebindPolicy.threshold: unknown dp_mode {dp_mode!r} (expected {GEOMETRY_MODES})")


# --- the closed unresolved-reason enum + the strict error (§1.5, D-6) ------------------------------ #

#: The **closed** set of reasons a node fails to auto-bind (§1.5). Mirrors evidence.py's closed
#: ``EVIDENCE_FINDING_KINDS`` discipline so a typo cannot mint a pseudo-reason. Their meanings are
#: deliberately disjoint: ``missing-anchor`` = "no legal signal to search with" (the slot's mode needs
#: a fingerprint and the node stores none); ``zero-candidate`` = "searched the legal space, found no
#: window compatible with a tiling" — a geometry pin excluded every atom, OR the fresh stream cannot be
#: tiled into the map's slots at all (e.g. a re-extraction merged atoms so there are fewer than the
#: slots); ``below-threshold`` = "found a pin-feasible window, best score < τ"; ``ambiguous`` = "≥ 2
#: windows ≥ τ, geometry could not break the tie"; ``stale-decision`` = "the rebound topology changed
#: the node's decision digest — a human must re-verify, never a re-stamp"; ``global-conflict`` = "the
#: per-node binds do not compose (two bound nodes claim the same fresh atom, or the whole map fails
#: validation)".
REBIND_UNRESOLVED_REASONS = (
    "zero-candidate",
    "ambiguous",
    "below-threshold",
    "missing-anchor",
    "stale-decision",
    "global-conflict",
)


class RebindError(EngineError):
    """A strict re-bind assertion failed: at least one stored ``node_id`` did not auto-bind to the
    fresh stream (:func:`assert_all_bound`). Carries the unresolved ``(node_id, reason)`` findings so a
    caller can route the worklist. Lives beside its raiser (the ``StructureValidationError`` /
    ``EvidenceGateError`` / ``GeometryError`` carrier-beside-the-vocabulary precedent) and takes the
    next free exit code (14) after ``GeometryError`` (13); the uniqueness sweep in
    ``test_authoring_evidence`` pins that it does not collide.

    Every reason is validated against the closed :data:`REBIND_UNRESOLVED_REASONS` set (a typo cannot
    mint a pseudo-reason), and an empty payload is a programming error (it would read "all bound, yet
    raised") — it fails loud, the ``EvidenceGateError`` precedent.
    """

    exit_code = 14

    def __init__(self, findings: Sequence[tuple[str, str]]):
        normalized: list[tuple[str, str]] = []
        for node_id, reason in findings:
            if reason not in REBIND_UNRESOLVED_REASONS:
                raise ValueError(
                    f"unknown re-bind reason {reason!r} — the closed set is {REBIND_UNRESOLVED_REASONS}"
                )
            normalized.append((node_id, reason))
        self.findings = tuple(normalized)
        if not self.findings:
            raise ValueError(
                "RebindError requires at least one (node_id, reason) finding — an empty payload would "
                "signal a re-bind failure with no unresolved node."
            )
        super().__init__(
            "re-bind did not fully bind the stored map to the fresh stream:\n  "
            + "\n  ".join(f"[{reason}] {node_id}" for node_id, reason in self.findings)
        )


# --- the typed report (§1.5, D-6/D-7) -------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SlotOutcome:
    """One node-slot's re-bind outcome — the leaf of the report. A node fails as soon as any of its
    slots fails; ``bound`` is the conjunction over the node's slots.

    ``score`` is the Jaccard primary (``None`` for a ``missing-anchor`` slot that was never scored);
    ``containment`` / ``token_count_ratio`` are the secondary evidence the report surfaces (§2.2) —
    containment is the fraction of stored (ordered k-gram) shingles present in the bound window, so it
    is a local-order-sensitive signal, the report's ``ordered_coverage`` role. ``fresh_atom_ids`` is
    the window this slot bound to (empty when unresolved). ``candidates_ge_tau`` is the saturated
    (0/1/2) count of full-tiling-compatible windows ≥ τ — the ambiguity signal.
    """

    slot_name: str
    bound: bool
    reason: str | None
    score: float | None
    fresh_atom_ids: tuple[str, ...]
    candidates_ge_tau: int
    region_page: int | None
    containment: float | None
    token_count_ratio: float | None


@dataclass(frozen=True, slots=True)
class NodeOutcome:
    """One stored ``node_id``'s aggregate outcome. ``bound`` iff every owned slot bound; ``reason`` is
    the dominant unresolved reason (the first owned slot's, in reason-severity order) when unbound."""

    node_id: str
    bound: bool
    reason: str | None
    slots: tuple[SlotOutcome, ...]


@dataclass(frozen=True, slots=True)
class ModeProvenance:
    """The active mode's provenance surfaced in the report (D-7): the resolved ``mode`` label, its
    ``source`` (``manifest`` | ``fallback``), and the old map's ``manifest_schema_version``. S5.2 is
    the named owner of *persisting* this into lineage; S5.1 only reports it."""

    mode: str
    source: str
    manifest_schema_version: int


@dataclass(frozen=True, slots=True)
class RebindReport:
    """The typed re-bind report (§1.5): per-node outcomes + mode provenance + the two canonical
    streams (ids + content/geometry hashes) the re-bind compared. Non-raising ``rebind()`` returns
    this; ``assert_all_bound`` reads :attr:`unresolved`."""

    mode: ModeProvenance
    nodes: tuple[NodeOutcome, ...]
    old_canonical_stream_id: str
    fresh_canonical_stream_id: str
    old_content_hash: str
    fresh_content_hash: str
    old_geometry_hash: str | None
    fresh_geometry_hash: str | None

    @property
    def bound_node_ids(self) -> tuple[str, ...]:
        """The node ids that auto-bound, in report order."""
        return tuple(n.node_id for n in self.nodes if n.bound)

    @property
    def unresolved(self) -> tuple[tuple[str, str], ...]:
        """The ``(node_id, reason)`` findings for every unbound node, in report order."""
        return tuple((n.node_id, n.reason) for n in self.nodes if not n.bound)


@dataclass(frozen=True, slots=True)
class RebindResult:
    """The re-bind output (§1.5, D-6): the migrated **structure-map document** (fresh atom ids in the
    bound nodes' slots; unpersisted — S5.2 owns the writer and the manifest re-stamp), the typed
    :class:`RebindReport`, and the in-memory re-stamped authoring-evidence entries — **separate from
    the map** (digests live in the evidence sidecar, never grafted onto the map schema). The evidence
    list is empty when no old evidence was supplied."""

    migrated_doc: Mapping
    report: RebindReport
    restamped_evidence: tuple[EvidenceEntry, ...] = ()


# --- the two-substrate frame (§1.4, D-5) ----------------------------------------------------------- #


def _split_streams(
    streams: Mapping[str, AtomStream], canonical_stream_id: str, which: str
) -> tuple[AtomStream, dict[str, AtomStream]]:
    """Split a ``{canonical + witnesses}`` set into ``(canonical, witnesses)``. A map-only re-bind
    (no canonical stream, or the named stream is not canonical-kind) **fails loud** — the pre-registered
    provenance flag (§1.4): without the old canonical we cannot verify the baseline or re-derive the
    geometry match-provenance the report surfaces."""
    canonical = streams.get(canonical_stream_id)
    if canonical is None:
        raise StaleArtifactError(
            f"{which} re-bind substrate has no stream {canonical_stream_id!r} — a map-only re-bind "
            f"cannot verify the baseline / re-derive geometry provenance (§1.4); supply the canonical "
            f"stream (have {sorted(streams)})"
        )
    if canonical.kind != CANONICAL:
        raise StaleArtifactError(
            f"{which} stream {canonical_stream_id!r} is kind {canonical.kind!r}, not {CANONICAL!r} — "
            f"the named canonical stream must be the canonical projection"
        )
    witnesses = {sid: s for sid, s in streams.items() if sid != canonical_stream_id}
    return canonical, witnesses


class RebindContext:
    """The re-bind frame (§1.4, D-5): a stored ``old_map`` (durable ids + anchors), the ``old_streams``
    it was authored against, and the ``fresh_streams`` to re-attach to — each a ``{canonical +
    witnesses}`` set. Optional ``old_evidence`` drives the re-stamp / ``stale-decision`` pass.

    Construction fails loud (never a silent proceed) on:

    - **reference integrity** — ``assert_reference_integrity(canonical, witnesses)`` on **both** sets
      (the workspace-level cross-stream check is bypassed when streams are passed directly, so we run
      it explicitly);
    - **baseline binding** — the old canonical's id **and** ``canonical_content_hash`` **and**
      ``canonical_geometry_hash`` must equal what ``old_map``'s manifest claims (geometry half gated on
      geometry being used — skipped in ``no-geometry``). Computed via the **shared**
      :func:`~engine.structure.structure_map.canonical_content_hash` /
      :func:`~engine.structure.structure_map.canonical_geometry_hash` producers — never a lookalike
      hash here, so a payload/field-list change ripples to both (inv 20 guards the shared producer).

    The mode is a **string parameter** (``geometry_mode``), resolved via :func:`resolve_mode`; the core
    reads no book config (inv 15). ``policy`` defaults to the uncalibrated :class:`RebindPolicy`.
    """

    def __init__(
        self,
        old_map: StructureMap,
        old_streams: Mapping[str, AtomStream],
        fresh_streams: Mapping[str, AtomStream],
        old_evidence: AuthoringEvidence | None = None,
        *,
        geometry_mode: str | None,
        policy: RebindPolicy | None = None,
        canonical_stream_id: str = "canonical",
    ) -> None:
        self.old_map = old_map
        self.old_evidence = old_evidence
        self.canonical_stream_id = canonical_stream_id
        self.policy = policy if policy is not None else RebindPolicy()
        self.dp_mode, self.reported_mode, self.mode_source = resolve_mode(geometry_mode)

        self.old_canonical, self.old_witnesses = _split_streams(old_streams, canonical_stream_id, "old")
        self.fresh_canonical, self.fresh_witnesses = _split_streams(
            fresh_streams, canonical_stream_id, "fresh"
        )
        assert_reference_integrity(self.old_canonical, self.old_witnesses)
        assert_reference_integrity(self.fresh_canonical, self.fresh_witnesses)

        self._check_baseline()
        self.fresh_reader = StreamAtomReader(fresh_streams, canonical_stream_id)

    def _check_baseline(self) -> None:
        """The dual-hash baseline gate (§1.4): the old canonical must be exactly the stream the old
        map's manifest was stamped against — otherwise the stored anchors describe a substrate we are
        not migrating from, and every re-bind would be against the wrong content."""
        manifest = self.old_map.doc.get("manifest")
        if not isinstance(manifest, Mapping):
            raise StaleArtifactError(
                "old map carries no manifest object — cannot verify the re-bind baseline (§1.4)"
            )
        stored_id = manifest.get("canonical_stream_id")
        if stored_id != self.old_canonical.stream_id:
            raise StaleArtifactError(
                f"baseline mismatch: old canonical stream_id {self.old_canonical.stream_id!r} != the "
                f"manifest's canonical_stream_id {stored_id!r} — wrong substrate for this map"
            )
        live_content = canonical_content_hash(self.old_canonical)
        if live_content != manifest.get("canonical_content_hash"):
            raise StaleArtifactError(
                f"baseline mismatch: recomputed canonical_content_hash {live_content!r} != the "
                f"manifest's {manifest.get('canonical_content_hash')!r} — the old canonical stream is "
                f"not the one this map was authored against"
            )
        if self.dp_mode != MODE_NO_GEOMETRY:
            live_geometry = canonical_geometry_hash(self.old_canonical)
            if live_geometry != manifest.get("canonical_geometry_hash"):
                raise StaleArtifactError(
                    f"baseline mismatch: recomputed canonical_geometry_hash {live_geometry!r} != the "
                    f"manifest's {manifest.get('canonical_geometry_hash')!r} — geometry is in use "
                    f"({self.dp_mode}); the region pins would key on the wrong boxes"
                )

    @property
    def manifest_schema_version(self) -> int:
        """The old map's structure-map schema version — surfaced in the report's mode provenance."""
        return self.old_map.doc["schema_version"]


# --- the assignment (§1.3) — slots, scoring, the monotone-tiling feasibility DPs ------------------- #


@dataclass(frozen=True, slots=True)
class _Slot:
    """One atom-owning slot of a stored node, in re-bind reading order: the node it belongs to, the
    slot name (``body`` | ``heading`` | ``signature``), its stored fingerprint (``None`` ⇒
    ``missing-anchor``), its optional region seed, and ``order_key`` (its first owned atom's index in
    the old canonical included stream — the reading-order sort key)."""

    node_id: str
    slot_name: str
    fingerprint: SlotFingerprint | None
    region: Region | None
    order_key: int


def _owning_slots_of(node: Node) -> list[tuple[str, tuple[str, ...]]]:
    """The node's atom-owning ``(slot_name, atom_ids)`` slots (mirrors ``projection._owning_slots`` —
    kept local so the neutral re-bind core does not import a private projection helper). Container
    ``children`` are node refs, not atoms, so they are not a slot here."""
    if isinstance(node, ContainerNode):
        return [("heading", node.heading_atoms), ("signature", node.signature_atoms)]
    return [("body", node.body_atoms)]


def _enumerate_slots(old_map: StructureMap, old_canonical: AtomStream) -> list[_Slot]:
    """Every atom-owning slot of the stored map, in old-canonical reading order (§1.3). Assumes a
    validated map (owned atoms are included canonical atoms, so each resolves in the index)."""
    old_index = {
        atom.atom_id: i
        for i, atom in enumerate(
            a for a in old_canonical.atoms if a.processing_scope == PROCESSING_SCOPE_INCLUDED
        )
    }
    slots: list[_Slot] = []
    for node in old_map.projection.nodes:
        anchors = node.rebind_anchors
        for slot_name, atom_ids in _owning_slots_of(node):
            if not atom_ids:
                continue
            order_key = min(old_index[aid] for aid in atom_ids)
            slots.append(
                _Slot(
                    node_id=node.node_id,
                    slot_name=slot_name,
                    fingerprint=anchors.fingerprint(slot_name) if anchors else None,
                    region=anchors.region if anchors else None,
                    order_key=order_key,
                )
            )
    slots.sort(key=lambda s: s.order_key)
    return slots


def _sat2(value: int) -> int:
    """Saturate a count at 2 — the DPs only ever need to distinguish 0 / 1 / many (≥2), and
    saturating keeps the free-slot wildcard counts from exploding combinatorially (the scale seam is
    S4.7's; correctness needs only the trichotomy)."""
    return value if value < 2 else 2


class _Assignment:
    """The monotone-tiling assignment engine over one (slots × fresh atoms) frame.

    The re-attach is a **single joint monotone tiling** of the fresh included-atom stream into the
    stored slots in reading order (§1.3): non-crossing, contiguous, one pass. Reading order *is* the
    structural-path tie-break — a node earlier in the stored order can only own earlier fresh atoms, so
    the monotone constraint encodes the parent-chain/ordinal ordering without a separate path term.

    Two boolean/count feasibility lattices drive per-slot attribution, both **pin-respecting** but
    **τ-free** (``_pin_ok``, never the fingerprint threshold): ``pref[j][a]`` = the number (saturated
    at 2) of ways slots ``[0:j]`` tile ``[0, a)`` as non-empty pin-respecting spans, and ``suf[j][b]``
    the same for slots ``[j:]`` over ``[b, N)``. Treating the *other* slots as free (pin-respecting but
    not τ-gated) isolates **this** slot's fingerprint: a neighbour that cannot reach τ (or has no
    fingerprint) never poisons a slot's own attribution. A slot then binds iff it has exactly one
    ``≥ τ`` window compatible with some global tiling; two ⇒ ``ambiguous`` (geometry may break the tie
    in ``geometry-tie-break``); zero ⇒ ``below-threshold`` (a pin-feasible window exists but none ≥ τ)
    or ``zero-candidate`` (no pin-feasible window at all). Global non-overlap is then re-checked by
    ``validate_projection`` on the assembled map (``global-conflict``) — the greedy per-node matcher's
    double-claim cannot survive it.

    The τ-free isolation is deliberately **conservative**: because a slot's ambiguity is judged with
    its neighbours free, a slot can be flagged ``ambiguous`` when a neighbour's own τ-constraint would
    in fact have disambiguated it. That bias is toward **fail-loud / missed-bind**, never a false bind
    (the direction R2 demands); tightening it against real rates is S5.2's calibration, not S5.1's.

    Complexity is ``O(K·N²)`` — correct and bounded for the mechanism's synthetic fixtures. The banded
    candidate index (DT-3 ``_bands`` / ``locate_pages`` pattern) that holds re-bind lookup
    sub-quadratic across 10⁴→10⁵ leaf nodes is the op **S4.7 names under its scale gate** (§1.3
    complexity note); it is a scale obligation, deliberately not built here (YAGNI at fixture scale).
    """

    def __init__(self, slots: list[_Slot], context: RebindContext) -> None:
        self.slots = slots
        self.dp_mode = context.dp_mode
        self.tau = context.policy.threshold(context.dp_mode)
        self.fresh_ids = list(context.fresh_reader.included_atom_ids())
        by_id = {a.atom_id: a for a in context.fresh_canonical.atoms}
        self.tokens = [normalize_tokens(by_id[aid].text) for aid in self.fresh_ids]
        self.pages = [
            by_id[aid].geom.page if by_id[aid].geom.present else None for aid in self.fresh_ids
        ]
        self.n = len(self.fresh_ids)
        self._pref = self._prefix_ways()
        self._suf = self._suffix_ways()

    # -- window scoring ---------------------------------------------------------------------------- #

    def _window_tokens(self, a: int, b: int) -> list[str]:
        out: list[str] = []
        for i in range(a, b):
            out.extend(self.tokens[i])
        return out

    def _score(self, slot: _Slot, a: int, b: int) -> float | None:
        if slot.fingerprint is None:
            return None
        return slot_similarity(slot.fingerprint, self._window_tokens(a, b))

    def _pin_ok(self, slot: _Slot, a: int, b: int) -> bool:
        """The geometry hard-pin: only ``geometry-primary`` constrains the tiling (a pinned slot's
        atoms must all sit on its region page). ``geometry-tie-break`` uses geometry only to break a
        ≥τ tie (applied at resolution, never as a tiling constraint — no rescue); ``no-geometry``
        ignores regions entirely."""
        if self.dp_mode == MODE_PRIMARY and slot.region is not None:
            return all(self.pages[i] == slot.region.page for i in range(a, b))
        return True

    def _valid_free(self, slot: _Slot, a: int, b: int) -> bool:
        """A slot may occupy the non-empty span ``[a, b)`` in the τ-free feasibility lattice: pin-ok
        and at least one atom. τ is applied only when attributing the slot's own binding."""
        return b > a and self._pin_ok(slot, a, b)

    def _on_region_page(self, slot: _Slot, a: int, b: int) -> bool:
        return slot.region is not None and all(self.pages[i] == slot.region.page for i in range(a, b))

    # -- the two feasibility lattices -------------------------------------------------------------- #

    def _prefix_ways(self) -> list[list[int]]:
        k, n = len(self.slots), self.n
        pref = [[0] * (n + 1) for _ in range(k + 1)]
        pref[0][0] = 1
        for j in range(1, k + 1):
            slot = self.slots[j - 1]
            row, prev = pref[j], pref[j - 1]
            for a in range(1, n + 1):
                total = 0
                for s in range(a):
                    if prev[s] and self._valid_free(slot, s, a):
                        total += prev[s]
                        if total >= 2:
                            break
                row[a] = _sat2(total)
        return pref

    def _suffix_ways(self) -> list[list[int]]:
        k, n = len(self.slots), self.n
        suf = [[0] * (n + 1) for _ in range(k + 1)]
        suf[k][n] = 1
        for j in range(k - 1, -1, -1):
            slot = self.slots[j]
            row, nxt = suf[j], suf[j + 1]
            for b in range(n, -1, -1):
                total = 0
                for e in range(b + 1, n + 1):
                    if self._valid_free(slot, b, e) and nxt[e]:
                        total += nxt[e]
                        if total >= 2:
                            break
                row[b] = _sat2(total)
        return suf

    # -- per-slot resolution ----------------------------------------------------------------------- #

    def resolve_slot(self, j: int) -> SlotOutcome:
        """Attribute slot ``j``'s outcome from the two lattices (see the class docstring)."""
        slot = self.slots[j]
        pref, suf = self._pref[j], self._suf[j + 1]
        region_page = slot.region.page if slot.region is not None else None

        if slot.fingerprint is None:
            return SlotOutcome(
                slot_name=slot.slot_name, bound=False, reason="missing-anchor", score=None,
                fresh_atom_ids=(), candidates_ge_tau=0, region_page=region_page,
                containment=None, token_count_ratio=None,
            )

        feasible: list[tuple[int, int]] = []       # pin-ok windows compatible with a global tiling
        ge_tau: list[tuple[int, int]] = []         # of those, the ones scoring >= tau
        best_score = 0.0
        best_window: tuple[int, int] | None = None
        for a in range(self.n):
            if not pref[a]:
                continue
            for b in range(a + 1, self.n + 1):
                if not suf[b] or not self._valid_free(slot, a, b):
                    continue
                feasible.append((a, b))
                score = self._score(slot, a, b) or 0.0
                if score > best_score:
                    best_score, best_window = score, (a, b)
                if score >= self.tau:
                    ge_tau.append((a, b))

        if not feasible:
            return self._slot_outcome(slot, "zero-candidate", 0.0, None, 0, region_page)
        if not ge_tau:
            return self._slot_outcome(slot, "below-threshold", best_score, best_window, 0, region_page)

        chosen = ge_tau
        # geometry-tie-break: among >=τ candidates, geometry may break a tie — never rescue a sub-τ one.
        if len(chosen) >= 2 and self.dp_mode == MODE_TIE_BREAK and slot.region is not None:
            on_page = [w for w in chosen if self._on_region_page(slot, *w)]
            if len(on_page) == 1:
                chosen = on_page

        if len(chosen) == 1:
            a, b = chosen[0]
            # report the PRE-tie-break ≥τ count, not 1: a geometry-broken tie (len(ge_tau) >= 2, chosen
            # filtered to one) is a weaker, geometry-dependent bind a worklist should still see as such.
            return self._slot_outcome(
                slot, None, self._score(slot, a, b), (a, b), _sat2(len(ge_tau)), region_page, bound=True
            )
        a, b = best_window  # report evidence for the strongest of the tied candidates
        return self._slot_outcome(slot, "ambiguous", best_score, (a, b), _sat2(len(ge_tau)), region_page)

    def _slot_outcome(
        self, slot, reason, score, window, candidates, region_page, *, bound=False
    ) -> SlotOutcome:
        containment = token_ratio = None
        fresh_ids: tuple[str, ...] = ()
        if window is not None and slot.fingerprint is not None:
            a, b = window
            fresh_tokens = self._window_tokens(a, b)
            fresh_fp = fingerprint_slot(fresh_tokens, k=slot.fingerprint.k)
            stored = frozenset(slot.fingerprint.shingles)
            fresh_sh = frozenset(fresh_fp.shingles) if fresh_fp else frozenset()
            # containment of the stored (ordered k-gram) shingles in the window — a local-order signal
            # (the report's ordered_coverage role); token_count_ratio is the multiplicity evidence.
            containment = len(stored & fresh_sh) / len(stored) if stored else None
            token_ratio = len(fresh_tokens) / slot.fingerprint.token_count if slot.fingerprint.token_count else None
            if bound:
                fresh_ids = tuple(self.fresh_ids[a:b])
        return SlotOutcome(
            slot_name=slot.slot_name, bound=bound, reason=reason, score=score,
            fresh_atom_ids=fresh_ids, candidates_ge_tau=candidates, region_page=region_page,
            containment=containment, token_count_ratio=token_ratio,
        )


# --- reason severity (dominant reason for a multi-slot node) --------------------------------------- #

#: Severity order for picking a node's dominant unresolved reason across its slots — the most
#: actionable "no signal" reasons first. Only used to summarize; every slot's own reason stays in the
#: per-slot outcomes.
_REASON_SEVERITY = {
    "missing-anchor": 0, "global-conflict": 1, "stale-decision": 2,
    "ambiguous": 3, "zero-candidate": 4, "below-threshold": 5,
}


def _dominant_reason(reasons: list[str]) -> str:
    return min(reasons, key=lambda r: _REASON_SEVERITY.get(r, 99))


# --- the re-stamp (§1.6) --------------------------------------------------------------------------- #


def _subtree_ids(node_id: str, projection: ProjectionMap) -> set[str]:
    """Every node id in the subtree rooted at ``node_id`` (inclusive), over the ``children`` edges.
    Guards re-entry so a (pre-validated-away) cycle cannot loop."""
    seen: set[str] = set()
    stack = [node_id]
    while stack:
        nid = stack.pop()
        if nid in seen:
            continue
        seen.add(nid)
        node = projection.by_id.get(nid)
        if isinstance(node, ContainerNode):
            stack.extend(node.children)
    return seen


def _stale_decision_nodes(
    evidence: AuthoringEvidence | None, projection: ProjectionMap
) -> set[str]:
    """The node ids whose stored **decision** digest no longer matches their node in the rebound
    projection (§1.6) — detected through the ``decision_digest`` producer (the same authority
    ``evidence_findings`` uses), against the rebound projection. A pure re-bind leaves the decision
    digest byte-identical (re-bind-stable by D33), so this only fires on a genuine topology change
    that a human must re-verify — **never** a re-stamp."""
    if evidence is None:
        return set()
    return {
        entry.node_id
        for entry in evidence.entries
        if (node := projection.by_id.get(entry.node_id)) is not None
        and entry.decision_digest != decision_digest(node)
    }


def _restamp_evidence(
    evidence: AuthoringEvidence | None,
    migrated_projection: ProjectionMap,
    bound_node_ids: set[str],
) -> tuple[EvidenceEntry, ...]:
    """Re-stamp the extent digests of fully-bound subtrees against the rebound projection (§1.6).

    Bottom-up gate: a node is re-stamped only when its **whole subtree is bound** (``bound_node_ids``
    already excludes ``stale-decision`` nodes, so a stale descendant blocks its ancestor — no node
    re-stamped while a descendant is unresolved). The **extent** digest is recomputed through the
    producer ``extent_digest(node, projection)`` (the atoms are new ids, same content); the
    **decision** digest is **carried from the old entry, never machine-refreshed** (re-bind-stable by
    D33)."""
    if evidence is None:
        return ()
    restamped: list[EvidenceEntry] = []
    for entry in evidence.entries:
        node = migrated_projection.by_id.get(entry.node_id)
        if node is None or entry.node_id not in bound_node_ids:
            continue
        if not _subtree_ids(entry.node_id, migrated_projection).issubset(bound_node_ids):
            continue  # a descendant is unresolved — do not re-stamp this ancestor (bottom-up gate)
        restamped.append(
            EvidenceEntry(
                node_id=entry.node_id,
                decision_digest=entry.decision_digest,  # carried, never machine-refreshed
                extent_digest=extent_digest(node, migrated_projection),  # mechanically re-stamped
                evidence=entry.evidence,
                authored_at_revision=entry.authored_at_revision,
                decision_payload=dict(entry.decision_payload),
                extent_payload=extent_payload(node, migrated_projection),
            )
        )
    return tuple(restamped)


# --- the entry points (§1.5) ----------------------------------------------------------------------- #


def rebind(context: RebindContext) -> RebindResult:
    """Re-attach every stored ``node_id`` to the fresh canonical stream — **non-raising** (§1.5): all
    tentative binds and all findings land in the returned :class:`RebindResult`. Partial success is
    represented, never hidden; :func:`assert_all_bound` is the strict complement.

    Order: enumerate slots → the monotone-tiling attribution → assemble the migrated map → the global
    ``validate_projection`` gate (all-bound only; a failure downgrades every tentative bind to
    ``global-conflict``) → the bottom-up extent re-stamp.
    """
    old_map = context.old_map
    slots = _enumerate_slots(old_map, context.old_canonical)
    assignment = _Assignment(slots, context)

    # per-slot outcomes, grouped by node
    slot_outcomes: dict[str, list[SlotOutcome]] = {node.node_id: [] for node in old_map.projection.nodes}
    for j in range(len(slots)):
        slot_outcomes[slots[j].node_id].append(assignment.resolve_slot(j))

    # per-node aggregation (a node with no atom-owning slots binds trivially — its identity is stable)
    node_outcomes: list[NodeOutcome] = []
    bound_node_ids: set[str] = set()
    for node in old_map.projection.nodes:
        outs = tuple(slot_outcomes[node.node_id])
        unresolved = [o.reason for o in outs if not o.bound and o.reason is not None]
        bound = not unresolved
        node_outcomes.append(
            NodeOutcome(
                node_id=node.node_id,
                bound=bound,
                reason=None if bound else _dominant_reason(unresolved),
                slots=outs,
            )
        )
        if bound:
            bound_node_ids.add(node.node_id)

    migrated_doc = _build_migrated_doc(old_map, slot_outcomes)
    migrated_projection = structure_map_from_json(migrated_doc).projection

    # global consistency — bound-SUBSET disjointness, ALWAYS (never gated on all-bound). Per-slot
    # resolution is independent, so two bound slots can each pick a "unique" ≥τ window that OVERLAPS
    # the other on repeated boundary content. A partial re-bind (some node unresolved) would otherwise
    # skip the whole-map gate and report the overlap as two clean binds — the R2 silent mis-bind. Any
    # fresh atom claimed by two bound nodes fails those nodes loud as global-conflict.
    contested = _contested_nodes(node_outcomes)
    # whole-map validation (coverage + empty-container + reference integrity) is meaningful only once
    # every node is tentatively bound (a partial migrated_doc keeps old ids on unbound slots, which
    # would spuriously fail coverage); it catches the map-level faults the pairwise check cannot.
    all_bound = len(bound_node_ids) == len(old_map.projection.nodes)
    if all_bound and not _map_validates(migrated_projection, context):
        contested = {n.node_id for n in node_outcomes}
    if contested:
        node_outcomes = [
            NodeOutcome(node_id=n.node_id, bound=False, reason="global-conflict", slots=n.slots)
            if n.node_id in contested
            else n
            for n in node_outcomes
        ]
        bound_node_ids -= contested

    # stale-decision: a rebound topology whose decision digest drifted is a human-re-verify finding
    # (never a re-stamp). Removed from bound_node_ids BEFORE the re-stamp so a stale descendant blocks
    # its ancestor (the bottom-up gate).
    stale_decisions = _stale_decision_nodes(context.old_evidence, migrated_projection) & bound_node_ids
    if stale_decisions:
        node_outcomes = [
            NodeOutcome(node_id=n.node_id, bound=False, reason="stale-decision", slots=n.slots)
            if n.node_id in stale_decisions
            else n
            for n in node_outcomes
        ]
        bound_node_ids -= stale_decisions

    restamped = _restamp_evidence(context.old_evidence, migrated_projection, bound_node_ids)

    report = RebindReport(
        mode=ModeProvenance(
            mode=context.reported_mode,
            source=context.mode_source,
            manifest_schema_version=context.manifest_schema_version,
        ),
        nodes=tuple(node_outcomes),
        old_canonical_stream_id=context.old_canonical.stream_id,
        fresh_canonical_stream_id=context.fresh_canonical.stream_id,
        old_content_hash=canonical_content_hash(context.old_canonical),
        fresh_content_hash=canonical_content_hash(context.fresh_canonical),
        old_geometry_hash=canonical_geometry_hash(context.old_canonical),
        fresh_geometry_hash=canonical_geometry_hash(context.fresh_canonical),
    )
    return RebindResult(migrated_doc=migrated_doc, report=report, restamped_evidence=restamped)


def _contested_nodes(node_outcomes: list[NodeOutcome]) -> set[str]:
    """The node ids that share a fresh atom with another **bound** node — the bound-SUBSET disjointness
    check (§1.3), run on every re-bind regardless of all-bound. Independent per-slot resolution can let
    two bound slots each claim a unique ≥τ window that overlaps on repeated boundary content; monotone
    reading order rules out *crossing*, so overlap is the only cross-node fault, and a shared fresh atom
    id is its exact witness. Returns every node touching a doubly-claimed atom (both sides fail loud)."""
    claims: dict[str, list[str]] = {}
    for node in node_outcomes:
        if node.bound:
            for slot in node.slots:
                for atom_id in slot.fresh_atom_ids:
                    claims.setdefault(atom_id, []).append(node.node_id)
    return {nid for owners in claims.values() if len(owners) > 1 for nid in owners}


def _map_validates(projection: ProjectionMap, context: RebindContext) -> bool:
    """The whole-map global-consistency gate (§1.3): the rebound projection must pass
    ``validate_projection`` (ownership disjoint + coverage + ordering) **and** reference integrity
    against the fresh reader. A double-claimed atom (the greedy mutant) or a coverage gap reds here."""
    try:
        validate_projection(projection, context.fresh_reader)
        validate_reference_integrity(projection)
    except StructureValidationError:
        return False
    except ValueError:
        # validate_reference_integrity's unresolved-root programming guard — treat as a conflict, never
        # a silent pass (a rebound map whose root does not resolve is not a valid bind).
        return False
    return True


def _build_migrated_doc(
    old_map: StructureMap, slot_outcomes: dict[str, list[SlotOutcome]]
) -> dict:
    """A deep copy of the old map document with each **bound** slot's atom ids replaced by its fresh
    window (§1.5). Unbound slots keep their old ids (a partial migration the report flags); the
    manifest is carried verbatim — S5.2 owns the writer and the manifest re-stamp on persist."""
    doc = copy.deepcopy(dict(old_map.doc))
    by_slot: dict[tuple[str, str], SlotOutcome] = {}
    for node_id, outs in slot_outcomes.items():
        for out in outs:
            if out.bound:
                by_slot[(node_id, out.slot_name)] = out
    slot_key = {"heading": "heading_atoms", "signature": "signature_atoms", "body": "body_atoms"}
    for node in doc["nodes"]:
        for slot_name, doc_key in slot_key.items():
            out = by_slot.get((node["node_id"], slot_name))
            if out is not None and doc_key in node:
                node[doc_key] = list(out.fresh_atom_ids)
    return doc


def assert_all_bound(result: RebindResult) -> None:
    """Strict complement of :func:`rebind` (§1.5): raise :class:`RebindError` if any stored node did
    not auto-bind, carrying the ``(node_id, reason)`` findings. Returns ``None`` when every node bound."""
    unresolved = result.report.unresolved
    if unresolved:
        raise RebindError(unresolved)
