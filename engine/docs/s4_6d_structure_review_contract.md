# S4.6d preregistration — evidence-bound structure review

**Issue:** #93  
**Status:** preregistered before implementation  
**Date:** 2026-07-19  
**Scope:** engine-owned read packet and guarded single-container evidence stamp for a separate
Book Review Workbench

## 1. Purpose and authority

S4.6 structure authoring needs a visual surface, but the browser is not an authority boundary.
The engine remains authoritative for the frozen atom substrate, structure-map semantics,
authoring-evidence findings, source locks, staleness, and durable evidence writes. The Workbench
owns presentation, navigation, notes, holds, and its operational history. The repositories remain
separate and communicate only through canonical JSON emitted by `engine.review_api` and guarded
single-item commands.

Version 1 is a **review-and-stamp** slice. It exposes every human-minted container in map reading
order, enough bounded context to judge it, and the exact status already computed by the S4.6
authoring producer. It cannot edit `structure_map.json`, bulk-stamp evidence, turn a Workbench note
into evidence, or make an advisory observation authoritative.

The terminal authoring commands remain an independent validation and recovery path. The packet and
CLI share one read model; neither independently walks or interprets the projection.

## 2. Load order and required inputs

Every build and write attempt starts from the book directory and runs the established
substrate-first authoring load:

1. load the committed stream-freeze record and bind its `book` to the directory;
2. load all persisted streams and validate their native integrity;
3. compare every live stream with the freeze pin;
4. load and Tier-1/Tier-2 validate the structure map;
5. load authoring evidence when present, otherwise represent the first-class all-missing state;
6. load each configured optional review adjunct through its own strict loader.

The freeze, streams, and structure map are required. Missing or stale required inputs fail through
their existing typed errors; no packet is emitted. Missing authoring evidence is not an artifact
error because an unstamped draft is a valid authoring state. Optional observation, flag, or visual
inputs use the absence vocabulary in section 7 and are never silently omitted.

## 3. Packet identity and canonical bytes

The persisted/machine-facing artifact is `structure-review-packet` schema version 1, stale class
`structure-review-packet`, policy `structure-review-packet-v1`, and renderer
`structure-review-json-v1`.

Its identity records:

- book and canonical stream id;
- packet schema, policy, and renderer ids;
- structure-map schema version, canonical-file SHA-256, map revision, and root id;
- freeze schema version, canonical-file SHA-256, and its ordered stream records;
- authoring-evidence availability plus schema version and canonical-file SHA-256 when present;
- structural-observation availability plus schema, policy, and canonical-file SHA-256 when present;
- review-flag availability plus schema, producer, and canonical-file SHA-256 when present; and
- every visual source/artifact descriptor and its exact source or rendered-byte lock.

All hashes are lowercase SHA-256 over the exact bytes read from disk unless a field explicitly says
it hashes a canonical JSON payload. Paths are POSIX paths relative to an explicitly named packet
asset root and must resolve beneath that root after symlink resolution. Host-absolute paths,
timestamps, reviewer identity, and Workbench database state are absent.

The packet is canonical UTF-8 JSON: sorted object keys, two-space indentation, no ASCII escaping,
one trailing newline, and no non-finite numbers. Arrays preserve their registered semantic order.
Equal inputs produce byte-identical output. `packet_sha256` is SHA-256 over the canonical packet
with that one field omitted.

The strict loader performs schema validation, genuine-integer checks, packet-hash reproduction,
unique-id checks, cross-reference checks, item-fingerprint reproduction, containment, and live
artifact hash checks. A malformed, escaping, missing, or hash-mismatched referenced artifact is a
stale packet, never a partial current packet.

## 4. Shared node-inspection model

One immutable read model serves both `authoring inspect` (#44) and packet assembly. It derives a
projection index once and exposes:

- lookup by exact node id;
- lookup by exact atom id through its owning slot;
- Unicode NFKC/casefolded substring search over designation/title;
- class counts;
- parent and ordered child ids;
- preceding/following **human container** in map reading order;
- compact root-to-node hierarchy; and
- the node's aliases, effective/stored handle inputs, own slots, and bounded atom views.

Parent links, atom ownership, and neighbor order are computed once per loaded map. Unknown node or
atom queries fail nonzero; a heading search may return several explicit matches. The CLI renderer
and packet serializer consume this model rather than reproducing traversal logic.

### 4.1 Bounded atom views

The item contains complete atom ids for each of its own atom slots, because those ids are the
boundary being judged. Descendant extent can be large, so v1 publishes a deterministic summary:

- total atom count and first/last atom id;
- at most the first 12 and last 12 extent atoms, without duplication when the extent is shorter;
- for each published atom: id, literal text bounded to 500 Unicode code points, source witness,
  raw source hash/span, page range, processing scope, derivation addresses, and geometry state;
- truncation booleans and original text length whenever literal text is clipped.

The canonical stream is the text source for canonical atom ids. A referenced own/extent atom that
cannot resolve is an invariant failure, not an absent preview. Bounded display does not alter the
decision/extent payloads or digests used by the authoring gate.

## 5. Authoring status and evidence

Per-container evidence state comes from the same node-attributed findings core used by
`authoring status` and `evidence_findings`; it is not re-derived from packet fields or parsed from
diagnostic prose.

An item carries the ordered subset of `missing`, `stale-decision`, and `stale-extent` applicable to
that live human container. No kinds means `fresh`. The current entry, when present, supplies its
evidence prose, authored revision, decision digest/payload, and extent digest/payload. `orphaned`
and `misbound` entries have no valid live human-container item; they remain packet-level anomalies
with their existing messages. This preserves the established finding vocabulary and ordering.

## 6. Item review fingerprint and write conflict

Every item has `review_fingerprint_policy: structure-review-item-v1` and a
`review_fingerprint`. The digest is SHA-256 over canonical compact JSON of exactly these item
regions, with the fingerprint field itself omitted:

- stable node identity and displayed map decision fields;
- hierarchy, neighbors, aliases, slots, and bounded atom views;
- the live decision and extent payloads used by evidence freshness;
- that node's evidence state and current evidence entry;
- flags associated with that node and their live lifecycle state;
- observations associated with that node, including source identity and locator; and
- visual descriptors shown for that node.

Packet-global artifact hashes, other items, packet anomalies, unmatched/ambiguous observations,
and evidence entries for other nodes are deliberately excluded. Therefore an evidence stamp on an
unrelated node changes the global evidence artifact hash and packet hash for audit, but does not
change this item's fingerprint. A relevant map, observation, flag, or visual change does.

The guarded write accepts exactly `book`, `node_id`, `review_fingerprint`, and non-blank evidence
prose (plus a source identity only if a future packet version marks it required). It reloads every
input, rebuilds the target item, and constant-time compares the submitted fingerprint before any
write. Mismatch raises the typed stale/conflict error used by the Workbench adapter and writes
nothing. A match calls the existing `stamp_evidence` path for exactly one human container. Success
is returned only after reloading the sidecar and confirming that the target has no evidence
finding. No bulk operation exists.

## 7. Optional-input and visual absence semantics

Every optional adjunct is represented with exactly one state:

- `available`: the referenced artifact was loaded, validated, contained, and hash-checked;
- `unavailable`: it is relevant but no registered current artifact can be supplied; `reason` is
  required;
- `not_applicable`: the artifact kind does not apply to this source/item; `reason` is required.

Only `available` carries an artifact descriptor. Absence is never represented as an empty path,
zero hash, omitted witness, or synthetic blank image. One unavailable witness remains independently
visible and cannot masquerade as cross-witness agreement.

A visual-source registration names a source id, kind, packet asset root, contained relative path,
source SHA-256/byte length, page-numbering convention, and media type. A derived page image or crop
additionally binds the source id/hash, page, renderer id/version, render parameters, pixel
dimensions, contained output path, and output SHA-256/byte length. OCR overlays bind their OCR
source/report and coordinate space. The Workbench may serve only an `available` descriptor after
rechecking containment and bytes.

The two PLL PDFs and historical HTML audit sheets are not packet evidence merely because they
exist. They become available only through a committed registration satisfying this section.
Historical sheets are UX references, never durable evidence or writable review state.

## 8. Observation association

S4.6c reports remain factual and `unverified: true`. Packet policy
`structure-observation-association-v1` associates expectations, not individual fuzzy text:

1. normalize the expectation literal and every live human container's non-blank designation/title
   using NFKC, casefold, and runs of Unicode non-alphanumeric characters collapsed to one space;
2. collect live containers with an **exact normalized equality** to either label;
3. exactly one candidate associates that expectation's ordered sightings and summaries to it;
4. zero candidates yields packet-level `unmatched` with the expectation id; and
5. more than one yields packet-level `ambiguous` with all candidate node ids in map order.

An ambiguous or unmatched expectation contributes to no item's fingerprint. There is no fuzzy,
page-proximity, atom-proximity, language-specific, hierarchy-role, or first-match fallback. A
sighting's source id, literal window, adjacent context, locator, locus features, interpretation,
and `unverified: true` survive unchanged. Association is advisory and cannot stamp or mutate.

## 9. Seeder-flag lifecycle

Legacy stdout strings are not a durable read contract. V1 admits an optional strict
`structure-review-flags` artifact whose producer emits stable flag ids and seed bindings at draft
construction time. Each record contains:

- flag id, producer id, immutable message and kind;
- zero or one target node id plus any cited atom ids;
- the target's seed decision/extent payload hashes when bound;
- resolution posture: `correction-required` or `review-required`; and
- zero or more observation ids that corroborate, but do not resolve, the warning.

The packet derives, never hand-accepts, one live state:

- `applicable`: the bound node exists and both seed hashes still equal live payload hashes;
- `superseded`: the bound node is absent or either live payload hash differs after human editing;
- `unresolved`: an unbound flag or a correction-required flag whose required correction has no
  registered deterministic completion predicate; or
- `corroborated`: the warning remains applicable/unresolved and at least one declared current
  observation id is present. The base state is retained alongside `corroborated`.

Corroboration never means resolved. A fresh reseed cannot overwrite or silently rebind the flag
artifact. If a legacy map has no committed flag artifact, flags are `unavailable` with a migration
reason; the seeder may generate a candidate migration only when its reconstructed draft identity is
explicitly checked against the registered seed identity. No flag affects the evidence gate,
automatically changes the map, or generates evidence prose.

## 10. Machine bridge

`engine.review_api` adds JSON-only operations equivalent to:

- `structure-packet --book-dir … [--asset-root …]`: build and emit the current packet;
- `record-structure-evidence --book-dir … --node … --review-fingerprint … --evidence …`:
  perform the guarded single-node stamp and emit refreshed target state.

Machine output is one canonical JSON document on stdout. Diagnostics go to stderr. Existing typed
engine exit codes are retained. Invalid caller syntax/value uses exit 2. The page-verdict operation
and its wire contract remain unchanged.

## 11. Red-first verification matrix

Before v1 is considered stable, tests must pin:

1. Generic non-PLL node, atom, heading, class-count, hierarchy, neighbor, alias, and handle
   inspection, including unknown and ambiguous queries.
2. CLI and packet consume identical inspection values from the shared model.
3. Missing/stale required substrate fails before packet output.
4. Missing evidence produces the existing all-missing states, not an artifact failure.
5. Schema/loader rejection of unknown fields, false integers, malformed ids/hashes, duplicate ids,
   incoherent references, wrong packet hash, and wrong item fingerprint.
6. Exact observation association, plus visible unmatched and ambiguous cases; no fuzzy association.
7. Visual path traversal, symlink escape, missing bytes, hash mismatch, wrong dimensions/metadata,
   and one-witness absence all fail or remain explicitly unavailable as registered.
8. Bounded atom excerpts are deterministic and report truncation without changing extent payloads.
9. Equal input renders byte-identically with stable map reading order.
10. Packet item status exactly equals the established attributed-finding producer for fresh,
    missing, stale-decision, and stale-extent; orphaned/misbound remain exact packet anomalies.
11. Applicable, superseded, unresolved, and corroborated flag states reproduce deterministically.
12. A relevant node/map/observation/flag/visual change changes that item fingerprint.
13. Stamping a different node changes global packet identity but not the unchanged item's
    fingerprint.
14. A stale submitted fingerprint returns typed conflict and leaves evidence bytes unchanged.
15. A valid submission changes exactly one evidence entry through the existing writer and returns
    the node fresh.
16. No bulk stamp, direct map-write command, Workbench dependency, FastAPI/Jinja import, PLL
    literal, language rule, fixed node count, page number, or hierarchy special case exists in the
    generic mechanism.
17. The live PLL packet lists all 61 human containers and exposes every registered applicable
    flag, associated observation, and available visual source without engine UI code.

## 12. Delivery boundary

Implementation proceeds contract-first, then shared inspection, strict packet read path, visual
registration, guarded write, and generic/PLL verification. Once the read packet is stable, its
fixture and schema are handed to Book Review Workbench #2 before engine writes are added, allowing
the two repositories to alternate against a frozen contract instead of completing in isolation.

