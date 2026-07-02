"""Persisted structure-substrate artifacts: where each lives in the work tree, and the
independent schema version each carries.

The document-structure substrate writes three durable artifacts under a book's
``BookWorkspace`` (``books/<id>/work/``), one per layer of the L1→L2→L3 model
(ENGINE_STRUCTURE_PLAN §3.2):

- **atom store** — per-witness + canonical L1 atom streams, under ``data/atoms/*.json`` (§11.1);
- **structure map** — B's durable container/projection catalogue, ``structure_map.json`` at the
  work root (§11.2);
- **relation store** — the L3 graph + cross-language alignment, ``relations.json`` at the work
  root (§11.3).

Each layer is **independently versioned**: a schema change to one does not bump the others, so a
lineage stale-check can name *which* layer changed and route the right migration — three distinct
stale classes (ENGINE_STRUCTURE_TASKS M3; the stores land in S1.5 / S4.4 / S7.1c). This module is
the S0.1 skeleton: it fixes the locations and the version constants now; the stores, JSON schemas,
and lineage manifest that read them arrive with those later tasks.

Beyond the three persisted layers, this module also carries the **resource + normalization-policy
lineage** constants (S3.0): a schema version and two further stale classes (``resource-set``,
``normalization-policy``) that version the *inputs* — the profile-declared dictionaries and the
pre-lookup fold policy — rather than a persisted layer. They have no work-tree location of their
own; the lineage record holding them is embedded in the structure-map header (S4.4) and routed by
governance (S8.1) as repairs distinct from any layer's.

Engine-agnostic by construction: artifact *names* and *layout* only — no language, ordinal, or
book-structure opinion (the recognizer and the structure profile carry that, never this core).
"""

from __future__ import annotations

from pathlib import Path

from engine.paths import BookWorkspace

# --- schema versions (independent per persisted layer — M3) ----------------------------- #

#: L1 atom-store schema version (per-witness + canonical streams). Bound by S1.5.
ATOM_STORE_SCHEMA_VERSION = 1
#: The L1 atom-store stale class — the M3 stale-class identifier the lineage governance (S8.1) routes
#: on, and the discriminator a persisted stream's envelope declares so a load can reject a file that
#: is structurally JSON but not an atom store. Distinct from the structure-map (B) and relation-store
#: (C) classes, so a schema change to one names *which* layer changed (§3.6). Bound by S1.5.
ATOM_STORE_STALE_CLASS = "atom-stream"
#: L2 structure-map schema version (containers/projections + lineage manifest). Bound by S4.4.
STRUCTURE_MAP_SCHEMA_VERSION = 1
#: The L2 structure-map stale class — the M3 discriminator the lineage manifest stamps and S8.1
#: routes on, so a structure-map schema change names *this* layer (not the atom store or relation
#: store). A distinct wire string from every other stale class (inv 12a). Built at S4.0; stamped
#: into the manifest at S4.4.
STRUCTURE_MAP_STALE_CLASS = "structure-map"
#: L3 relation-store schema version (graph + cross-language alignment). Bound by S7.1c.
RELATION_STORE_SCHEMA_VERSION = 1
#: The L3 relation-store stale class — pre-placed **inert** in S4.0 (O1/D-S4-F): it declares a
#: future layer identity, *not* the existence of a relation schema, reader, or artifact. No
#: relation-store loader is exported from ``engine.structure`` until S7.1c, and every S4-era manifest
#: example pins the relation layer ``present: false``. A distinct wire string from every other stale
#: class (inv 12a). Bound by S7.1c.
RELATION_STORE_STALE_CLASS = "relation-store"

# --- structure-map schema birth status (S4.0 / §1.2.2) ---------------------------------- #

#: The two lifecycle states a structure-map schema *version* can occupy. ``provisional``: the schema
#: shape exists but is not yet proven to generalize beyond the first book; ``born``: S4.5's
#: differ-fixture (a *conforming* non-PLL-shaped map) has validated against it. This lifecycle is a
#: property of the schema version, tracked here beside the version constant — it never persists in
#: any map file (Audit 2).
SCHEMA_STATUS_PROVISIONAL = "provisional"
SCHEMA_STATUS_BORN = "born"
#: ``{structure-map schema version → birth status}``. A version stays ``provisional`` until S4.5's
#: differ-fixture test flips it (a human edit to this literal, bound by inv 23); a version bump
#: (e.g. S6's role/authorship addition) re-enters ``provisional`` and needs its own birth gate. The
#: born-gate ``assert_schema_born()`` (S4.4) reads this map, and a *missing* key is fail-safe
#: (treated as ``provisional`` → raise). Nothing here makes ``load_structure_map`` born-aware — that
#: loader is deliberately born-agnostic (§1.2.3); the gate is a separate call.
#:
#: **Version 1 flipped ``born`` at S4.5/B-6 (2026-07-02):** the hand-authored D18 differ-fixture
#: (``tests/fixtures/structure/differ_structure_map.json`` — depth-0 body, designation-string
#: policy, non-ordinal headings, interleaved segmentation) shape- and semantically-validated
#: through the born-agnostic ``load_structure_map`` (``test_structure_born_gate.py``, inv 23's two
#: unconditional asserts). The schema is thereby proven to generalize beyond PLL (§1.2.1).
STRUCTURE_MAP_SCHEMA_STATUS: dict[int, str] = {STRUCTURE_MAP_SCHEMA_VERSION: SCHEMA_STATUS_BORN}

# --- resource + normalization-policy lineage (S3.0) ------------------------------------- #

#: Schema version of the resource/normalizer lineage record (``ResourceLineage`` — structure/lineage.py).
#: Independent of the three persisted-layer versions above: S4.4 embeds this record in the
#: structure-map header, and a change to its shape bumps only this constant. Bound by S3.0.
RESOURCE_LINEAGE_SCHEMA_VERSION = 1
#: Stale class for the *resource set* — the frequency dictionary + the period dictionaries resolved
#: through the language profile. A content change (member swap/add/remove, re-OCR, ``oracle_min``)
#: trips this class so the lineage governance (S8.1) routes the *re-segment* repair. Distinct from
#: the normalizer class below and from every persisted-layer class. Bound by S3.0.
RESOURCE_STALE_CLASS = "resource-set"
#: Stale class for the *normalization policy* — the pre-lookup fold (case + accent) built from the
#: profile. A policy change trips this class so S8.1 routes the *re-derive offsets* repair, a
#: different migration from a resource swap (§3.6). Distinct from the resource class above and from
#: every persisted-layer class. Bound by S3.0.
NORMALIZER_STALE_CLASS = "normalization-policy"

#: Schema version of the stream-freeze record (``structure/freeze.py`` — S4.6-pre): the committed
#: per-book pin over the persisted atom streams' envelope hashes, the id-stability substrate a
#: hand-authored structure map references before S5's re-bind exists. A *pin*, not a governed
#: pipeline layer — it carries no stale class and no birth gate (S8.1 may formalize it into the
#: governance family later); ``load_freeze_record`` still validates this version at the load
#: boundary like every persisted engine artifact.
STREAM_FREEZE_SCHEMA_VERSION = 1

# --- fixed work-tree locations ---------------------------------------------------------- #

#: Workspace area + subdirectory the L1 atom streams live under (``<work>/data/atoms/``).
ATOMS_AREA = "data"
ATOMS_SUBDIR = "atoms"
#: Work-root filenames for the durable catalogue (B) and the relation graph (C). These sit at
#: the work root, not under an area, by design (§11.2/§11.3) — the top-level book artifacts.
STRUCTURE_MAP_FILENAME = "structure_map.json"
RELATIONS_FILENAME = "relations.json"
#: Where the regen-guarded writer (S4.4, s4_plan §3.E.8) snapshots the superseded structure map
#: before its licensed overwrite — one immutable ``structure_map.rev{N}.json`` per superseded
#: ``map_revision``, beside the live map at the work root.
STRUCTURE_MAP_SNAPSHOT_DIRNAME = "structure_map.snapshots"


def atoms_dir(workspace: BookWorkspace) -> Path:
    """Directory holding the L1 atom streams (``<work>/data/atoms/``), containment-checked.

    Returns the path only; creating it is the atom store's job (S1.5), as with every other
    workspace path accessor.
    """
    return workspace.resolve(ATOMS_AREA, ATOMS_SUBDIR)


def structure_map_path(workspace: BookWorkspace) -> Path:
    """Path to the durable structure map (``<work>/structure_map.json``)."""
    return workspace.resolve_root(STRUCTURE_MAP_FILENAME)


def structure_map_snapshot_path(workspace: BookWorkspace, revision: int) -> Path:
    """Path to the pre-overwrite snapshot of the superseded map at ``map_revision == revision``
    (``<work>/structure_map.snapshots/structure_map.rev{revision}.json``), containment-checked.

    Returns the path only; creating the directory (and refusing to clobber an existing snapshot)
    is the regen-guarded writer's job (``structure_map.write_structure_map``, s4_plan §3.E.8).
    """
    return workspace.resolve_root(STRUCTURE_MAP_SNAPSHOT_DIRNAME, f"structure_map.rev{revision}.json")


def relations_path(workspace: BookWorkspace) -> Path:
    """Path to the relation store (``<work>/relations.json``)."""
    return workspace.resolve_root(RELATIONS_FILENAME)
