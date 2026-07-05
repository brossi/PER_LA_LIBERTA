"""Engine exception taxonomy → CLI exit codes.

One type per concrete failure an engine step can raise, each carrying the non-zero
``exit_code`` the CLI returns so a known failure is a clean message + code, not a traceback.
Deliberately minimal (F7): a category is added only when a real raiser exists — not pre-populated
"for completeness" (YAGNI). Exit codes ``1`` (config) and ``2`` (unported stub) are owned by the
CLI; the step failures below start at ``3``.

Three structure-owned :class:`EngineError` subclasses live beside their raisers rather than here
(the carrier-beside-the-vocabulary posture), continuing the exit-code sequence:
``StructureValidationError`` (``11``, ``structure/errors.py`` — Tier-2 semantic findings carrying
the closed ``EC`` payload), ``EvidenceGateError`` (``12``, ``structure/evidence.py`` — the
authoring-evidence gate's typed ``(kind, message)`` findings), and ``GeometryError`` (``13``,
``structure/geometry.py`` — the fail-loud geometry/OCR-backend + geometry-integrity carrier,
deliberately not reusing :class:`BackendError` 5, whose degrade-to-sentinel posture is the
opposite). The CLI maps every :class:`EngineError` generically via ``exc.exit_code``, so
subclassing elsewhere costs nothing here; a new code must stay unique across all four files (pinned
by ``test_authoring_evidence.py``'s uniqueness sweep).

The shared load-boundary taxonomy of the persisted structure-*document* loaders (structure maps,
stream-freeze records, authoring-evidence sidecars, geometry sidecars): an **absent** artifact is
:class:`MissingInputError`; a **present-but-unloadable** one (malformed, unreadable, non-UTF-8,
parse-depth blowup, stale-version, wrong stale class) is :class:`StaleArtifactError`; nothing else
escapes those loaders. Known gap (delta re-audit 2026-07-02): ``structure.atom_store.load_stream``
predates the unreadable/non-UTF-8/parse-depth hardening and still leaks those raw — an S1.5
follow-up, not a claim.
"""

from __future__ import annotations


class EngineError(Exception):
    """Base for engine failures the CLI maps to a clean exit code."""

    exit_code = 1


class MissingInputError(EngineError):
    """A step's required input artifact — or a config-referenced asset — is absent or unusable.

    Covers an absent workspace input (``reconcile``'s OCR copies, ``ocr``'s scan PDF), a
    referenced asset that does not resolve (``validate``'s frequency dictionary, ``adjudicate``'s
    period-dictionary dir — via ``paths.require_asset``), and a present-but-structurally-unusable
    input (a malformed/non-UTF-8 dictionary ``index.json``, or one declaring no chunks —
    ``structure.lineage``). All are known, user-facing failures, so they exit cleanly (code 3)
    instead of as a bare ``FileNotFoundError`` / ``KeyError`` / ``UnicodeDecodeError`` traceback.
    """

    exit_code = 3


class AcquisitionError(EngineError):
    """``download`` could not fetch a source (network / HTTP failure)."""

    exit_code = 4


class BackendError(EngineError):
    """``ocr``'s rendering or transcription backend failed (an unreadable scan PDF at page-count,
    the vision-model call, or a missing key). A *per-page* render failure does not raise — it
    degrades to an ``[OCR_ERROR]`` sentinel; this is the whole-document / transcription case."""

    exit_code = 5


class RegenerationGuardError(EngineError):
    """A step refused to overwrite an existing protectable output without an explicit override.

    ``cleanup`` (and, at M4c, ``translate``/``refine``) writes an artifact a human may have
    hand-tuned inside ``work/``; a silent re-run would clobber it. The guard refuses unless
    ``allow_regen=True`` (kwarg) or ``ENGINE_ALLOW_REGEN=1`` (env) is set — deliberate friction
    mirroring the live ``PER_LA_LIBERTA_ALLOW_REGEN`` escape (BR-012/M4b-D2). The override form is
    a kwarg + env, no CLI flag; the error message names the escape for discoverability.
    """

    exit_code = 6


class RoundTripError(EngineError):
    """An L1 atom's raw/normalized round-trip floor failed (``structure.roundtrip``; §9, D22).

    Distinct from the operational step failures above: this is an *integrity* violation, not a
    missing input or a backend fault. Raised when the byte-exact raw tier fails — an out-of-bounds
    ``raw_span`` or a slice whose hash does not match ``raw_source_hash`` (the source artifact
    drifted, or the span is wrong) — or when the normalized tier fails (the declared transforms do
    not produce the stored text, or their inverses do not recover the raw). The floor a ``norm_layer``
    label cannot fake; failing it loud is the point.
    """

    exit_code = 7


class CaptureError(EngineError):
    """An L1 atom *stream*'s capture-completeness or span topology is violated (``structure.capture``;
    S1.3a, §3.0/§9).

    A stream-level integrity violation, the complement of :class:`RoundTripError`'s per-atom check:
    raised when a witness's atoms do not *tile* their source — a span out of bounds, an
    overlap/out-of-order span, or an uncovered non-whitespace gap (a *silent loss*: source bytes
    captured into no atom, the failure mode "everything is brought in" exists to forbid). The
    captured-but-excluded vs never-captured distinction is what makes this checkable (§3.0). Also
    covers the **cross-stream** reference-integrity tier of the atom store (S1.5): a canonical atom
    that derives from no witness, or whose ``derived_from`` back-link resolves to no atom in the named
    witness stream — the same "the streams don't hang together" family as a within-stream tiling fault.
    """

    exit_code = 8


class IncompleteTypingError(EngineError):
    """A *typed* L1 projection is structurally incomplete (``structure.typed``; S1.3b, §2-A/§9, R3).

    The completeness complement of :class:`CaptureError` (which checks the *raw* stream tiles its
    source): once the raw atoms are typed via a ``BlockClassifier``, ``unknown`` is a first-class
    *incomplete* state, never a quiet green. Raised when the typing leaves the structure unresolved
    in a way the profile cannot tolerate — an atom in one of the profile's declared
    ``boundary_classes`` (a structurally load-bearing slot) typed ``unknown``, or an **all-unknown**
    projection that resolved nothing (the degenerate stub's output). A body-leaf ``unknown`` is the
    *non*-fatal case: it does not raise, it routes to review (count + location) in the returned
    report. This is the failure a confidence label cannot fake.
    """

    exit_code = 9


class StaleArtifactError(EngineError):
    """A persisted engine artifact is present but cannot be loaded as a valid current-schema
    document (S1.5/S4, §3.5/§3.6, D21).

    The fail-loud the lineage governance rests on (§3.6 "Stale = fail-loud"): a *load* boundary
    failure, distinct from the in-memory integrity violations above. One family of raisers, one
    contract, across every governed persisted layer — atom streams (``structure.atom_store``),
    structure maps (``structure.structure_map``), stream-freeze records (``structure.freeze``),
    and authoring-evidence sidecars (``structure.evidence``) — plus the deny-by-default writers
    (``write_freeze_record``/``write_authoring_evidence``), where refusing to overwrite differing
    hand-tuned content is the same "do not trust the silent path" posture. Raised when a persisted
    document carries a ``schema_version`` that is not the current registered one (genuinely
    **stale** — refresh or migrate, the M3/S8.1 stale-class hook), declares the wrong
    ``stale_class``, is missing a required key, is unreadable or unparseable (``OSError``/
    ``RecursionError``/non-UTF-8/non-JSON wrapped at the boundary — the three document loaders
    hold this in full; ``atom_store.load_stream`` wraps only the JSON tier so far, the known S1.5
    gap noted in the module docstring), or is otherwise structurally
    malformed (a model-invariant violation a ``ValueError`` would raise in memory is wrapped here,
    so every loader has a total contract: a valid object or this error). ``assert_freeze_matches``
    also raises it: a drifted freeze pin *is* a stale artifact. One human action — do not trust
    the file — so one exit code; the message distinguishes the cases. A *missing* file is
    :class:`MissingInputError` (absent, not stale); a persisted stream whose text drifted off its
    span is :class:`RoundTripError` (the anchored round-trip self-check); an evidence sidecar that
    loads fine but no longer *corresponds* to the live map is
    ``structure.evidence.EvidenceGateError`` (the correspondence/staleness taxonomy line).
    """

    exit_code = 10
