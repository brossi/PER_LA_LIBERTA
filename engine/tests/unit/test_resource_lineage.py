"""S3.0 resource + normalization-policy lineage — the red-first invariant battery.

Home of the S3.0 lineage battery (ENGINE_STRUCTURE_PLAN S3.0; ``docs/s3_0_plan.md`` §4), built
red-first across the S3.0 build order (§5). #23 seated the stale-class distinctness invariant
(test 5) against the constants in ``structure/artifacts.py``. #25 adds invariants **1–4, 6–10, and
13–18** against the importable stubs (``structure/lineage.py``, ``dictionaries/normalization.py``):
each currently fails on the stub's ``NotImplementedError`` and greens surface-by-surface as #26
(fold ops) and #27 (resource digest + lineage) land. This commit is red by design — the battery is
the red-first evidence, not a regression. It also pins two resource-digest design properties D-C
states but §4 never numbered — ``oracle_min`` as a resource-version input, and index.json
manifest-bytes-out — surfaced by the #25 adversarial audit as "passes even if the impl drops them".

Two invariants were **not** seated against the stubs: 11 (a targeted source-language scan) and 12
(the hand-mutation pass) are green-*down* validation, not fail-against-stub assertions, so they
landed with the #28 neutrality + mutation pass (§5.9). **Invariant 12** is the "#28 mutation
green-down" section at the foot of this file — the four survivors the #27 pre-commit audit's
mutation hunt left green (the impl was correct, the red-first pins were missing): sha256-KAT,
``_canonical`` key-order, intra-member chunk-order, and declared-filename identity. **Invariant 11**
lives in ``test_resource_neutrality.py`` — a targeted source-language *resource*-literal scan over
``dictionaries/normalization.py`` **and** ``structure/lineage.py`` (the #27 audit found the existing
``test_structure_neutrality`` / ``test_core_neutrality`` denylists would not catch a baked dictionary
dir / ``it_combined.txt`` / source-language name / accent-fold literal in either module, so it widened
the plan's normalization-only §11 scope to both). The structure-half of 11's *structural* terms
(headings/guillemets/counts) is still covered by ``test_structure_neutrality`` globbing
``structure/lineage.py``; the new scan adds the orthogonal resource/language axis.

The ``to_json()`` shape the battery pins (the contract #27 implements, the fragment S4.4 embeds)::

    {
      "schema_version": <int>,
      "resource":   {"version": "sha256:…", "stale_class": "resource-set",
                     "descriptor": {"oracle_min": <int>, "frequency": "sha256:…",
                                    "members": [{"name","kind","dir","hash"}, …]}},
      "normalizer": {"version": "sha256:…", "stale_class": "normalization-policy",
                     "descriptor": {"case_fold": <str>, "accent_fold": {"from","to"}}},
    }

where ``<tier>["version"] == _sha256_bytes(_canonical(<tier>["descriptor"]).encode("utf-8"))`` — the
binding invariant 7 recomputes, valid because ``_canonical`` is round-trip stable (invariant 16).

Invariant 5 — two distinct stale classes (D-D). ``RESOURCE_STALE_CLASS`` and
``NORMALIZER_STALE_CLASS`` must differ from each other and from the one persisted-layer class that
exists after this task (``ATOM_STORE_STALE_CLASS``), so governance (S8.1) routes a *resource swap →
re-segment* and a *normalizer change → re-derive offsets* as **different** repairs (§3.6). Red-proof:
collapse the two classes to one literal, or alias either onto ``ATOM_STORE_STALE_CLASS``, and the
set-size assertion goes red.

A second check here — ``test_resource_lineage_schema_version_is_a_positive_int`` — is a binding
sanity check on ``RESOURCE_LINEAGE_SCHEMA_VERSION`` (feedback_validate_bindings), **not** a §4
numbered invariant. #25 must not re-seat either (both already live here).
"""

from __future__ import annotations

import dataclasses
import json

import pytest

import engine.structure as structure
from engine import paths
from engine.config.loader import load_book
from engine.config.models import PeriodDictionary
from engine.dictionaries.normalization import NormalizationPolicy
from engine.errors import MissingInputError
from engine.structure.lineage import ResourceLineage, _canonical, _sha256_bytes
from engine.util.text import build_fold_table

REAL_BOOK = "per_la_liberta"


# --- fake-asset staging (mutable resource tree mirroring the real declared paths) ---------- #

def _member_layout() -> dict:
    """member dir (assets-relative) → {chunk_key: (filename, content_bytes)}.

    Mirrors the real config's three declared period-dictionary dirs, each with distinct bytes so a
    test can prove one member's hash moves independently of the others (invariant 13).
    """
    return {
        "dictionary/zingarelli_1922": {"A": ("a.txt", b"abaco\nabate\n")},
        "dictionary/edgren_1901": {"A": ("a.txt", b"alfa\nalbero\n")},
        "dictionary/hoare_1915": {"A": ("a.txt", b"acca\nacqua\n")},
    }


def _stage_assets(root, *, freq: bytes = b"alpha 5\nbeta 3\n", layout: dict | None = None) -> None:
    """Write a small, mutable asset tree: the frequency file + each period member (index.json +
    its declared chunk files), at exactly the assets-relative paths the real profile names."""
    (root / "frequency").mkdir(parents=True, exist_ok=True)
    (root / "frequency" / "it_combined.txt").write_bytes(freq)
    for rel, chunks in (layout or _member_layout()).items():
        member = root / rel
        member.mkdir(parents=True, exist_ok=True)
        # incidental metadata (counts/sizes) mirrors the real index.json shape; the resource digest
        # hashes only chunks[*].file identity + chunk content (D-C "manifest bytes out"), so a test
        # can churn these and prove the version is stable.
        index = {
            "chunks": {
                key: {"file": filename, "lines": 10, "size_kb": 1.5}
                for key, (filename, _) in chunks.items()
            }
        }
        (member / "index.json").write_text(json.dumps(index), encoding="utf-8")
        for _key, (filename, content) in chunks.items():
            (member / filename).write_bytes(content)


@pytest.fixture
def fake_assets(tmp_path, monkeypatch):
    """A mutable asset tree mirroring the real declared paths, with ``ASSETS_ROOT`` pointed at it.

    Returns ``(cfg, root)``: ``cfg`` is the real PLL config (whose frequency/dictionary rel-paths now
    resolve under the patched root); ``root`` is the tmp tree a test mutates before rebuilding. The
    config loads from the real profiles (unaffected by ``ASSETS_ROOT``); only ``build``'s
    ``require_asset`` resolution is redirected.
    """
    root = tmp_path / "assets"
    _stage_assets(root)
    monkeypatch.setattr(paths, "ASSETS_ROOT", root)
    return load_book(REAL_BOOK), root


def _with_language(cfg, **changes):
    """A copy of ``cfg`` with ``cfg.language`` fields replaced (frozen-dataclass ``replace``)."""
    return dataclasses.replace(cfg, language=dataclasses.replace(cfg.language, **changes))


def _normalizer_version(policy: NormalizationPolicy) -> str:
    """The normalizer version a policy alone implies — the same formula ``build`` uses."""
    return _sha256_bytes(_canonical(policy.descriptor()).encode("utf-8"))


# --- invariant 5 + schema-version sanity (seated in #23 — do not re-seat) ------------------ #

def test_resource_and_normalizer_stale_classes_are_distinct():
    # D-D / invariant 5. The two S3.0 stale classes and the existing atom-store class are three
    # different routing keys; any collision would have S8.1 apply the wrong migration.
    resource = structure.RESOURCE_STALE_CLASS
    normalizer = structure.NORMALIZER_STALE_CLASS
    atom = structure.ATOM_STORE_STALE_CLASS
    # a stale class is a wire discriminator — never blank
    assert isinstance(resource, str) and resource
    assert isinstance(normalizer, str) and normalizer
    # distinct from each other and from the only persisted-layer class minted so far (S4.4/S7.1c
    # have not minted theirs — asserting against non-existent constants would be scope creep)
    assert len({resource, normalizer, atom}) == 3


def test_resource_lineage_schema_version_is_a_positive_int():
    # The lineage record (S4.4 embeds it) carries its own schema version, independent of the three
    # persisted-layer versions, so its shape can evolve without bumping a layer. bool is excluded
    # (int subclass) so a stray True/False cannot masquerade as a version.
    version = structure.RESOURCE_LINEAGE_SCHEMA_VERSION
    assert isinstance(version, int) and not isinstance(version, bool)
    assert version >= 1


# --- invariant 1 — resource version ↔ content, same path ----------------------------------- #

def test_resource_version_tracks_content_at_the_same_path(fake_assets):
    cfg, root = fake_assets
    freq = root / "frequency" / "it_combined.txt"
    v0 = ResourceLineage.build(cfg).resource_version
    # rewrite identical bytes (a touch / re-checkout) ⇒ unchanged: kills mtime-based + a stale cache
    freq.write_bytes(freq.read_bytes())
    assert ResourceLineage.build(cfg).resource_version == v0
    # different bytes at the SAME resolved path ⇒ changed: kills a path-only "version"
    freq.write_bytes(b"totally different content\n")
    assert ResourceLineage.build(cfg).resource_version != v0


# --- invariant 2 — resource version independent of the normalizer -------------------------- #

def test_resource_version_is_independent_of_the_normalizer(fake_assets):
    cfg, _ = fake_assets
    lower = ResourceLineage.build(_with_language(cfg, case_fold="lower"))
    none_fold = ResourceLineage.build(_with_language(cfg, case_fold="none"))
    # only the fold policy changed; the resource bytes are identical ⇒ resource_version unmoved
    assert lower.resource_version == none_fold.resource_version


# --- invariant 3 — normalizer version moves on a policy change ----------------------------- #

def test_normalizer_version_moves_on_a_policy_change(fake_assets):
    cfg, _ = fake_assets
    base = ResourceLineage.build(cfg).normalizer_version
    # the case axis…
    assert ResourceLineage.build(_with_language(cfg, case_fold="none")).normalizer_version != base
    # …and the accent axis each move the normalizer version
    other_fold = {"from": "ÆØ", "to": "AO"}
    assert ResourceLineage.build(_with_language(cfg, accent_fold=other_fold)).normalizer_version != base


# --- invariant 4 — normalizer version independent of resources ----------------------------- #

def test_normalizer_version_is_independent_of_resources(fake_assets):
    cfg, _ = fake_assets
    full = ResourceLineage.build(cfg)
    # drop one period dictionary (a resource swap) — the staged tree still resolves the rest
    fewer = ResourceLineage.build(
        _with_language(cfg, period_dictionaries=cfg.language.period_dictionaries[:-1])
    )
    assert fewer.normalizer_version == full.normalizer_version  # fold untouched ⇒ unmoved
    assert fewer.resource_version != full.resource_version       # but it WAS a resource change


# --- invariant 6 — determinism + reorder-invariance ---------------------------------------- #

def test_build_is_deterministic_and_reorder_invariant(fake_assets):
    cfg, _ = fake_assets
    assert ResourceLineage.build(cfg) == ResourceLineage.build(cfg)  # byte-identical, twice
    reordered = _with_language(
        cfg, period_dictionaries=tuple(reversed(cfg.language.period_dictionaries))
    )
    assert (
        ResourceLineage.build(reordered).resource_version
        == ResourceLineage.build(cfg).resource_version
    )


# --- invariant 6 (extended) — reorder-invariance survives a duplicate member name ---------- #
# The base reorder test above uses the three real members, whose names are distinct — so sorting
# members by `name` alone is enough there. But the sort is STABLE, so two members sharing a `name`
# keep their input order and a profile reorder flips them, moving resource_version. A realistic
# trigger is a manifest `override` that appends a dictionary under a name already present (D-C cites
# exactly this swap path). The sort key must be a TOTAL order — (name, kind, dir) — so a duplicate
# name still resolves deterministically by the unique `dir`. (#27 pre-commit audit, portability MED-1.)

def test_reorder_invariance_survives_a_duplicate_member_name(fake_assets):
    cfg, _ = fake_assets
    # same name AND same kind, differing only in dir — so the pin requires `dir` in the sort key
    # (a (name) or (name, kind) key both stay input-order-dependent and go red).
    dup = (
        PeriodDictionary(name="Dup", kind="monolingual", dir="dictionary/zingarelli_1922"),
        PeriodDictionary(name="Dup", kind="monolingual", dir="dictionary/edgren_1901"),
    )
    fwd = ResourceLineage.build(_with_language(cfg, period_dictionaries=dup)).resource_version
    rev = ResourceLineage.build(
        _with_language(cfg, period_dictionaries=tuple(reversed(dup)))
    ).resource_version
    assert fwd == rev


# --- invariant 7 — versions correspond to descriptors (binding, not shape) ----------------- #

def test_versions_recompute_from_the_emitted_descriptors(fake_assets):
    cfg, _ = fake_assets
    rec = ResourceLineage.build(cfg).to_json()
    res = rec["resource"]
    assert _sha256_bytes(_canonical(res["descriptor"]).encode("utf-8")) == res["version"]
    norm = rec["normalizer"]
    assert _sha256_bytes(_canonical(norm["descriptor"]).encode("utf-8")) == norm["version"]


# --- invariant 8 — fold ops reproduce the DictionaryOracle fold path ----------------------- #

def test_fold_ops_reproduce_the_dictionary_oracle():
    # Bound to the live oracle ops *specifically* (steps/adjudicate.py:114 chunk key;
    # :116-121 probe forms), not a vague "live behaviour". case_fold == "lower" in the real profile.
    cfg = load_book(REAL_BOOK)
    fold = build_fold_table(cfg.language.accent_fold)
    policy = NormalizationPolicy(
        case_fold=cfg.language.case_fold, accent_fold=cfg.language.accent_fold
    )
    # "Àncora" exercises an accented FIRST char (chunk-key fold); "perché"/"città" exercise the
    # accent-folded probe form; "Italia" the de-duplicated single-form branch.
    for token in ("Italia", "perché", "città", "Àncora"):
        # chunk_key == word[0].lower().translate(fold)  (adjudicate.py:114)
        assert policy.chunk_key(token) == token[0].lower().translate(fold)
        # probe_forms == [word, word.translate(fold)], the second only when it differs (the oracle
        # searches `stripped` only `if stripped != word` — adjudicate.py:118-121)
        folded = token.translate(fold)
        expected = [token] if folded == token else [token, folded]
        assert policy.probe_forms(token) == expected


# --- invariant 9 — loads via the profile; bindings resolve (hard, no skip) ----------------- #

def test_build_resolves_real_assets_and_fails_loud_on_a_typo():
    # Real assets (no patch): the frequency dict + every period-dictionary dir resolve via
    # require_asset and hash — hard, no skip (feedback_validate_bindings).
    cfg = load_book(REAL_BOOK)
    lineage = ResourceLineage.build(cfg)
    assert lineage.resource_version.startswith("sha256:")
    # a typo'd frequency dict ⇒ MissingInputError (require_asset), not a bare FileNotFoundError
    with pytest.raises(MissingInputError):
        ResourceLineage.build(_with_language(cfg, frequency_dictionary="frequency/NOPE.txt"))
    # …and a typo'd period-dictionary dir
    bad = (dataclasses.replace(cfg.language.period_dictionaries[0], dir="dictionary/nope"),)
    bad += cfg.language.period_dictionaries[1:]
    with pytest.raises(MissingInputError):
        ResourceLineage.build(_with_language(cfg, period_dictionaries=bad))


# --- invariant 10 — sourced-not-baked / not-Italian-only ----------------------------------- #

def test_synthetic_profile_breaks_on_any_bake():
    # A profile unlike Italian on every axis a bake could hardcode: a non-Latin (Greek) token, a
    # case-sensitive fold (case_fold="none" — catches a hardcoded .lower()), and a non-Italian
    # accent-fold table (catches a baked _ACCENT_MAP).
    greek_fold = {"from": "άέήίόύώ", "to": "αεηιουω"}
    table = build_fold_table(greek_fold)
    policy = NormalizationPolicy(case_fold="none", accent_fold=greek_fold)
    # case_fold="none": the uppercase first char is NOT lowered (a baked .lower() folds Ό→ό→ο)
    assert policy.chunk_key("Όμικρον") == "Ό".translate(table)
    assert policy.chunk_key("Όμικρον") != "Όμικρον"[0].lower().translate(table)
    # the accent fold applies to the probe forms; a baked Italian table would not touch ί
    assert policy.probe_forms("ποίηση") == ["ποίηση", "ποίηση".translate(table)]
    # and the whole policy versions differently from Italian's (different descriptor ⇒ different hash)
    italian = NormalizationPolicy(
        case_fold="lower", accent_fold=load_book(REAL_BOOK).language.accent_fold
    )
    assert _normalizer_version(policy) != _normalizer_version(italian)


# --- fold-op robustness: an unsupported case_fold mode fails loud (not a numbered §4 invariant) #
# case_fold is enum-bound at the schema, but a policy constructed directly (as this battery does)
# can carry a drifted mode — e.g. a 4th mode added to the schema without a matching fold op. The op
# must reject it loudly, not mis-route the chunk key by leaving the case unfolded. Exercises the
# _fold_case failure branch #26 adds; red if that branch falls through to a bare None.translate.

def test_chunk_key_fails_loud_on_an_unsupported_case_fold_mode():
    policy = NormalizationPolicy(case_fold="titlecase", accent_fold={"from": "à", "to": "a"})
    with pytest.raises(ValueError):
        policy.chunk_key("Àncora")


# The "lower" path has a live oracle referent (test 8); these two pin the case-axis branches the real
# Italian profile never exercises (feedback_red_first_tests / single-fixture blind spots — a
# non-default config value is born untested). The module docstring motivates "casefold" for a
# non-Latin/case-sensitive book, and the chunk_key docstring states the case-before-accent order;
# without these, a `casefold→lower` swap and an order reversal both survive the suite green.

def test_chunk_key_casefold_mode_differs_from_lower():
    # ẞ (capital sharp s) casefolds to "ss" but lowercases to "ß" — so this pins that "casefold" is
    # str.casefold, not a hardcoded .lower(). Fold table chosen not to touch the result.
    policy = NormalizationPolicy(case_fold="casefold", accent_fold={"from": "à", "to": "a"})
    assert policy.chunk_key("ẞoo") == "ss"          # casefold; a `.lower()` bake yields "ß"
    assert policy.chunk_key("ẞoo") != "ẞoo"[0].lower()


def test_chunk_key_lower_mode_differs_from_casefold():
    # The symmetric pin: the "lower" path — the one the real profile uses and the live oracle bakes
    # (adjudicate.py:114 word[0].lower()) — must be str.lower, not str.casefold. Without this, a
    # `.lower()`→`.casefold()` swap in the lower branch survives green (it diverges only on ẞ-like
    # chars absent from the all-"lower" Italian fixture), mis-routing "ß" to a 2-char "ss" chunk.
    policy = NormalizationPolicy(case_fold="lower", accent_fold={"from": "à", "to": "a"})
    assert policy.chunk_key("ẞoo") == "ß"           # lower; a `.casefold()` bake yields "ss"
    assert policy.chunk_key("ẞoo") != "ẞoo"[0].casefold()


def test_chunk_key_applies_case_before_accent():
    # A lowercase-only fold table makes the order observable: case-first lowers À→à then folds à→a
    # ("a"); accent-first would translate À (absent from the table) unchanged then lower it ("à").
    # Every real profile's table is case-complete (À→A and à→a both present), so the order is a no-op
    # there and only a synthetic asymmetric table can pin the docstring's load-bearing claim.
    policy = NormalizationPolicy(case_fold="lower", accent_fold={"from": "à", "to": "a"})
    assert policy.chunk_key("Àncora") == "a"        # case→accent; reversed order yields "à"


# --- invariant 13 — per-member tier localizes a change ------------------------------------- #

def test_per_member_hash_localizes_a_change(fake_assets):
    cfg, root = fake_assets
    before = {
        m["name"]: m["hash"]
        for m in ResourceLineage.build(cfg).to_json()["resource"]["descriptor"]["members"]
    }
    v0 = ResourceLineage.build(cfg).resource_version
    # mutate exactly one member's declared chunk
    (root / "dictionary" / "zingarelli_1922" / "a.txt").write_bytes(b"mutated\n")
    res = ResourceLineage.build(cfg).to_json()["resource"]
    after = {m["name"]: m["hash"] for m in res["descriptor"]["members"]}
    assert after["Zingarelli 1922"] != before["Zingarelli 1922"]  # the changed member moved
    assert after["Edgren 1901"] == before["Edgren 1901"]          # the others did not
    assert after["Hoare 1915"] == before["Hoare 1915"]
    assert res["version"] != v0                                   # and the roll-up moved with it
    # each member carries the full localizable shape (D-E), not just name+hash — so a diff can name
    # "Zingarelli 1922 (dictionary/zingarelli_1922) changed", not merely "a hash moved"
    for member in res["descriptor"]["members"]:
        assert set(member) == {"name", "kind", "dir", "hash"}


# --- invariant 14 — lineage record is journal-diffable ------------------------------------- #

def test_lineage_record_is_journal_diffable(fake_assets):
    cfg, _ = fake_assets
    # differ only in case_fold ⇒ only the normalizer tier moves
    lower = ResourceLineage.build(_with_language(cfg, case_fold="lower")).to_json()
    none_fold = ResourceLineage.build(_with_language(cfg, case_fold="none")).to_json()
    assert lower["resource"] == none_fold["resource"]      # resource tier byte-identical
    assert lower["normalizer"] != none_fold["normalizer"]  # normalizer tier differs
    # differ only in the dictionary set ⇒ only the resource tier moves
    full = ResourceLineage.build(cfg).to_json()
    fewer = ResourceLineage.build(
        _with_language(cfg, period_dictionaries=cfg.language.period_dictionaries[:-1])
    ).to_json()
    assert full["normalizer"] == fewer["normalizer"]       # normalizer tier identical
    assert full["resource"] != fewer["resource"]           # resource tier differs


# --- invariant 15 — fail-loud on a broken file set; undeclared stray ignored --------------- #

def test_fail_loud_when_a_declared_chunk_file_is_absent(fake_assets):
    cfg, root = fake_assets
    (root / "dictionary" / "zingarelli_1922" / "a.txt").unlink()  # declared in index.json, now gone
    with pytest.raises(MissingInputError):
        ResourceLineage.build(cfg)


def test_fail_loud_when_a_member_has_no_index(fake_assets):
    cfg, root = fake_assets
    (root / "dictionary" / "edgren_1901" / "index.json").unlink()  # no manifest ⇒ no glob fallback
    with pytest.raises(MissingInputError):
        ResourceLineage.build(cfg)


def test_an_undeclared_stray_file_is_ignored(fake_assets):
    cfg, root = fake_assets
    v0 = ResourceLineage.build(cfg).resource_version
    # a present-but-undeclared file (e.g. the regenerable raw download) is not in chunks ⇒ unmoved
    (root / "dictionary" / "hoare_1915" / "raw.txt").write_bytes(b"regenerable download\n")
    assert ResourceLineage.build(cfg).resource_version == v0


# --- invariant 15 (extended) — fail loud on a malformed manifest, not a bare KeyError ------ #
# D-C's fail-loud surface enumerates "declared-but-absent file" and "no index.json"; both are
# covered above. But a present-but-STRUCTURALLY-malformed index.json (a half-written / hand-edited
# manifest — the likeliest corruption) must also raise the clean MissingInputError (exit 3) the
# engine raises for every unusable input asset, not a bare KeyError/JSONDecodeError from deep in the
# digest loop (the I1/require_asset "no raw traceback from a loader" contract). (#27 pre-commit
# audit, portability MED-2 + spec-seam OBS-2.)

def test_fail_loud_when_a_member_index_is_malformed(fake_assets):
    cfg, root = fake_assets
    index = root / "dictionary" / "edgren_1901" / "index.json"

    def _expect_malformed(write):
        write(index)
        with pytest.raises(MissingInputError, match="malformed dictionary manifest"):
            ResourceLineage.build(cfg)

    # Every arm of the except must map to the clean MissingInputError (message-pinned), not just the
    # KeyError arms a no-`chunks`/no-`file` test would reach — the JSONDecodeError / TypeError /
    # UnicodeError arms a KeyError-only test would leave free to be silently deleted (#27 audit-2,
    # R1/R2). The truncated-JSON case is the "half-written manifest" this fail-loud path most targets.
    _expect_malformed(lambda p: p.write_text(json.dumps({"version": 1}), encoding="utf-8"))         # no "chunks"  → KeyError
    _expect_malformed(lambda p: p.write_text(json.dumps({"chunks": {"A": {"x": 1}}}), encoding="utf-8"))  # chunk w/o "file" → KeyError
    _expect_malformed(lambda p: p.write_text('{"chunks": {', encoding="utf-8"))                     # truncated     → JSONDecodeError
    _expect_malformed(lambda p: p.write_text(json.dumps({"chunks": [1, 2, 3]}), encoding="utf-8"))  # non-dict chunks → TypeError
    _expect_malformed(lambda p: p.write_bytes(b"\xff\xfe not utf-8\n"))                             # non-UTF-8     → UnicodeError

    # R4: a well-formed manifest declaring ZERO chunks can't be content-hashed — a constant digest
    # blind to disk content is the "silent partial hash" D-C forbids, so it fails loud too (distinct
    # message, distinct cause from the malformed shapes above).
    index.write_text(json.dumps({"chunks": {}}), encoding="utf-8")
    with pytest.raises(MissingInputError, match="declares no chunks"):
        ResourceLineage.build(cfg)


# --- D-C resource-digest design properties (not promoted to a numbered §4 invariant) ------- #
# oracle_min and index.json's incidental metadata are resource-digest guarantees the plan states
# (D-C) but §4 never numbered. Without a red-first pin, an #27 impl that drops oracle_min from the
# descriptor, or folds whole-index.json bytes into the digest, passes the entire battery — the
# "passes even if wrong" hole the #25 adversarial audit surfaced (A + B converged on oracle_min).

def test_resource_version_tracks_oracle_min(fake_assets):
    cfg, _ = fake_assets
    base = ResourceLineage.build(cfg)
    bumped = ResourceLineage.build(_with_language(cfg, oracle_min=cfg.language.oracle_min + 1))
    # 2-of-3 → 3-of-3 changes the membership verdict (a semantic resource change, D-C) and is the
    # ONLY resource input not already caught by the per-member byte hashes — so it needs its own pin.
    assert bumped.resource_version != base.resource_version       # resource tier moves
    assert bumped.normalizer_version == base.normalizer_version   # and it is not a normalizer change


def test_index_metadata_churn_does_not_move_the_version(fake_assets):
    cfg, root = fake_assets
    v0 = ResourceLineage.build(cfg).resource_version
    index = root / "dictionary" / "zingarelli_1922" / "index.json"
    data = json.loads(index.read_text(encoding="utf-8"))
    # same declared file set + same chunk bytes; only incidental counts/sizes churn (an index regen)
    data["chunks"]["A"]["lines"] = 99999
    data["chunks"]["A"]["size_kb"] = 4242.0
    data["_regenerated_note"] = "counts recomputed"
    index.write_text(json.dumps(data), encoding="utf-8")
    # D-C "manifest bytes out": the digest hashes chunks[*].file identity + content, not the index
    # bytes — so a no-op index regeneration must not trip a false re-segment.
    assert ResourceLineage.build(cfg).resource_version == v0


def test_resource_version_tracks_the_chunk_routing_key(fake_assets):
    # F1 (#27 audit, forward consumer-seam): the chunk key is the oracle's ROUTING bucket
    # (DictionaryOracle loads word[0]→`{letter}.txt`, adjudicate.py:102/114), so it must enter the
    # per-member digest — not just the declared filename. Re-declaring the same file + same bytes
    # under a different routing key (A→B) is a real routing change an index.json-reading oracle would
    # resolve differently, so resource_version must move. A filename-only digest misses it (the file
    # identity + content are unchanged), so this pins the chunk-key half of the (key, file, content)
    # identity D-C now hashes.
    cfg, root = fake_assets
    before = ResourceLineage.build(cfg)
    v0 = before.resource_version
    h0 = {m["name"]: m["hash"] for m in before.to_json()["resource"]["descriptor"]["members"]}
    index = root / "dictionary" / "zingarelli_1922" / "index.json"
    data = json.loads(index.read_text(encoding="utf-8"))
    assert list(data["chunks"]) == ["A"]  # single-chunk precondition the pin's strength rests on
    data["chunks"]["B"] = data["chunks"].pop("A")  # same file (a.txt) + bytes, new routing key
    index.write_text(json.dumps(data), encoding="utf-8")
    after = ResourceLineage.build(cfg)
    # the changed member's per-member hash moves, the others don't — pins chunk-key *membership* in
    # the digest, not merely a roll-up shift (a wrong "hash the whole index.json" impl is separately
    # forbidden by test_index_metadata_churn_does_not_move_the_version, the complementary pin).
    h1 = {m["name"]: m["hash"] for m in after.to_json()["resource"]["descriptor"]["members"]}
    assert h1["Zingarelli 1922"] != h0["Zingarelli 1922"]
    assert h1["Edgren 1901"] == h0["Edgren 1901"]
    assert after.resource_version != v0


# --- invariant 16 — canonicalizer round-trip stability ------------------------------------- #

def test_canonical_is_round_trip_stable():
    # The precondition test 7's recompute rests on: re-canonicalizing a parsed canonical string is a
    # fixed point, across the descriptor value types (strings, the oracle_min int, nested string maps).
    for descriptor in (
        {"oracle_min": 2, "members": [{"name": "Z", "kind": "monolingual", "dir": "d", "hash": "sha256:x"}]},
        {"case_fold": "lower", "accent_fold": {"from": "àé", "to": "ae"}},
        {"b": 1, "a": 2, "nested": {"y": [3, 2, 1], "x": "ünïcödé"}},
    ):
        once = _canonical(descriptor)
        assert _canonical(json.loads(once)) == once


# --- invariant 17 — descriptor keys == ops' inputs (no hollow version) --------------------- #

def test_normalizer_descriptor_keys_are_exactly_the_fold_ops_inputs():
    # chunk_key reads {case_fold, accent_fold}; probe_forms reads {accent_fold}; their union is
    # exactly the descriptor's keys — so the normalizer version hashes precisely what is applied. A
    # field hashed-but-unused (a hollow version) or used-but-unhashed turns this red.
    policy = NormalizationPolicy(case_fold="lower", accent_fold={"from": "à", "to": "a"})
    assert set(policy.descriptor().keys()) == {"case_fold", "accent_fold"}
    # …and each key maps to its OWN axis value, not merely the right key SET: a descriptor that swaps
    # the two axis values (``{"case_fold": self.accent_fold, "accent_fold": self.case_fold}``) keeps
    # the key set but mislabels which axis is which — the emitted normalizer descriptor would then
    # version the wrong axis under each name. Distinct value types (str vs dict) make the swap
    # observable. (#28 audit, narrow mutation-hunt, MED.)
    assert policy.descriptor() == {"case_fold": "lower", "accent_fold": {"from": "à", "to": "a"}}


# --- invariant 18 — stale-class wire values pinned at the serialization site --------------- #

def test_stale_class_wire_values_are_pinned_at_the_serialization_site(fake_assets):
    cfg, _ = fake_assets
    rec = ResourceLineage.build(cfg).to_json()
    # the persisted literals S4.4 writes + S8.1 routes on — pinned at the EMITTED record, not the
    # bare constant (which would only restate its own literal). Mirrors test_atom_store.py's
    # env["stale_class"] == "atom-stream". A discriminator rename drifts the wire value while
    # distinctness (5) / diffability (14) / version-binding (7) all stay green — this catches it.
    assert rec["resource"]["stale_class"] == "resource-set"
    assert rec["normalizer"]["stale_class"] == "normalization-policy"


# --- invariant 12 — #28 mutation green-down (the four #27-audit survivors) ------------------ #
# The #27 pre-commit audit's mutation hunt left four mutations green: the impl was *correct*, the
# red-first PINS were missing (exactly invariant 12's remit — "hand-mutate the hashing + descriptor
# assembly ⇒ 0 survivors"). Each test below goes red under precisely one mutation, closing one gap.
# (The audit also confirmed two EQUIVALENT mutants that need no pin — the `name`-primary member sort,
# and `_canonical`'s separators/ensure_ascii — see the per-test notes / feedback_no_cheating_results.)

def test_sha256_is_the_pinned_algorithm():
    # M1b: invariant 9 asserts only the ``"sha256:"`` PREFIX (a hardcoded f-string label, not derived
    # from the algorithm), so a ``hashlib.sha256`` → ``md5``/``sha1`` swap stays green. Pin the digest
    # BYTES to the NIST SHA-256 known-answer vectors so the algorithm itself is bound. ("abc" and the
    # empty input are two distinct known answers — the empty case also kills a constant-return mutant.)
    assert _sha256_bytes(b"abc") == (
        "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    assert _sha256_bytes(b"") == (
        "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_canonical_is_key_order_independent():
    # M2: ``build`` constructs every descriptor in fixed literal key order, so dropping
    # ``sort_keys=True`` survives the whole battery — until a future descriptor is assembled from a
    # dict whose key order varies (a member built from a mapping, say). Pin ``sort_keys`` directly:
    # the same items in different insertion order must canonicalize identically (flat and nested).
    assert _canonical({"a": 1, "b": 2}) == _canonical({"b": 2, "a": 1})
    assert _canonical({"x": {"p": 1, "q": 2}}) == _canonical({"x": {"q": 2, "p": 1}})
    # ``separators=(",",":")`` and ``ensure_ascii=False`` are deterministic-but-EQUIVALENT mutants
    # here: nothing pins the canonical string (or its hash) to an external constant for a non-ASCII /
    # whitespace-sensitive descriptor, so flipping either stays self-consistent and unobservable. They
    # are left unpinned by design (not overlooked) — only key-order stability is load-bearing.


def test_chunk_order_within_a_member_does_not_move_the_version(fake_assets):
    # M6: every fixture member has a SINGLE chunk, so dropping ``sorted(chunks)`` in ``_digest_member``
    # survives — a one-element declaration is trivially canonical. Stage a 2-chunk member and permute
    # its ``index.json`` KEY ORDER (same files, same bytes): an index regen that reorders keys must NOT
    # move the version (D-C "manifest bytes out"), so the per-member hash and the roll-up both hold.
    cfg, root = fake_assets
    member = root / "dictionary" / "zingarelli_1922"
    (member / "a.txt").write_bytes(b"abaco\n")
    (member / "b.txt").write_bytes(b"baco\n")
    index = member / "index.json"
    index.write_text(json.dumps({"chunks": {"A": {"file": "a.txt"}, "B": {"file": "b.txt"}}}), encoding="utf-8")
    ordered = ResourceLineage.build(cfg)
    h_ordered = {m["name"]: m["hash"] for m in ordered.to_json()["resource"]["descriptor"]["members"]}
    # same file→content bindings, only the manifest key order permuted (B before A on disk)
    index.write_text(json.dumps({"chunks": {"B": {"file": "b.txt"}, "A": {"file": "a.txt"}}}), encoding="utf-8")
    assert list(json.loads(index.read_text(encoding="utf-8"))["chunks"]) == ["B", "A"]  # order really permuted on disk
    after = ResourceLineage.build(cfg)
    h_after = {m["name"]: m["hash"] for m in after.to_json()["resource"]["descriptor"]["members"]}
    assert h_after["Zingarelli 1922"] == h_ordered["Zingarelli 1922"]  # per-member hash stable under reorder
    assert after.resource_version == ordered.resource_version          # and the roll-up with it


def test_resource_version_tracks_a_declared_filename_rename(fake_assets):
    # M7: no test renames a declared file while holding the chunk key + bytes fixed, so dropping
    # ``filename`` from the ``(chunk_key, filename, content_hash)`` triple survives. But the declared
    # filename IS the file an ``index.json``-reading oracle opens for that key, so a key-stable,
    # byte-stable rename is a real change to the declared key→file binding (F1) ⇒ the version must
    # move. Complements ``test_resource_version_tracks_the_chunk_routing_key`` (the key half of the
    # same (key, file, content) identity).
    cfg, root = fake_assets
    member = root / "dictionary" / "zingarelli_1922"
    index = member / "index.json"
    assert list(json.loads(index.read_text(encoding="utf-8"))["chunks"]) == ["A"]  # single-chunk precondition
    before = ResourceLineage.build(cfg)
    h0 = {m["name"]: m["hash"] for m in before.to_json()["resource"]["descriptor"]["members"]}
    # rename the declared file, same chunk key "A", same bytes
    (member / "renamed.txt").write_bytes((member / "a.txt").read_bytes())
    (member / "a.txt").unlink()
    index.write_text(json.dumps({"chunks": {"A": {"file": "renamed.txt"}}}), encoding="utf-8")
    after = ResourceLineage.build(cfg)
    h1 = {m["name"]: m["hash"] for m in after.to_json()["resource"]["descriptor"]["members"]}
    assert h1["Zingarelli 1922"] != h0["Zingarelli 1922"]  # the rename moved the member hash
    assert h1["Edgren 1901"] == h0["Edgren 1901"]          # the other members untouched
    assert after.resource_version != before.resource_version


def test_every_declared_chunk_contributes_to_the_member_digest(fake_assets):
    # #1 (#28 audit, narrow mutation-hunt, HIGH): the M6 reorder pin proves chunk ORDER is canonical,
    # but every other fixture member is single-chunk, so a digest hashing only a SUBSET of the declared
    # chunks (e.g. ``sorted(chunks)[:1]`` — the first only) survives the whole suite. The real period
    # dictionaries are 22–26 chunks (A–Z), so that regression would leave ``resource_version`` blind to
    # ~21/22 of each dictionary's bytes. Pin CONTENT-sensitivity of EACH declared chunk: mutate one
    # chunk at a time and assert the member hash AND the roll-up move every time — killing a first-only
    # (``[:1]``), a non-first-only (``[1:]``), or any other proper-subset digest.
    cfg, root = fake_assets
    member = root / "dictionary" / "zingarelli_1922"
    (member / "a.txt").write_bytes(b"alpha\n")
    (member / "b.txt").write_bytes(b"beta\n")
    index = member / "index.json"
    index.write_text(json.dumps({"chunks": {"A": {"file": "a.txt"}, "B": {"file": "b.txt"}}}), encoding="utf-8")

    def _member_state():
        res = ResourceLineage.build(cfg)
        members = res.to_json()["resource"]["descriptor"]["members"]
        return {m["name"]: m["hash"] for m in members}["Zingarelli 1922"], res.resource_version

    h0, v0 = _member_state()
    # mutating the FIRST declared chunk moves both the member hash and the roll-up (kills a [1:] digest)
    (member / "a.txt").write_bytes(b"alpha MUTATED\n")
    h1, v1 = _member_state()
    assert h1 != h0 and v1 != v0
    # …and mutating the SECOND declared chunk does too (kills a [:1] digest — the HIGH gap). Restore the
    # first chunk so ONLY the second differs from the baseline, isolating the second chunk's contribution.
    (member / "a.txt").write_bytes(b"alpha\n")
    (member / "b.txt").write_bytes(b"beta MUTATED\n")
    h2, v2 = _member_state()
    assert h2 != h0 and v2 != v0


def test_resource_descriptor_and_schema_version_wire_shape_is_pinned(fake_assets):
    # #3/#4 (#28 audit, narrow mutation-hunt, LOW): the resource-descriptor's top-level key labels and
    # the record's schema_version are a wire contract (S4.4 embeds the fragment, S8.1 routes on it), but
    # nothing pinned them at the SERIALIZATION site — a ``build`` that renamed ``oracle_min``/
    # ``frequency``, or a ``to_json`` emitting a wrong schema_version (e.g. +1), stayed green. Mirror
    # invariant 18's stale-class wire pin (the emitted record, not the bare constant) for these shapes.
    cfg, _ = fake_assets
    rec = ResourceLineage.build(cfg).to_json()
    assert set(rec["resource"]["descriptor"]) == {"oracle_min", "frequency", "members"}
    assert rec["schema_version"] == 1  # the persisted wire value; a schema bump must update this pin
