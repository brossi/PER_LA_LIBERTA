"""``engine.structure`` — the document-structure substrate (concerns A/B/C, three layers).

A book/language-agnostic model of document structure: L1 immutable addressed atoms → L2
versioned block projections (the durable ``node_id`` catalogue) → L3 spans / relations /
cross-language alignment (ENGINE_STRUCTURE_PLAN §2–§3). The core here carries **no** language,
ordinal, or book-structure literal — heading grammar, matter labels, and numbering are data in
the structure profile + the per-book structure map, never code (invariant I4; the S0.2 neutrality
guard makes that a standing assertion). The atom/projection models, the recognizer, the persisted
stores, and governance land milestone by milestone (ENGINE_STRUCTURE_TASKS S1–S11); this package
is the S0.1 skeleton — the schema-version constants and the fixed artifact locations everything
else pins to.
"""

from __future__ import annotations

from engine.structure.artifacts import (
    ATOM_STORE_SCHEMA_VERSION,
    ATOM_STORE_STALE_CLASS,
    ATOMS_AREA,
    ATOMS_SUBDIR,
    AUTHORING_EVIDENCE_FILENAME,
    AUTHORING_EVIDENCE_SCHEMA_VERSION,
    AUTHORING_EVIDENCE_STALE_CLASS,
    NORMALIZER_STALE_CLASS,
    RELATION_STORE_SCHEMA_VERSION,
    RELATION_STORE_STALE_CLASS,
    RELATIONS_FILENAME,
    RESOURCE_LINEAGE_SCHEMA_VERSION,
    RESOURCE_STALE_CLASS,
    SCHEMA_STATUS_BORN,
    SCHEMA_STATUS_PROVISIONAL,
    STRUCTURE_MAP_FILENAME,
    STRUCTURE_MAP_SCHEMA_STATUS,
    STRUCTURE_MAP_SCHEMA_VERSION,
    STRUCTURE_MAP_STALE_CLASS,
    atoms_dir,
    authoring_evidence_path,
    relations_path,
    structure_map_path,
)
from engine.structure.errors import EC, StructureValidationError
from engine.structure.projection import (
    ContainerNode,
    FurnitureAtom,
    LeafNode,
    Node,
    ProjectionMap,
    mint_node_id,
    validate_projection,
)
from engine.structure.handles import (
    Alias,
    render_handle,
    resolve,
)
from engine.structure.structure_map import (
    StreamAtomReader,
    StructureMap,
    assert_schema_born,
    build_manifest,
    load_structure_map,
    render_structure_map,
    schema_version_const,
    validate_structure_map,
    workspace_reader,
    write_structure_map,
)
from engine.structure.evidence import (
    AuthoringEvidence,
    EvidenceEntry,
    assert_evidence_gate,
    evidence_schema_version_const,
    load_authoring_evidence,
    node_structure_digest,
)
from engine.structure.atom_store import (
    CANONICAL,
    WITNESS,
    AtomStream,
    assert_atom_hashes,
    assert_reference_integrity,
    assert_stream_roundtrip,
    load_stream,
    load_workspace_streams,
    save_stream,
    stream_ids,
    stream_path,
)
from engine.structure.atoms import (
    PROCESSING_SCOPE_EXCLUDED,
    PROCESSING_SCOPE_INCLUDED,
    Atom,
    AtomDerivation,
    Geom,
    duplicate_atom_ids,
)
from engine.structure.capture import (
    PAGE_UNMAPPED,
    align_streams,
    assert_capture_tiles,
    build_canonical,
    capture_witness,
    marker_page_binding,
)
from engine.structure.freeze import (
    assert_freeze_matches,
    build_freeze_record,
    load_freeze_record,
    render_freeze_record,
    write_freeze_record,
)
from engine.structure.classify import (
    DEGENERATE_CLASSIFIER_NAME,
    UNKNOWN,
    BlockClassification,
    BlockClassifier,
    DegenerateBlockClassifier,
)
from engine.structure.roundtrip import (
    ReversibleTransform,
    apply_forward,
    apply_inverse,
    hash_raw,
    is_reversible,
    reconstruct_raw,
    verify_atom_roundtrip,
)
from engine.structure.roundtrip_gate import (
    DEFAULT_MIN_INCLUDED_FRACTION,
    GapRecord,
    assert_no_wholesale_exclusion,
    assert_production_roundtrip,
    gap_records,
    reconstruct_source,
)
from engine.structure.typed import (
    CompletenessReport,
    ReviewItem,
    TypedAtom,
    check_completeness,
    typed_projection,
)

__all__ = [
    "ATOM_STORE_SCHEMA_VERSION",
    "ATOM_STORE_STALE_CLASS",
    "STRUCTURE_MAP_SCHEMA_VERSION",
    "RELATION_STORE_SCHEMA_VERSION",
    # S4.0 — structure-map + relation-store stale classes; schema birth-status map; EC code set
    "STRUCTURE_MAP_STALE_CLASS",
    "RELATION_STORE_STALE_CLASS",
    "SCHEMA_STATUS_PROVISIONAL",
    "SCHEMA_STATUS_BORN",
    "STRUCTURE_MAP_SCHEMA_STATUS",
    "EC",
    # S4.1 — L2 projection model (concern B): nodes + flat map + per-module validator + carrier error
    "Node",
    "ContainerNode",
    "LeafNode",
    "FurnitureAtom",
    "ProjectionMap",
    "validate_projection",
    "StructureValidationError",
    # S4.2 — node_id identity + minting split (mint_node_id seam; minted_by/designation/title fields)
    "mint_node_id",
    # S4.3 — handle policy + rendered handles + alias records (render_handle/resolve; Alias record)
    "Alias",
    "render_handle",
    "resolve",
    # S4.4 — structure_map.json schema + loader + manifest + born-gate + regen-guarded writer
    "StructureMap",
    "StreamAtomReader",
    "validate_structure_map",
    "load_structure_map",
    "write_structure_map",
    "render_structure_map",
    "build_manifest",
    "schema_version_const",
    "assert_schema_born",
    # S3.0 — resource + normalization-policy lineage constants
    "RESOURCE_LINEAGE_SCHEMA_VERSION",
    "RESOURCE_STALE_CLASS",
    "NORMALIZER_STALE_CLASS",
    "ATOMS_AREA",
    "ATOMS_SUBDIR",
    "STRUCTURE_MAP_FILENAME",
    "RELATIONS_FILENAME",
    "atoms_dir",
    "structure_map_path",
    "relations_path",
    # S1.1 — L1 atom model (concern A capture)
    "Atom",
    "Geom",
    "AtomDerivation",
    "duplicate_atom_ids",
    "PROCESSING_SCOPE_INCLUDED",
    "PROCESSING_SCOPE_EXCLUDED",
    # S0.4 — block-classifier seam (concern A typing)
    "BlockClassifier",
    "BlockClassification",
    "DegenerateBlockClassifier",
    "UNKNOWN",
    "DEGENERATE_CLASSIFIER_NAME",
    # S1.2 — raw/normalized round-trip floor (concern A capture)
    "hash_raw",
    "reconstruct_raw",
    "ReversibleTransform",
    "apply_forward",
    "apply_inverse",
    "is_reversible",
    "verify_atom_roundtrip",
    # S1.3a — raw addressed capture (per-witness streams + canonical projection)
    "capture_witness",
    "build_canonical",
    "align_streams",
    "assert_capture_tiles",
    "PAGE_UNMAPPED",
    "marker_page_binding",
    # S1.4 — production round-trip gate (explicit gaps + whole-artifact byte-exactness)
    "GapRecord",
    "gap_records",
    "reconstruct_source",
    "assert_no_wholesale_exclusion",
    "assert_production_roundtrip",
    "DEFAULT_MIN_INCLUDED_FRACTION",
    # S1.3b — typed projection over the raw atoms (concern A typing + completeness)
    "TypedAtom",
    "typed_projection",
    "ReviewItem",
    "CompletenessReport",
    "check_completeness",
    # S1.5 — persisted atom store (per-witness + canonical streams, versioned + integrity-checked)
    "AtomStream",
    "WITNESS",
    "CANONICAL",
    "save_stream",
    "load_stream",
    "stream_path",
    "stream_ids",
    "assert_stream_roundtrip",
    "assert_atom_hashes",
    "assert_reference_integrity",
    # S4.6-pre — the committed stream-freeze pin (id-stability substrate for S4.6 authoring)
    "build_freeze_record",
    "render_freeze_record",
    "load_freeze_record",
    "write_freeze_record",
    "assert_freeze_matches",
    # S4.6a — authoring-evidence sidecar (engine half) + store-backed reader glue
    "AUTHORING_EVIDENCE_SCHEMA_VERSION",
    "AUTHORING_EVIDENCE_STALE_CLASS",
    "AUTHORING_EVIDENCE_FILENAME",
    "authoring_evidence_path",
    "EvidenceEntry",
    "AuthoringEvidence",
    "node_structure_digest",
    "load_authoring_evidence",
    "assert_evidence_gate",
    "evidence_schema_version_const",
    "load_workspace_streams",
    "workspace_reader",
]
