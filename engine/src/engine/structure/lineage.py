"""S3.0 resource + normalization-policy lineage — the input-versioning value object.

Where the atom store / structure map / relation store version *persisted layers*, this versions
the **inputs** a build consumes (S3.0 R3; ``docs/s3_0_plan.md`` D-C/D-E/D-G): the profile-declared
resources (the frequency dictionary + each period dictionary) and the pre-lookup fold policy. Both
collapse to content-derived ``sha256:`` versions held in one :class:`ResourceLineage`, under **two
distinct stale classes** (``structure.artifacts``) so governance (S8.1) routes a *resource swap →
re-segment* and a *normalizer change → re-derive offsets* as different repairs.

The two version producers:

- **Resources** — a content hash of the bytes each member declares, resolved through the profile
  (``require_asset``) and the member's ``index.json`` ``chunks[*].file`` set (never a glob): a
  member swap/add/remove, a re-OCR of the same source, or an ``oracle_min`` change all move the
  version; an undeclared stray file does not. Fail-loud — a declared-but-absent file, a member
  with no ``index.json``, or a structurally malformed manifest raises ``MissingInputError``, never a
  silent partial hash or a bare loader traceback. Two tiers: a
  rolled-up ``resource_version`` plus the per-member hashes that produced it (so a diff localizes to
  "which dictionary changed").
- **Normalizer** — a hash of ``NormalizationPolicy.descriptor()`` (``{case_fold, accent_fold}``),
  exactly the axes the fold ops apply.

Determinism (D-G): descriptors are canonical JSON (``_canonical`` — ``sort_keys``, so the ``{…}``
field orders shown throughout this module are *logical*, not the sorted byte order) hashed via
``_sha256_bytes``; members are sorted by ``(name, kind, dir)`` and each member's files by chunk key,
so reordering the profile's dictionary list does not move the version. ``to_json`` emits the *parsed*
descriptors (the header fragment S4.4 embeds); the stored canonical strings are the exact hashed
bytes, and the version↔descriptor binding is re-established by re-canonicalizing (invariant 7), valid
because ``_canonical`` is round-trip stable (invariant 16). No ``from_json`` / stale-compare here —
that loader is S8.1's, and its compare must check ``schema_version`` independently of the version
hash (which covers the descriptor only — a schema bump does not move a descriptor-unchanged version).

Engine-agnostic: this module reads paths and fold tables from the profile and carries no language,
ordinal, or book-structure literal. The load-bearing neutrality proof is *behavioural* — a baked
asset path breaks the real-asset binding test (``test_build_resolves_real_assets_and_fails_loud_on_a_typo``)
and the ``fake_assets``-fixture tests, and a baked accent table or case rule breaks
``test_synthetic_profile_breaks_on_any_bake``. The S0.2
structure-neutrality scan also globs this file, but its denylist (structural heading/punctuation/count
terms) would not catch a baked dictionary dir or accent map, so it is belt-and-suspenders here, not
the primary guard.

The frequency dictionary is a flat file (no chunk manifest, no ``kind``), so it does **not** fit the
``{name, kind, dir, hash}`` member shape the period dictionaries take; its content hash rides the
resource descriptor as a sibling ``frequency`` key (``{oracle_min, frequency, members}``) rather than
overloading ``kind``/``dir`` to force it into ``members``. It still moves ``resource_version`` (a
re-OCR of the frequency dict is a resource change); it is simply not localizable to a "member" row.

Implemented at S3.0.5 (#27): the byte/canonical digests (``_sha256_bytes``/``_canonical``), the
per-member content digest (``_digest_member``), and the ``ResourceLineage.build`` / ``to_json``
value object.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from engine.dictionaries.normalization import NormalizationPolicy
from engine.errors import MissingInputError
from engine.paths import require_asset
from engine.structure.artifacts import (
    NORMALIZER_STALE_CLASS,
    RESOURCE_LINEAGE_SCHEMA_VERSION,
    RESOURCE_STALE_CLASS,
)

if TYPE_CHECKING:  # the real build() reads only cfg.language; typed here without a runtime import
    from engine.config.models import PeriodDictionary, ResolvedConfig


def _sha256_bytes(data: bytes) -> str:
    """``sha256:<hex>`` over raw ``data`` bytes — the single digest producer for the lineage.

    Distinct from ``structure.roundtrip.hash_raw``, which takes a ``str``: hashing a resource as text
    (decoded via ``read_text``) would normalize a CRLF/encoding change at the *decode* step and hide a
    real byte difference. Resources are hashed as raw bytes (``read_bytes``); the canonical-JSON
    descriptor path feeds its UTF-8-encoded string through this same producer.
    """
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _canonical(obj: object) -> str:
    """Canonical JSON for ``obj`` — ``sort_keys``, ``ensure_ascii=False``, compact separators.

    The one serializer behind both the stored descriptor string and the hashed bytes, so the two
    cannot diverge. Round-trip stable (``_canonical(json.loads(_canonical(d))) == _canonical(d)``),
    the precondition the recompute-binding rests on.
    """
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest_member(member: PeriodDictionary) -> str:
    """Content digest of one period-dictionary member, over the files its ``index.json`` declares.

    Resolves the member dir + its ``index.json`` through ``require_asset`` (fail-loud:
    ``MissingInputError`` on an absent dir, a missing manifest, a declared-but-absent chunk file, a
    structurally malformed or non-UTF-8 manifest, or a manifest declaring no chunks — never a bare
    ``KeyError``/``JSONDecodeError``/``UnicodeDecodeError`` from inside the loop), then hashes the
    ordered ``[chunk-key, declared-filename, content-hash]`` triples for the files named in
    ``chunks[*].file``, sorted by chunk key for determinism. The **chunk key** is part of the identity
    (not only the sort order): it versions the declared *key→file binding*, so re-declaring the same
    file+bytes under a different key moves the version (D-C, F1). (The *current* ``DictionaryOracle``
    routes by filename — ``word[0]`` selects ``{letter}.txt`` — and never reads this key; hashing it is
    conservative forward-coverage for an ``index.json``-reading oracle, not a change the present system
    routes on — see the §2 consumed-set caveat.) Only key + declared filename + bytes enter the digest
    — the manifest's incidental metadata (``lines``/``size_kb``/…) never enters it, so a no-op index
    regeneration does not move it (D-C "manifest bytes out"), and a present-but-undeclared stray file
    (e.g. the regenerable ``raw.txt``) is ignored.
    """
    require_asset(member.dir, kind="dir")
    index_path = require_asset(f"{member.dir}/index.json", kind="file")
    try:
        chunks = json.loads(index_path.read_text(encoding="utf-8"))["chunks"]
        declared = [(key, chunks[key]["file"]) for key in sorted(chunks)]
    except (json.JSONDecodeError, UnicodeError, KeyError, TypeError) as exc:
        raise MissingInputError(
            f"malformed dictionary manifest {member.dir}/index.json ({exc})"
        ) from exc
    if not declared:
        raise MissingInputError(
            f"dictionary manifest {member.dir}/index.json declares no chunks"
        )
    triples = []
    for chunk_key, filename in declared:
        chunk_path = require_asset(f"{member.dir}/{filename}", kind="file")
        triples.append([chunk_key, filename, _sha256_bytes(chunk_path.read_bytes())])
    return _sha256_bytes(_canonical(triples).encode("utf-8"))


@dataclass(frozen=True, slots=True)
class ResourceLineage:
    """Versioned lineage of a build's resources + normalization policy (two stale classes).

    Each descriptor is held as its **canonical JSON string** — immutable and by construction the
    exact bytes hashed, so a stored descriptor cannot drift from its version. ``to_json`` parses
    them back to dicts for the embeddable header fragment. Build via :meth:`build`; there is no
    ``from_json`` / stale-compare (that is S8.1's loader). The stale classes live here as fields
    (set by :meth:`build` from the ``structure.artifacts`` constants); S8.1's future ``from_json``
    must **re-validate** each stored ``stale_class`` against the live constant and re-stamp it (the
    atom-store precedent), never trust the value round-tripped from disk — otherwise a renamed
    discriminator would silently echo a stale class instead of failing the load (F3).
    """

    resource_version: str        # "sha256:…" over the resource descriptor
    resource_descriptor: str     # canonical JSON: {oracle_min, frequency, members:[{name,kind,dir,hash}, …]}
    resource_stale_class: str
    normalizer_version: str      # "sha256:…" over the normalizer descriptor
    normalizer_descriptor: str   # canonical JSON: {case_fold, accent_fold}
    normalizer_stale_class: str
    schema_version: int = RESOURCE_LINEAGE_SCHEMA_VERSION

    @classmethod
    def build(cls, cfg: "ResolvedConfig") -> "ResourceLineage":
        """Resolve + hash the profile-declared resources and the fold policy into a lineage.

        Reads only ``cfg.language`` (the frequency dict, the period dictionaries + ``oracle_min``,
        and ``case_fold``/``accent_fold``). Members are sorted by the total order
        ``(name, kind, dir)`` so a profile reorder does not move ``resource_version`` (D-G) — the
        ``dir`` tiebreak keeps the order deterministic even if two members share a ``name`` (a
        manifest ``override`` can append a duplicate-named dictionary). Raises ``MissingInputError``
        on a declared-but-absent file, a member without an ``index.json``, or a malformed manifest
        (fail-loud, never a silent partial hash).
        """
        lang = cfg.language
        freq_hash = _sha256_bytes(require_asset(lang.frequency_dictionary, kind="file").read_bytes())
        members = [
            {"name": m.name, "kind": m.kind, "dir": m.dir, "hash": _digest_member(m)}
            for m in sorted(lang.period_dictionaries, key=lambda m: (m.name, m.kind, m.dir))
        ]
        resource_descriptor = _canonical(
            {"oracle_min": lang.oracle_min, "frequency": freq_hash, "members": members}
        )
        normalizer_descriptor = _canonical(
            NormalizationPolicy(case_fold=lang.case_fold, accent_fold=lang.accent_fold).descriptor()
        )
        return cls(
            resource_version=_sha256_bytes(resource_descriptor.encode("utf-8")),
            resource_descriptor=resource_descriptor,
            resource_stale_class=RESOURCE_STALE_CLASS,
            normalizer_version=_sha256_bytes(normalizer_descriptor.encode("utf-8")),
            normalizer_descriptor=normalizer_descriptor,
            normalizer_stale_class=NORMALIZER_STALE_CLASS,
        )

    def to_json(self) -> dict:
        """The embeddable header fragment: schema version + the resource/normalizer tiers, each as
        ``{version, stale_class, descriptor}`` with the descriptor parsed back to a dict.

        The descriptor is emitted as a parsed dict (readability); the version↔descriptor binding is
        re-established by re-canonicalizing the emitted dict through ``_canonical`` (test 7), valid
        because ``_canonical`` is round-trip stable (test 16).
        """
        return {
            "schema_version": self.schema_version,
            "resource": {
                "version": self.resource_version,
                "stale_class": self.resource_stale_class,
                "descriptor": json.loads(self.resource_descriptor),
            },
            "normalizer": {
                "version": self.normalizer_version,
                "stale_class": self.normalizer_stale_class,
                "descriptor": json.loads(self.normalizer_descriptor),
            },
        }
