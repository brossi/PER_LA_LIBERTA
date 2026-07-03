"""S4.6b — the authoring-loop toolkit: composite gate, validate-on-save, worklist status, evidence
stamping, and the digest-diff explainer (s4_6_tooling_plan, ratified 2026-07-02; issue #34).

This module is the engine half of the S4.6 hand-authoring loop. It owns nothing of its own — every
check composes the persisted-layer owners (``freeze``/``atom_store``/``structure_map``/
``evidence``), which is why it lives beside them instead of inside any one: the composite gate
spans all four, and homing it in a single-artifact module would invert that module's ownership
(plan DT-1).

The loop it serves (plan §1): a book-side seeder drafts ``<work>/structure_map.json``; the human
edits it; ``validate`` (optionally ``--watch``) surfaces Tier-1/Tier-2 findings per edit;
``status`` renders the evidence worklist (all containers ``missing`` at first — the TODO list);
``stamp`` writes one verified container's evidence entry; ``explain`` names exactly WHICH
children/atoms moved when a stamped entry goes stale (diffing the entry's DT-4 payload witnesses
against the live producers — no baseline document, snapshot, or git archaeology); ``gate`` is the
one-command "is this authored map trustworthy" check. The gate flipping green *is* S4.6
completion.

Composite-gate order is substrate-first (plan DT-5) so a failure is attributed to the right
layer: freeze pin → persisted streams → pin↔live match → structure map (Tier-1+2) → evidence
correspondence. Deliberate non-goal, guarded by test: the gate does **not** compare the map's
stored manifest hashes against the live streams — that stored-vs-live comparison is S8.1's
(s4_plan §3.E.9); the freshness claim here rides the freeze pin, which pins the same envelope
hashes the manifest stamps.

There is deliberately **no bulk stamp** (plan DT-6): stamping without per-node human verification
is exactly what the evidence gate exists to prevent. One node per ``stamp_evidence`` call, prose
required.

Neutral core (inv 15): no language/book/typeface literal — the book-shaped knowledge (heading
grammars, skeleton counts) lives in the book-side seeder script, never here.

CLI: ``uv run python -m engine.structure.authoring --book <id> <command>`` (plan DT-2). Exit codes
ride the ``EngineError`` taxonomy: 12 for evidence findings, 11 for map findings, the stale/missing
codes otherwise. Shaped as a package (``__init__`` = the library, ``__main__`` = the entry) so
``python -m`` does not re-execute a module the ``engine.structure`` package already imported — the
single-file form ran everything twice per invocation with a runpy warning.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping

from engine.errors import EngineError, MissingInputError, StaleArtifactError
from engine.paths import BookWorkspace
from engine.structure.artifacts import authoring_evidence_path, structure_map_path
from engine.structure.atom_store import AtomStream, load_workspace_streams
from engine.structure.evidence import (
    EVIDENCE_FINDING_KINDS,
    AuthoringEvidence,
    _attributed_findings,
    _encode_atom_runs,
    assert_evidence_gate,
    build_evidence_entry,
    decision_payload,
    extent_payload,
    load_authoring_evidence,
    write_authoring_evidence,
)
from engine.structure.freeze import assert_freeze_matches, load_freeze_record
from engine.structure.projection import (
    MINTED_BY_HUMAN,
    ContainerNode,
    Node,
)
from engine.structure.structure_map import StreamAtomReader, StructureMap, load_structure_map

#: The committed per-book freeze pin's filename, at the book dir root beside ``inputs/`` (the
#: S4.6-pre layout) — a *committed* sibling of the disposable ``work/`` tree, which is why it is
#: not a ``BookWorkspace`` path accessor like the map/sidecar.
STREAM_FREEZE_FILENAME = "stream_freeze.json"


# --- staged context loading (the DT-5 order, shared by every command) ---------------------------- #


@dataclass(frozen=True, slots=True)
class _AuthoringContext:
    """Everything a command needs once the substrate-first stages have held: the freeze record,
    the loaded streams + reader, the loaded map, and the sidecar (empty-but-book-bound when the
    file does not exist yet — mid-authoring is a first-class state, plan §1)."""

    book: str
    streams: Mapping[str, AtomStream]
    reader: StreamAtomReader
    smap: StructureMap
    evidence: AuthoringEvidence
    evidence_path: Path


def _workspace(book_dir: Path) -> BookWorkspace:
    book_dir = Path(book_dir)
    return BookWorkspace.for_book(book_dir.name, book_dir.parent)


def _load_context(book_dir: Path, *, canonical_stream_id: str = "canonical") -> _AuthoringContext:
    """Run the substrate-first stages (plan DT-5) and hand back the loaded context.

    1. the committed freeze pin (its ``book`` must equal the book dir's name — a copy-pasted pin
       from another book is the wrong artifact, however well-formed);
    2. the persisted streams (per-stream round-trip + hash tiers + reference integrity);
    3. pin ↔ live (``assert_freeze_matches``);
    4. the structure map (Tier-1 + Tier-2 through the born-agnostic loader);
    5. the sidecar — loaded with the pin's ``book`` binding when present; an *absent* sidecar is
       the empty worklist state, not an error (the gate then reports every container ``missing``,
       which is exactly the S4.6 TODO list).

    Everything raises its owner's typed error; nothing here re-wraps, so a failure names the layer
    that actually failed.
    """
    book_dir = Path(book_dir)
    record = load_freeze_record(book_dir / STREAM_FREEZE_FILENAME)
    book = record["book"]
    if book != book_dir.name:
        raise StaleArtifactError(
            f"freeze pin at {book_dir / STREAM_FREEZE_FILENAME} names book {book!r}, but the book "
            f"dir is {book_dir.name!r} — wrong pin for this book"
        )
    workspace = _workspace(book_dir)
    streams = load_workspace_streams(workspace, canonical_stream_id=canonical_stream_id)
    assert_freeze_matches(record, streams)
    reader = StreamAtomReader(streams, canonical_stream_id)
    smap = load_structure_map(structure_map_path(workspace), reader)
    evidence_path = authoring_evidence_path(workspace)
    try:
        evidence = load_authoring_evidence(evidence_path, expected_book=book)
    except MissingInputError:
        evidence = AuthoringEvidence(book=book, entries=())
    return _AuthoringContext(
        book=book,
        streams=MappingProxyType(dict(streams)),
        reader=reader,
        smap=smap,
        evidence=evidence,
        evidence_path=evidence_path,
    )


# --- T-3: the freeze×evidence composite gate ------------------------------------------------------ #


def assert_authoring_integrity(
    book_dir: Path, *, canonical_stream_id: str = "canonical"
) -> StructureMap:
    """THE one-command "is this authored map trustworthy" check (plan T-3): every DT-5 stage plus
    the evidence gate, in substrate-first order. Returns the loaded map when everything holds;
    raises the failing layer's typed error otherwise (``EvidenceGateError`` carries the full
    findings worklist). An absent sidecar gates as all-``missing`` — a fresh draft is *not yet*
    trustworthy, and the findings say exactly what remains."""
    context = _load_context(book_dir, canonical_stream_id=canonical_stream_id)
    assert_evidence_gate(context.evidence, context.smap.projection)
    return context.smap


# --- T-2: validate-on-save (the non-raising editor loop) ------------------------------------------ #


def validate_authoring(
    book_dir: Path, *, canonical_stream_id: str = "canonical"
) -> tuple[str, ...]:
    """The per-edit validation pass (plan T-2): the same stages as the gate, collected instead of
    raised — the editor loop wants findings on stdout, not a traceback. Returns ``()`` when the
    authored pair holds end to end. Evidence findings are included (the worklist is a finding
    while authoring is incomplete); the enforcing form is :func:`assert_authoring_integrity`."""
    try:
        context = _load_context(book_dir, canonical_stream_id=canonical_stream_id)
    except EngineError as exc:
        return (f"[{type(exc).__name__}] {exc}",)
    return tuple(
        f"[{kind}] {message}"
        for _, kind, message in _attributed_findings(context.evidence, context.smap.projection)
    )


def watch_validate(
    book_dir: Path,
    *,
    interval: float = 1.0,
    emit: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
    canonical_stream_id: str = "canonical",
) -> None:
    """``validate`` re-run on every save (plan DT-8): a 1 Hz stdlib mtime poll over the map + the
    sidecar — two files need no watcher dependency. Runs until interrupted (``KeyboardInterrupt``
    from ``sleep`` returns cleanly); ``sleep`` is injectable so the loop is testable without
    threads."""
    workspace = _workspace(book_dir)
    watched = (structure_map_path(workspace), authoring_evidence_path(workspace))
    last: tuple | None = None
    while True:
        stamp = tuple(p.stat().st_mtime_ns if p.exists() else None for p in watched)
        if stamp != last:
            last = stamp
            findings = validate_authoring(book_dir, canonical_stream_id=canonical_stream_id)
            if findings:
                emit(f"--- {len(findings)} finding(s) ---")
                for line in findings:
                    emit(line)
            else:
                emit("--- clean: freeze ↔ streams ↔ map ↔ evidence all hold ---")
        try:
            sleep(interval)
        except KeyboardInterrupt:
            return


# --- T-5: the worklist status view ---------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class WorklistRow:
    """One human-minted container's evidence state, in map reading order. ``kinds`` is drawn from
    the closed ``EVIDENCE_FINDING_KINDS`` set; empty means fresh (stamped and both digests hold)."""

    node_id: str
    node_class: str
    designation: str
    title: str
    kinds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AuthoringStatus:
    """The status listing (plan T-5): per-container rows plus the sidecar-side anomalies
    (``orphaned``/``misbound`` findings, which have no container row to live on) and the kind
    counts. Non-raising by design — a worklist is a view, the gate is the enforcement."""

    book: str
    map_revision: int
    rows: tuple[WorklistRow, ...]
    anomalies: tuple[tuple[str, str], ...]
    counts: Mapping[str, int]


def authoring_status(
    book_dir: Path, *, canonical_stream_id: str = "canonical"
) -> AuthoringStatus:
    """Assemble the worklist view from THE findings producer's node-attributed core — per-node
    status is never re-derived by a second staleness computation or by parsing messages (the
    single-producer discipline, s4_plan §1.4.1a)."""
    context = _load_context(book_dir, canonical_stream_id=canonical_stream_id)
    projection = context.smap.projection
    attributed = _attributed_findings(context.evidence, projection)
    kinds_by_node: dict[str, list[str]] = {}
    anomalies: list[tuple[str, str]] = []
    for node_id, kind, message in attributed:
        if kind in ("orphaned", "misbound"):
            anomalies.append((kind, message))
        else:
            kinds_by_node.setdefault(node_id, []).append(kind)
    rows = tuple(
        WorklistRow(
            node_id=node.node_id,
            node_class=node.node_class,
            designation=node.designation,
            title=node.title,
            kinds=tuple(kinds_by_node.get(node.node_id, ())),
        )
        for node in projection.nodes  # map reading order — the order a human works the list
        if isinstance(node, ContainerNode) and node.minted_by == MINTED_BY_HUMAN
    )
    counts = {kind: 0 for kind in EVIDENCE_FINDING_KINDS}
    for _, kind, _ in attributed:
        counts[kind] += 1
    counts["fresh"] = sum(1 for row in rows if not row.kinds)
    counts["containers"] = len(rows)
    return AuthoringStatus(
        book=context.book,
        map_revision=context.smap.map_revision,
        rows=rows,
        anomalies=tuple(anomalies),
        counts=MappingProxyType(counts),
    )


def render_status(status: AuthoringStatus) -> str:
    """The worklist table (kinds as columns, per the ratified runway wording), plus anomaly lines
    and the counts footer — plain text, one row per human container in map reading order."""
    kind_columns = ("missing", "stale-decision", "stale-extent")
    headers = ("node_id", "class", "designation / title", *kind_columns)
    table_rows = []
    for row in status.rows:
        label = row.designation or row.title
        if row.title and row.title != row.designation:
            label = f"{label} — {row.title}" if row.designation else row.title
        table_rows.append(
            (
                row.node_id,
                row.node_class,
                label,
                *("×" if kind in row.kinds else "" for kind in kind_columns),
            )
        )
    widths = [
        max(len(headers[i]), *(len(r[i]) for r in table_rows)) if table_rows else len(headers[i])
        for i in range(len(headers))
    ]
    lines = [
        f"book {status.book!r} — map_revision {status.map_revision}",
        "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)),
        "  ".join("-" * w for w in widths),
    ]
    lines.extend(
        "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)) for r in table_rows
    )
    for kind, message in status.anomalies:
        lines.append(f"[{kind}] {message}")
    lines.append(
        "fresh {fresh}/{containers} · missing {missing} · stale-decision {sd} · stale-extent {se}"
        " · orphaned {orphaned} · misbound {misbound}".format(
            fresh=status.counts["fresh"],
            containers=status.counts["containers"],
            missing=status.counts["missing"],
            sd=status.counts["stale-decision"],
            se=status.counts["stale-extent"],
            orphaned=status.counts["orphaned"],
            misbound=status.counts["misbound"],
        )
    )
    return "\n".join(lines) + "\n"


# --- T-6: the single-node evidence stamp ----------------------------------------------------------- #


def stamp_evidence(
    book_dir: Path, node_id: str, *, evidence: str, canonical_stream_id: str = "canonical"
) -> Path:
    """Stamp ONE verified container's evidence entry (plan DT-6, ratified): digests + DT-4 payload
    witnesses through THE producers (``build_evidence_entry``), ``authored_at_revision`` from the
    live map, merged into the loaded sidecar (every other entry preserved byte-for-byte) and
    written through the deny-by-default writer with ``force=True`` — justified as
    read-modify-write: this command loads the existing sidecar and replaces or appends exactly one
    entry; it never regenerates from nothing. There is deliberately no bulk variant."""
    context = _load_context(book_dir, canonical_stream_id=canonical_stream_id)
    node = context.smap.projection.by_id.get(node_id)
    if node is None:
        raise ValueError(
            f"stamp_evidence: {node_id!r} names no node in the structure map — nothing to verify"
        )
    entry = build_evidence_entry(
        node,
        context.smap.projection,
        evidence=evidence,
        authored_at_revision=context.smap.map_revision,
    )
    existing = context.evidence.entries
    if node_id in context.evidence.by_node:
        entries = tuple(entry if e.node_id == node_id else e for e in existing)
    else:
        entries = (*existing, entry)
    merged = AuthoringEvidence(book=context.book, entries=entries)
    return write_authoring_evidence(context.evidence_path, merged, force=True)


# --- T-4: the digest-diff explainer ---------------------------------------------------------------- #


def _fmt_ids(ids: list[str]) -> str:
    """Compact human form of an id set: the DT-4 run encoding rendered as ``first..last`` — the
    same codec the wire uses, so the display can never disagree with what is stored."""
    if not ids:
        return "(none)"
    tokens = _encode_atom_runs(sorted(ids))
    parts = [t if isinstance(t, str) else f"{t[0]}..{t[1]}" for t in tokens]
    return f"{', '.join(parts)} ({len(ids)} atom{'s' if len(ids) != 1 else ''})"


def _diff_id_sets(stored: list[str], live: list[str], label: str, lines: list[str]) -> None:
    entered = sorted(set(live) - set(stored))
    left = sorted(set(stored) - set(live))
    if not entered and not left:
        lines.append(f"    {label}: unchanged")
        return
    if entered:
        lines.append(f"    {label} entered: {_fmt_ids(entered)}")
    if left:
        lines.append(f"    {label} left:    {_fmt_ids(left)}")


def _describe_row(node: Node) -> str:
    title = node.title or node.designation
    return f"{node.node_id!r} ({title!r})" if title else f"{node.node_id!r}"


def explain_evidence_drift(
    book_dir: Path, node_id: str, *, canonical_stream_id: str = "canonical"
) -> str:
    """Name exactly WHICH children/atoms moved for one container (plan T-4): the entry's stored
    DT-4 payload witnesses (self-verified at load — always trustworthy) diffed against the live
    producers. stale-decision explains class + children (added/removed/reordered); stale-extent
    explains each own slot and the beneath union. The non-diff states (missing / orphaned /
    misbound / fresh) are stated plainly — there is nothing to diff for them by definition."""
    context = _load_context(book_dir, canonical_stream_id=canonical_stream_id)
    projection = context.smap.projection
    node = projection.by_id.get(node_id)
    entry = context.evidence.by_node.get(node_id)
    if node is None and entry is None:
        raise ValueError(
            f"explain_evidence_drift: {node_id!r} names no node in the map and no sidecar entry"
        )
    if entry is None:
        return (
            f"{_describe_row(node)}: missing — no evidence entry yet (nothing to diff); verify "
            f"the container against the scans and stamp it"
        )
    if node is None:
        return (
            f"entry {node_id!r}: orphaned — it binds no node in the map (nothing to diff); the "
            f"container was removed or renamed after stamping"
        )
    if not (isinstance(node, ContainerNode) and node.minted_by == MINTED_BY_HUMAN):
        return (
            f"entry {node_id!r}: misbound — it binds a node that is not a human-minted container "
            f"(nothing to diff)"
        )
    lines: list[str] = [f"{_describe_row(node)} — evidence drift report"]
    stored_decision = entry.decision_payload
    live_decision = decision_payload(node)
    if stored_decision == live_decision:
        lines.append("  decision: fresh")
    else:
        lines.append("  decision: STALE")
        if stored_decision["node_class"] != live_decision["node_class"]:
            lines.append(
                f"    node_class: {stored_decision['node_class']!r} -> "
                f"{live_decision['node_class']!r}"
            )
        stored_children = list(stored_decision["children"])
        live_children = list(live_decision["children"])
        removed = [c for c in stored_children if c not in live_children]
        added = [c for c in live_children if c not in stored_children]
        if removed:
            lines.append(f"    children removed: {removed}")
        if added:
            lines.append(f"    children added:   {added}")
        if not removed and not added and stored_children != live_children:
            lines.append(
                f"    children reordered: {stored_children} -> {live_children}"
            )
    stored_extent = entry.extent_payload
    live_extent = extent_payload(node, projection)
    if stored_extent == live_extent:
        lines.append("  extent: fresh")
    else:
        lines.append("  extent: STALE")
        slots = sorted(set(stored_extent["own"]) | set(live_extent["own"]))
        for slot in slots:
            _diff_id_sets(
                list(stored_extent["own"].get(slot, [])),
                list(live_extent["own"].get(slot, [])),
                f"own.{slot}",
                lines,
            )
        _diff_id_sets(
            list(stored_extent["beneath"]), list(live_extent["beneath"]), "beneath", lines
        )
    if stored_decision == live_decision and stored_extent == live_extent:
        lines.append("  both digests hold — nothing moved since the stamp")
    return "\n".join(lines)


# --- CLI (plan DT-2) -------------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m engine.structure.authoring",
        description="S4.6 authoring-loop tooling: validate / status / stamp / explain / gate.",
    )
    parser.add_argument("--book", required=True, help="Book id under --books-dir.")
    parser.add_argument(
        "--books-dir",
        type=Path,
        # engine root from src/engine/structure/authoring/__init__.py — bound by the tooling
        # test's default-books-dir check, so a file move cannot silently re-aim the default
        default=Path(__file__).resolve().parents[4] / "books",
        help="Directory holding the per-book dirs (default: engine/books).",
    )
    parser.add_argument(
        "--canonical-stream-id",
        default="canonical",
        help="The canonical stream id the map anchors on (default: canonical).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Non-raising validation pass (the editor loop).")
    validate.add_argument(
        "--watch", action="store_true", help="Re-validate on every map/sidecar save (mtime poll)."
    )
    validate.add_argument(
        "--interval", type=float, default=1.0, help="Watch poll interval in seconds."
    )
    sub.add_parser("status", help="The evidence worklist (kinds as columns).")
    stamp = sub.add_parser("stamp", help="Stamp ONE verified container's evidence entry.")
    stamp.add_argument("--node", required=True, help="The container's node_id.")
    stamp.add_argument(
        "--evidence", required=True, help="The prose rationale (scan-grounded, non-blank)."
    )
    explain = sub.add_parser("explain", help="Name WHICH children/atoms moved for one container.")
    explain.add_argument("--node", required=True, help="The container's node_id.")
    sub.add_parser("gate", help="The composite freeze×map×evidence gate (exit 0 = trustworthy).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    book_dir = Path(args.books_dir) / args.book
    stream_id = args.canonical_stream_id
    try:
        if args.command == "validate":
            if args.watch:
                watch_validate(book_dir, interval=args.interval, canonical_stream_id=stream_id)
                return 0
            findings = validate_authoring(book_dir, canonical_stream_id=stream_id)
            for line in findings:
                print(line)
            if findings:
                print(f"{len(findings)} finding(s)")
                return 1
            print("clean: freeze ↔ streams ↔ map ↔ evidence all hold")
            return 0
        if args.command == "status":
            print(render_status(authoring_status(book_dir, canonical_stream_id=stream_id)), end="")
            return 0
        if args.command == "stamp":
            path = stamp_evidence(
                book_dir, args.node, evidence=args.evidence, canonical_stream_id=stream_id
            )
            print(f"stamped {args.node} -> {path}")
            return 0
        if args.command == "explain":
            print(explain_evidence_drift(book_dir, args.node, canonical_stream_id=stream_id))
            return 0
        if args.command == "gate":
            smap = assert_authoring_integrity(book_dir, canonical_stream_id=stream_id)
            print(
                f"authoring gate: OK — freeze ↔ streams ↔ map ↔ evidence all hold "
                f"(map_revision {smap.map_revision}, {len(smap.projection.nodes)} nodes)"
            )
            return 0
    except EngineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
    except UnicodeDecodeError:
        # The documented S1.5 atom_store load gap (engine.errors module docstring): non-UTF-8
        # stream bytes still leak raw, and UnicodeDecodeError SUBCLASSES ValueError — the clause
        # below would otherwise mislabel a substrate fault as the caller-error exit 2 (delta
        # re-audit finding). Surface it raw until S1.5 wraps it.
        raise
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(f"unhandled command {args.command!r}")  # argparse makes this unreachable

