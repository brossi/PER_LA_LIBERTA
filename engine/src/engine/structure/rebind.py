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

Three anchors and three modes remain, but S4.7/#48 replaces the cubic assignment with anchored
annotation transfer:

- **region seed** — a single ``{page, bbox_region}`` used only for page-equality pin/tie behavior;
  **content fingerprint** — the per-slot fuzzy ratio gate; **stored boundary anchors** — bounded
  prefix/exact/suffix context that independently confirms the aligned start/end positions.
- modes ``geometry-primary | geometry-tie-break | no-geometry`` (from
  ``manifest.segmentation.geometry_mode``; PLL = ``geometry-tie-break``, #30): geometry leads /
  corroborates / is discarded. **No rescue** — geometry and path only disambiguate among candidates
  already ≥ τ; they never lift a sub-τ fingerprint over τ (geometry is a pin, never a cost term).
- unique-in-both 3-gram landmarks → LIS monotone chain → capped per-gap RapidFuzz opcodes; token
  boundaries project back through token→atom pointers and the whole rebound projection validates
  globally before any bind counts.

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
import math
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from engine.errors import EngineError, StaleArtifactError
from engine.structure.atom_store import (
    CANONICAL,
    AtomStream,
    assert_reference_integrity,
)
from engine.structure.atoms import PROCESSING_SCOPE_INCLUDED
from engine.structure.errors import StructureValidationError
from engine.structure.evidence import (
    AuthoringEvidence,
    EvidenceEntry,
    _batch_live_extent_payloads,
    decision_digest,
    extent_digest,
    extent_payload,
)
from engine.structure.geom_match import normalize_tokens
from engine.structure.geom_regate import MODE_NO_GEOMETRY, MODE_PRIMARY, MODE_TIE_BREAK
from engine.structure.reanchor import (
    ALIGNMENT_BACKEND_ID,
    BoundaryAnchorBatchLocator,
    align_token_streams,
    materialize_token_stream,
    tokenless_gap_context,
)
from engine.structure.rebind_telemetry import (
    NULL_REBIND_TELEMETRY,
    RebindTelemetry,
)
from engine.structure.projection import (
    ContainerNode,
    Node,
    ProjectionMap,
    Region,
    SlotBoundaryAnchors,
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

WORK_PROGRESS_PUBLISH_INTERVAL_SECONDS = 1.0

RESOLVER_COMPONENTS = (
    "old-span-discovery",
    "boundary-projection",
    "atom-boundary-conversion",
    "fingerprint-construction",
    "fingerprint-metrics",
    "page-check",
    "outcome-assembly",
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


def fingerprint_slot(
    tokens: Sequence[str], *, k: int = DEFAULT_SHINGLE_K
) -> SlotFingerprint | None:
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
    shingles = sorted(
        {" ".join(toks[i : i + k_eff]) for i in range(len(toks) - k_eff + 1)}
    )
    return SlotFingerprint(
        algo_id=FINGERPRINT_ALGO_ID,
        normalizer_id=FINGERPRINT_NORMALIZER_ID,
        k=k_eff,
        token_count=len(toks),
        shingles=tuple(shingles),
    )


@dataclass(frozen=True, slots=True)
class _RuntimeSlotFingerprint:
    """Immutable comparison-only fingerprint without serialized ordering work."""

    k: int
    token_count: int
    shingles: frozenset[str]


def _runtime_fingerprint_slot(
    tokens: Sequence[str], *, k: int = DEFAULT_SHINGLE_K
) -> _RuntimeSlotFingerprint | None:
    """Build the fresh runtime fingerprint without sorting it for persistence.

    Stored fingerprints remain the public :class:`SlotFingerprint` representation with stable
    tuple ordering.  Fresh rebind fingerprints are consumed only as sets, so sorting that set and
    constructing a persistence-shaped object is pure overhead.  This immutable representation keeps
    the same short-slot and shingle-string semantics while making the distinction explicit.
    """
    if not tokens:
        return None
    k_eff = min(k, len(tokens)) if k >= 1 else 1
    return _RuntimeSlotFingerprint(
        k=k_eff,
        token_count=len(tokens),
        shingles=frozenset(
            " ".join(tokens[index : index + k_eff])
            for index in range(len(tokens) - k_eff + 1)
        ),
    )


@dataclass(frozen=True, slots=True)
class _SlotFingerprintMetrics:
    """The immutable evidence derived from one fresh-slot fingerprint construction."""

    fresh: _RuntimeSlotFingerprint | None
    score: float
    containment: float | None
    token_count_ratio: float | None


def _slot_fingerprint_metrics(
    stored: SlotFingerprint, window_tokens: Sequence[str]
) -> _SlotFingerprintMetrics:
    """Construct one fresh fingerprint and derive every decision/report metric from it."""
    fresh = _runtime_fingerprint_slot(window_tokens, k=stored.k)
    return _slot_fingerprint_metrics_from_fresh(
        stored, fresh, fresh_token_count=len(window_tokens)
    )


def _slot_fingerprint_metrics_from_fresh(
    stored: SlotFingerprint,
    fresh: _RuntimeSlotFingerprint | None,
    *,
    fresh_token_count: int,
) -> _SlotFingerprintMetrics:
    """Derive every metric from one already-constructed fresh fingerprint."""
    stored_shingles = frozenset(stored.shingles)
    fresh_shingles = fresh.shingles if fresh is not None else frozenset()
    intersection_size = len(stored_shingles & fresh_shingles)
    union_size = len(stored_shingles) + len(fresh_shingles) - intersection_size
    return _SlotFingerprintMetrics(
        fresh=fresh,
        score=intersection_size / union_size if union_size else 0.0,
        containment=(
            intersection_size / len(stored_shingles)
            if stored_shingles
            else None
        ),
        token_count_ratio=(
            fresh_token_count / stored.token_count if stored.token_count else None
        ),
    )


def slot_similarity(stored: SlotFingerprint, window_tokens: Sequence[str]) -> float:
    """The ``[0, 1]`` similarity of a candidate window's normalized ``window_tokens`` to a ``stored``
    slot fingerprint: Jaccard over the shingle sets, the fresh side recomputed at the **stored** ``k``
    (short-slot fallback included) so the two shingle vocabularies line up. An empty window scores 0
    (the short-slot guard: it never binds on an empty set). Fuzzy by construction — a locally edited
    window scores strictly between 0 and 1, never the exact-substring all-or-nothing R2 tombstoned."""
    return _slot_fingerprint_metrics(stored, window_tokens).score


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
    identity: str | None = None

    def __post_init__(self) -> None:
        for name in ("tau_primary", "tau_tie_break", "tau_no_geometry"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0.0 <= value <= 1.0
            ):
                raise ValueError(f"RebindPolicy.{name} must be finite in [0, 1]")
        if not (self.tau_no_geometry >= self.tau_tie_break >= self.tau_primary):
            raise ValueError(
                f"RebindPolicy violates the default-ordering τ(no-geometry) >= τ(tie-break) >= "
                f"τ(primary): got no-geometry={self.tau_no_geometry}, tie-break={self.tau_tie_break}, "
                f"primary={self.tau_primary} — weaker geometry must never lower the fingerprint bar "
                f"(monotone-strictness, feedback_no_cheating_results)"
            )
        if self.identity is not None and not self.identity.strip():
            raise ValueError(
                "RebindPolicy.identity must be None or a non-blank registered identity"
            )

    def threshold(self, dp_mode: str) -> float:
        """The fingerprint threshold τ for a resolved DP mode."""
        if dp_mode == MODE_PRIMARY:
            return self.tau_primary
        if dp_mode == MODE_TIE_BREAK:
            return self.tau_tie_break
        if dp_mode == MODE_NO_GEOMETRY:
            return self.tau_no_geometry
        raise ValueError(
            f"RebindPolicy.threshold: unknown dp_mode {dp_mode!r} (expected {GEOMETRY_MODES})"
        )


# --- the closed unresolved-reason enum + the strict error (§1.5, D-6) ------------------------------ #

#: The **closed** set of reasons a node fails to auto-bind (§1.5). Mirrors evidence.py's closed
#: ``EVIDENCE_FINDING_KINDS`` discipline so a typo cannot mint a pseudo-reason. Their meanings are
#: deliberately disjoint: ``missing-anchor`` = "no legal signal to search with" (the slot's mode needs
#: a fingerprint and the node stores none); ``zero-candidate`` = "searched the legal space, found no
#: projected/confirmed candidate" — the near-duplicate precheck failed, geometry excluded the
#: projection, or no non-empty atom representation exists; ``below-threshold`` = "the projected
#: content/anchor score is < τ"; ``ambiguous`` = "anchor occurrence/boundary ownership is not unique";
#: ``stale-decision`` = "the rebound topology changed
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


class RebindNotConsumableError(EngineError):
    """A fully-bound result lacks the registered policy identity required for consumption."""

    exit_code = 17

    def __init__(self) -> None:
        super().__init__(
            "re-bind result is not-for-consumption: no registered policy/calibration identity "
            "is present in the report (ER-A3; S5.2 owns calibration registration)"
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
    the atom span this slot bound to (empty when unresolved). ``ambiguity_candidates`` is the
    saturated (0/1/2) count of competing anchor locations. ``boundary_classes`` and ``located_by``
    expose how the diff proposal was independently confirmed.
    """

    slot_name: str
    bound: bool
    reason: str | None
    score: float | None
    fresh_atom_ids: tuple[str, ...]
    ambiguity_candidates: int
    region_page: int | None
    containment: float | None
    token_count_ratio: float | None
    boundary_classes: tuple[str, str] | None = None
    located_by: tuple[str, str] | None = None

    @property
    def candidates_ge_tau(self) -> int:
        """Compatibility alias for the v2 report field, now an anchor-ambiguity count."""
        return self.ambiguity_candidates


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
    alignment_backend: str = ALIGNMENT_BACKEND_ID
    policy_identity: str | None = None

    @property
    def consumable(self) -> bool:
        """Whether strict pre-S5.2 consumption has a registered policy/calibration identity."""
        return self.policy_identity is not None

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
        telemetry: RebindTelemetry | None = None,
    ) -> None:
        self.old_map = old_map
        self.old_evidence = old_evidence
        self.canonical_stream_id = canonical_stream_id
        self.policy = policy if policy is not None else RebindPolicy()
        self.telemetry = telemetry
        self.dp_mode, self.reported_mode, self.mode_source = resolve_mode(geometry_mode)

        self.old_canonical, self.old_witnesses = _split_streams(
            old_streams, canonical_stream_id, "old"
        )
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


# --- anchored annotation transfer (§2.1–§2.3) ----------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _Slot:
    """One atom-owning slot of a stored node, in re-bind reading order: the node it belongs to, the
    slot name (``body`` | ``heading`` | ``signature``), its stored fingerprint (``None`` ⇒
    ``missing-anchor``), its optional region seed, and ``order_key`` (its first owned atom's index in
    the old canonical included stream — the reading-order sort key)."""

    node_id: str
    slot_name: str
    fingerprint: SlotFingerprint | None
    boundary_anchors: SlotBoundaryAnchors | None
    region: Region | None
    order_key: int
    old_atom_start: int
    old_atom_end: int
    contiguous: bool


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
            a
            for a in old_canonical.atoms
            if a.processing_scope == PROCESSING_SCOPE_INCLUDED
        )
    }
    slots: list[_Slot] = []
    for node in old_map.projection.nodes:
        anchors = node.rebind_anchors
        for slot_name, atom_ids in _owning_slots_of(node):
            if not atom_ids:
                continue
            positions = [old_index[aid] for aid in atom_ids]
            order_key = min(positions)
            contiguous = positions == list(range(order_key, order_key + len(positions)))
            slots.append(
                _Slot(
                    node_id=node.node_id,
                    slot_name=slot_name,
                    fingerprint=anchors.fingerprint(slot_name) if anchors else None,
                    boundary_anchors=anchors.boundaries(slot_name) if anchors else None,
                    region=anchors.region if anchors else None,
                    order_key=order_key,
                    old_atom_start=order_key,
                    old_atom_end=order_key + len(positions),
                    contiguous=contiguous,
                )
            )
    slots.sort(key=lambda s: s.order_key)
    return slots


def _detect_introduced_token_duplication(
    old_tokens: tuple[str, ...], fresh_tokens: tuple[str, ...]
) -> tuple[bool, dict[str, int]]:
    """Detect fresh 1/2/3-gram duplication and return its telemetry cardinalities."""
    introduced = False
    cardinalities: dict[str, int] = {}
    for width in range(1, 4):
        old_grams = Counter(
            tuple(old_tokens[index : index + width])
            for index in range(max(0, len(old_tokens) - width + 1))
        )
        fresh_grams = Counter(
            tuple(fresh_tokens[index : index + width])
            for index in range(max(0, len(fresh_tokens) - width + 1))
        )
        cardinalities[f"old_unique_{width}gram"] = len(old_grams)
        cardinalities[f"fresh_unique_{width}gram"] = len(fresh_grams)
        introduced |= any(
            old_grams[gram] == 1 and count > 1 for gram, count in fresh_grams.items()
        )
    return introduced, cardinalities


class _AnchoredAssignment:
    """One anchored alignment followed by O(1)-per-slot boundary projection.

    The expensive work is shared: token materialization, unique-k-gram indexing, LIS chaining,
    and capped per-gap opcodes run once for the whole generation pair.  Slot work is arithmetic
    plus bounded anchor lookup; no slot enumerates candidate windows.
    """

    def __init__(self, slots: list[_Slot], context: RebindContext) -> None:
        self.slots = slots
        self.context = context
        self.telemetry = context.telemetry or NULL_REBIND_TELEMETRY
        self.dp_mode = context.dp_mode
        self.tau = context.policy.threshold(context.dp_mode)
        with self.telemetry.span("rebind.materialize-old-tokens") as span:
            self.old = materialize_token_stream(context.old_canonical)
            span.update(
                atom_count=len(self.old.atom_ids), token_count=len(self.old.tokens)
            )
        with self.telemetry.span("rebind.materialize-fresh-tokens") as span:
            self.fresh = materialize_token_stream(context.fresh_canonical)
            span.update(
                atom_count=len(self.fresh.atom_ids), token_count=len(self.fresh.tokens)
            )
        self.tokens_identical = self.fresh.tokens == self.old.tokens
        with self.telemetry.span("rebind.align-tokens") as span:
            self.alignment = align_token_streams(self.old.tokens, self.fresh.tokens)
            span.update(
                alignment_blocks=len(self.alignment.blocks),
                chained_anchors=len(self.alignment.chained_anchors),
                near_duplicate=self.alignment.near_duplicate,
                identity_fast_path=self.alignment.identity,
            )
        with self.telemetry.span("rebind.prepare-anchor-queries") as span:
            anchor_queries = tuple(
                query
                for slot in slots
                if slot.boundary_anchors is not None
                for query in (
                    (slot.boundary_anchors.start, "start"),
                    (slot.boundary_anchors.end, "end"),
                )
            )
            span.update(
                query_count=len(anchor_queries),
                unique_query_count=len(set(anchor_queries)),
            )
        with self.telemetry.span("rebind.locate-old-anchors") as span:
            self.old_anchor_locations = BoundaryAnchorBatchLocator(
                self.old.tokens, anchor_queries, threshold=self.tau
            )
            span.update(
                windows_scanned=self.old_anchor_locations.windows_scanned,
                exact_windows_scanned=(self.old_anchor_locations.exact_windows_scanned),
                fuzzy_windows_scanned=(self.old_anchor_locations.fuzzy_windows_scanned),
                group_count=self.old_anchor_locations.group_count,
                signature_count=self.old_anchor_locations.signature_count,
                fuzzy_searched_queries=(
                    self.old_anchor_locations.fuzzy_searched_query_count
                ),
                exact_resolved_queries=(
                    self.old_anchor_locations.exact_resolved_query_count
                ),
                fuzzy_resolved_queries=(
                    self.old_anchor_locations.fuzzy_resolved_query_count
                ),
                unresolved_queries=self.old_anchor_locations.unresolved_query_count,
            )
        with self.telemetry.span(
            "rebind.locate-fresh-anchors", tokens_identical=self.tokens_identical
        ) as span:
            self.fresh_anchor_locations = (
                self.old_anchor_locations
                if self.tokens_identical
                else BoundaryAnchorBatchLocator(
                    self.fresh.tokens, anchor_queries, threshold=self.tau
                )
            )
            span.update(
                reused_old_locator=self.tokens_identical,
                windows_scanned=(
                    0
                    if self.tokens_identical
                    else self.fresh_anchor_locations.windows_scanned
                ),
                exact_windows_scanned=(
                    0
                    if self.tokens_identical
                    else self.fresh_anchor_locations.exact_windows_scanned
                ),
                fuzzy_windows_scanned=(
                    0
                    if self.tokens_identical
                    else self.fresh_anchor_locations.fuzzy_windows_scanned
                ),
                signature_count=(
                    0
                    if self.tokens_identical
                    else self.fresh_anchor_locations.signature_count
                ),
                fuzzy_searched_queries=(
                    0
                    if self.tokens_identical
                    else self.fresh_anchor_locations.fuzzy_searched_query_count
                ),
                exact_resolved_queries=(
                    self.fresh_anchor_locations.exact_resolved_query_count
                ),
                fuzzy_resolved_queries=(
                    self.fresh_anchor_locations.fuzzy_resolved_query_count
                ),
                unresolved_queries=(self.fresh_anchor_locations.unresolved_query_count),
            )
        with self.telemetry.span("rebind.index-boundary-owners") as span:
            self._old_boundary_owners = Counter(
                boundary
                for slot in slots
                for boundary in (slot.old_atom_start, slot.old_atom_end)
            )
            span.update(unique_boundaries=len(self._old_boundary_owners))
        self.unresolved_duplication = False
        with self.telemetry.span("rebind.detect-token-duplication") as span:
            if self.tokens_identical:
                span.update(
                    tokens_identical=True,
                    analysis_skipped=True,
                    gram_widths_analyzed=0,
                )
            else:
                introduced, cardinalities = _detect_introduced_token_duplication(
                    self.old.tokens, self.fresh.tokens
                )
                self.unresolved_duplication |= introduced
                span.update(
                    tokens_identical=False,
                    analysis_skipped=False,
                    gram_widths_analyzed=3,
                    **cardinalities,
                )
            span.update(unresolved_duplication=self.unresolved_duplication)
        with self.telemetry.span("rebind.detect-tokenless-duplication") as span:
            old_tokenless = Counter(
                text
                for text, token_range in zip(
                    self.old.atom_texts, self.old.atom_token_ranges, strict=True
                )
                if token_range[0] == token_range[1]
            )
            fresh_tokenless = Counter(
                text
                for text, token_range in zip(
                    self.fresh.atom_texts, self.fresh.atom_token_ranges, strict=True
                )
                if token_range[0] == token_range[1]
            )
            self.unresolved_duplication |= any(
                fresh_tokenless[text] > count for text, count in old_tokenless.items()
            )
            span.update(
                old_tokenless_atoms=sum(old_tokenless.values()),
                fresh_tokenless_atoms=sum(fresh_tokenless.values()),
                unresolved_duplication=self.unresolved_duplication,
            )
        self._resolved: dict[tuple[int, str], int] = {}
        self._fingerprint_evaluated_slot_indexes: set[int] = set()
        self._fresh_fingerprint_computations = 0
        self._collect_resolver_components = self.telemetry is not NULL_REBIND_TELEMETRY
        self._resolver_component_timings: dict[str, dict[str, int]] = {
            name: {
                "first_started_wall_ns": 0,
                "wall_ns": 0,
                "cpu_ns": 0,
                "occurrences": 0,
            }
            for name in RESOLVER_COMPONENTS
        }
        self._atom_boundary_lookup_calls = 0
        self._atom_boundary_inspected_ranges = 0
        self._atom_boundary_lookup_outcomes: Counter[str] = Counter()

    def _start_resolver_component(self) -> tuple[int, int] | None:
        if not self._collect_resolver_components:
            return None
        return time.perf_counter_ns(), time.process_time_ns()

    def _finish_resolver_component(
        self, name: str, started: tuple[int, int] | None
    ) -> None:
        if started is None:
            return
        ended_cpu_ns = time.process_time_ns()
        ended_wall_ns = time.perf_counter_ns()
        record = self._resolver_component_timings[name]
        if record["occurrences"] == 0:
            record["first_started_wall_ns"] = started[0]
        record["wall_ns"] += ended_wall_ns - started[0]
        record["cpu_ns"] += ended_cpu_ns - started[1]
        record["occurrences"] += 1

    def publish_resolver_component_spans(self) -> None:
        for name in RESOLVER_COMPONENTS:
            record = self._resolver_component_timings[name]
            attributes: dict[str, object] = {}
            if name == "atom-boundary-conversion":
                attributes = {
                    "lookup_calls": self._atom_boundary_lookup_calls,
                    "inspected_ranges": self._atom_boundary_inspected_ranges,
                    "lookup_outcomes": dict(
                        sorted(self._atom_boundary_lookup_outcomes.items())
                    ),
                }
            self.telemetry.record_aggregate_span(
                f"rebind.resolve-slots.{name}",
                first_started_wall_ns=record["first_started_wall_ns"],
                wall_ns=record["wall_ns"],
                cpu_ns=record["cpu_ns"],
                occurrences=record["occurrences"],
                **attributes,
            )

    def _slot_token_span(self, slot: _Slot) -> tuple[int, int] | None:
        ranges = self.old.atom_token_ranges[slot.old_atom_start : slot.old_atom_end]
        tokened = [(start, end) for start, end in ranges if start != end]
        if not tokened:
            return None
        return tokened[0][0], tokened[-1][1]

    @staticmethod
    def _boundary_page(stream, boundary: int, side: str) -> int | None:
        if not stream.tokens:
            return None
        token_index = boundary if side == "start" else boundary - 1
        token_index = min(max(token_index, 0), len(stream.tokens) - 1)
        atom_index = stream.token_atom_indexes[token_index]
        return stream.atom_pages[atom_index]

    def _geometry_filter(
        self, boundaries: tuple[int, ...], slot: _Slot, side: str, *, old: bool = False
    ) -> tuple[int, ...]:
        if slot.region is None or self.dp_mode == MODE_NO_GEOMETRY:
            return boundaries
        stream = self.old if old else self.fresh
        on_page = tuple(
            boundary
            for boundary in boundaries
            if self._boundary_page(stream, boundary, side) == slot.region.page
        )
        if self.dp_mode == MODE_PRIMARY:
            return on_page
        # Tie-break geometry narrows an actual content tie only; it never rescues an absent match.
        return on_page if len(boundaries) > 1 and on_page else boundaries

    def _resolve_boundary(
        self,
        slot_index: int,
        slot: _Slot,
        anchors,
        old_token_boundary: int,
        old_atom_boundary: int,
        side: str,
    ) -> tuple[int | None, int | None, str, str | None, int, str | None]:
        projection = self.alignment.project_boundary(old_token_boundary)
        anchor = anchors.start if side == "start" else anchors.end
        old_location = self.old_anchor_locations.locate(anchor, side=side)
        old_boundaries = (
            self._geometry_filter(old_location.boundaries, slot, side, old=True)
            if len(old_location.boundaries) > 1
            else old_location.boundaries
        )
        if old_boundaries != (old_token_boundary,):
            return (
                None,
                None,
                projection.boundary_class,
                None,
                len(old_boundaries),
                "ambiguous",
            )

        fresh_location = self.fresh_anchor_locations.locate(anchor, side=side)
        located = self._geometry_filter(fresh_location.boundaries, slot, side)
        ambiguity = min(2, len(located))
        if not located:
            if self.dp_mode == MODE_PRIMARY and fresh_location.boundaries:
                reason = "zero-candidate"
            else:
                reason = (
                    "below-threshold"
                    if fresh_location.best_score < self.tau
                    else "ambiguous"
                )
            return None, None, projection.boundary_class, None, ambiguity, reason

        if projection.boundary_class == "no-candidate":
            lo, hi = projection.fresh_window
            admitted = tuple(boundary for boundary in located if lo <= boundary <= hi)
            method = "anchor-window"
        else:
            admitted = tuple(
                boundary for boundary in located if boundary in projection.candidates
            )
            method = (
                "anchor-insert-side"
                if projection.boundary_class == "two-candidate"
                else "anchor-projected"
            )
        if (
            projection.boundary_class == "two-candidate"
            and self._old_boundary_owners[old_atom_boundary] < 2
        ):
            return (
                None,
                None,
                projection.boundary_class,
                None,
                max(2, ambiguity),
                "ambiguous",
            )
        if len(admitted) != 1:
            return (
                None,
                None,
                projection.boundary_class,
                None,
                max(ambiguity, min(2, len(admitted))),
                "ambiguous",
            )

        token_boundary = admitted[0]
        gap_offset, tokenless_texts = tokenless_gap_context(
            self.old, old_atom_boundary, old_token_boundary
        )
        component_started = self._start_resolver_component()
        lookup = self.fresh.lookup_atom_boundary_for_token_boundary(
            token_boundary,
            old_gap_offset=gap_offset,
            old_tokenless_texts=tokenless_texts,
        )
        self._finish_resolver_component(
            "atom-boundary-conversion", component_started
        )
        self._atom_boundary_lookup_calls += 1
        self._atom_boundary_inspected_ranges += lookup.inspected_ranges
        self._atom_boundary_lookup_outcomes[lookup.outcome] += 1
        atom_boundary = lookup.atom_boundary
        if atom_boundary is None:
            # A clean token projection inside a merged fresh atom is an ownership conflict, not a
            # rounding opportunity.  Both sides of a shared seam are downgraded by resolve_all().
            return (
                None,
                None,
                projection.boundary_class,
                None,
                ambiguity,
                "global-conflict",
            )
        self._resolved[(slot_index, side)] = atom_boundary
        return (
            atom_boundary,
            token_boundary,
            projection.boundary_class,
            method,
            ambiguity,
            None,
        )

    def _outcome(
        self,
        slot: _Slot,
        *,
        bound: bool,
        reason: str | None,
        atom_span: tuple[int, int] | None,
        token_span: tuple[int, int] | None,
        ambiguity: int,
        boundary_classes: tuple[str, str] | None,
        located_by: tuple[str, str] | None,
        fingerprint_metrics: _SlotFingerprintMetrics | None = None,
    ) -> SlotOutcome:
        component_started = self._start_resolver_component()
        try:
            score = containment = token_ratio = None
            fresh_ids: tuple[str, ...] = ()
            if fingerprint_metrics is not None:
                score = fingerprint_metrics.score
                containment = fingerprint_metrics.containment
                token_ratio = fingerprint_metrics.token_count_ratio
            if bound and atom_span is not None:
                fresh_ids = self.fresh.atom_ids[atom_span[0] : atom_span[1]]
            return SlotOutcome(
                slot_name=slot.slot_name,
                bound=bound,
                reason=reason,
                score=score,
                fresh_atom_ids=fresh_ids,
                ambiguity_candidates=min(2, ambiguity),
                region_page=slot.region.page if slot.region is not None else None,
                containment=containment,
                token_count_ratio=token_ratio,
                boundary_classes=boundary_classes,
                located_by=located_by,
            )
        finally:
            self._finish_resolver_component("outcome-assembly", component_started)

    def _evaluate_slot_fingerprint(
        self,
        slot_index: int,
        slot: _Slot,
        token_span: tuple[int, int],
    ) -> _SlotFingerprintMetrics:
        """Evaluate one slot exactly where the pre-optimization path already evaluated it."""
        if slot.fingerprint is None:
            raise AssertionError("fingerprint evaluation requires a stored fingerprint")
        self._fingerprint_evaluated_slot_indexes.add(slot_index)
        self._fresh_fingerprint_computations += 1
        fresh_tokens = self.fresh.tokens[token_span[0] : token_span[1]]
        component_started = self._start_resolver_component()
        fresh_fingerprint = _runtime_fingerprint_slot(
            fresh_tokens, k=slot.fingerprint.k
        )
        self._finish_resolver_component(
            "fingerprint-construction", component_started
        )
        component_started = self._start_resolver_component()
        metrics = _slot_fingerprint_metrics_from_fresh(
            slot.fingerprint,
            fresh_fingerprint,
            fresh_token_count=len(fresh_tokens),
        )
        self._finish_resolver_component("fingerprint-metrics", component_started)
        return metrics

    @property
    def fingerprint_evaluated_slot_count(self) -> int:
        return len(self._fingerprint_evaluated_slot_indexes)

    @property
    def fresh_fingerprint_computation_count(self) -> int:
        return self._fresh_fingerprint_computations

    def resolve_slot(self, slot_index: int) -> SlotOutcome:
        slot = self.slots[slot_index]
        if slot.fingerprint is None or slot.boundary_anchors is None:
            return self._outcome(
                slot,
                bound=False,
                reason="missing-anchor",
                atom_span=None,
                token_span=None,
                ambiguity=0,
                boundary_classes=None,
                located_by=None,
            )
        if not slot.contiguous:
            return self._outcome(
                slot,
                bound=False,
                reason="ambiguous",
                atom_span=None,
                token_span=None,
                ambiguity=2,
                boundary_classes=None,
                located_by=None,
            )
        component_started = self._start_resolver_component()
        old_token_span = self._slot_token_span(slot)
        self._finish_resolver_component("old-span-discovery", component_started)
        if old_token_span is None:
            return self._outcome(
                slot,
                bound=False,
                reason="missing-anchor",
                atom_span=None,
                token_span=None,
                ambiguity=0,
                boundary_classes=None,
                located_by=None,
            )
        if not self.alignment.near_duplicate:
            return self._outcome(
                slot,
                bound=False,
                reason="zero-candidate",
                atom_span=None,
                token_span=None,
                ambiguity=0,
                boundary_classes=None,
                located_by=None,
            )
        if self.dp_mode == MODE_NO_GEOMETRY and self.unresolved_duplication:
            return self._outcome(
                slot,
                bound=False,
                reason="ambiguous",
                atom_span=None,
                token_span=None,
                ambiguity=2,
                boundary_classes=None,
                located_by=None,
            )

        component_started = self._start_resolver_component()
        start = self._resolve_boundary(
            slot_index,
            slot,
            slot.boundary_anchors,
            old_token_span[0],
            slot.old_atom_start,
            "start",
        )
        end = self._resolve_boundary(
            slot_index,
            slot,
            slot.boundary_anchors,
            old_token_span[1],
            slot.old_atom_end,
            "end",
        )
        self._finish_resolver_component("boundary-projection", component_started)
        classes = (start[2], end[2])
        ambiguity = max(start[4], end[4])
        reason = start[5] or end[5]
        if (
            reason is not None
            or start[0] is None
            or start[1] is None
            or end[0] is None
            or end[1] is None
        ):
            return self._outcome(
                slot,
                bound=False,
                reason=reason or "ambiguous",
                atom_span=None,
                token_span=None,
                ambiguity=ambiguity,
                boundary_classes=classes,
                located_by=None,
            )
        fresh_atom_span = (start[0], end[0])
        fresh_token_span = (start[1], end[1])
        fingerprint_metrics = self._evaluate_slot_fingerprint(
            slot_index, slot, fresh_token_span
        )
        if (
            fresh_atom_span[0] >= fresh_atom_span[1]
            or fresh_token_span[0] >= fresh_token_span[1]
        ):
            return self._outcome(
                slot,
                bound=False,
                reason="zero-candidate",
                atom_span=None,
                token_span=fresh_token_span,
                ambiguity=ambiguity,
                boundary_classes=classes,
                located_by=None,
                fingerprint_metrics=fingerprint_metrics,
            )
        if fingerprint_metrics.score < self.tau:
            return self._outcome(
                slot,
                bound=False,
                reason="below-threshold",
                atom_span=fresh_atom_span,
                token_span=fresh_token_span,
                ambiguity=ambiguity,
                boundary_classes=classes,
                located_by=None,
                fingerprint_metrics=fingerprint_metrics,
            )
        if self.dp_mode == MODE_PRIMARY and slot.region is not None:
            component_started = self._start_resolver_component()
            pages = self.fresh.atom_pages[fresh_atom_span[0] : fresh_atom_span[1]]
            page_mismatch = any(page != slot.region.page for page in pages)
            self._finish_resolver_component("page-check", component_started)
            if page_mismatch:
                return self._outcome(
                    slot,
                    bound=False,
                    reason="zero-candidate",
                    atom_span=fresh_atom_span,
                    token_span=fresh_token_span,
                    ambiguity=ambiguity,
                    boundary_classes=classes,
                    located_by=None,
                    fingerprint_metrics=fingerprint_metrics,
                )
        return self._outcome(
            slot,
            bound=True,
            reason=None,
            atom_span=fresh_atom_span,
            token_span=fresh_token_span,
            ambiguity=ambiguity,
            boundary_classes=classes,
            located_by=(start[3] or "anchor", end[3] or "anchor"),
            fingerprint_metrics=fingerprint_metrics,
        )

    def resolve_all(self) -> list[SlotOutcome]:
        if self.telemetry is NULL_REBIND_TELEMETRY:
            outcomes = [self.resolve_slot(index) for index in range(len(self.slots))]
        else:
            outcomes = []
            total = len(self.slots)
            next_progress_at = (
                time.monotonic() + WORK_PROGRESS_PUBLISH_INTERVAL_SECONDS
            )
            for index in range(total):
                outcomes.append(self.resolve_slot(index))
                completed = index + 1
                if completed == total:
                    self.telemetry.progress(completed, total)
                    continue
                now = time.monotonic()
                if now >= next_progress_at:
                    self.telemetry.progress(completed, total)
                    next_progress_at = now + WORK_PROGRESS_PUBLISH_INTERVAL_SECONDS
        shared: dict[int, list[tuple[int, str, int]]] = {}
        shared_all: dict[int, list[tuple[int, str, int | None, str | None]]] = {}
        for index, slot in enumerate(self.slots):
            for side, old_boundary in (
                ("start", slot.old_atom_start),
                ("end", slot.old_atom_end),
            ):
                resolved = self._resolved.get((index, side))
                classes = outcomes[index].boundary_classes
                boundary_class = (
                    classes[0 if side == "start" else 1]
                    if classes is not None
                    else None
                )
                shared_all.setdefault(old_boundary, []).append(
                    (index, side, resolved, boundary_class)
                )
                if resolved is not None:
                    shared.setdefault(old_boundary, []).append((index, side, resolved))
        conflicted: set[int] = set()
        for decisions in shared.values():
            if len({resolved for _, _, resolved in decisions}) > 1:
                conflicted.update(index for index, _, _ in decisions)
        for decisions in shared_all.values():
            if len(decisions) < 2 or not any(
                boundary_class == "two-candidate"
                for _, _, _, boundary_class in decisions
            ):
                continue
            resolved = [value for _, _, value, _ in decisions]
            if any(value is None for value in resolved) or len(set(resolved)) > 1:
                conflicted.update(index for index, _, _, _ in decisions)
        for index in conflicted:
            outcome = outcomes[index]
            outcomes[index] = SlotOutcome(
                slot_name=outcome.slot_name,
                bound=False,
                reason="global-conflict",
                score=outcome.score,
                fresh_atom_ids=(),
                ambiguity_candidates=outcome.ambiguity_candidates,
                region_page=outcome.region_page,
                containment=outcome.containment,
                token_count_ratio=outcome.token_count_ratio,
                boundary_classes=outcome.boundary_classes,
                located_by=None,
            )
        return outcomes


# --- reason severity (dominant reason for a multi-slot node) --------------------------------------- #

#: Severity order for picking a node's dominant unresolved reason across its slots — the most
#: actionable "no signal" reasons first. Only used to summarize; every slot's own reason stays in the
#: per-slot outcomes.
_REASON_SEVERITY = {
    "missing-anchor": 0,
    "global-conflict": 1,
    "stale-decision": 2,
    "ambiguous": 3,
    "zero-candidate": 4,
    "below-threshold": 5,
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
    re-stamped while a descendant is unresolved). One shared extent pass constructs each eligible
    live payload once and hashes that same payload through the canonical producer. The **decision**
    digest is **carried from the old entry, never machine-refreshed** (re-bind-stable by D33).

    A malformed flat table falls back to the pre-optimization scalar path so its fail-loud error is
    byte-for-byte unchanged; validated production projections stay on the shared pass.
    """
    if evidence is None:
        return ()
    live_batch = _batch_live_extent_payloads(
        (entry.node_id for entry in evidence.entries),
        migrated_projection,
        included_node_ids=bound_node_ids,
    )
    if live_batch is None:
        return _restamp_evidence_scalar(evidence, migrated_projection, bound_node_ids)

    restamped: list[EvidenceEntry] = []
    for entry in evidence.entries:
        # Consume the private raw payload once: releasing it here prevents the batch's complete
        # payload set from overlapping the complete tuple of frozen EvidenceEntry witnesses.
        live = live_batch.by_node.pop(entry.node_id, None)
        if live is None:
            continue
        restamped.append(
            EvidenceEntry(
                node_id=entry.node_id,
                decision_digest=entry.decision_digest,  # carried, never machine-refreshed
                extent_digest=live.digest,  # mechanically re-stamped from this exact payload
                evidence=entry.evidence,
                authored_at_revision=entry.authored_at_revision,
                decision_payload=dict(entry.decision_payload),
                extent_payload=live.payload,
            )
        )
    return tuple(restamped)


def _restamp_evidence_scalar(
    evidence: AuthoringEvidence,
    migrated_projection: ProjectionMap,
    bound_node_ids: set[str],
) -> tuple[EvidenceEntry, ...]:
    """The established malformed-map fallback, kept verbatim for diagnostic compatibility."""
    restamped: list[EvidenceEntry] = []
    for entry in evidence.entries:
        node = migrated_projection.by_id.get(entry.node_id)
        if node is None or entry.node_id not in bound_node_ids:
            continue
        if not _subtree_ids(entry.node_id, migrated_projection).issubset(
            bound_node_ids
        ):
            continue
        restamped.append(
            EvidenceEntry(
                node_id=entry.node_id,
                decision_digest=entry.decision_digest,
                extent_digest=extent_digest(node, migrated_projection),
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

    Order: enumerate slots → anchored alignment + boundary confirmation → assemble the migrated map → the global
    ``validate_projection`` gate (all-bound only; a failure downgrades every tentative bind to
    ``global-conflict``) → the bottom-up extent re-stamp.
    """
    old_map = context.old_map
    telemetry = context.telemetry or NULL_REBIND_TELEMETRY
    with telemetry.span("rebind.enumerate-slots") as span:
        slots = _enumerate_slots(old_map, context.old_canonical)
        span.update(slot_count=len(slots), node_count=len(old_map.projection.nodes))
    assignment = _AnchoredAssignment(slots, context)

    # per-slot outcomes, grouped by node
    with telemetry.span("rebind.resolve-slots") as span:
        resolved_outcomes = assignment.resolve_all()
        assignment.publish_resolver_component_spans()
        slot_outcomes: dict[str, list[SlotOutcome]] = {
            node.node_id: [] for node in old_map.projection.nodes
        }
        for slot, outcome in zip(slots, resolved_outcomes, strict=True):
            slot_outcomes[slot.node_id].append(outcome)
        reasons = Counter(
            outcome.reason
            for outcome in resolved_outcomes
            if outcome.reason is not None
        )
        span.update(
            slot_count=len(slots),
            bound_slots=sum(outcome.bound for outcome in resolved_outcomes),
            resolved_boundaries=len(assignment._resolved),
            unresolved_reasons=dict(sorted(reasons.items())),
            fingerprint_evaluated_slots=(assignment.fingerprint_evaluated_slot_count),
            fresh_fingerprint_computations=(
                assignment.fresh_fingerprint_computation_count
            ),
            atom_boundary_lookup_calls=assignment._atom_boundary_lookup_calls,
            atom_boundary_inspected_ranges=(
                assignment._atom_boundary_inspected_ranges
            ),
            atom_boundary_lookup_outcomes=dict(
                sorted(assignment._atom_boundary_lookup_outcomes.items())
            ),
        )

    # per-node aggregation (a node with no atom-owning slots binds trivially — its identity is stable)
    with telemetry.span("rebind.aggregate-nodes") as span:
        node_outcomes: list[NodeOutcome] = []
        bound_node_ids: set[str] = set()
        for node in old_map.projection.nodes:
            outs = tuple(slot_outcomes[node.node_id])
            unresolved = [
                o.reason for o in outs if not o.bound and o.reason is not None
            ]
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
        span.update(node_count=len(node_outcomes), bound_nodes=len(bound_node_ids))

    with telemetry.span("rebind.migrate-projection") as span:
        migrated_doc = _build_migrated_doc(old_map, slot_outcomes)
        migrated_projection = structure_map_from_json(migrated_doc).projection
        span.update(node_count=len(migrated_projection.nodes))

    # global consistency — bound-SUBSET disjointness, ALWAYS (never gated on all-bound). Per-slot
    # resolution is independent, so two bound slots can each pick a "unique" ≥τ window that OVERLAPS
    # the other on repeated boundary content. A partial re-bind (some node unresolved) would otherwise
    # skip the whole-map gate and report the overlap as two clean binds — the R2 silent mis-bind. Any
    # fresh atom claimed by two bound nodes fails those nodes loud as global-conflict.
    with telemetry.span("rebind.validate-projection") as span:
        contested = _contested_nodes(node_outcomes)
        # Whole-map validation is meaningful only once every node is tentatively bound.
        all_bound = len(bound_node_ids) == len(old_map.projection.nodes)
        map_valid = not all_bound or _map_validates(migrated_projection, context)
        if not map_valid:
            contested = {n.node_id for n in node_outcomes}
        if contested:
            node_outcomes = [
                NodeOutcome(
                    node_id=n.node_id,
                    bound=False,
                    reason="global-conflict",
                    slots=n.slots,
                )
                if n.node_id in contested
                else n
                for n in node_outcomes
            ]
            bound_node_ids -= contested
        span.update(
            all_bound_before_validation=all_bound,
            map_valid=map_valid,
            contested_nodes=len(contested),
        )

    # stale-decision: a rebound topology whose decision digest drifted is a human-re-verify finding
    # (never a re-stamp). Removed from bound_node_ids BEFORE the re-stamp so a stale descendant blocks
    # its ancestor (the bottom-up gate).
    with telemetry.span("rebind.restamp-evidence") as span:
        stale_decisions = (
            _stale_decision_nodes(context.old_evidence, migrated_projection)
            & bound_node_ids
        )
        if stale_decisions:
            node_outcomes = [
                NodeOutcome(
                    node_id=n.node_id,
                    bound=False,
                    reason="stale-decision",
                    slots=n.slots,
                )
                if n.node_id in stale_decisions
                else n
                for n in node_outcomes
            ]
            bound_node_ids -= stale_decisions
        restamped = _restamp_evidence(
            context.old_evidence, migrated_projection, bound_node_ids
        )
        span.update(
            stale_decisions=len(stale_decisions), restamped_entries=len(restamped)
        )

    with telemetry.span("rebind.assemble-report") as span:
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
            alignment_backend=ALIGNMENT_BACKEND_ID,
            policy_identity=context.policy.identity,
        )
        span.update(
            bound_nodes=sum(node.bound for node in report.nodes),
            unresolved_nodes=len(report.unresolved),
        )
    return RebindResult(
        migrated_doc=migrated_doc, report=report, restamped_evidence=restamped
    )


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
    slot_key = {
        "heading": "heading_atoms",
        "signature": "signature_atoms",
        "body": "body_atoms",
    }
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
    if not result.report.consumable:
        raise RebindNotConsumableError()
