"""S4.3 — handle policy, rendered handles, and alias records over the L2 projection (s4_plan §3.D).

A ``node_id`` is opaque and permanent (S4.2); a **handle** is the *rendered*, human-facing address of
a node — a section number, a slug, a markdown anchor key. Handles are **derived, never persisted**
(§3.D.3): this module renders them on demand from a node's position/designation/title under a declared
per-``node_class`` **handle policy**, and never stores the result. When a designation changes the
handle re-renders, but the ``node_id`` stays fixed and the *old* handle survives as a hand-authored
**alias** that still :func:`resolve`\\ s to the same node — the BR-021 win (§3.D.7, inv 9).

This is the **Phase-1** slice (s4_plan §4.2): the per-module validators here raise the ``EC.*`` codes
**directly** and are red-tested against in-memory dataclasses; the aggregate ``validate_structure_map``
+ born-agnostic loader compose them at B-5.

What lives here (S4.3 / M-S4.3):

- :func:`render_handle` ``(pmap, node_id, policy, target_format, scope)`` — the derived-only renderer
  (§3.D.2). Three policies (``position-path`` | ``designation-string`` | ``title``, the tracker's open
  set) × three target formats (``short`` | ``parse_md`` | ``html_slug``). ``designation-string`` folds
  in **ancestor context** (the chain from the ``scope`` boundary down to the node) and **disambiguates
  colliding siblings** by an ordinal suffix (inv 8).
- :class:`Alias` + :func:`resolve` — a hand-authored retired-handle record with a temporal coordinate
  and the resolver that maps an old handle back to its node. Active-alias uniqueness is re-guarded here
  at resolve time (``ALIAS_COLLISION``) in addition to :func:`validate_aliases` at load (inv 18, §3.D.4).
- :func:`validate_handle_policies` — policy resolvability (``POLICY_NOT_IN_VOCAB`` /
  ``POLICY_UNRESOLVED``), class-kind ↔ slot (``CLASS_KIND_MISMATCH``), and the S4.3 re-run of inv 6's
  **substring-of-rendered-handle** derivation cheat (``NODE_ID_DERIVED``) — now that a renderer exists
  to compare against (§3.C.3, inv 19).
- :func:`validate_aliases` — active-alias uniqueness, target/scope liveness, and the §3.D.5 temporal
  rules (``ALIAS_COLLISION`` / ``ALIAS_DANGLING_TARGET`` / ``ALIAS_INTERVAL_INVALID`` /
  ``ALIAS_TEMPORAL_INCOMPLETE``, inv 18).
- :func:`validate_block_vocabulary` (S4.4/B-5, single-sourced here beside :class:`NodeClassSpec`) —
  the §3.E.7/§4.5 vocab hygiene (``VOCAB_UNKNOWN_COLLISION`` / ``VOCAB_EMPTY`` / ``VOCAB_DUPLICATE`` /
  ``VOCAB_UNUSED``), normalized exact-match only (NFC + casefold + strip, X17). ``NodeClassSpec``
  gained its persisted ``status`` (active|reserved) at B-5, and ``HANDLE_RENDERER_VERSION`` lives
  here for the S4.4 manifest to stamp (§3.D.6).

Neutral core (inv 15): every policy / format / kind / status token is a **structural** wire string —
no source-language heading, book entity, or typeface literal (the S0.2 scan globs this module).
``_slugify`` is deliberately its *own* fold, distinct from :func:`engine.structure.projection._slug`:
that one only has to recognise the ``node_id == slug(designation)`` *cheat shape*; this one is the
renderer's per-policy ``html_slug``/``parse_md`` output. They may diverge (the renderer is versioned,
§3.D.6); keeping them separate is intentional, not duplication to fold.

Not here (owned by neighbours): the ``handle_renderer_version`` mismatch **routing** (S8.1, §3.D.6);
auto-minting an alias on a designation/renderer change (aliases are hand-authored, §3.D.7); persisted
rendered handles (§3.D.3); the JSON schema + manifest that will carry ``handle_policies`` /
``block_vocabulary`` / ``map_revision`` on disk (S4.4/B-5 — here they are plain call arguments).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from engine.structure.classify import UNKNOWN
from engine.structure.errors import EC, StructureValidationError
from engine.structure.projection import ContainerNode, Node, ProjectionMap

#: The handle policies the renderer understands (§3.D.1, tracker S4.3 open set). A per-node override or
#: a ``handle_policies`` default naming anything outside this set is ``POLICY_UNRESOLVED`` (inv 19).
POLICY_POSITION_PATH = "position-path"
POLICY_DESIGNATION = "designation-string"
POLICY_TITLE = "title"
HANDLE_POLICIES = frozenset({POLICY_POSITION_PATH, POLICY_DESIGNATION, POLICY_TITLE})

#: The rendered target formats (§3.D.2). ``short`` is the compact own-field/dotted form; ``parse_md``
#: and ``html_slug`` are the two collision-sensitive slug forms (``_`` vs ``-`` separated).
TARGET_SHORT = "short"
TARGET_PARSE_MD = "parse_md"
TARGET_HTML_SLUG = "html_slug"
TARGET_FORMATS = frozenset({TARGET_SHORT, TARGET_PARSE_MD, TARGET_HTML_SLUG})

#: A ``block_vocabulary`` entry's kind (§3.B.2): the slot shape a ``node_class`` admits. ``either``
#: permits both variants; the others pin the node to one (``CLASS_KIND_MISMATCH`` otherwise, inv 19).
KIND_CONTAINER = "container"
KIND_LEAF = "leaf"
KIND_EITHER = "either"
NODE_CLASS_KINDS = frozenset({KIND_CONTAINER, KIND_LEAF, KIND_EITHER})

#: Alias status vocabulary (§3.D.4). Only an ``active`` alias participates in default :func:`resolve`
#: and in the uniqueness key; a retired alias is history addressable via ``resolve(..., at_revision=N)``.
ALIAS_ACTIVE = "active"
ALIAS_RETIRED = "retired"

#: A ``block_vocabulary`` entry's lifecycle status (§3.E.7): ``active`` entries must be used by some
#: node (else ``VOCAB_UNUSED``); ``reserved`` is the honest way to declare a name held for a later
#: book/milestone without tripping the dead-config check. Closed set, validated at construction.
STATUS_ACTIVE = "active"
STATUS_RESERVED = "reserved"
NODE_CLASS_STATUSES = frozenset({STATUS_ACTIVE, STATUS_RESERVED})

#: The rendered-handle rule version (§3.D.6): **stamped** into the structure-map manifest by S4.4's
#: assembly and bumped whenever a slug/disambiguation/format rule in this module changes, so S8.1 can
#: later compare stored-vs-live and route a handle-review/alias-migration diagnostic. S4 reserves and
#: stamps the field only — no mismatch comparison is implemented here.
HANDLE_RENDERER_VERSION = 1

#: The global resolution namespace (§3.D.4). Any other ``scope`` must name a live **container** node.
SCOPE_GLOBAL = "global"

#: A handle_policies table maps a ``node_class`` name → its default policy; a per-node override on the
#: node's ``handle_policy`` slot (or the nearest ancestor's) takes precedence (§3.D.1).
HandlePolicies = Mapping[str, str]


@dataclass(frozen=True, slots=True)
class NodeClassSpec:
    """A ``block_vocabulary`` header entry (§3.E.7): a ``node_class`` name, the slot ``kind`` it
    admits, and its lifecycle ``status``. S4.3 reads ``name`` → ``kind`` (for ``CLASS_KIND_MISMATCH``)
    and the set of declared names (for ``POLICY_NOT_IN_VOCAB``); S4.4/B-5's
    :func:`validate_block_vocabulary` reads ``status`` for the ``VOCAB_UNUSED`` exemption.
    """

    name: str
    kind: str
    status: str = STATUS_ACTIVE

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("NodeClassSpec.name must be a non-empty node_class label")
        if self.kind not in NODE_CLASS_KINDS:
            raise ValueError(
                f"NodeClassSpec.kind must be one of {sorted(NODE_CLASS_KINDS)}, got {self.kind!r}"
            )
        if self.status not in NODE_CLASS_STATUSES:
            raise ValueError(
                f"NodeClassSpec.status must be one of {sorted(NODE_CLASS_STATUSES)}, got {self.status!r}"
            )


@dataclass(frozen=True, slots=True)
class Alias:
    """A hand-authored retired-handle record (§3.D.4). ``value`` is the literal old handle string;
    ``handle_type`` is which rendered ``target_format`` it preserves; ``scope`` is the resolution
    namespace (``global`` or a container ``node_id``); ``locale_or_witness`` is the locale (a witness
    axis is reserved for S7). ``target_node_id`` is the node it still resolves to. ``valid_from`` /
    ``valid_to`` are ``map_revision`` coordinates (the header clock, §3.D.5) — ``valid_to`` ``None``
    means open-ended. ``status`` gates default resolution (``active``) vs history.

    The active-alias uniqueness **key** is ``(handle_type, value, scope, locale_or_witness)`` — two
    ``active`` aliases sharing it collide (``ALIAS_COLLISION``, inv 18).
    """

    handle_type: str
    value: str
    scope: str
    locale_or_witness: str
    target_node_id: str
    valid_from: int
    valid_to: int | None = None
    status: str = ALIAS_ACTIVE

    def __post_init__(self) -> None:
        for name, val in (
            ("handle_type", self.handle_type),
            ("value", self.value),
            ("scope", self.scope),
            ("locale_or_witness", self.locale_or_witness),
            ("target_node_id", self.target_node_id),
            ("status", self.status),
        ):
            if not val:
                raise ValueError(f"Alias.{name} must be a non-empty wire string")
        # bool is an int subclass — exclude it so a stray True/False can't ride in as a revision.
        if not isinstance(self.valid_from, int) or isinstance(self.valid_from, bool):
            raise ValueError("Alias.valid_from must be an int map_revision coordinate")
        if self.valid_from < 0:
            raise ValueError("Alias.valid_from must be a non-negative map_revision coordinate")
        if self.valid_to is not None and (
            not isinstance(self.valid_to, int) or isinstance(self.valid_to, bool)
        ):
            raise ValueError("Alias.valid_to must be an int map_revision coordinate or None")

    def _key(self) -> tuple[str, str, str, str]:
        """The active-alias uniqueness key (§3.D.4)."""
        return (self.handle_type, self.value, self.scope, self.locale_or_witness)

    def _interval_contains(self, revision: int) -> bool:
        """Whether ``revision`` lies within ``[valid_from, valid_to]`` (``valid_to`` ``None`` = open)."""
        if revision < self.valid_from:
            return False
        return self.valid_to is None or revision <= self.valid_to


# --- tree helpers (parent/ancestor walks over the children edges, resolved through by_id) ---------- #


def _parent_map(pmap: ProjectionMap) -> dict[str, str]:
    """Derive ``child_node_id → parent_node_id`` from the ``children`` edges (§3.B.4: parent is
    derived, not stored). A pre-order walk from ``root_id``; ``setdefault`` keeps the first parent so a
    malformed ``MULTI_PARENT`` map (B-5's report) cannot corrupt the walk, and ``seen`` makes it
    cycle-safe. The root has no entry (it is nobody's child)."""
    parents: dict[str, str] = {}
    seen: set[str] = set()
    stack = [pmap.root_id]
    while stack:
        node_id = stack.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        node = pmap.by_id.get(node_id)
        if not isinstance(node, ContainerNode):
            continue
        for child in node.children:
            parents.setdefault(child, node_id)
            stack.append(child)
    return parents


def _self_and_ancestors(node_id: str, parents: Mapping[str, str]) -> set[str]:
    """The node plus every ancestor reachable by walking ``parents`` up to the root (cycle-guarded)."""
    out = {node_id}
    cur = parents.get(node_id)
    while cur is not None and cur not in out:
        out.add(cur)
        cur = parents.get(cur)
    return out


def _chain_top_down(
    pmap: ProjectionMap, node_id: str, scope: str, parents: Mapping[str, str]
) -> list[str]:
    """The node_ids from just-below ``scope`` down to ``node_id`` inclusive, in top-down (reading)
    order. For ``scope == 'global'`` the chain starts at the root; for a container ``scope`` it starts
    at the scope's child on the path to the node (the scope node itself is excluded as a segment)."""
    chain: list[str] = []
    cur: str | None = node_id
    seen: set[str] = set()
    while cur is not None and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        if scope != SCOPE_GLOBAL and cur == scope:
            break
        cur = parents.get(cur)
    chain.reverse()
    if scope != SCOPE_GLOBAL and chain and chain[0] == scope:
        chain = chain[1:]
    return chain or [node_id]


def _index_path(
    pmap: ProjectionMap, node_id: str, scope: str, parents: Mapping[str, str]
) -> list[int]:
    """The child-index path for the ``position-path`` policy: each node's index in its parent's
    ``children`` (the ``scope`` root — the top of the chain — indexes as ``0``).

    The scope-root guard is load-bearing for ``scope == the node itself`` (scope=self): the chain is
    just ``[node]``, and without the guard ``_index_path`` would read the node's index in its **real**
    parent (its sibling position) rather than ``0`` — making the own-scoped position handle
    sibling-dependent and, via :func:`_node_id_derived_from_handle`, the derived-ness verdict
    position-dependent. Self is the root of its own scope, so it indexes ``0``."""
    out: list[int] = []
    for nid in _chain_top_down(pmap, node_id, scope, parents):
        if scope != SCOPE_GLOBAL and nid == scope:
            out.append(0)  # scope == this node (scope=self): it is the root of its own scope
            continue
        parent_id = parents.get(nid)
        parent = pmap.by_id.get(parent_id) if parent_id is not None else None
        if isinstance(parent, ContainerNode) and nid in parent.children:
            out.append(parent.children.index(nid))
        else:
            out.append(0)  # the scope/global root (no parent within scope) — index 0
    return out


def _slugify(text: str, sep: str) -> str:
    """Fold ``text`` to a slug joined by ``sep``: lowercase, NFKD-decompose and drop combining marks
    (accent-fold, so ``"Città"`` → ``"citta"`` and ``"Über"`` → ``"uber"`` — mark anywhere in the
    word), then collapse every run of non-``a-z0-9`` to a single ``sep`` and strip it from the ends.

    The renderer's slug, distinct by design from :func:`engine.structure.projection._slug` (which only
    recognises the derivation *cheat shape*): this one is versioned output (§3.D.6). Carries no
    language/book literal (inv 15).
    """
    decomposed = unicodedata.normalize("NFKD", text.lower())
    deaccented = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", sep, deaccented).strip(sep)


def _designation_source(node: Node) -> str:
    """The raw string the ``designation-string`` policy slugs — the node's designation (never the
    ``node_id``: a handle must not derive from the identity it addresses — the BR-021 separation, and
    a ``node_id`` fallback would make :func:`validate_handle_policies`'s substring cheat fire on every
    designation-less node). A node with no designation renders an empty designation segment."""
    return node.designation


def _title_source(node: Node) -> str:
    """The raw string the ``title`` policy slugs — the node's title, empty when it has none (no
    ``node_id`` fallback, same reason as :func:`_designation_source`)."""
    return node.title


def _sibling_disambiguator(
    pmap: ProjectionMap,
    node_id: str,
    parents: Mapping[str, str],
    source: Callable[[Node], str],
    sep: str,
) -> str:
    """The slug-disambiguation suffix (§3.D.2, inv 8): among the node's siblings that slug to the
    **same** own segment (in ``children`` order), the first keeps the bare slug and each subsequent one
    gets a ``"{sep}{sep}{rank}"`` suffix (1-based). Empty when the node has no colliding sibling.

    The suffix uses a **doubled** separator on purpose: ``_slugify`` collapses every run of non-alnum to
    a *single* ``sep``, so no natural sibling slug can contain a ``sep``-``sep`` run — the doubled
    suffix therefore cannot collide with any sibling's natural slug. A single-``sep`` suffix would (a
    2nd ``"Poem"`` disambiguating to ``poem-2`` collides with a natural sibling ``"Poem 2"`` → also
    ``poem-2``), which is the exact collision this guards against. Distinct ranks keep the disambiguated
    forms distinct among themselves, and a naturally-numbered sibling keeps its natural single-``sep``
    slug."""
    parent_id = parents.get(node_id)
    parent = pmap.by_id.get(parent_id) if parent_id is not None else None
    if not isinstance(parent, ContainerNode):
        return ""
    own = _slugify(source(pmap.by_id[node_id]), "-")
    if not own:
        return ""  # an empty own slug (no designation/title) is not a handle to disambiguate — a
        # "{sep}{sep}{rank}" suffix on nothing is meaningless and would spuriously match a digit node_id
        # in the own-scoped derivation check (audit finding: title-less siblings → own handle "--3").
    same = [
        c
        for c in parent.children
        if c in pmap.by_id and _slugify(source(pmap.by_id[c]), "-") == own
    ]
    if len(same) <= 1 or node_id not in same:
        return ""
    rank = same.index(node_id) + 1
    return "" if rank == 1 else f"{sep}{sep}{rank}"


def render_handle(
    pmap: ProjectionMap, node_id: str, policy: str, target_format: str, scope: str
) -> str:
    """Render the derived, non-persisted handle of ``node_id`` under ``policy`` in ``target_format``,
    within ``scope`` (§3.D.2/§3.D.3). ``scope`` is ``'global'`` (relative to the root) or a live
    container ``node_id`` that is an ancestor of the node (relative to it).

    An unknown ``policy`` / ``target_format``, an unknown node, or a ``scope`` that is not an ancestor
    is a caller programming error (``ValueError``) — the *validators* raise ``EC`` codes; the renderer
    presumes a resolved policy and a real node.
    """
    if policy not in HANDLE_POLICIES:
        raise ValueError(f"render_handle: unknown policy {policy!r} (expected one of {sorted(HANDLE_POLICIES)})")
    if target_format not in TARGET_FORMATS:
        raise ValueError(
            f"render_handle: unknown target_format {target_format!r} (expected {sorted(TARGET_FORMATS)})"
        )
    if node_id not in pmap.by_id:
        raise ValueError(f"render_handle: node_id {node_id!r} is not in the map")
    parents = _parent_map(pmap)
    if scope != SCOPE_GLOBAL:
        if scope not in pmap.by_id:
            raise ValueError(f"render_handle: scope {scope!r} names no node")
        if scope not in _self_and_ancestors(node_id, parents):
            raise ValueError(f"render_handle: scope {scope!r} is not an ancestor of {node_id!r}")

    if policy == POLICY_POSITION_PATH:
        parts = [str(i) for i in _index_path(pmap, node_id, scope, parents)]
        if target_format == TARGET_SHORT:
            return ".".join(parts)
        sep = "_" if target_format == TARGET_PARSE_MD else "-"
        return sep.join(parts)

    source = _designation_source if policy == POLICY_DESIGNATION else _title_source
    node = pmap.by_id[node_id]
    if target_format == TARGET_SHORT:
        return source(node)
    sep = "_" if target_format == TARGET_PARSE_MD else "-"
    if policy == POLICY_DESIGNATION:
        chain = _chain_top_down(pmap, node_id, scope, parents)
        raw = " ".join(source(pmap.by_id[nid]) for nid in chain)  # ancestor context
    else:  # POLICY_TITLE — own field only
        raw = source(node)
    return _slugify(raw, sep) + _sibling_disambiguator(pmap, node_id, parents, source, sep)


def resolve(
    pmap: ProjectionMap,
    aliases: Sequence[Alias],
    *,
    handle_type: str,
    value: str,
    scope: str,
    locale_or_witness: str,
    at_revision: int | None = None,
) -> str | None:
    """Resolve a retired handle to its current ``node_id`` via the ``aliases`` (§3.D.5), or ``None`` if
    no alias preserves it. The default considers only ``status:active`` aliases; ``at_revision=N``
    considers any alias whose ``[valid_from, valid_to]`` interval contained ``N`` (historical lookup).

    Re-guards active-alias uniqueness (inv 18, C-8): if the key resolves to **more than one** alias,
    raises ``ALIAS_COLLISION`` rather than silently picking one — the second enforcement site besides
    :func:`validate_aliases`, so a map that bypassed the load-time check still fails at resolve.
    """
    key = (handle_type, value, scope, locale_or_witness)
    matches = [
        a
        for a in aliases
        if a._key() == key
        and (a.status == ALIAS_ACTIVE if at_revision is None else a._interval_contains(at_revision))
    ]
    if not matches:
        return None
    if len(matches) > 1:
        raise StructureValidationError(
            [
                (
                    EC.ALIAS_COLLISION,
                    f"handle {key!r} resolves to {len(matches)} aliases "
                    f"(targets {sorted({a.target_node_id for a in matches})}) — the active-alias key "
                    f"must be unique (§3.D.4)",
                )
            ]
        )
    return matches[0].target_node_id


# --- validators (Phase-1 direct; each raises its collected EC payload) --------------------------- #


def _effective_policy(
    node: Node, pmap: ProjectionMap, parents: Mapping[str, str], handle_policies: HandlePolicies
) -> str | None:
    """The node's effective handle policy by the §3.D.1 order: the node's own ``handle_policy``
    override, else the nearest ancestor's override, else the ``handle_policies`` default for its
    ``node_class``. Returns the resolved token (which the caller checks against
    :data:`HANDLE_POLICIES`), or ``None`` when nothing resolves. An override is returned *as written* —
    an unknown one surfaces as ``POLICY_UNRESOLVED`` at the membership check, not silently ignored."""
    cur: Node | None = node
    seen: set[str] = set()
    while cur is not None and cur.node_id not in seen:
        seen.add(cur.node_id)
        if cur.handle_policy:
            return cur.handle_policy
        parent_id = parents.get(cur.node_id)
        cur = pmap.by_id.get(parent_id) if parent_id is not None else None
    return handle_policies.get(node.node_class)


def validate_handle_policies(
    pmap: ProjectionMap,
    block_vocabulary: Sequence[NodeClassSpec],
    handle_policies: HandlePolicies,
) -> None:
    """Raise :class:`~engine.structure.errors.StructureValidationError` with the collected handle-policy
    codes (inv 19 + inv 6's rendered-handle clause), or return ``None`` when clean:

    - ``POLICY_NOT_IN_VOCAB`` — a ``handle_policies`` key naming no ``block_vocabulary`` entry (§3.D.1).
    - ``CLASS_KIND_MISMATCH`` — a node whose variant contradicts its ``node_class`` declared kind.
    - ``POLICY_UNRESOLVED`` — a node whose effective policy does not resolve to a known policy (a
      missing default *and* no override, or an override/default naming an unknown policy).
    - ``NODE_ID_DERIVED`` — the S4.3 re-run of inv 6: a ``node_id`` that is a **substring of its own
      rendered handle** under its effective policy (§3.C.3). The projection.py cheats (designation /
      slug / position) run at S4.2; this clause needs the renderer, so it lands here.
    """
    findings: list[tuple[EC, str]] = []
    kind_by_class = {spec.name: spec.kind for spec in block_vocabulary}
    parents = _parent_map(pmap)

    for key in handle_policies:
        if key not in kind_by_class:
            findings.append(
                (EC.POLICY_NOT_IN_VOCAB, f"handle_policies key {key!r} is not a declared block_vocabulary node_class")
            )

    for node in pmap.nodes:
        kind = kind_by_class.get(node.node_class)
        if kind == KIND_CONTAINER and not isinstance(node, ContainerNode):
            findings.append(
                (EC.CLASS_KIND_MISMATCH, f"node {node.node_id!r} is a leaf but node_class {node.node_class!r} is kind {KIND_CONTAINER!r}")
            )
        elif kind == KIND_LEAF and isinstance(node, ContainerNode):
            findings.append(
                (EC.CLASS_KIND_MISMATCH, f"node {node.node_id!r} is a container but node_class {node.node_class!r} is kind {KIND_LEAF!r}")
            )

    for node in pmap.nodes:
        policy = _effective_policy(node, pmap, parents, handle_policies)
        if policy not in HANDLE_POLICIES:
            findings.append(
                (
                    EC.POLICY_UNRESOLVED,
                    f"node {node.node_id!r} (node_class {node.node_class!r}) has no resolvable handle "
                    f"policy — effective {policy!r} is not a known policy {sorted(HANDLE_POLICIES)}",
                )
            )
            continue  # cannot render under an unresolved policy — the derivation clause is skipped
        if node.node_id and _node_id_derived_from_handle(pmap, node, policy):
            findings.append(
                (
                    EC.NODE_ID_DERIVED,
                    f"node_id {node.node_id!r} appears derived from its rendered handle "
                    f"(policy {policy}) — a node_id is minted independently of any handle (§3.C.3)",
                )
            )

    if findings:
        raise StructureValidationError(findings)


def _node_id_derived_from_handle(pmap: ProjectionMap, node: Node, policy: str) -> bool:
    """Whether ``node.node_id`` looks derived from its rendered handle — the S4.3 arm of inv 6 (§3.C.3).

    Two shapes, tested across both slug formats (``-`` and ``_``): the id **equals the full**
    ancestor-inclusive rendered handle (the author copied the whole rendered slug into the id), **or**
    the id is a **substring of the node's OWN-scoped** handle — its own designation/title/index slug,
    rendered with ``scope = the node itself`` so the ancestor prefix is dropped.

    The full handle uses *equality*, not substring, on purpose: a substring test against the
    ancestor-inclusive handle false-flags a legitimately-opaque id that merely appears inside an
    **ancestor's** designation slug (audit finding: ``node_id="abc"`` under a container designated
    ``"ABChapter"`` renders ``"abchapter-widgets"`` and ``"abc" ⊂`` that, though ``"abc"`` derives from
    nothing on the node). The own-scoped substring is the genuine own-field derivation signal.

    Bounded residual (accepted): an id that is a *partial ancestor+own span* of the full handle — e.g.
    ``node_id="book-chap"`` under ``"book-chapter"`` — is neither equal to the full handle nor a
    substring of the own slug, so it escapes this secondary check. That is the deliberate cost of
    narrowing the full-handle arm to equality (it is what removes the ancestor false-positive); the
    **primary** non-derivation control remains the arg-free :func:`mint_node_id` seam, and S4.2's
    exact/slug/position cheats are unaffected.
    """
    nid = node.node_id
    for target_format in (TARGET_HTML_SLUG, TARGET_PARSE_MD):
        full = render_handle(pmap, nid, policy, target_format, SCOPE_GLOBAL)
        own = render_handle(pmap, nid, policy, target_format, nid)  # scope=self → no ancestor prefix
        if nid == full or nid in own:
            return True
    return False


def validate_aliases(
    pmap: ProjectionMap, aliases: Sequence[Alias], map_revision: int
) -> None:
    """Raise :class:`~engine.structure.errors.StructureValidationError` with the collected alias codes
    (inv 18), or return ``None`` when clean:

    - ``ALIAS_COLLISION`` — two ``active`` aliases sharing the uniqueness key (§3.D.4).
    - ``ALIAS_DANGLING_TARGET`` — a ``target_node_id`` naming no live node, or a non-``global`` ``scope``
      that is not a live container node.
    - ``ALIAS_INTERVAL_INVALID`` — ``valid_from`` after the current ``map_revision``, or ``valid_to``
      before ``valid_from`` (§3.D.5).
    - ``ALIAS_TEMPORAL_INCOMPLETE`` — a non-``active`` alias missing ``valid_to``, or an ``active`` alias
      whose interval has already closed before ``map_revision`` (§3.D.5).
    """
    findings: list[tuple[EC, str]] = []

    active_groups: dict[tuple[str, str, str, str], int] = {}
    for alias in aliases:
        if alias.status == ALIAS_ACTIVE:
            active_groups[alias._key()] = active_groups.get(alias._key(), 0) + 1
    for key, count in active_groups.items():
        if count >= 2:
            findings.append(
                (EC.ALIAS_COLLISION, f"{count} active aliases share the uniqueness key {key!r} (§3.D.4)")
            )

    for alias in aliases:
        if alias.target_node_id not in pmap.by_id:
            findings.append(
                (EC.ALIAS_DANGLING_TARGET, f"alias target_node_id {alias.target_node_id!r} names no live node")
            )
        if alias.scope != SCOPE_GLOBAL and not isinstance(pmap.by_id.get(alias.scope), ContainerNode):
            findings.append(
                (
                    EC.ALIAS_DANGLING_TARGET,
                    f"alias scope {alias.scope!r} must be 'global' or a live container node",
                )
            )

    for alias in aliases:
        if alias.valid_from > map_revision:
            findings.append(
                (
                    EC.ALIAS_INTERVAL_INVALID,
                    f"alias {alias.value!r} valid_from {alias.valid_from} is after the current map_revision {map_revision}",
                )
            )
        elif alias.valid_to is not None and alias.valid_to < alias.valid_from:
            findings.append(
                (
                    EC.ALIAS_INTERVAL_INVALID,
                    f"alias {alias.value!r} valid_to {alias.valid_to} is before valid_from {alias.valid_from}",
                )
            )
        if alias.status != ALIAS_ACTIVE and alias.valid_to is None:
            findings.append(
                (
                    EC.ALIAS_TEMPORAL_INCOMPLETE,
                    f"retired alias {alias.value!r} must carry a valid_to (§3.D.5)",
                )
            )
        elif (
            alias.status == ALIAS_ACTIVE
            and alias.valid_to is not None
            and map_revision > alias.valid_to
        ):
            findings.append(
                (
                    EC.ALIAS_TEMPORAL_INCOMPLETE,
                    f"active alias {alias.value!r} interval closed at {alias.valid_to} but map_revision is {map_revision}",
                )
            )

    if findings:
        raise StructureValidationError(findings)


def _normalized_vocab_name(name: str) -> str:
    """The §3.E.7/X17 comparison key: Unicode NFC + casefold + strip. Exact-match after this fold is
    the ONLY de-duplication — no fuzzy near-duplicate metric, which would risk rejecting legitimately
    distinct per-book classes."""
    return unicodedata.normalize("NFC", name).casefold().strip()


def validate_block_vocabulary(
    block_vocabulary: Sequence[NodeClassSpec], pmap: ProjectionMap
) -> None:
    """Raise :class:`~engine.structure.errors.StructureValidationError` with the collected
    vocab-hygiene codes (§3.E.7 / §4.5, Tier-2b), or return ``None`` when the vocabulary is clean:

    - ``VOCAB_UNKNOWN_COLLISION`` — an entry that normalizes to :data:`engine.structure.classify.UNKNOWN`
      (a block class indistinguishable from the classifier's abstain sentinel — the S9.1 footgun).
    - ``VOCAB_EMPTY`` — an entry that normalizes to nothing (whitespace-only; the constructor already
      rejects the empty string).
    - ``VOCAB_DUPLICATE`` — two entries sharing one normalized form.
    - ``VOCAB_UNUSED`` — an ``active`` entry no node's ``node_class`` uses (``reserved`` is exempt —
      the honest way to hold a name for later).
    - ``CLASS_NOT_IN_VOCAB`` — a node whose ``node_class`` the vocabulary does not declare (the
      mirror direction; added post-B-7 audit, user-ratified 2026-07-02 — without it an undeclared
      class with a per-node ``handle_policy`` override validated completely clean).

    Usage is matched by the **declared name exactly** (the same key ``kind_by_class`` and the policy
    table resolve by), not the normalized form — normalization exists to catch *collisions between
    declarations*, not to widen what counts as use.
    """
    findings: list[tuple[EC, str]] = []
    used = {node.node_class for node in pmap.nodes}
    declared = {spec.name for spec in block_vocabulary}
    # CLASS_NOT_IN_VOCAB (post-B-7 audit): the mirror of VOCAB_UNUSED — every USED class must be
    # declared. Without this, an undeclared class riding a per-node handle_policy override escaped
    # every check (kind lookup skips, the override short-circuits POLICY_UNRESOLVED). Matched by the
    # declared name exactly, like usage; a RESERVED entry is still a declaration (using it is not an
    # error in S4 — whether use should force active status is S6/S8 policy, not invented here).
    for node in pmap.nodes:
        if node.node_class not in declared:
            findings.append(
                (
                    EC.CLASS_NOT_IN_VOCAB,
                    f"node {node.node_id!r} uses node_class {node.node_class!r}, which "
                    f"block_vocabulary does not declare — the vocabulary is open per-book but "
                    f"always declared (§3.B.2)",
                )
            )
    first_declared: dict[str, str] = {}
    for spec in block_vocabulary:
        normalized = _normalized_vocab_name(spec.name)
        if not normalized:
            findings.append(
                (EC.VOCAB_EMPTY, f"block_vocabulary entry {spec.name!r} normalizes to nothing")
            )
            continue
        if normalized == UNKNOWN:
            findings.append(
                (
                    EC.VOCAB_UNKNOWN_COLLISION,
                    f"block_vocabulary entry {spec.name!r} collides with the classifier abstain "
                    f"sentinel {UNKNOWN!r} after normalization",
                )
            )
        if normalized in first_declared:
            findings.append(
                (
                    EC.VOCAB_DUPLICATE,
                    f"block_vocabulary entry {spec.name!r} collides with {first_declared[normalized]!r} "
                    f"after NFC+casefold+strip normalization",
                )
            )
        else:
            first_declared[normalized] = spec.name
        if spec.status != STATUS_RESERVED and spec.name not in used:
            findings.append(
                (
                    EC.VOCAB_UNUSED,
                    f"block_vocabulary entry {spec.name!r} is active but no node uses it — reserve it "
                    f"or remove it (dead vocabulary, §3.E.7)",
                )
            )
    if findings:
        raise StructureValidationError(findings)
