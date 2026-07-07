"""S2.1.6 — the human-review worklist + verdict application (``s2_1_plan.md`` DT-10; issue #40).

The segmentation front-end routes a page to a human when its own evidence is too weak to trust:
a density-abstain, an in-margin column verdict with disagreeing neighbours, a text-empty locate
window, or a sub-threshold match rate. DT-10 makes that routing a **specified gate, not a slogan**
(S2.0 audit Finding E): one record per routed page, a stable id, a signal/value/threshold triple,
a reproducibility ``input_fingerprint``, and the tentative auto-classification a reviewer confirms
or overrides.

The artifact split follows DT-10's durability rule — human labour never lives in a disposable
tree:

- **Generated, disposable** — the candidate worklist
  ``<work>/state/geometry_review/worklist_candidates.json`` (this module writes it; regenerable
  from the tracked verdicts + inputs, so gitignored ``work/`` is its right home).
- **Tracked, human-durable** — the verdicts ``books/<id>/review/geometry_verdicts.json`` (the
  verdict CLI writes it on the human's behalf; sibling of ``work/`` like ``inputs/`` and the
  density calibration, so a human decision survives a ``work/`` wipe — the corrections.json
  tombstone failure class from the live pipeline).

**Volume bound (P-6, RULED 2026-07-03):** ``review_fraction_max`` per stage, default
:data:`REVIEW_FRACTION_MAX_DEFAULT`. Exceeding it **hard-fails the run**
(:class:`~engine.structure.geometry.GeometryError`) — the automation premise failed, so the
classifier gets re-designed, never the bar lowered to drain the queue (G-13).

Pure core: witness ids, signals, thresholds, and the tentative payloads are all caller-supplied.
The one baked number is the ruled P-6 default, value-pin tested — the same posture as the P-5
tripwire constants in ``geom_sidecar``. The neutrality guard scans this module.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from engine.errors import EngineError, MissingInputError, StaleArtifactError
from engine.paths import BookWorkspace
from engine.structure.geom_sidecar import (
    PAGE_DECLINED,
    PAGE_ROUTED,
    GeomSidecar,
    PageRecord,
)
from engine.structure.geom_match import normalize_tokens
from engine.structure.geometry import GeometryError
from engine.structure.segmentation import ordered_coverage, reading_order
from engine.util.jsonio import atomic_write_json, read_json

#: Independent schema version of the worklist artifact (M3 posture: one artifact, one version).
WORKLIST_SCHEMA_VERSION = 1
#: The envelope discriminator — a load rejects a structurally-JSON file that is a different
#: persisted layer (the sidecar, the structure map, …). Beside its raiser, not in the governed
#: ``artifacts.py`` roster: the worklist is disposable, so this is a wrong-artifact guard, not a
#: migration route.
WORKLIST_STALE_CLASS = "geometry-worklist"

#: Workspace area/subdir the worklist lives under (``<work>/state/geometry_review/``) — an existing
#: ignored work area (R7), so nothing is added to ``paths._AREAS`` and containment is enforced.
WORKLIST_AREA = "state"
WORKLIST_SUBDIR = "geometry_review"
WORKLIST_FILENAME = "worklist_candidates.json"

#: The four front-end gates a page can route at, in pipeline order (which is also the deterministic
#: same-page emission order): the density pre-check (#38), the column detector (#39), the
#: page-locate window (empty-window, DT-10 enum extension), and the per-atom match rate (#37).
WORKLIST_STAGES = ("density", "columns", "locate", "match")

#: The volume bound per stage (P-6, RULED 2026-07-03; value-pin tested). The engine core refuses to
#: *default* it in :func:`build_worklist` — the runner passes the manifest value or reaches for this
#: named default — but the ruled number is recorded here so a silent drift re-opens the review
#: budget loudly rather than quietly.
REVIEW_FRACTION_MAX_DEFAULT = 0.15

# The witness id lands in a candidate-id prefix and (indirectly) the file path; a path-shaped id is
# rejected at the model, the same flat-stem discipline as the sidecar / atom store.
_WITNESS_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
#: ``{witness}:p{page:04d}:{stage}`` — the stable id (DT-10). ``page`` is ≥4 digits (zero-padded;
#: more only past 9999 pages), ``stage`` a lowercase word from :data:`WORKLIST_STAGES`.
_CANDIDATE_ID = re.compile(r"^(?P<witness>[A-Za-z0-9][A-Za-z0-9._-]*):p(?P<page>\d{4,}):(?P<stage>[a-z]+)$")


def _is_int(value) -> bool:
    return type(value) is int  # bool is an int subclass; True is not a page number or a count


def _is_finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _canonical_json(value):
    """Recursively key-sort every nested mapping (lists keep order — order is data there), so a
    payload serializes as a pure function of its *content*: the byte-stability the idempotent
    replay (G-22) asserts against."""
    if isinstance(value, Mapping):
        return {k: _canonical_json(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical_json(v) for v in value]
    return value


def _require(data: Mapping, key: str, ctx: str):
    if key not in data:
        raise StaleArtifactError(f"malformed geometry worklist {ctx}: missing required key {key!r}")
    return data[key]


def _reject_unknown_keys(data: Mapping, allowed: frozenset[str], ctx: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise StaleArtifactError(f"malformed geometry worklist {ctx}: unknown key(s) {unknown}")


# --- id + fingerprint --------------------------------------------------------------------------- #


def candidate_id(witness_id: str, page: int, stage: str) -> str:
    """The stable DT-10 candidate id ``{witness}:p{page:04d}:{stage}``."""
    if not (isinstance(witness_id, str) and _WITNESS_ID.fullmatch(witness_id)):
        raise ValueError(f"witness_id must be a flat stem matching {_WITNESS_ID.pattern!r}, got {witness_id!r}")
    if not (_is_int(page) and page > 0):
        raise ValueError(f"candidate id needs a positive scan page, got {page!r}")
    if stage not in WORKLIST_STAGES:
        raise ValueError(f"candidate id stage must be one of {WORKLIST_STAGES}, got {stage!r}")
    return f"{witness_id}:p{page:04d}:{stage}"


def input_fingerprint(
    *,
    stream_source_hash: str,
    source_scan_sha256: str,
    engine_id: str,
    classifier_version: str,
    policy_values: Mapping[str, object],
) -> str:
    """The reproducibility fingerprint over every input a routing/verdict depends on (DT-9/DT-10):
    the witness stream, the scan, the OCR engine, the density classifier version, and the ruled
    policy values (band edges + column thresholds + the review bound). A pure function of content —
    ``policy_values`` key order does not matter (canonicalized) — so a verdict taken under one set
    of inputs is *mechanically* refused against a different set (G-22's stale-guard)."""
    for name, value in (
        ("stream_source_hash", stream_source_hash),
        ("source_scan_sha256", source_scan_sha256),
        ("engine_id", engine_id),
        ("classifier_version", classifier_version),
    ):
        if not (isinstance(value, str) and value.strip()):
            raise ValueError(f"input_fingerprint {name} must be a non-empty string, got {value!r}")
    if not (isinstance(policy_values, Mapping) and policy_values):
        raise ValueError("input_fingerprint policy_values must be a non-empty mapping")
    payload = {
        "classifier_version": classifier_version,
        "engine_id": engine_id,
        "policy_values": _canonical_json(policy_values),
        "source_scan_sha256": source_scan_sha256,
        "stream_source_hash": stream_source_hash,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --- records ------------------------------------------------------------------------------------ #


@dataclass(frozen=True, slots=True)
class RouteInput:
    """One routed page as the front-end produces it (before it becomes a durable candidate): which
    gate fired (``stage``), the ``signal`` name, its ``value`` against the ``threshold``, and the
    ``tentative`` auto-classification a reviewer confirms or overrides (box/token counts for a
    density route, ``n_cols``/``split_x`` for a columns route, the match rate for a match route)."""

    page: int
    stage: str
    signal: str
    value: float
    threshold: float
    tentative: Mapping[str, object]

    def __post_init__(self) -> None:
        if not (_is_int(self.page) and self.page > 0):
            raise ValueError(f"RouteInput.page must be a positive scan page, got {self.page!r}")
        if self.stage not in WORKLIST_STAGES:
            raise ValueError(f"RouteInput.stage must be one of {WORKLIST_STAGES}, got {self.stage!r}")
        if not (isinstance(self.signal, str) and self.signal.strip()):
            raise ValueError("RouteInput.signal must name the routing signal")
        if not _is_finite(self.value):
            raise ValueError(f"RouteInput.value must be finite, got {self.value!r}")
        if not _is_finite(self.threshold):
            raise ValueError(f"RouteInput.threshold must be finite, got {self.threshold!r}")
        if not isinstance(self.tentative, Mapping):
            raise ValueError(f"RouteInput.tentative must be a mapping, got {type(self.tentative).__name__}")
        object.__setattr__(self, "tentative", dict(self.tentative))


@dataclass(frozen=True, slots=True)
class WorklistCandidate:
    """One routed page's durable worklist record (DT-10). ``id`` is the stable
    ``{witness}:p{page:04d}:{stage}`` and must agree with ``page``/``stage`` (a mismatch is a
    corrupt record, unconstructible). ``verdict`` is ``None`` until a human rules; ``history``
    retains any **superseded** verdict — a stale-refused one whose inputs drifted — as evidence
    rather than vanishing (G-22). (The tracked verdicts store is one verdict per id, so an *applied*
    verdict lives in ``verdict``; ``history`` holds the refused predecessors, not an applied log.)"""

    id: str
    page: int
    stage: str
    signal: str
    value: float
    threshold: float
    input_fingerprint: str
    tentative: Mapping[str, object]
    verdict: Mapping[str, object] | None = None
    history: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not (_is_int(self.page) and self.page > 0):
            raise ValueError(f"WorklistCandidate.page must be a positive scan page, got {self.page!r}")
        if self.stage not in WORKLIST_STAGES:
            raise ValueError(f"WorklistCandidate.stage must be one of {WORKLIST_STAGES}, got {self.stage!r}")
        if not (isinstance(self.signal, str) and self.signal.strip()):
            raise ValueError("WorklistCandidate.signal must name the routing signal")
        if not _is_finite(self.value):
            raise ValueError(f"WorklistCandidate.value must be finite, got {self.value!r}")
        if not _is_finite(self.threshold):
            raise ValueError(f"WorklistCandidate.threshold must be finite, got {self.threshold!r}")
        if not (isinstance(self.input_fingerprint, str) and self.input_fingerprint.strip()):
            raise ValueError("WorklistCandidate.input_fingerprint must be a non-empty fingerprint")
        if not isinstance(self.tentative, Mapping):
            raise ValueError(f"WorklistCandidate.tentative must be a mapping, got {type(self.tentative).__name__}")
        match = _CANDIDATE_ID.fullmatch(self.id) if isinstance(self.id, str) else None
        if not match or int(match["page"]) != self.page or match["stage"] != self.stage:
            raise ValueError(
                f"WorklistCandidate.id must be the {{witness}}:p{{page:04d}}:{{stage}} template agreeing "
                f"with page={self.page} stage={self.stage!r}, got {self.id!r}"
            )
        if self.verdict is not None and not (isinstance(self.verdict, Mapping) and self.verdict):
            raise ValueError("WorklistCandidate.verdict must be a non-empty mapping or None")
        if not isinstance(self.history, tuple) or not all(isinstance(h, Mapping) for h in self.history):
            raise ValueError("WorklistCandidate.history must be a tuple of verdict mappings")
        object.__setattr__(self, "tentative", dict(self.tentative))
        if self.verdict is not None:
            object.__setattr__(self, "verdict", dict(self.verdict))
        object.__setattr__(self, "history", tuple(dict(h) for h in self.history))


@dataclass(frozen=True, slots=True)
class Worklist:
    """The whole candidate worklist for a witness (DT-10): the schema envelope plus the ordered
    candidates. ``review_fraction_max`` is recorded so the artifact carries the budget it was built
    under."""

    witness_id: str
    review_fraction_max: float
    candidates: tuple[WorklistCandidate, ...]
    schema_version: int = WORKLIST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not (isinstance(self.witness_id, str) and _WITNESS_ID.fullmatch(self.witness_id)):
            raise ValueError(f"Worklist.witness_id must be a flat stem, got {self.witness_id!r}")
        if not (_is_finite(self.review_fraction_max) and 0.0 < self.review_fraction_max <= 1.0):
            raise ValueError(f"Worklist.review_fraction_max must be in (0, 1], got {self.review_fraction_max!r}")
        if not (isinstance(self.candidates, tuple) and all(isinstance(c, WorklistCandidate) for c in self.candidates)):
            raise ValueError("Worklist.candidates must be a tuple of WorklistCandidate")
        if self.schema_version != WORKLIST_SCHEMA_VERSION:
            raise ValueError(f"Worklist.schema_version must be {WORKLIST_SCHEMA_VERSION}, got {self.schema_version!r}")


# --- volume bound (G-13) ------------------------------------------------------------------------ #


def assert_review_within_bound(
    routes: Sequence[RouteInput], *, n_pages: int, review_fraction_max: float
) -> dict[str, float]:
    """Hard-fail if any **stage's** routed fraction exceeds ``review_fraction_max`` (P-6/G-13).

    The bound is *per stage* (not aggregate): a single gate flooding the queue is the automation
    failure worth catching, and one noisy stage must not be masked by three quiet ones. Denominator
    is the whole book (``n_pages``) — the fraction of the book each gate sends to review. Boundary
    is inclusive (``>`` not ``>=``): a fraction exactly at the bound is tolerated. Returns the
    per-stage fractions for the run report. A trip means re-design the classifier — never lower the
    bar to drain the queue.
    """
    if not (_is_int(n_pages) and n_pages > 0):
        raise ValueError(f"n_pages must be a positive page count, got {n_pages!r}")
    if not (_is_finite(review_fraction_max) and 0.0 < review_fraction_max <= 1.0):
        raise ValueError(f"review_fraction_max must be in (0, 1], got {review_fraction_max!r}")
    counts = {stage: 0 for stage in WORKLIST_STAGES}
    for r in routes:
        counts[r.stage] += 1
    fractions = {stage: counts[stage] / n_pages for stage in WORKLIST_STAGES}
    for stage in WORKLIST_STAGES:  # deterministic first-failure in pipeline order
        fraction = fractions[stage]
        if fraction > review_fraction_max:
            raise GeometryError(
                f"review volume bound breached at the {stage!r} stage: {counts[stage]}/{n_pages} = "
                f"{fraction:.4f} of pages routed (> {review_fraction_max}) — the automation premise "
                f"failed. Re-design the classifier; never lower the bar to drain the queue (P-6/G-13)"
            )
    return fractions


# --- build -------------------------------------------------------------------------------------- #


def build_worklist(
    routes: Sequence[RouteInput],
    *,
    witness_id: str,
    n_pages: int,
    review_fraction_max: float,
    fingerprint: str,
) -> Worklist:
    """Turn the front-end's routed pages into the durable candidate worklist (DT-10).

    Enforces the volume bound first (G-13) — an over-quota run never produces a worklist. Candidate
    emission order is a pure function of ``(page, stage-in-pipeline-order)``, independent of the
    order ``routes`` arrives in, so the artifact is byte-stable across runs (G-22). ``fingerprint``
    is the single :func:`input_fingerprint` for this run — every candidate carries it, so a later
    verdict binds to the exact inputs its routing was computed under.
    """
    seen: set[tuple[int, str]] = set()
    for r in routes:
        key = (r.page, r.stage)
        if key in seen:
            # The candidate id is (page, stage)-derived and is the verdicts-dict key; a duplicate
            # would collide ids and make emission order input-dependent (a stable sort preserves
            # input order on a tie). A front-end emitting one gate twice for a page is malformed.
            raise ValueError(
                f"duplicate route for page {r.page} at stage {r.stage!r} — one candidate per "
                f"(page, stage); the front-end must not route a page through the same gate twice"
            )
        seen.add(key)
    assert_review_within_bound(routes, n_pages=n_pages, review_fraction_max=review_fraction_max)
    if not (isinstance(fingerprint, str) and fingerprint.strip()):
        raise ValueError("build_worklist fingerprint must be the run's non-empty input_fingerprint")
    ordered = sorted(routes, key=lambda r: (r.page, WORKLIST_STAGES.index(r.stage)))
    candidates = tuple(
        WorklistCandidate(
            id=candidate_id(witness_id, r.page, r.stage),
            page=r.page,
            stage=r.stage,
            signal=r.signal,
            value=r.value,
            threshold=r.threshold,
            input_fingerprint=fingerprint,
            tentative=r.tentative,
        )
        for r in ordered
    )
    return Worklist(witness_id=witness_id, review_fraction_max=review_fraction_max, candidates=candidates)


# --- serialization (envelope ⇄ Worklist) -------------------------------------------------------- #


_ENVELOPE_KEYS = frozenset(
    {"schema_version", "stale_class", "witness_id", "review_fraction_max", "candidates"}
)
_CANDIDATE_KEYS = frozenset(
    {"id", "page", "stage", "signal", "value", "threshold", "input_fingerprint", "tentative", "verdict", "history"}
)


def _candidate_to_json(candidate: WorklistCandidate) -> dict:
    return {
        "id": candidate.id,
        "page": candidate.page,
        "stage": candidate.stage,
        "signal": candidate.signal,
        "value": candidate.value,
        "threshold": candidate.threshold,
        "input_fingerprint": candidate.input_fingerprint,
        "tentative": _canonical_json(candidate.tentative),
        "verdict": _canonical_json(candidate.verdict) if candidate.verdict is not None else None,
        "history": [_canonical_json(h) for h in candidate.history],
    }


def _candidate_from_json(data: Mapping) -> WorklistCandidate:
    if not isinstance(data, Mapping):
        raise StaleArtifactError(f"worklist candidate must be a JSON object, got {type(data).__name__}")
    _reject_unknown_keys(data, _CANDIDATE_KEYS, "candidate")
    history = data.get("history", [])
    if not isinstance(history, list):
        raise StaleArtifactError(f"candidate history must be a JSON array, got {type(history).__name__}")
    return WorklistCandidate(
        id=_require(data, "id", "candidate"),
        page=_require(data, "page", "candidate"),
        stage=_require(data, "stage", "candidate"),
        signal=_require(data, "signal", "candidate"),
        value=_require(data, "value", "candidate"),
        threshold=_require(data, "threshold", "candidate"),
        input_fingerprint=_require(data, "input_fingerprint", "candidate"),
        tentative=_require(data, "tentative", "candidate"),
        verdict=data.get("verdict"),
        history=tuple(history),
    )


def worklist_to_json(worklist: Worklist) -> dict:
    """The persisted envelope, a pure function of content: candidates keep their build order (order
    is data — DT-10's page/stage order), every nested payload key-sorted via ``_canonical_json``."""
    return {
        "schema_version": worklist.schema_version,
        "stale_class": WORKLIST_STALE_CLASS,
        "witness_id": worklist.witness_id,
        "review_fraction_max": worklist.review_fraction_max,
        "candidates": [_candidate_to_json(c) for c in worklist.candidates],
    }


def worklist_from_json(data: Mapping) -> Worklist:
    """Parse + validate a persisted worklist, or fail loud (G-18 totality): a valid
    :class:`Worklist` or :class:`~engine.errors.StaleArtifactError`, never a bare traceback."""
    if not isinstance(data, Mapping):
        raise StaleArtifactError(f"geometry-worklist envelope must be a JSON object, got {type(data).__name__}")
    version = _require(data, "schema_version", "envelope")
    if version != WORKLIST_SCHEMA_VERSION:
        raise StaleArtifactError(
            f"geometry-worklist schema version {version!r} != current {WORKLIST_SCHEMA_VERSION!r} "
            f"(stale class {WORKLIST_STALE_CLASS!r}) — regenerate the worklist"
        )
    stale_class = _require(data, "stale_class", "envelope")
    if stale_class != WORKLIST_STALE_CLASS:
        raise StaleArtifactError(
            f"stale_class {stale_class!r} != {WORKLIST_STALE_CLASS!r} — not a geometry worklist "
            f"(a different persisted layer, or a malformed file)"
        )
    _reject_unknown_keys(data, _ENVELOPE_KEYS, "envelope")
    raw = _require(data, "candidates", "envelope")
    if not isinstance(raw, list):
        raise StaleArtifactError(f"candidates must be a JSON array, got {type(raw).__name__}")
    try:
        return Worklist(
            witness_id=_require(data, "witness_id", "envelope"),
            review_fraction_max=_require(data, "review_fraction_max", "envelope"),
            candidates=tuple(_candidate_from_json(c) for c in raw),
            schema_version=version,
        )
    except StaleArtifactError:
        raise
    except (ValueError, TypeError) as exc:
        raise StaleArtifactError(f"malformed geometry worklist: {exc}") from exc


# --- persistence (atomic JSON under state/geometry_review/) ------------------------------------- #


def worklist_path(workspace: BookWorkspace) -> Path:
    """The containment-checked path to ``<work>/state/geometry_review/worklist_candidates.json``.
    One file per book — candidates namespace by witness in their ids (DT-10)."""
    return workspace.resolve(WORKLIST_AREA, WORKLIST_SUBDIR, WORKLIST_FILENAME)


def save_worklist(workspace: BookWorkspace, worklist: Worklist) -> Path:
    """Persist ``worklist`` atomically; return the path. Disposable by convention — the tracked
    verdicts + inputs regenerate it, so there is no clobber guard (unlike the sidecar's scan
    identity): a stale worklist is simply overwritten by the next run."""
    path = worklist_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, worklist_to_json(worklist))
    return path


def load_worklist(workspace: BookWorkspace) -> Worklist:
    """Read + validate the worklist, or fail loud (G-18): absent →
    :class:`~engine.errors.MissingInputError`; non-JSON / stale / malformed →
    :class:`~engine.errors.StaleArtifactError`."""
    path = worklist_path(workspace)
    if not path.is_file():
        raise MissingInputError(f"geometry worklist not found at {path}")
    try:
        data = read_json(path)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError, RecursionError) as exc:
        raise StaleArtifactError(f"geometry worklist at {path} is unloadable: {exc}") from exc
    return worklist_from_json(data)


# --- order_qa: the S2.2 measurement feed (DT-12) ------------------------------------------------ #


def page_order_qa(witness_window: Sequence[str], boxes: Sequence, split_x: float | None) -> float:
    """One page's ``order_qa`` — the ordered coverage of the detector's reading order against the
    witness window (DT-12; the S2.2 re-gate feed).

    ``witness_window`` is the page's copy1 tokens in reading order (already normalized). The boxes
    are ordered by :func:`~engine.structure.segmentation.reading_order` under the detected column
    split, then each box's text is put through the same :func:`~engine.structure.geom_match.normalize_tokens`
    the witness went through — so the comparison is order-only, in one token space. ``1.0`` iff the
    detector recovers the witness's token order; a column-interleaved order scores below ``1.0``.
    """
    ordered_texts = reading_order(boxes, split_x=split_x)
    detector_tokens = [tok for text in ordered_texts for tok in normalize_tokens(text)]
    return ordered_coverage(list(witness_window), detector_tokens)


# --- verdicts: the human ruling on a routed page (DT-10) ---------------------------------------- #

#: The four verdict actions a human can rule (DT-10). ``decline_geometry`` is the only page-level
#: route to ``Geom.absent`` (besides a zero-match atom on an accepted page); the other three send
#: the page back through the front-end with the human's parameters, its result marked
#: human-reviewed.
ACTION_CONFIRM = "confirm"
ACTION_REDRAW_SPLIT = "redraw_split"
ACTION_RECLASSIFY = "reclassify"
ACTION_DECLINE_GEOMETRY = "decline_geometry"
VERDICT_ACTIONS = (ACTION_CONFIRM, ACTION_REDRAW_SPLIT, ACTION_RECLASSIFY, ACTION_DECLINE_GEOMETRY)
_REENTER_ACTIONS = (ACTION_CONFIRM, ACTION_REDRAW_SPLIT, ACTION_RECLASSIFY)

#: The two semantic outcomes an applied verdict resolves to (G-14): a decline writes the page's
#: geometry absent; the re-entry actions send the page back through the pipeline with human params.
OUTCOME_DECLINED = "declined"
OUTCOME_REENTERED = "reentered"

VERDICTS_SCHEMA_VERSION = 1
VERDICTS_STALE_CLASS = "geometry-verdicts"
_VERDICTS_ENVELOPE_KEYS = frozenset({"schema_version", "stale_class", "verdicts"})
VERDICTS_SUBDIR = "review"  # book-level, TRACKED (sibling of work/) — human labour is durable
VERDICTS_FILENAME = "geometry_verdicts.json"


def verdict_outcome(verdict: Mapping) -> str:
    """The total DT-10 verdict→outcome map (G-14): ``decline_geometry`` → :data:`OUTCOME_DECLINED`,
    the three re-entry actions → :data:`OUTCOME_REENTERED`, **anything else → fail loud**
    (:class:`~engine.structure.geometry.GeometryError`). Refusing to guess which gate outcome an
    unknown action means is the whole point — a silent "treat unknown as confirm" would let a
    typo confirm geometry a human never approved."""
    action = verdict.get("action") if isinstance(verdict, Mapping) else None
    if action == ACTION_DECLINE_GEOMETRY:
        return OUTCOME_DECLINED
    if action in _REENTER_ACTIONS:
        return OUTCOME_REENTERED
    raise GeometryError(
        f"unknown verdict action {action!r} — must be one of {VERDICT_ACTIONS}; refusing to guess "
        f"which gate outcome to apply (G-14)"
    )


def validate_verdict(verdict: Mapping) -> None:
    """A live verdict is well-formed: a known action (via :func:`verdict_outcome`) plus the
    provenance a durable human decision must carry — ``by`` (who), ``at`` (when), and
    ``input_fingerprint`` (the inputs it was ruled against, so G-22 can detect drift). Malformed →
    fail loud (:class:`~engine.structure.geometry.GeometryError`)."""
    if not isinstance(verdict, Mapping):
        raise GeometryError(f"verdict must be a mapping, got {type(verdict).__name__}")
    verdict_outcome(verdict)  # unknown/missing action fails loud here
    for name in ("by", "at", "input_fingerprint"):
        value = verdict.get(name)
        if not (isinstance(value, str) and value.strip()):
            raise GeometryError(f"verdict missing provenance: {name!r} must be a non-empty string, got {value!r}")
    params = verdict.get("params", {})
    if not isinstance(params, Mapping):
        raise GeometryError(f"verdict params must be a mapping, got {type(params).__name__}")


def apply_verdicts(
    worklist: Worklist, verdicts: Mapping[str, Mapping]
) -> tuple[Worklist, dict[str, int]]:
    """Project the tracked ``verdicts`` onto ``worklist`` (DT-10; G-22).

    A **pure projection from base**: every candidate is reset to its open state (``verdict=None``,
    ``history=()``) before a verdict is applied, so applying twice — or applying to an
    already-applied worklist — is byte-identical (idempotent, G-22). For each candidate:

    - no verdict for its id → stays open;
    - a verdict whose ``input_fingerprint`` matches the candidate's → **applied** (its
      ``verdict`` set); ``verdict_outcome`` classifies it (declined / reentered) for the stats, and
      an unknown action fails loud (G-14);
    - a verdict whose fingerprint **differs** → **refused** (the inputs drifted under it): the
      candidate re-routes as a fresh open record and the stale verdict is retained in ``history`` as
      evidence, never silently re-applied to different inputs (the D14/D21 stale posture at the human
      boundary).

    A verdict whose id is in no candidate is **orphaned** — reported in the stats (never silently
    dropped), never fabricating a candidate. Returns the projected worklist + a stats dict.
    """
    if not isinstance(verdicts, Mapping):
        raise ValueError(f"verdicts must be a mapping of id → verdict, got {type(verdicts).__name__}")
    ids = {c.id for c in worklist.candidates}
    stats = {"applied": 0, "open": 0, "stale": 0, "orphaned": 0, OUTCOME_DECLINED: 0, OUTCOME_REENTERED: 0}
    new_candidates: list[WorklistCandidate] = []
    for candidate in worklist.candidates:
        base = replace(candidate, verdict=None, history=())  # project from base → idempotent
        found = verdicts.get(candidate.id)
        if found is None:
            new_candidates.append(base)
            stats["open"] += 1
            continue
        validate_verdict(found)  # unknown action / missing provenance fails loud (G-14)
        if found.get("input_fingerprint") != candidate.input_fingerprint:
            new_candidates.append(replace(base, verdict=None, history=(dict(found),)))
            stats["stale"] += 1
            continue
        new_candidates.append(replace(base, verdict=dict(found)))
        stats["applied"] += 1
        stats[verdict_outcome(found)] += 1
    for vid in verdicts:
        if vid not in ids:
            stats["orphaned"] += 1
    return replace(worklist, candidates=tuple(new_candidates)), stats


def apply_declines_to_sidecar(sidecar: GeomSidecar, worklist: Worklist) -> GeomSidecar:
    """Effect the **page-level** decline→absent transition on the sidecar (G-14): every applied
    ``decline_geometry`` verdict turns its routed page record into a ``declined`` one carrying the
    human verdict — the page's atoms, already pending (absent from the atoms map), are now
    human-declined. The re-entry actions (confirm / redraw_split / reclassify) are NOT effected here
    — they send the page back through the front-end with human params, which the runner re-runs;
    this function only writes the one outcome the sidecar can carry without re-matching.

    A decline on a page that is not ``routed`` is an inconsistency (you decline a page in review),
    and fails loud."""
    # Keyed by page (decline is a page-level action); iterate in a stable (page, stage) order so a
    # page declined at two gates resolves deterministically to one declined record, never
    # input-order-dependent.
    declines = {
        c.page: c.verdict
        for c in sorted(worklist.candidates, key=lambda c: (c.page, c.stage))
        if c.verdict is not None and c.verdict.get("action") == ACTION_DECLINE_GEOMETRY
    }
    if not declines:
        return sidecar
    new_pages = dict(sidecar.pages)
    for page, verdict in declines.items():
        existing = new_pages.get(page)
        if existing is None or existing.status != PAGE_ROUTED:
            status = existing.status if existing is not None else "absent"
            raise GeometryError(
                f"cannot decline geometry for page {page}: its sidecar record is {status!r}, not "
                f"{PAGE_ROUTED!r} — only a routed page (one actually in review) can be declined"
            )
        new_pages[page] = PageRecord(status=PAGE_DECLINED, verdict=verdict)
    return replace(sidecar, pages=new_pages)


# --- verdicts persistence (tracked, book-level review/) ----------------------------------------- #


def verdicts_path(book_dir) -> Path:
    """The TRACKED verdicts file ``books/<id>/review/geometry_verdicts.json`` — a sibling of
    ``work/`` (like ``inputs/`` and the density calibration), so a human decision survives a
    ``work/`` wipe. Outside the step write-containment contract by design (DT-10, the authoring-tool
    family)."""
    return Path(book_dir) / VERDICTS_SUBDIR / VERDICTS_FILENAME


def verdicts_to_json(verdicts: Mapping[str, Mapping]) -> dict:
    return {
        "schema_version": VERDICTS_SCHEMA_VERSION,
        "stale_class": VERDICTS_STALE_CLASS,
        "verdicts": {vid: _canonical_json(v) for vid, v in sorted(verdicts.items())},
    }


def verdicts_from_json(data: Mapping) -> dict[str, dict]:
    """Parse + validate the persisted verdicts, or fail loud (G-18). Structural totality only — a
    verdict's *action* is validated at apply time (:func:`validate_verdict`), so a book can carry a
    verdict for a since-retired action without the file failing to load."""
    if not isinstance(data, Mapping):
        raise StaleArtifactError(f"geometry-verdicts envelope must be a JSON object, got {type(data).__name__}")
    version = _require(data, "schema_version", "verdicts envelope")
    if version != VERDICTS_SCHEMA_VERSION:
        raise StaleArtifactError(
            f"geometry-verdicts schema version {version!r} != current {VERDICTS_SCHEMA_VERSION!r} — "
            f"regenerate/migrate the verdicts file"
        )
    stale_class = _require(data, "stale_class", "verdicts envelope")
    if stale_class != VERDICTS_STALE_CLASS:
        raise StaleArtifactError(
            f"stale_class {stale_class!r} != {VERDICTS_STALE_CLASS!r} — not a geometry-verdicts file"
        )
    _reject_unknown_keys(data, _VERDICTS_ENVELOPE_KEYS, "verdicts envelope")
    raw = _require(data, "verdicts", "verdicts envelope")
    if not isinstance(raw, Mapping):
        raise StaleArtifactError(f"verdicts must be a JSON object, got {type(raw).__name__}")
    out: dict[str, dict] = {}
    for vid, value in raw.items():
        if not isinstance(value, Mapping):
            raise StaleArtifactError(f"verdict {vid!r} must be a JSON object, got {type(value).__name__}")
        out[vid] = dict(value)
    return out


def save_verdicts(book_dir, verdicts: Mapping[str, Mapping]) -> Path:
    """Persist the verdicts atomically to the tracked ``review/`` file; return the path."""
    path = verdicts_path(book_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, verdicts_to_json(verdicts))
    return path


def load_verdicts(book_dir) -> dict[str, dict]:
    """Read the tracked verdicts, or ``{}`` when the file is absent — an unruled book is the normal
    fresh state (a clean no-op apply), NOT a :class:`~engine.errors.MissingInputError`. A present
    but unloadable/stale/malformed file still fails loud (:class:`~engine.errors.StaleArtifactError`,
    G-18)."""
    path = verdicts_path(book_dir)
    if not path.is_file():
        return {}
    try:
        data = read_json(path)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError, RecursionError) as exc:
        raise StaleArtifactError(f"geometry verdicts at {path} is unloadable: {exc}") from exc
    return verdicts_from_json(data)


def record_verdict(book_dir, candidate_id: str, *, action: str, by: str, params=None, at=None) -> Path:
    """Stamp one human verdict into the tracked verdicts file (the CLI's write path). Reads the
    current worklist to bind the verdict to that candidate's ``input_fingerprint`` (so a later
    inputs change makes it stale, G-22), validates the action (unknown → fail loud), and writes
    atomically. Returns the verdicts path."""
    book_dir = Path(book_dir)
    workspace = BookWorkspace.for_book(book_dir.name, book_dir.parent)
    worklist = load_worklist(workspace)
    candidate = next((c for c in worklist.candidates if c.id == candidate_id), None)
    if candidate is None:
        raise GeometryError(
            f"no worklist candidate {candidate_id!r} to rule on — the page is not in review (or the "
            f"worklist is stale; regenerate it)"
        )
    stamp = at if at is not None else datetime.datetime.now(datetime.timezone.utc).isoformat()
    verdict = {
        "action": action,
        "by": by,
        "at": stamp,
        "params": dict(params) if params else {},
        "input_fingerprint": candidate.input_fingerprint,
    }
    validate_verdict(verdict)  # unknown action / bad provenance fails loud before we persist
    verdicts = load_verdicts(book_dir)
    verdicts[candidate_id] = verdict
    return save_verdicts(book_dir, verdicts)


# --- on-demand overlay renders (DT-10) ---------------------------------------------------------- #

OVERLAY_AREA = "output"
OVERLAY_SUBDIR = "geometry_review"
OVERLAY_OVERLAYS = "overlays"


def overlay_path(workspace: BookWorkspace, page: int, stage: str) -> Path:
    """The containment-checked path to a candidate's review overlay
    ``<work>/output/geometry_review/overlays/page_NNNN_{stage}.png`` (disposable, gitignored). Keyed
    by **(page, stage)**, not page alone: a page routed at two gates (e.g. ``columns`` + ``match``)
    has two candidates whose overlays differ (only the columns one carries the split + ruler), so a
    page-keyed file would let one overwrite the other (#46 audit M1)."""
    if not (isinstance(page, int) and not isinstance(page, bool) and page > 0):
        raise ValueError(f"overlay page must be a positive scan page, got {page!r}")
    if stage not in WORKLIST_STAGES:
        raise ValueError(f"overlay stage must be one of {WORKLIST_STAGES}, got {stage!r}")
    return workspace.resolve(OVERLAY_AREA, OVERLAY_SUBDIR, OVERLAY_OVERLAYS, f"page_{page:04d}_{stage}.png")


#: Ruler tick spacing (page points) — a light grid along the top edge so a reviewer can read an
#: x-coordinate off a column overlay for ``redraw_split=<x>`` (#46).
_RULER_TICK_PTS = 50


def render_overlay(
    *,
    width: float,
    height: float,
    boxes: Sequence,
    split_x: float | None,
    out_path: Path,
    background=None,
    dpi: int = 150,
    ruler: bool = False,
) -> Path:
    """Render a review overlay for one routed page: the tentative boxes (red outlines) and the
    column split (blue line) drawn in the page's point space, over the optional scan ``background``
    pixmap. On-demand — a reviewer renders the pages they are working, not the whole book. ``boxes``
    are objects with a ``bbox`` 4-tuple or bare ``(x0, y0, x1, y1)`` tuples (point space, DT-4).
    ``ruler`` draws a labelled pixel ruler along the top edge so ``redraw_split=<x>`` can be read
    straight off a column overlay.

    fitz is imported lazily so the CLI's apply/status paths (which never render) stay light."""
    if not (math.isfinite(width) and width > 0.0 and math.isfinite(height) and height > 0.0):
        raise ValueError(f"overlay page dimensions must be positive, got width={width!r} height={height!r}")
    import fitz  # PyMuPDF — lazy; only rendering needs it (the probe's pattern)

    doc = fitz.open()
    try:
        page = doc.new_page(width=width, height=height)
        if background is not None:
            page.insert_image(page.rect, pixmap=background)
        for box in boxes:
            bbox = box.bbox if hasattr(box, "bbox") else box
            page.draw_rect(fitz.Rect(*bbox), color=(0.85, 0.1, 0.1), width=0.7)
        if split_x is not None:
            page.draw_line(fitz.Point(split_x, 0.0), fitz.Point(split_x, height), color=(0.1, 0.1, 0.85), width=1.5)
        if ruler:
            for x in range(_RULER_TICK_PTS, int(width), _RULER_TICK_PTS):
                page.draw_line(fitz.Point(x, 0.0), fitz.Point(x, 12.0), color=(0.1, 0.55, 0.1), width=0.5)
                page.insert_text(fitz.Point(x + 1.0, 20.0), str(x), fontsize=6, color=(0.1, 0.55, 0.1))
        pixmap = page.get_pixmap(dpi=dpi)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pixmap.save(out_path)
    finally:
        doc.close()
    return out_path


# --- read-only review sheet + walk mode (#46, DT-10 read-side) ---------------------------------- #

#: The verbs the sheet/walk pre-fills per stage — the reviewer's *plausible* moves, a strict subset
#: of :data:`VERDICT_ACTIONS` (so an unknown verb is unemittable; the command-binding green).
#: ``redraw_split`` is offered only where there is a split to redraw (the ``columns`` stage).
_PLAUSIBLE_VERBS: dict[str, tuple[str, ...]] = {
    "density": (ACTION_CONFIRM, ACTION_RECLASSIFY, ACTION_DECLINE_GEOMETRY),
    "columns": (ACTION_CONFIRM, ACTION_REDRAW_SPLIT, ACTION_RECLASSIFY, ACTION_DECLINE_GEOMETRY),
    "locate": (ACTION_CONFIRM, ACTION_DECLINE_GEOMETRY),
    "match": (ACTION_CONFIRM, ACTION_RECLASSIFY, ACTION_DECLINE_GEOMETRY),
}
assert set(_PLAUSIBLE_VERBS) == set(WORKLIST_STAGES), "every worklist stage needs a plausible-verb set"

#: Per-stage human framing for the sheet — a short badge naming the check, and the plain-language
#: question the reviewer answers by looking at the scan. The stages ask genuinely different things
#: (locate = "is this a real page?"; match = "is the attached word-geometry sound?"), so the sheet
#: frames the decision per stage rather than dumping the same telemetry on each.
_STAGE_COPY: dict[str, tuple[str, str]] = {
    "locate": (
        "Real-page check",
        "This scan leaf has no text mapped to it. Decide, from the scan, whether it is a genuinely "
        "blank leaf — a cover, plate, divider, or empty page — or a real page whose text was missed.",
    ),
    "match": (
        "Geometry check",
        "The text mapped to this page, but its words attached to the scan's OCR word-boxes weakly. "
        "Decide, from the scan, whether the word-geometry is sound to keep or the page should be dropped.",
    ),
    "density": (
        "Blank-page check",
        "This page reads as near-blank by ink coverage. Decide whether it is real content or an empty "
        "/ bleed-through leaf whose boxes are noise.",
    ),
    "columns": (
        "Column check",
        "The column layout is ambiguous. Decide whether the page is one column or two, and where the "
        "divider falls — read the split off the pixel ruler on the scan.",
    ),
}

#: Plain-language meaning of each verdict verb (what it DOES to the page), shown beside its
#: copy-paste command. The command still carries the raw DT-10 action (command-binding green).
_VERB_LABEL: dict[str, str] = {
    ACTION_CONFIRM: "Keep — accept this page's geometry as sound (re-runs, marked human-reviewed)",
    ACTION_DECLINE_GEOMETRY: "Drop — no trustworthy geometry here; mark the page's atoms absent",
    ACTION_REDRAW_SPLIT: "Fix the split — supply the correct column divider (split_x, read off the ruler)",
    ACTION_RECLASSIFY: "Reclassify — re-run the page with a corrected classification",
}
assert set(_VERB_LABEL) == set(VERDICT_ACTIONS), "every verdict action needs a human label"

REVIEW_SHEET_FILENAME = "review_sheet.html"

_SHEET_HEAD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Geometry review</title><style>
:root{--paper:#f4f2ee;--card:#fff;--ink:#232020;--muted:#6f6860;--line:#e0dcd4;--accent:#3a4a7a;
  --keep:#2f7d4f;--drop:#b23b3b;--fix:#b8791f;
  --b-locate:#7a5a3a;--b-match:#3a4a7a;--b-density:#5a6a3a;--b-columns:#6a3a6a}
*{box-sizing:border-box}
body{font:15px/1.55 system-ui,-apple-system,sans-serif;margin:0;color:var(--ink);background:var(--paper)}
.wrap{max-width:1200px;margin:0 auto;padding:0 1.5rem 2rem}
header{border-bottom:2px solid var(--line);padding:1rem 0 .8rem;margin-bottom:1.2rem}
header h1{font-size:1.15rem;margin:0 0 .3rem;text-wrap:balance}
header p{margin:.2rem 0;max-width:66ch}
header details{margin:.4rem 0}
table.ladder{border-collapse:collapse;margin:.4rem 0;font-size:.82rem;font-variant-numeric:tabular-nums}
table.ladder td,table.ladder th{border:1px solid var(--line);padding:.1rem .55rem;text-align:right}
details summary{cursor:pointer;color:var(--accent)}
.entry{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:1.3rem;background:var(--card);
  border:1px solid var(--line);border-radius:10px;padding:1rem;margin:0 0 1.3rem;box-shadow:0 1px 3px rgba(0,0,0,.04)}
.scan{align-self:start;position:sticky;top:1rem}
.scan img{width:100%;max-height:82vh;object-fit:contain;border:1px solid var(--line);border-radius:6px;background:#fbfaf8}
.adjudicate{min-width:0}
.ehead{display:flex;align-items:center;gap:.6rem;margin-bottom:.7rem}
.pageno{font-weight:700;font-size:1.15rem}
.cid{font-family:ui-monospace,Menlo,monospace;font-size:.72rem;color:var(--muted);margin-left:auto}
.badge{font-size:.68rem;letter-spacing:.05em;text-transform:uppercase;font-weight:700;color:#fff;padding:.18rem .55rem;border-radius:20px}
.b-locate{background:var(--b-locate)}.b-match{background:var(--b-match)}
.b-density{background:var(--b-density)}.b-columns{background:var(--b-columns)}
.deciding,.why{margin:.4rem 0}
.deciding{font-size:1.03rem}
.lbl{display:block;font-size:.68rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:700;margin-bottom:.1rem}
.support{border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:.55rem 0;margin:.8rem 0;font-size:.9rem;color:var(--muted)}
.support strong{color:var(--ink)}
.den{margin:0}.den strong{font-size:1.05em}
.chips{display:flex;flex-wrap:wrap;gap:.25rem;margin:.4rem 0 0}
.chip{background:#f6ecec;border:1px solid #d8b0b0;border-radius:3px;padding:.05rem .4rem;font-family:ui-monospace,Menlo,monospace;font-size:.82em;color:#7a3838}
.pos{margin:.4rem 0 0}.dz-flag{color:var(--drop);font-weight:700}
ul.cmds{list-style:none;padding:0;margin:.7rem 0 0;display:flex;flex-direction:column;gap:.55rem}
.act{border-left:3px solid var(--line);padding-left:.65rem}
.act-confirm{border-left-color:var(--keep)}.act-decline_geometry{border-left-color:var(--drop)}
.act-redraw_split,.act-reclassify{border-left-color:var(--fix)}
.vlabel{display:block;font-size:.87rem;margin-bottom:.18rem;font-weight:600}
.act-confirm .vlabel{color:var(--keep)}.act-decline_geometry .vlabel{color:var(--drop)}
.act-redraw_split .vlabel,.act-reclassify .vlabel{color:var(--fix)}
ul.cmds code{display:block;background:#f3f1ec;padding:.32rem .5rem;border-radius:4px;font-family:ui-monospace,Menlo,monospace;font-size:.77rem;overflow-x:auto;color:#555}
@media (max-width:820px){.entry{grid-template-columns:1fr}.scan{position:static}}
@media (prefers-color-scheme:dark){
  :root{--paper:#1a1816;--card:#232020;--ink:#eae6e0;--muted:#a89e92;--line:#3a352f;--accent:#8a9ad0}
  .scan img{background:#2a2622}
  .chip{background:#3a2828;border-color:#6a4444;color:#e0a0a0}
  ul.cmds code{background:#2a2622;color:#c8c0b4}
}
</style></head><body><div class="wrap">"""
_SHEET_FOOT = "</div></body></html>"


def _esc(value: object) -> str:
    """Minimal HTML-text escape — the sheet is offline and its inputs are ids/tokens/numbers, but a
    stray ``<`` in a witness token must never break the markup."""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _plausible_verbs(stage: str) -> tuple[str, ...]:
    return _PLAUSIBLE_VERBS[stage]  # stage is WORKLIST_STAGES-validated at the candidate model


def prefilled_record_command(book_id: str, candidate: "WorklistCandidate", action: str) -> str:
    """The copy-paste ``record`` command for one (candidate, verb) — the sheet proposes, the DT-10
    CLI disposes. The command-binding guard: an ``action`` outside :data:`VERDICT_ACTIONS` is
    refused, so the sheet can only ever emit a runnable verdict. ``redraw_split`` carries a
    ``split_x`` placeholder read off the overlay ruler."""
    if action not in VERDICT_ACTIONS:
        raise ValueError(
            f"cannot pre-fill a command for unknown verdict action {action!r} — must be one of "
            f"{VERDICT_ACTIONS} (command-binding: the sheet never emits an unrunnable verb)"
        )
    cmd = (
        f"python -m engine.structure.geom_review --book {book_id} record "
        f"--id {candidate.id} --action {action} --by YOU"
    )
    if action == ACTION_REDRAW_SPLIT:
        cmd += " --param split_x=<X>"
    return cmd


def _match_denominator(candidate: "WorklistCandidate") -> tuple[object, int]:
    """The (matched, total) behind a match candidate's bare rate. The **denominator rule**: a match
    route whose tentative carries no non-negative-integer ``total`` fails loud rather than rendering a
    rate whose window size is hidden (the p6 4-token-window trap — a healthy-looking 0.75 over 4
    tokens). A ``total`` of **zero** is honest, not a violation — an all-tokenless page has a real
    (zero) window size and renders it; only an *absent/malformed* denominator (the #40-as-shipped bare
    rate) fails loud. ``matched`` is optional (rendered when present)."""
    total = candidate.tentative.get("total")
    if not (_is_int(total) and total >= 0):
        raise GeometryError(
            f"candidate {candidate.id} is a match route but its tentative carries no integer 'total' "
            f"— refusing to render a bare rate without its token denominator (the p6 tiny-window trap "
            f"the review sheet exists to expose); regenerate the worklist from the current matcher"
        )
    return candidate.tentative.get("matched"), total


def _evidence_html(candidate: "WorklistCandidate") -> str:
    if candidate.stage == "match":  # the rate-bearing stage — key here, not on the signal wording
        matched, total = _match_denominator(candidate)
        if total == 0:
            return "<p class='den'>0 witness tokens (all-tokenless page — nothing to match)</p>"
        num = _esc(matched) if matched is not None else "?"
        chips = candidate.tentative.get("unmatched_tokens") or ()
        chip_html = "".join(f"<span class='chip'>{_esc(t)}</span>" for t in chips)
        return (
            f"<p class='den'>matched <strong>{num}/{_esc(total)}</strong> witness tokens</p>"
            f"<div class='chips'>{chip_html}</div>"
        )
    if not candidate.tentative:
        empty = candidate.signal == "empty-window"
        return f"<p class='den'>{'empty window (0 tokens)' if empty else '—'}</p>"
    rows = "".join(f"<li>{_esc(k)}: {_esc(candidate.tentative[k])}</li>" for k in sorted(candidate.tentative))
    return f"<ul class='tentative'>{rows}</ul>"


def _position_html(candidate: "WorklistCandidate", sweep: Mapping | None) -> str:
    # The accept-rate cut + its decision zone are match-stage concepts (the page-accept sweep); other
    # stages have no such bar, so this line renders only for match.
    if candidate.stage != "match":
        return ""
    gap = candidate.threshold - candidate.value
    flag = ""
    if sweep and str(candidate.page) in (sweep.get("decision_zone") or {}):
        flag = " <span class='dz-flag'>· just under the cut (in the decision zone — a close call)</span>"
    return f"<p class='pos'>Auto-accept bar {_esc(candidate.threshold)}; fell short by {_esc(round(gap, 4))}.{flag}</p>"


def _why_html(candidate: "WorklistCandidate") -> str:
    """Plain-language reason this page was flagged — the numbers as a sentence, not raw telemetry."""
    stage = candidate.stage
    if stage == "match":
        total = candidate.tentative.get("total")
        matched = candidate.tentative.get("matched")
        if _is_int(total) and total > 0 and matched is not None:
            pct = 100.0 * matched / total
            return (
                f"Only <strong>{_esc(matched)} of {_esc(total)}</strong> witness words attached to the "
                f"scan's OCR boxes ({pct:.0f}%), under the {candidate.threshold * 100:.0f}% we accept "
                f"automatically."
            )
        return "This page's words attached to the scan's OCR boxes below the auto-accept bar."
    if stage == "locate":
        return "Page-locate found no witness text anywhere on this scan leaf — an empty window."
    if stage == "density":
        return (
            f"The density gate could not confidently call this leaf content vs blank "
            f"({_esc(candidate.signal)} {_esc(round(candidate.value, 3))})."
        )
    if stage == "columns":
        return (
            f"Column confidence {_esc(round(candidate.value, 3))} sits in the undecided margin around "
            f"the {_esc(candidate.threshold)} threshold — the detector isn't sure of the layout."
        )
    return ""


def _sheet_header(worklist: Worklist, book_id: str, sweep: Mapping | None) -> str:
    parts = [
        f"<h1>Geometry review — {_esc(book_id)} · {len(worklist.candidates)} page(s) to adjudicate</h1>",
        "<p>Pages the geometry stage couldn’t auto-accept while attaching word-boxes to the text. For "
        "each, read the scan and decide whether to <strong>keep</strong> or <strong>drop</strong> its "
        "geometry (or fix a column split). Nothing here changes anything — record a verdict by running "
        "the command shown under your choice.</p>",
    ]
    if sweep:
        parts.append(f"<p>Applied auto-accept cut: <strong>{_esc(sweep.get('applied_cut'))}</strong>.</p>")
        ladder = sweep.get("ladder") or {}
        if ladder:
            body = "".join(
                f"<tr><td>{_esc(k)}</td><td>{_esc(v.get('accepted'))}</td><td>{_esc(v.get('routed'))}</td></tr>"
                for k, v in sorted(ladder.items())
            )
            parts.append(
                "<details><summary>threshold sweep — accepted / routed at each candidate cut</summary>"
                "<table class='ladder'><thead><tr><th>cut</th><th>accepted</th><th>routed</th></tr>"
                f"</thead><tbody>{body}</tbody></table></details>"
            )
        dz = sweep.get("decision_zone") or {}
        if dz:
            items = "".join(
                f"<li>p{_esc(k)} @ {_esc(round(float(v), 4))}</li>"
                for k, v in sorted(dz.items(), key=lambda kv: (float(kv[1]), kv[0]))
            )
            parts.append(f"<details><summary>decision zone — {len(dz)} pages near the cut</summary><ul>{items}</ul></details>")
    return "<header>" + "".join(parts) + "</header>"


def render_review_sheet(
    worklist: Worklist,
    *,
    book_id: str,
    available_overlays: "set[tuple[int, str]] | frozenset[tuple[int, str]]",
    sweep: Mapping | None = None,
    overlay_dir_href: str = "overlays",
) -> str:
    """Render the whole worklist into one read-only HTML evidence sheet (#46; DT-10 read-side).

    A **pure function** of ``(worklist, book_id, available_overlays, sweep, overlay_dir_href)`` — no
    clock, no filesystem, no set-iteration order leaks (candidates render in their stored order,
    ``available_overlays`` is consulted only for membership) — so the same inputs give byte-identical
    HTML (**determinism**). Every candidate renders exactly once and a candidate whose overlay is not
    in ``available_overlays`` is a hard fail, never a silent skip (**totality**). Match-rate entries
    render their denominator or fail loud (**denominator rule**), and every pre-filled command is a
    real DT-10 verb (**command binding**). Writes nothing — verdicts enter only through the ``record``
    CLI (DT-10's "not a new HTML sheet" governs the *write* path)."""
    if not (isinstance(book_id, str) and _WITNESS_ID.fullmatch(book_id)):
        raise ValueError(f"book_id must be a flat stem matching {_WITNESS_ID.pattern!r}, got {book_id!r}")
    sections = [_SHEET_HEAD, _sheet_header(worklist, book_id, sweep)]
    for c in worklist.candidates:
        if (c.page, c.stage) not in available_overlays:
            raise GeometryError(
                f"no rendered overlay for candidate {c.id} (page {c.page}, stage {c.stage}) — render "
                f"the worklist overlays before building the sheet; a missing overlay is a hard fail, "
                f"never a silent skip (totality)"
            )
        overlay = f"{overlay_dir_href}/page_{c.page:04d}_{c.stage}.png"
        badge, deciding = _STAGE_COPY[c.stage]
        cmds = "".join(
            f'<li class="act act-{v}"><span class="vlabel">{_esc(_VERB_LABEL[v])}</span>'
            f"<code>{_esc(prefilled_record_command(book_id, c, v))}</code></li>"
            for v in _plausible_verbs(c.stage)
        )
        sections.append(
            f'<section class="entry" data-candidate-id="{_esc(c.id)}">'
            f'<div class="scan"><a href="{_esc(overlay)}" target="_blank" rel="noopener">'
            f'<img src="{_esc(overlay)}" alt="page {c.page} scan with detected boxes"></a></div>'
            f'<div class="adjudicate">'
            f'<div class="ehead"><span class="pageno">Page {c.page}</span>'
            f'<span class="badge b-{c.stage}">{_esc(badge)}</span>'
            f'<span class="cid">{_esc(c.id)}</span></div>'
            f'<p class="deciding"><span class="lbl">What you’re deciding</span>{_esc(deciding)}</p>'
            f'<p class="why"><span class="lbl">Why it’s flagged</span>{_why_html(c)}</p>'
            f'<div class="support">{_evidence_html(c)}{_position_html(c, sweep)}</div>'
            f'<ul class="cmds"><li class="lbl" style="list-style:none">Your options</li>{cmds}</ul>'
            f"</div></section>"
        )
    sections.append(_SHEET_FOOT)
    return "\n".join(sections) + "\n"


def walk_diagnostic(candidate: "WorklistCandidate", *, book_id: str, sweep: Mapping | None = None) -> str:
    """The plain-text per-candidate block for ``review next`` walk mode — the same evidence the sheet
    shows (denominator + chips + pre-filled verbs), honouring the denominator rule."""
    lines = [
        f"{candidate.id}  [{candidate.stage}/{candidate.signal}]",
        f"  value {round(candidate.value, 4)} vs threshold {candidate.threshold} "
        f"(Δ {round(candidate.value - candidate.threshold, 4)})",
    ]
    if sweep and str(candidate.page) in (sweep.get("decision_zone") or {}):
        lines.append("  · in decision zone")
    if candidate.stage == "match":
        matched, total = _match_denominator(candidate)
        lines.append(f"  matched {matched if matched is not None else '?'}/{total} witness tokens")
        chips = candidate.tentative.get("unmatched_tokens") or ()
        if chips:
            lines.append(f"  unmatched: {' '.join(str(t) for t in chips)}")
    else:
        for k in sorted(candidate.tentative):
            lines.append(f"  {k}: {candidate.tentative[k]}")
    for v in _plausible_verbs(candidate.stage):
        lines.append(f"  {v}: {prefilled_record_command(book_id, candidate, v)}")
    return "\n".join(lines)


def review_sheet_path(workspace: BookWorkspace) -> Path:
    """The containment-checked path to the disposable review sheet
    ``<work>/output/geometry_review/review_sheet.html`` (regenerable from worklist + overlays)."""
    return workspace.resolve(OVERLAY_AREA, OVERLAY_SUBDIR, REVIEW_SHEET_FILENAME)


def available_overlays(workspace: BookWorkspace, worklist: Worklist) -> set[tuple[int, str]]:
    """The ``(page, stage)`` keys of the worklist whose overlay PNG exists on disk — the sheet's
    totality check consults this and fails loud on any candidate whose overlay is missing."""
    return {(c.page, c.stage) for c in worklist.candidates if overlay_path(workspace, c.page, c.stage).is_file()}


def _load_sweep(stats_path) -> Mapping | None:
    """The optional ``threshold_sweep`` header block, read from a run-stats JSON (the ladder +
    decision zone the header shows). ``None`` when no path is given; a present-but-unreadable/
    malformed file fails loud (never a silently header-less sheet)."""
    if stats_path is None:
        return None
    path = Path(stats_path)
    if not path.is_file():
        raise MissingInputError(f"run-stats file for the review-sheet header not found at {path}")
    try:
        data = read_json(path)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        raise StaleArtifactError(f"run-stats file {path} is unloadable: {exc}") from exc
    if not isinstance(data, Mapping):
        raise StaleArtifactError(f"run-stats file {path} must be a JSON object, got {type(data).__name__}")
    return data.get("threshold_sweep")


def write_review_sheet(
    workspace: BookWorkspace, book_id: str, worklist: Worklist, *, sweep: Mapping | None = None
) -> Path:
    """Render the worklist into the disposable HTML sheet on disk (the ``sheet`` CLI path). Fails
    loud if any candidate's overlay is missing (totality). Returns the written path."""
    html = render_review_sheet(
        worklist, book_id=book_id, available_overlays=available_overlays(workspace, worklist), sweep=sweep
    )
    path = review_sheet_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def _open_in_viewer(path: Path) -> None:  # pragma: no cover — OS side effect, injected in tests
    """Open a rendered overlay in the OS image viewer for walk mode — ``open`` on macOS,
    ``xdg-open`` elsewhere (Linux reviewers)."""
    import subprocess

    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.run([opener, str(path)], check=False)


def walk_review(
    book_dir,
    workspace: BookWorkspace,
    *,
    by: str,
    sweep: Mapping | None = None,
    input_fn=input,
    open_fn=_open_in_viewer,
    out=None,
) -> int:
    """``review next`` walk mode: step through the OPEN candidates, opening each overlay and printing
    its diagnostic, and prompt for a verb (or ``skip``/``quit``). A ruled verb is written through the
    **same** :func:`record_verdict` write path as the CLI (DT-10; no second write path). Returns the
    number of verdicts recorded. IO is injected so the loop is testable without a TTY."""
    out = out if out is not None else sys.stdout
    worklist = load_worklist(workspace)
    verdicts = load_verdicts(Path(book_dir))
    book_id = Path(book_dir).name
    recorded = 0
    for c in worklist.candidates:
        if c.id in verdicts:
            continue  # already ruled — walk only surfaces the open queue
        overlay = overlay_path(workspace, c.page, c.stage)
        if overlay.is_file():
            open_fn(overlay)
        print(walk_diagnostic(c, book_id=book_id, sweep=sweep), file=out)
        answer = (input_fn(f"verb for {c.id} ({'/'.join(_plausible_verbs(c.stage))}/skip/quit): ") or "").strip()
        if answer == "quit":
            break
        if answer in ("", "skip"):
            continue
        if answer not in _plausible_verbs(c.stage):
            print(f"  not a plausible verb here: {answer!r} — skipped", file=out)
            continue
        params = None
        if answer == ACTION_REDRAW_SPLIT:
            # redraw_split is a re-entry WITH a parameter — capture the split_x read off the ruler,
            # so walk mode records a complete verdict (not a coordinate-less one the re-entry ignores).
            raw = (input_fn(f"  split_x for {c.id} (blank to skip): ") or "").strip()
            if not raw:
                print("  redraw_split needs a split_x — skipped", file=out)
                continue
            params = _parse_params([f"split_x={raw}"])
        record_verdict(book_dir, c.id, action=answer, by=by, params=params)
        recorded += 1
        print(f"  recorded {answer} for {c.id}", file=out)
    return recorded


# --- CLI (S4.6b gate-CLI pattern; DT-10) -------------------------------------------------------- #


def _parse_params(raw: Sequence[str] | None) -> dict[str, object]:
    """Parse ``--param k=v`` pairs, coercing ints/floats so ``split_x=310.5`` lands as a number."""
    out: dict[str, object] = {}
    for item in raw or ():
        if "=" not in item:
            raise ValueError(f"--param must be key=value, got {item!r}")
        key, _, value = item.partition("=")
        for cast in (int, float):
            try:
                out[key] = cast(value)
                break
            except ValueError:
                continue
        else:
            out[key] = value
    return out


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m engine.structure.geom_review",
        description="Apply and record human verdicts on the geometry-review worklist (S2.1.6 / DT-10).",
    )
    parser.add_argument("--book", required=True, help="Book id under --books-dir.")
    parser.add_argument("--books-dir", default="books", help="Directory holding book workspaces.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="List the worklist candidates and their verdict state.")
    sub.add_parser("apply", help="Project the tracked verdicts onto the worklist + report.")
    record = sub.add_parser("record", help="Stamp ONE verdict for a candidate into the tracked file.")
    record.add_argument("--id", required=True, help="The candidate id ({witness}:p{page:04d}:{stage}).")
    record.add_argument("--action", required=True, choices=VERDICT_ACTIONS, help="The verdict action.")
    record.add_argument("--by", required=True, help="Who is ruling (provenance).")
    record.add_argument("--param", action="append", help="A key=value verdict parameter (repeatable).")
    sheet = sub.add_parser("sheet", help="Render the read-only HTML evidence sheet (#46; writes nothing but HTML).")
    sheet.add_argument("--stats", help="Optional run-stats JSON for the threshold-sweep header.")
    nxt = sub.add_parser("next", help="Walk the open candidates, opening each overlay and prompting for a verb.")
    nxt.add_argument("--by", required=True, help="Who is ruling (provenance, threaded to recorded verdicts).")
    nxt.add_argument("--stats", help="Optional run-stats JSON for the decision-zone context.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    book_dir = Path(args.books_dir) / args.book
    workspace = BookWorkspace.for_book(args.book, args.books_dir)
    try:
        if args.command == "status":
            worklist = load_worklist(workspace)
            for c in worklist.candidates:
                state = "open" if c.verdict is None else c.verdict.get("action", "?")
                print(f"{c.id}  {c.signal}={c.value:.4f} (thr {c.threshold})  {state}")
            print(f"{len(worklist.candidates)} candidate(s)")
            return 0
        if args.command == "apply":
            worklist = load_worklist(workspace)
            verdicts = load_verdicts(book_dir)
            applied, stats = apply_verdicts(worklist, verdicts)
            save_worklist(workspace, applied)
            print(
                f"{stats['applied']} applied ({stats[OUTCOME_DECLINED]} declined, "
                f"{stats[OUTCOME_REENTERED]} re-enter), {stats['open']} open, {stats['stale']} stale, "
                f"{stats['orphaned']} orphaned"
            )
            return 0
        if args.command == "record":
            path = record_verdict(book_dir, args.id, action=args.action, by=args.by, params=_parse_params(args.param))
            print(f"recorded {args.action} for {args.id} -> {path}")
            return 0
        if args.command == "sheet":
            worklist = load_worklist(workspace)
            path = write_review_sheet(workspace, args.book, worklist, sweep=_load_sweep(args.stats))
            print(f"review sheet -> {path}  ({len(worklist.candidates)} candidate(s))")
            return 0
        if args.command == "next":
            recorded = walk_review(book_dir, workspace, by=args.by, sweep=_load_sweep(args.stats))
            print(f"{recorded} verdict(s) recorded")
            return 0
    except EngineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(f"unhandled command {args.command!r}")  # argparse makes this unreachable


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
