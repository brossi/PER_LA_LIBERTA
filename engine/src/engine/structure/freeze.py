"""S4.6-pre — the stream-freeze record: a committed hash pin over a book's persisted atom streams.

Why this exists (issue #31): canonical atom ids are **positional** (``canonical_NNNNN`` in capture
order), and the S4.6 hand-authored structure map references those ids *before* S5's re-bind
machinery exists. The book workspace is disposable (gitignored), so the durable pin is this small
committed record — one envelope hash per stream, the SAME producer value ``build_manifest`` stamps
into ``manifest.atom_streams[*].hash`` (never a re-implementation), plus each witness's
``source_hash`` anchor and the atom count. A capture change that renumbers or re-texts any stream
then reds the freeze tripwire (and later S8.1's stored-vs-live comparison) instead of silently
orphaning an authored map.

The record is a *pin*, not a governed pipeline layer: no stale class, no birth gate (S8.1 may
formalize it into the governance family later). It is also purely content-derived — no timestamp —
so regenerating unchanged streams is byte-idempotent and a no-drift regeneration is an empty git
diff. ``load_freeze_record`` holds the total load-boundary contract every persisted engine artifact
obeys (a valid record or :class:`~engine.errors.StaleArtifactError`), and ``write_freeze_record``
is deny-by-default: a differing committed pin is never overwritten silently, because the ids it
pins may already be load-bearing under an authored map.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from engine.errors import MissingInputError, StaleArtifactError
from engine.structure.artifacts import STREAM_FREEZE_SCHEMA_VERSION
from engine.structure.atom_store import CANONICAL, WITNESS, AtomStream
from engine.structure.atom_store import to_json as stream_envelope_json
from engine.structure.structure_map import _hash_canonical

# The per-entry fields assert_freeze_matches compares — each in its own right, so a hand-edited
# record cannot pass on the strength of the others (an atom_count tamper leaves the hash agreeing).
_ENTRY_FIELDS = ("kind", "atom_count", "envelope_hash", "source_hash")


def build_freeze_record(streams: Mapping[str, AtomStream], *, book: str) -> dict:
    """Assemble the freeze record over ``streams`` (id → stream), entries sorted by stream id.

    The envelope hash is THE manifest producer (D-S4-I): ``_hash_canonical`` over the persisted
    envelope (``atom_store.to_json``). A mapping key that contradicts its stream's own id would pin
    a lie, and an empty freeze would pin nothing — both are caller errors, refused here.
    """
    if not streams:
        raise ValueError("build_freeze_record: no streams to freeze — an empty pin protects nothing")
    entries = []
    for stream_id, stream in sorted(streams.items()):
        if stream_id != stream.stream_id:
            raise ValueError(
                f"build_freeze_record: mapping key {stream_id!r} contradicts the stream's own id "
                f"{stream.stream_id!r} — the record would pin an id save_stream never wrote"
            )
        entry: dict = {
            "id": stream_id,
            "kind": stream.kind,
            "atom_count": len(stream.atoms),
            "envelope_hash": _hash_canonical(stream_envelope_json(stream)),
        }
        if stream.kind == WITNESS:
            entry["source_hash"] = stream.source_hash
        entries.append(entry)
    return {
        "stream_freeze_schema_version": STREAM_FREEZE_SCHEMA_VERSION,
        "book": book,
        "streams": entries,
    }


def render_freeze_record(record: Mapping) -> str:
    """The record's canonical file form: stable indented JSON, newline-terminated."""
    return json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _malformed(path: Path, why: str) -> StaleArtifactError:
    return StaleArtifactError(f"stream-freeze record {path} is not loadable: {why}")


def load_freeze_record(path: Path) -> dict:
    """Load a committed freeze record — total contract: a valid record,
    ``MissingInputError`` (absent, not stale — the taxonomy every persisted engine artifact
    shares), or ``StaleArtifactError`` (present but unloadable).

    Validates the registered ``stream_freeze_schema_version``, the required top-level keys, and
    each entry's required fields (witness entries must carry their ``source_hash`` anchor).
    """
    path = Path(path)
    if not path.is_file():
        raise MissingInputError(f"stream-freeze record not found at {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise _malformed(path, f"unreadable ({exc})") from exc
    except UnicodeDecodeError as exc:
        raise _malformed(path, f"not valid UTF-8 ({exc})") from exc
    try:
        doc = json.loads(text)
    except RecursionError as exc:
        raise _malformed(path, "not valid JSON (nested beyond parseable depth)") from exc
    except ValueError as exc:
        raise _malformed(path, f"not valid JSON ({exc})") from exc
    if not isinstance(doc, dict):
        raise _malformed(path, f"top level is {type(doc).__name__}, not an object")
    version = doc.get("stream_freeze_schema_version")
    if version != STREAM_FREEZE_SCHEMA_VERSION:
        raise _malformed(
            path,
            f"stream_freeze_schema_version {version!r} is not the registered "
            f"{STREAM_FREEZE_SCHEMA_VERSION} — stale record; regenerate consciously",
        )
    for key in ("book", "streams"):
        if key not in doc:
            raise _malformed(path, f"required key {key!r} missing")
    if not isinstance(doc["streams"], list) or not doc["streams"]:
        raise _malformed(path, "'streams' must be a non-empty array")
    for entry in doc["streams"]:
        if not isinstance(entry, dict):
            raise _malformed(path, "a stream entry is not an object")
        for key in ("id", "kind", "atom_count", "envelope_hash"):
            if key not in entry:
                raise _malformed(path, f"stream entry {entry.get('id')!r} is missing {key!r}")
        if entry["kind"] not in (WITNESS, CANONICAL):
            raise _malformed(path, f"stream {entry['id']!r} has unknown kind {entry['kind']!r}")
        if entry["kind"] == WITNESS and "source_hash" not in entry:
            raise _malformed(path, f"witness stream {entry['id']!r} carries no source_hash anchor")
    return doc


def assert_freeze_matches(record: Mapping, streams: Mapping[str, AtomStream]) -> None:
    """Hold live ``streams`` against a freeze ``record`` — fail loud listing **every** drifted stream.

    Raises ``StaleArtifactError`` naming each stream that is missing, extra, or whose frozen fields
    (kind, atom count, envelope hash, witness source anchor) no longer match the live capture. A
    red here means the frozen substrate an authored map references has drifted — refresh the freeze
    consciously and re-verify the map, never re-pin silently.
    """
    live = {e["id"]: e for e in build_freeze_record(streams, book=str(record.get("book")))["streams"]}
    frozen = {e["id"]: e for e in record["streams"]}
    problems = []
    for sid in sorted(frozen.keys() - live.keys()):
        problems.append(f"stream {sid!r}: frozen in the record but absent from the live streams")
    for sid in sorted(live.keys() - frozen.keys()):
        problems.append(f"stream {sid!r}: live but not in the freeze record")
    for sid in sorted(frozen.keys() & live.keys()):
        for field in _ENTRY_FIELDS:
            f_val, l_val = frozen[sid].get(field), live[sid].get(field)
            if f_val != l_val:
                problems.append(f"stream {sid!r}: {field} drifted (frozen {f_val!r} != live {l_val!r})")
    if problems:
        raise StaleArtifactError(
            "stream freeze mismatch — the frozen substrate has drifted:\n  " + "\n  ".join(problems)
        )


def write_freeze_record(path: Path, record: Mapping, *, force: bool = False) -> Path:
    """Write the committed pin — deny-by-default against overwriting a *different* record.

    Identical bytes are an idempotent no-op (re-running a no-drift freeze churns nothing). A
    differing existing record is refused without ``force=True``: the pinned ids may already be
    load-bearing under an authored structure map, so replacing them is explicit human intent, not
    a side effect. The record is rendered before any disk mutation.
    """
    rendered = render_freeze_record(record)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == rendered:
            return path
        if not force:
            raise StaleArtifactError(
                f"{path} already holds a different freeze record — refusing the silent overwrite. "
                "An authored structure map may reference the pinned ids; pass force=True only "
                "after verifying the drift is intentional and re-verifying any authored map"
            )
    path.write_text(rendered, encoding="utf-8")
    return path
