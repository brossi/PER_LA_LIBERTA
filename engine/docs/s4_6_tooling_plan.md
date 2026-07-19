# S4.6b — Authoring-loop tooling (plan)

Status: **RATIFIED 2026-07-02 (v2) — BUILT 2026-07-03** (issue #34; suite 1066+ green, mutation
hunt 36/36 killed, live demo run — see the tracker S4.6b row for the as-built record; per-DT
as-built notes inline where the build deviated in form, never in substance). DT-4 + DT-6 ratified
individually (user rulings recorded in place); DT-1/2/3/5/7/8 ratified as uncontested by user
directive same day ("Ratify the uncontested ones and start building"). Drafted against runway.md §3 item 3, s4_plan §1.4.1a (the
status-listing hook), and the tracker S4.6 row. v2 = DT-4 resolved by adopting alternative A′
(payload witnesses in the sidecar; the v1 baseline-resolution chain deleted) + DT-6 stamp command
ratified. Audit convention remains available for post-hoc review: `@@@@@@` blocks inline, paired
`======` responses.

Everything cited here was read or run this session: the evidence/freeze/structure_map/projection
surfaces, the frozen PLL canonical stream (4,786 atoms), the schema, the gitignore, and the
`freeze_streams.py` book-script precedent.

---

## §0 Scope and provenance

The S4.6 tracker row pins the authoring *workflow* (skeleton seeds candidates, evidence recorded,
embedded-letter placement pinned) but nothing owns the *mechanics*. This plan gives them an owner
and a tracker row (**S4.6b**, engine owner), sitting between S4.6a (`DONE`) and S4.6 (Ben authors
the map). Ratified scope (runway §3.3, five deliverables):

1. **candidate-map seeder** from the known PLL skeleton;
2. **validate-on-save runner** (the loader over the frozen streams, per-edit);
3. **freeze×evidence composite gate** — one command = "is this authored map trustworthy";
4. **digest-diff explainer** — WHICH children/atoms moved, not just hashes;
5. **non-raising status listing** consuming `evidence_findings()` (worklist view, kinds as columns).

Plus one addition, **ratified 2026-07-02** (DT-6): an **evidence stamp command** — the loop has
no ergonomic way to write a sidecar entry (the digests are 64-hex strings; hand-editing them is
not a workflow), and retrofitting it after authoring begins would mean Ben hand-assembling hashes
in the meantime — a downgrade, per the user's ruling.

**Substrate reality check (run this session).** All 4,786 canonical atoms are
`capture_provenance_class: body`. Heading-like atoms exist (`Capitolo Primo` …) but are noisy:
OCR-garbled ordinals (`Capitolo Qyarto`, `Capitolo Dccimoscttimo`), duplicate headings (running
heads / the end-matter index at `canonical_04743`+), and out-of-order sightings
(`Dodicesimo` at 00953 before `Undicesimo` at 00969). So the seeder is a **candidate generator
that abstains and flags**, never a recognizer — consistent with the ingestion-HITL premise
(D28/D29): low-confidence candidates route to the human worklist, they don't guess.

**Path reality check (run this session).** `structure_map.json` and `authoring_evidence.json`
resolve to the **work root** (`workspace.resolve_root`), and `.gitignore` masks only
`books/*/work/{data,output,state}/*` — `git check-ignore` confirms both files are committable.
The "committed companion" premise holds with no gitignore change.

## §1 The authoring loop (end-to-end)

```
seed (once)      books/per_la_liberta/seed_structure_map.py
                   → <work>/structure_map.json  rev 0, draft containers, full atom coverage
edit             Ben hand-edits the JSON (boundaries, titles, the Mazzini-letter placement)
validate         `authoring validate --book per_la_liberta [--watch]`
                   → load_structure_map over workspace_reader; Tier-1+2 findings per edit
worklist         `authoring status --book per_la_liberta`
                   → per human-container evidence state; starts all-missing (~61 rows) = the TODO
verify + stamp   Ben verifies a container against the scans, then
                 `authoring stamp --book … --node n-… --evidence "…"`
drift            edit after stamping → stale-decision / stale-extent;
                 `authoring explain --book … --node n-…` names what moved
gate             `authoring gate --book per_la_liberta`
                   → freeze pin ↔ live streams ↔ map ↔ evidence, one command, exit 0 or typed
commit           the map + sidecar are committed at the book work root (the durable pair)
```

The draft map **fails the evidence gate by construction** until Ben has worked every container —
`missing` findings are the worklist, and the gate flipping green *is* S4.6 completion. No tooling
path stamps evidence in bulk (§5).

## §2 Deliverables and homes

| Id | Deliverable | Home | Surface |
|----|-------------|------|---------|
| T-1 | Seeder | `books/per_la_liberta/seed_structure_map.py` (book-side, `freeze_streams.py` precedent) | script `main()`; a pure `build_draft(streams) -> (doc, flags)` for the lockstep test |
| T-2 | Validate-on-save | `structure/authoring.py` + CLI `validate` (`--watch`, stdlib mtime poll) | `validate_authoring(book_dir)` (non-raising findings) |
| T-3 | Composite gate | `structure/authoring.py` + CLI `gate` | `assert_authoring_integrity(book_dir, *, canonical_stream_id="canonical")` |
| T-4 | Digest-diff explainer | `structure/authoring.py` + CLI `explain` | `explain_evidence_drift(book_dir, node_id)` (exact diff from the sidecar's stored payload witness, DT-4) |
| T-5 | Status listing | `structure/authoring.py` + CLI `status` | `authoring_status(book_dir)` → structured rows; CLI renders the table |
| T-6 | Stamp command (**ratified addition**, DT-6) | `structure/authoring.py` + CLI `stamp` | `stamp_evidence(book_dir, node_id, *, evidence)` |

New engine module: **`structure/authoring.py`** (one file, plus its `main()` argparse entry run as
`uv run python -m engine.structure.authoring <cmd> --book <id>`; *as built: a two-file package —
see the DT-1 as-built note*). Complexity justification
(Principle 2): the deliverables compose *across* the persisted layers (freeze + streams + map +
sidecar); homing them in any one layer module would invert its single-artifact ownership, and the
CLI is the HITL surface S4.6 runs on. `main()` stays module-internal; the five library functions
(plus DT-4's two payload producers — seven new names, §7) export via `engine.structure` with the
pin amended in the same commit.

Neutrality: `authoring.py` carries no book/language literal — everything book-shaped lives in the
seeder script. Verified: `test_structure_neutrality.py` walks the live package
(`STRUCTURE_SRC.rglob("*.py")`), so the new module enters the scan automatically; §4 row 19 still
proves it red once at build (plant a literal, watch the scan fire) rather than trusting the glob.

## §3 Decisions to ratify (DT-1 … DT-8)

**DT-1 — module home.** As §2: one new `structure/authoring.py`; no new dependency; no change to
`engine.cli` (the orchestrator stays the pipeline-step surface; authoring is a different audience).
*(As built 2026-07-03: shaped as a package — `structure/authoring/__init__.py` (the library,
same import surface) + a 3-line `__main__.py` — because the single-file form made ``python -m``
re-execute a module `engine.structure` had already imported: double execution plus a runpy
warning on every HITL invocation. Same command, same exports.)*

**DT-2 — CLI form.** `python -m engine.structure.authoring` with subcommands
`validate | status | stamp | explain | gate`, `--book` + `--books-dir` (default `engine/books`,
same resolution as `cli.py`). No new console script in `pyproject.toml` (can be added later as a
one-liner if the ergonomics warrant). Exit codes ride the existing `EngineError` machinery — the
gate exits 12 on evidence findings, 11 on map findings, the stale/missing codes otherwise.

**DT-3 — seeder posture.** Book-side entirely; composes only engine exports (`workspace_reader`,
`mint_node_id`, `build_manifest`, `render_structure_map`/`write_structure_map`). Draft semantics:

- Containers are `minted_by: human` (MINTED_BY_SPLIT requires it) with
  `decision: plugin-suggested` **written, never read** — the S4 gate keys on evidence only, so
  inv 25 (decision is inert; no S4 code reads it) is not breached. Ben may flip values to
  `human-approved` as bookkeeping while authoring; nothing in this tooling branches on it.
- Full coverage is mandatory (Tier-2 `UNOWNED_INCLUDED_ATOM`): the seeder buckets *every*
  canonical atom — front-matter (library stamps, atoms 0–88), the part/chapter spans, and the
  end-matter index — into container/leaf spans between heading candidates. `front_matter` and
  `index` containers come from the known skeleton (`chapter_start_pages.json` has front_matter
  already). *(As built: there is NO index container — segmenting the index off is a judgment
  call, not a match, so it abstains: the index rides inside the last chapter's span with an
  explicit flag, and Ben draws that boundary in the loop. And the skeleton source is
  `reconciled_chapters.json` + the manifest's declared `structure.parts` — the seeder never
  reads `chapter_start_pages.json`; its scan-page data adds nothing to atom-index boundaries.)*
- Heading candidates come from the frozen inputs (`reconciled_chapters.json`, 58 entries;
  part names/counts cross-checked against the book manifest) matched against atom text;
  **anomalies (duplicate, garbled, out-of-order ordinals) are emitted as a review-flags section
  in the seeder's stdout report and as node `title` markers, not silently resolved** — the
  abstain-don't-guess rule. *(As built, one addition the live substrate forced: a fuzzy match
  may never consume a candidate that exactly matches a DIFFERENT expected chapter's heading —
  without that guard, P2 ch22's genuinely-absent heading stole ch32's atom at ratio 0.94 and
  cascaded ten chapters into abstention.)*
- Re-seed protection: the first `write_structure_map` is unguarded (no map present); a re-run
  against an existing map hits `MAP_OVERWRITE_BLOCKED` with no escape — re-seeding after hand
  edits requires a human to delete the draft first. Deliberate; documented in the script header.

**DT-4 — explainer baselines (RATIFIED 2026-07-02: alternative A′ adopted — payload witnesses
in the sidecar).** The sidecar stores *digests*, which cannot be inverted, so "which
children/atoms moved" needs the pre-edit payload. Resolution: each evidence entry persists,
beside its two digests, a **payload witness** — the decision payload verbatim (children order is
meaningful, no sorting, no compression) and the extent payload with each sorted atom-id list
**run-length encoded** (a two-element array `["canonical_00089", "canonical_00102"]` is an
inclusive run; singletons stay plain strings — the mixed-type list is unambiguous to decode).

- **Digests stay authoritative and unchanged.** §1.4.1b's producers and payload shapes are
  untouched; the witness is explanation data, never attestation. The gate and
  `evidence_findings()` still compare digests only — no codec on the gate path.
- **Load-boundary self-verification.** `load_authoring_evidence` decodes each witness, recomputes
  the digest from it via THE producer, and a mismatch is `StaleArtifactError` naming the node —
  an internally incoherent sidecar fails its own load contract (the staleness-taxonomy line); it
  never degrades quietly. The sidecar is machine-written (DT-6's stamp), so a hand-edit that
  breaks coherence should red loudly, and the repair is one re-stamp.
- **Canonical codec, engine-neutral.** Maximal runs over the sorted list; a run forms only when
  two ids share a prefix and a same-width trailing decimal suffix with consecutive values — pure
  string mechanics, no id-scheme literal (ids that don't fit the pattern simply stay singletons).
  The encoder verifies `decode(encode(x)) == x` on every call; encoding is deterministic, so an
  unchanged re-stamp re-renders byte-identically. The codec lives private to `evidence.py`
  (entries hold *decoded* payloads in memory; `authoring.py` never touches the wire form).
  *(As built: `authoring` does reuse the codec read-only for DISPLAY — the explainer's `_fmt_ids`
  renders id sets in the same run form the wire uses, so the display can never disagree with
  what is stored; it never writes wire form. Two hardenings from the pre-commit delta re-audit:
  the run-expansion ceiling became a **document-wide cumulative decode budget** — per-run
  ceilings summed without bound, letting a 578-byte sidecar force a ~700 MB allocation before
  coherence could reject it — and the stored witnesses are **deep-frozen**
  (`MappingProxyType` + tuples; producers emit tuple interiors, identical canonical-JSON bytes,
  digests unchanged) so a consumer cannot mutate a witness out from under its digest.)*
- **Explainer consequence: exact diffs, always.** stale-decision names added/removed/reordered
  children and any class change; stale-extent names the atoms entering/leaving each own slot and
  the beneath union. The v1 baseline-resolution chain (snapshot auto-discovery, `--baseline`,
  degraded mode, revision-mismatch labeling) is **deleted from scope** — the stored witness
  supersedes all of it. The only non-diff outputs left are `missing`/`orphaned`/`misbound`, which
  have nothing to diff by definition.
- **Cost + governance, disclosed.** This reopens the just-ratified §1.4.1b document once,
  deliberately, inside the still-open free-edit window (no sidecar exists yet — the window closes
  when S4.6 authors the first one). `evidence.py`, `authoring_evidence.schema.json`, and their
  tests are re-opened: Rule A delta re-audit + an evidence mutation-hunt re-run are budgeted in
  §6, and s4_plan §1.4.1b is amended in the same commit (the Option B amendment precedent). The
  witness fields are **required** entry shape — no optional dialect; there is no legacy sidecar
  to accommodate.

**Alternatives considered (expanded 2026-07-02; ruling: A′ adopted, v1 chain rejected):**

- **A′ — range-encoded payloads stored beside the digests, self-verified — ADOPTED** (the
  resolution above). Because `body_atoms` are strictly ascending and near-contiguous, interval
  encoding collapses even the root's `beneath` union to a handful of runs — defusing the raw-size
  objection against naive payload storage (which was also overstated in v1: uncompressed would be
  ~0.4 MB, not megabytes; the real uncompressed cost is drowning the sidecar's reviewable prose
  in id dumps on every re-stamp diff). **Reversal record, for the audit trail:** v1 recommended
  against A′ on deferability (a later schema-v2 bump backfills fresh entries mechanically; stale
  entries need human re-verification anyway — that argument stands and is correct). It lost
  because it weighed the wrong axis: the capability's primary consumer is S4.6 *itself*, the very
  next milestone — with ~61 containers over a noisy substrate, stamps and boundary edits
  interleave, and re-verifying a 2-atom delta instead of re-reading a whole container's
  boundaries is load-bearing HITL economics across dozens of stale-explain cycles, not sugar.
  Deferring a capability past its primary consumer is a scheduling error. Adopting A′ also
  *deletes* the v1 baseline-resolution machinery (three-mode chain, revision-mismatch labeling),
  so net complexity is roughly a wash for strictly better output.
- **v1 recommendation — snapshot auto-discovery → `--baseline` (git history) → degraded honest
  mode — REJECTED.** Workable and storage-free, but exact diffs become contingent on external
  state (snapshots don't exist until the first CAS supersede — i.e., not during initial
  authoring) and on git discipline, with per-use friction (commit, extract, point) recurring in
  the loop's hottest phase.
- **Git-aware baseline resolution** (`--baseline git:<rev>` shelling out to `git show`). Moot
  under A′ (no baselines needed); would otherwise have been YAGNI-deferred CLI sugar.
- **Shadow journal** (gitignored payload log appended by validate/stamp). Rejected: un-governed
  machine-local state — explanations become non-reproducible across checkouts, the exact failure
  mode (transient caches drifting from committed truth) the live pipeline's
  `corrections.json`/`llm_cleaned` history is standing evidence against.
- **Sibling committed artifact** (`authoring_payloads.json`). Same content as A′ without reopening
  the sidecar schema; dominated by A′ — a fourth persisted artifact with its own M3 versioning
  ceremony, holding data whose natural home is beside the digests it explains.
- **No baselines at all** (degraded mode only, everywhere). The floor; fails the ratified
  deliverable ("WHICH children/atoms moved, not just the hashes") whenever a baseline exists to do
  better.

**DT-5 — composite gate composition.** Substrate-first order, so a failure is attributed to the
right layer and nothing downstream reports against a drifted base:

1. `load_freeze_record(book_dir / "stream_freeze.json")`; assert `record["book"] == book_dir.name`;
2. `load_workspace_streams(workspace)` (round-trip + hash tiers + reference integrity);
3. `assert_freeze_matches(record, streams)` — pin ↔ live;
4. `load_structure_map(map_path, StreamAtomReader(streams))` — Tier-1 + Tier-2;
5. `load_authoring_evidence(evidence_path, expected_book=record["book"])`;
6. `assert_evidence_gate(evidence, smap.projection)`.

**Non-goal guarded here:** the gate does *not* compare the map's stored manifest hashes against
the live streams — that stored-vs-live comparison is S8.1's, deliberately (s4_plan §3.E.9). The
gate's freshness claim rides the freeze pin, which pins the same envelope hashes the manifest
stamps.

**DT-6 — stamp command (scope addition — RATIFIED 2026-07-02,** user ruling: skipping it now
would downgrade the loop; the digests are not hand-writable**).** One node per invocation,
`--evidence` prose required; computes both digests from the *current* map via
`build_evidence_entry` (which already refuses non-human containers), merges into the loaded
sidecar, writes via `write_authoring_evidence(..., force=True)`. The `force` is justified as
read-modify-write — the command loads the existing sidecar and preserves every other entry; it
never regenerates from nothing. What is deliberately **not** built: any `--all` / bulk re-stamp —
stamping without per-node human verification is exactly what the evidence gate exists to prevent.
Re-stamping an already-fresh node is allowed (updates `authored_at_revision` + prose).

**DT-7 — revision discipline during initial authoring.** The map stays `map_revision: 0` through
the whole hand-authoring session; evidence entries stamp `authored_at_revision: 0`. The CAS
writer + snapshots govern *post-authoring* supersessions (S8-era). The explainer is unaffected by
this (DT-4's stored payload witnesses are baseline-free); snapshots remain the map-*history*
mechanism, not an explainer input.

**DT-8 — validate-on-save.** One-shot `validate` plus `--watch`: stdlib mtime poll (default 1s)
over `structure_map.json` + `authoring_evidence.json`, re-running the non-raising validation and
printing findings on each change. No watchdog dependency (Principle 2 — polling two files at 1Hz
needs nothing more). `validate` is non-raising by design (it's the editor loop); `gate` is the
enforcing form.

## §4 Invariants and red-first matrix

Every row is seen RED before green, against the named mutation/violation (the planted-violation
discipline; hunts run with `PYTHONDONTWRITEBYTECODE=1` + `__pycache__` purge).

| # | Invariant | Named red |
|---|-----------|-----------|
| 1 | Gate routes a freeze drift as `StaleArtifactError` naming the drifted stream | tamper one `envelope_hash` in a tmp pin |
| 2 | Gate routes an invalid map as `StructureValidationError` (exit 11) | plant a dangling child ref |
| 3 | Gate routes missing/stale evidence as `EvidenceGateError` (exit 12) | delete one entry / edit a stamped node's children |
| 4 | Gate **order**: freeze drift + stale evidence together reports the freeze, not evidence | compose both violations, assert error type |
| 5 | Gate book binding: `record["book"] != book_dir.name` refuses | rename a tmp book dir |
| 6 | Gate does NOT do S8.1's stored-manifest comparison | mutate a manifest `atom_streams[*].hash` in the map doc → gate still passes (with pin fresh); the invariant is a *pass*, pinned by an explicit test naming §3.E.9 |
| 7 | `status` is non-raising on gate-failing input and exits 0 | run it on the all-missing draft |
| 8 | `status` columns cover the full closed `EVIDENCE_FINDING_KINDS` | mutation: drop a kind from the renderer → red |
| 9 | Explainer names the exact added/removed/reordered children (stale-decision) and the atoms entering/leaving each own slot + beneath (stale-extent) — always, from the stored witness | scripted edit after stamp; assert the moved ids appear verbatim |
| 10 | Codec is lossless and canonical: `decode(encode(x)) == x`, maximal runs, deterministic bytes | mutation: off-by-one in run expansion → red; adversarial id shapes (mixed suffix widths, differing prefixes, singletons, width-boundary `_09`/`_10`) |
| 11 | Load rejects a witness↔digest mismatch as `StaleArtifactError` naming the node (internal coherence at the load boundary, never quiet degradation) | tamper one stored payload atom id |
| 12 | `stamp` preserves every other sidecar entry (read-modify-write, not regenerate) | stamp one node, byte-compare the rest |
| 13 | `stamp` refuses a machine-minted leaf (via `build_evidence_entry`) | attempt on a leaf |
| 14 | No bulk-stamp path exists | argparse rejects `--all` (test asserts the flag is absent) |
| 15 | Seeder draft loads clean through `load_structure_map` (Tier-1+2, zero findings) over the frozen streams | lockstep test, `test_stream_freeze.py` pattern |
| 16 | Seeder draft covers every canonical atom exactly once | mutation: drop one span from `build_draft` → `UNOWNED_INCLUDED_ATOM` red |
| 17 | Seeder emits its anomaly flags (duplicate/garbled/out-of-order headings) rather than resolving them | assert the known `Capitolo Sesto` duplicate is flagged |
| 18 | Fresh draft + empty sidecar → `status` shows every container `missing` (the worklist state) | run on the seeded fixture |
| 19 | `authoring.py` enters the neutrality scan | plant `"per_la_liberta"` in it → scan red, remove |
| 20 | Export pin: the seven new exports (five toolkit + two payload producers) amend `test_structure_artifacts.py` in the same commit | pin red before amendment |
| 21 | `--watch` re-validates on mtime change | temp file touch in a bounded loop |
| 22 | Witness payload fields are required entry shape (no payload-less dialect) | load-negative: strip `extent_payload` from one entry |
| 23 | Re-stamp of an unchanged node re-renders the sidecar byte-identically (canonical codec + renderer) | stamp twice, byte-compare |
| 24 | *(re-audit)* Decode budget is cumulative AND document-wide — a sub-KB sidecar can never force an unbounded allocation | two 600k-runs in one witness; two 600k-run entries sharing one budget |
| 25 | *(re-audit)* Witnesses are deep-frozen — no in-place mutation can decouple a witness from its digest | mutate proxy/tuple → TypeError/AttributeError |

## §5 Non-goals (defers to)

- Stored-manifest vs live staleness comparison — **S8.1** (§3.E.9); the gate rides the freeze pin.
- Extent re-stamp protocol / re-bind — **S5.1**; nothing here refreshes a digest mechanically.
- Recognizer-vs-map comparison — **S9** (advisory per the S4.6 row).
- Bulk evidence stamping — **anti-feature**, permanently (see DT-6).
- Sidecar schema changes beyond DT-4's ratified payload-witness amendment — none; DT-4 spends the
  free-edit window once, deliberately, before the first sidecar exists.
- File-watching dependency, new console script, JSON output modes — all YAGNI until asked.

## §6 Verification plan

- **Suite:** new `tests/unit/test_authoring_tooling.py` (engine half, tmp-book fixtures built from
  live producers) + `tests/unit/test_seed_structure_map.py` (lockstep with the book script, the
  `test_stream_freeze.py` recapture pattern). All §4 rows red-first.
- **Mutation hunt:** extend the session-script pattern (a new `authoring_mutation_hunt.py`) over
  `authoring.py` + the seeder's `build_draft`; timeout=KILLED convention; all mutants killed
  before commit. *(As run: 38/38. Two survivor classes were test gaps, fixed by sharpening —
  degenerate payloads paired with stale digests let coherence mask the shape checks; and
  `pytest.raises(match=...)` is `re.search` over the FULL message including `tmp_path`, which
  contains the test's own name — `match="budget"` in a test named `test_decode_budget_…` passed
  on ANY error. Match on the raise's own wording, never on a word that names the test.)*
- **Rule A over the reopened S4.6a surface:** DT-4 re-opens `evidence.py` + the sidecar schema —
  the evidence mutation hunt re-runs over the delta (the 58-mutant baseline plus codec /
  self-verification mutants), and the delta gets its own re-audit before commit.
- **Audits:** Rule B pre-commit (wide impact sweep + narrow demolisher with RAN repros), Rule A
  re-audit on any remediation delta.
- **Live demo as acceptance:** run the real loop once — seed the PLL draft, `status` shows the
  ~61-row all-missing worklist, `gate` fails with `missing` findings, `validate --watch` catches a
  scripted bad edit. (The draft map produced here is the *input* to S4.6, not a committed
  deliverable of S4.6b — committing it is Ben's first authoring act, or it stays uncommitted until
  reviewed. Flagged for your call.)

## §7 Bookkeeping (same-commit amendments)

- Tracker: insert row **S4.6b** (engine owner; deps S4.6a/#32, S4.6-pre/#31; successor S4.6);
  amend the S4.6 row's workflow sentence to name the tooling; runway §3 item 3 struck DONE.
- GitHub: issue minted for S4.6b (this plan is its spec); closed on land.
- Export pin + `structure/__init__.py`: `assert_authoring_integrity`, `authoring_status`,
  `explain_evidence_drift`, `stamp_evidence`, `validate_authoring` (final — DT-6 ratified, all
  five ship) **plus the DT-4 payload producers `decision_payload`/`extent_payload`** (seven new
  names total; the CLI internals — `render_status`, `watch_validate`, `main`, the dataclasses —
  stay module-level, importable from `engine.structure.authoring` but outside the package pin).
- s4_plan §1.4.1a needs no edit (verified this session): it already names `evidence_findings()` as
  "the ONE non-raising producer … the S4.6 tooling status listing also consumes".
- s4_plan §1.4.1b: amended in the same commit to record the DT-4 payload-witness fields (the
  Option B amendment precedent — the ratified digest semantics are untouched; the witness is
  additive document shape).

## §8 Definition of done

1. All §4 invariants green, each documented red-first (test names in the commit body).
2. Mutation hunt: all killed.
3. Suite + ruff clean; neutrality scans green with the new module in scope.
4. The live-demo acceptance run performed and its output quoted in the closing commit/issue.
5. Tracker/runway/pin amendments in the same commit; issue closed.
6. Rule B audit passed pre-commit; any delta Rule A re-audited.

## §9 Post-ratification S4.6c source-observation addendum (2026-07-19)

Issue #90 adds a source-observation step before the human stamping loop. The strict,
source-locked `work/structure_observations.json` report is advisory input: it records declared
structural-label sightings and candidate page features, but it does not alter this plan's gate,
stamp, status, or structure-map semantics. Counts are factual diagnostics, never scalar confidence
weights. No observation can supply `heading_atoms`, mutate `structure_map.json`, write
`authoring_evidence.json`, or accept an evidence finding.

An S4.6 author may cite an observation id in evidence prose only after checking its exact scan
locator. The current PLL report is SHA-256
`cf19c081c461f5aab2228cd3bfa8ad8232c7650fed6a7ccb002d31e754009bac`: both independent
DjVu witnesses find `Parte Prima` only on their printed end-matter contents page, while
`Parte Seconda` also appears in body pages. This supports reviewing `n-3` as an intentionally
unheaded logical container; it does not synthesize an opening heading.
