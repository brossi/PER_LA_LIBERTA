"""S4.3 / B-4 — handle policy, rendered handles, and alias records (``handles.py``).

The **Phase-1** slice (s4_plan §4.2): the per-module validators here raise the ``EC.*`` codes directly
and are red-tested against in-memory dataclasses; the aggregate ``validate_structure_map`` + loader
compose them at B-5. Done-when → inv 6 (rendered-handle cheat), 8, 9, 18, 19, 15.

Invariants (each proven red by a targeted SUT mutation — red-first, ENGINE_STRUCTURE_PLAN §9; the
mutation harness runs under ``PYTHONDONTWRITEBYTECODE=1`` / ``__pycache__`` purge, X13):
  - **inv 8 — ``render_handle``** renders three policies × three formats, folds ancestor context into
    the ``designation-string`` slug, and disambiguates colliding siblings by an ordinal suffix. Exact
    strings are pinned, so a corrupted disambiguation/slug/format-separator rule reds a named test.
  - **inv 19 — policy resolvability + class-kind:** ``POLICY_NOT_IN_VOCAB`` (a ``handle_policies`` key
    outside ``block_vocabulary``), ``POLICY_UNRESOLVED`` (no default + no override, or an
    override/default naming an unknown policy), ``CLASS_KIND_MISMATCH`` (a node variant contradicting
    its ``node_class`` kind). The §3.D.1 order (own override → nearest ancestor override → class
    default) is pinned by an inheritance-only positive.
  - **inv 6 (rendered-handle clause)** — a ``node_id`` that is a substring of its own rendered handle
    → ``NODE_ID_DERIVED`` (the S4.3 re-run; the projection.py designation/slug/position cheats are S4.2).
  - **inv 18 — alias integrity:** ``ALIAS_COLLISION`` (two active aliases sharing the uniqueness key —
    enforced at :func:`validate_aliases` **and** re-guarded at :func:`resolve`), ``ALIAS_DANGLING_TARGET``
    (dead target / non-container non-global scope), ``ALIAS_INTERVAL_INVALID`` / ``ALIAS_TEMPORAL_INCOMPLETE``
    (the §3.D.5 temporal rules, each isolated so its sibling code cannot co-fire, P3B-6).
  - **inv 9 — a handle change leaves ``node_id`` fixed and the old handle survives as an alias** that
    still :func:`resolve`\\ s to the same node (the BR-021 property); deleting the alias makes resolve miss.
  - **inv 15 — neutrality** — ``handles.py`` carries no language/book literal; auto-covered by the
    dynamic ``structure/*.py`` glob in ``test_structure_neutrality.py`` (no test lives here).
"""

from __future__ import annotations

import inspect

import pytest

import engine.structure as structure
from engine.structure import (
    Alias,
    ContainerNode,
    LeafNode,
    ProjectionMap,
    StructureValidationError,
    EC,
    render_handle,
    resolve,
)
from engine.structure.handles import (
    NodeClassSpec,
    validate_aliases,
    validate_handle_policies,
)


# --- builders ------------------------------------------------------------------------------------ #


def _cont(node_id, *, children=(), designation="", title="", handle_policy="", node_class="section"):
    return ContainerNode(
        node_id=node_id,
        node_class=node_class,
        minted_by="human",
        children=children,
        designation=designation,
        title=title,
        handle_policy=handle_policy,
    )


def _leaf(node_id, *, designation="", title="", handle_policy="", node_class="para"):
    return LeafNode(
        node_id=node_id,
        node_class=node_class,
        minted_by="machine",
        designation=designation,
        title=title,
        handle_policy=handle_policy,
    )


def _map(root_id, nodes):
    return ProjectionMap(root_id=root_id, nodes=nodes)


def _codes(err: StructureValidationError) -> set[EC]:
    return set(err.codes)


# A "Book → [Chapter-designated leaves]" map, reused by the render tests.
def _book_map():
    root = _cont("root", children=("a", "b"), designation="Book", node_class="document")
    a = _leaf("a", designation="Chapter One")
    b = _leaf("b", designation="Chapter Two")
    return _map("root", (root, a, b))


# ================================================================================================ #
# inv 8 — render_handle: signature, formats, ancestor context, slug disambiguation, scope
# ================================================================================================ #


def test_render_handle_signature_is_the_pinned_shape():
    # §3.D.2: render_handle(map, node_id, policy, target_format, scope). Positional, five params — the
    # signature inv 8 references. A drifted signature reds here.
    params = list(inspect.signature(render_handle).parameters)
    assert params == ["pmap", "node_id", "policy", "target_format", "scope"]


def test_position_path_renders_distinct_formats_by_separator():
    # position-path: the child-index path from the (global) root, joined by the format's separator —
    # "." short, "_" parse_md, "-" html_slug. Exact strings pin each separator: a mutation swapping a
    # join separator changes the exact rendered string, caught.
    m = _book_map()
    assert render_handle(m, "a", "position-path", "short", "global") == "0.0"
    assert render_handle(m, "a", "position-path", "parse_md", "global") == "0_0"
    assert render_handle(m, "a", "position-path", "html_slug", "global") == "0-0"
    assert render_handle(m, "b", "position-path", "short", "global") == "0.1"  # second child → index 1


def test_position_path_scope_relative_truncates_at_scope():
    # scope = a container node_id renders the path RELATIVE to that container (its subtree), not the
    # global root — the leaf under root renders "0" within scope=root vs "0.0" globally. Drop the
    # scope-truncation and the two coincide → red.
    m = _book_map()
    assert render_handle(m, "a", "position-path", "short", "root") == "0"
    assert render_handle(m, "a", "position-path", "short", "global") == "0.0"


def test_designation_policy_folds_in_ancestor_context():
    # designation-string html_slug includes the ANCESTOR chain (Book › Chapter One → "book-chapter-one"),
    # not just the node's own designation — the ancestor-context case of inv 8. parse_md uses "_", short
    # returns the node's own raw designation.
    m = _book_map()
    assert render_handle(m, "a", "designation-string", "html_slug", "global") == "book-chapter-one"
    assert render_handle(m, "a", "designation-string", "parse_md", "global") == "book_chapter_one"
    assert render_handle(m, "a", "designation-string", "short", "global") == "Chapter One"


def test_designation_handle_changes_when_an_ancestor_designation_changes():
    # The ancestor-context binding: re-render the SAME node after its ancestor's designation changes —
    # the rendered handle changes (the node_id would not, inv 9). A render that ignored ancestors would
    # produce the same string both times.
    a = _leaf("a", designation="Chapter One")
    under_book = _map("root", (_cont("root", children=("a",), designation="Book", node_class="document"), a))
    under_tome = _map("root", (_cont("root", children=("a",), designation="Tome", node_class="document"), a))
    assert render_handle(under_book, "a", "designation-string", "html_slug", "global") == "book-chapter-one"
    assert render_handle(under_tome, "a", "designation-string", "html_slug", "global") == "tome-chapter-one"


def test_designation_slug_disambiguates_colliding_siblings():
    # Two siblings with the SAME designation collide on the full-chain slug; the first keeps the bare
    # slug, the second gets a DOUBLED-separator ordinal suffix ("--2" html, "__2" parse_md). This is
    # the slug-disambiguation case (inv 8): corrupt the suffix rule and the exact second-sibling string
    # changes, caught.
    root = _cont("root", children=("x", "y"), designation="Book", node_class="document")
    x = _leaf("x", designation="Chapter")
    y = _leaf("y", designation="Chapter")
    m = _map("root", (root, x, y))
    assert render_handle(m, "x", "designation-string", "html_slug", "global") == "book-chapter"
    assert render_handle(m, "y", "designation-string", "html_slug", "global") == "book-chapter--2"
    assert render_handle(m, "y", "designation-string", "parse_md", "global") == "book_chapter__2"


def test_disambiguation_does_not_collide_with_a_naturally_numbered_sibling():
    # Adversarial-audit regression (correctness lens F1): a single-separator suffix made the 2nd "Poem"
    # render "book-poem-2", COLLIDING with a natural sibling "Poem 2" → also "book-poem-2". The doubled
    # separator ("--") cannot occur in a natural slug (runs collapse to one sep), so all three siblings
    # render distinctly. A revert to a single-sep suffix reds this.
    root = _cont("root", children=("c0", "c1", "c2"), designation="Book", node_class="document")
    c0 = _leaf("c0", designation="Poem")
    c1 = _leaf("c1", designation="Poem")
    c2 = _leaf("c2", designation="Poem 2")
    m = _map("root", (root, c0, c1, c2))
    handles = {c: render_handle(m, c, "designation-string", "html_slug", "global") for c in ("c0", "c1", "c2")}
    assert handles == {"c0": "book-poem", "c1": "book-poem--2", "c2": "book-poem-2"}
    assert len(set(handles.values())) == 3  # all distinct — the disambiguation contract


def test_three_colliding_siblings_rank_incrementally():
    # Adversarial-audit regression (test-quality lens F4): with only 2 colliding siblings tested, a
    # `min(rank, 2)` mutation survived. A third identical sibling must rank to 3 ("--3").
    root = _cont("root", children=("a", "b", "c"), designation="Book", node_class="document")
    nodes = (root,) + tuple(_leaf(i, designation="Chapter") for i in ("a", "b", "c"))
    m = _map("root", nodes)
    assert render_handle(m, "a", "designation-string", "html_slug", "global") == "book-chapter"
    assert render_handle(m, "b", "designation-string", "html_slug", "global") == "book-chapter--2"
    assert render_handle(m, "c", "designation-string", "html_slug", "global") == "book-chapter--3"
    assert render_handle(m, "c", "designation-string", "parse_md", "global") == "book_chapter__3"


def test_designation_render_is_scope_relative():
    # Adversarial-audit regression (test-quality lens F2): designation-string rendering under a
    # container scope was untested (only position-path scope was). Under scope = the "Part One"
    # container, the leaf's handle drops the ancestry above the scope → "chapter", vs the global
    # "book-part-one-chapter". A `scope → SCOPE_GLOBAL` mutation in render_handle reds this.
    root = _cont("root", children=("part",), designation="Book", node_class="document")
    part = _cont("part", children=("ch",), designation="Part One", node_class="section")
    ch = _leaf("ch", designation="Chapter")
    m = _map("root", (root, part, ch))
    assert render_handle(m, "ch", "designation-string", "html_slug", "global") == "book-part-one-chapter"
    assert render_handle(m, "ch", "designation-string", "html_slug", "part") == "chapter"


def test_position_path_own_scope_is_zero_for_every_node():
    # Delta-audit regression (new-code correctness): render with scope == the node itself (scope=self,
    # the internal call the narrowed derivation check makes) must give position-path "0" for EVERY node
    # — self is the root of its own scope. Before the _index_path scope-root guard, a 3rd child rendered
    # its real sibling index "2", making the own-scoped derivation verdict position-dependent.
    root = _cont("root", children=("a", "b", "c"), node_class="document")
    m = _map("root", (root,) + tuple(_leaf(i) for i in ("a", "b", "c")))
    for n in ("a", "b", "c"):
        assert render_handle(m, n, "position-path", "short", n) == "0"


def test_empty_designation_siblings_do_not_get_a_disambiguation_suffix():
    # Delta-audit regression (new-code correctness, F2 residual): an EMPTY own slug is not a handle to
    # disambiguate — a "{sep}{sep}{rank}" suffix on nothing is a meaningless "--2" artifact (and it
    # spuriously matched a digit node_id in the own-scoped derivation check). Designation-less siblings
    # render the base with NO suffix (they collide by design — such nodes should use position-path for
    # distinct addresses); dropping the empty-own guard gives "q" a "book--2".
    root = _cont("root", children=("p", "q"), designation="Book", node_class="document")
    m = _map("root", (root, _leaf("p"), _leaf("q")))  # p, q both designation-less
    assert render_handle(m, "q", "designation-string", "html_slug", "global") == "book"


def test_designation_slug_accent_folds_like_a_real_slugifier():
    # The renderer's _slugify NFKD-folds and drops combining marks (word-internal accent too): "Città"
    # → "citta", "Über" → "uber". A revert to an ASCII-only or normalize-without-strip slug changes the
    # exact string (the same single-fixture blind spot the B-3 delta audit caught).
    root = _cont("root", children=("c",), designation="Über", node_class="document")
    c = _leaf("c", designation="Città")
    m = _map("root", (root, c))
    assert render_handle(m, "c", "designation-string", "html_slug", "global") == "uber-citta"


def test_title_policy_renders_from_the_title_field():
    # title policy uses the node's own title (no ancestor chain), distinct from designation-string.
    n = _leaf("n", title="The Preface")
    m = _map("root", (_cont("root", children=("n",), node_class="document"), n))
    assert render_handle(m, "n", "title", "short", "global") == "The Preface"
    assert render_handle(m, "n", "title", "html_slug", "global") == "the-preface"
    assert render_handle(m, "n", "title", "parse_md", "global") == "the_preface"


@pytest.mark.parametrize(
    ("policy", "target_format", "scope"),
    [
        ("bogus-policy", "short", "global"),
        ("position-path", "bogus-format", "global"),
        ("position-path", "short", "b"),  # scope 'b' is a sibling of 'a', not its ancestor
    ],
    ids=["unknown-policy", "unknown-format", "scope-not-ancestor"],
)
def test_render_handle_rejects_bad_policy_format_or_scope(policy, target_format, scope):
    # A caller programming error — an unknown policy/format, or a scope that is not an ancestor of the
    # node — is a ValueError (distinct from the validators' EC codes). Rendering 'a' under scope 'b'
    # (its sibling) must fail rather than silently render global-relative.
    m = _book_map()
    with pytest.raises(ValueError):
        render_handle(m, "a", policy, target_format, scope)


def test_render_handle_rejects_unknown_node():
    m = _book_map()
    with pytest.raises(ValueError):
        render_handle(m, "ghost", "position-path", "short", "global")


# ================================================================================================ #
# inv 19 — handle-policy resolvability + class-kind (POLICY_NOT_IN_VOCAB / POLICY_UNRESOLVED /
#          CLASS_KIND_MISMATCH)
# ================================================================================================ #

# A clean base: document → section → para, every class declared, every class with a position-path
# default. Perturbing ONE axis fires only that axis's code.
_VOCAB = (
    NodeClassSpec("document", "container"),
    NodeClassSpec("section", "container"),
    NodeClassSpec("para", "leaf"),
)
_POLICIES = {"document": "position-path", "section": "position-path", "para": "position-path"}


def _policy_base():
    root = _cont("root", children=("sec",), node_class="document")
    sec = _cont("sec", children=("p",), node_class="section")
    p = _leaf("p", node_class="para")
    return _map("root", (root, sec, p))


def test_clean_policies_validate():
    # The floor every single-violation test perturbs away from.
    validate_handle_policies(_policy_base(), _VOCAB, _POLICIES)  # no raise


def test_handle_policies_key_not_in_vocab_raises():
    # POLICY_NOT_IN_VOCAB: a handle_policies key naming no declared node_class. Every node still
    # resolves (its class has a default), so the code isolates.
    policies = {**_POLICIES, "ghost": "position-path"}
    with pytest.raises(StructureValidationError) as ei:
        validate_handle_policies(_policy_base(), _VOCAB, policies)
    assert _codes(ei.value) == {EC.POLICY_NOT_IN_VOCAB}


def test_used_node_class_with_no_default_and_no_override_is_unresolved():
    # POLICY_UNRESOLVED: 'para' has no default policy and the leaf carries no override / inheritable
    # ancestor override → its effective policy is None. document/section keep their defaults, so only
    # the leaf's code fires.
    policies = {"document": "position-path", "section": "position-path"}  # no 'para'
    with pytest.raises(StructureValidationError) as ei:
        validate_handle_policies(_policy_base(), _VOCAB, policies)
    assert _codes(ei.value) == {EC.POLICY_UNRESOLVED}


def test_per_node_override_naming_unknown_policy_is_unresolved():
    # POLICY_UNRESOLVED (override arm): a per-node handle_policy override that is not a known policy.
    # The default for 'para' exists, so only the bad override makes it unresolved.
    root = _cont("root", children=("sec",), node_class="document")
    sec = _cont("sec", children=("p",), node_class="section")
    p = _leaf("p", node_class="para", handle_policy="not-a-real-policy")
    with pytest.raises(StructureValidationError) as ei:
        validate_handle_policies(_map("root", (root, sec, p)), _VOCAB, _POLICIES)
    assert _codes(ei.value) == {EC.POLICY_UNRESOLVED}


def test_policy_resolves_via_nearest_ancestor_override():
    # The §3.D.1 order — own override → nearest ancestor override → class default. 'para' has NO
    # default; the leaf has NO own override; its ancestor 'sec' carries an override → the leaf inherits
    # it and validates clean. Drop the ancestor walk in _effective_policy and the leaf goes
    # POLICY_UNRESOLVED → this positive reds (the mutation that pins inheritance).
    policies = {"document": "position-path", "section": "position-path"}  # no 'para' default
    root = _cont("root", children=("sec",), node_class="document")
    sec = _cont("sec", children=("p",), node_class="section", handle_policy="designation-string")
    p = _leaf("p", node_class="para")  # no own override → inherits sec's
    validate_handle_policies(_map("root", (root, sec, p)), _VOCAB, policies)  # no raise


def test_own_override_takes_precedence_over_class_default():
    # Own override wins over the class default (order step 1) — bound OBSERVABLY, not vacuously. The
    # class default for 'para' is position-path (under which node_id "book-chapter" is NOT derived); the
    # leaf overrides to 'designation-string' (under which its full handle IS "book-chapter" == node_id).
    # So validate raising NODE_ID_DERIVED can only happen if the OWN override was honored — a mutation
    # that ignored the override / preferred the class default would render position-path and validate
    # CLEAN, reding this test.
    root = _cont("root", children=("book-chapter",), designation="Book", node_class="document")
    p = _leaf("book-chapter", node_class="para", designation="Chapter", handle_policy="designation-string")
    with pytest.raises(StructureValidationError) as ei:
        validate_handle_policies(_map("root", (root, p)), _VOCAB, _POLICIES)
    assert _codes(ei.value) == {EC.NODE_ID_DERIVED}


@pytest.mark.parametrize(
    ("node", "declared_kind"),
    [
        (_cont("bad", node_class="para"), "leaf"),   # a container declared leaf-kind
        (_leaf("bad", node_class="section"), "container"),  # a leaf declared container-kind
    ],
    ids=["container-declared-leaf", "leaf-declared-container"],
)
def test_class_kind_mismatch_raises(node, declared_kind):
    # CLASS_KIND_MISMATCH: a node whose variant contradicts its node_class's declared kind. The kind is
    # declared on the vocab entry; the node's variant is structural — a mismatch fires in BOTH
    # directions (a one-sided check passes one of these).
    root = _cont("root", children=("bad",), node_class="document")
    vocab = (NodeClassSpec("document", "container"), NodeClassSpec(node.node_class, declared_kind))
    policies = {"document": "position-path", node.node_class: "position-path"}
    with pytest.raises(StructureValidationError) as ei:
        validate_handle_policies(_map("root", (root, node)), vocab, policies)
    assert _codes(ei.value) == {EC.CLASS_KIND_MISMATCH}  # isolation: only the kind fault fires


def test_class_kind_either_allows_both_variants():
    # kind 'either' admits a container OR a leaf under the same node_class — no CLASS_KIND_MISMATCH. A
    # mutation that treated 'either' as one specific kind would red one of these.
    root = _cont("root", children=("c", "lf"), node_class="flex")
    c = _cont("c", children=("l2",), node_class="flex")
    l2 = _leaf("l2", node_class="flex")
    lf = _leaf("lf", node_class="flex")
    vocab = (NodeClassSpec("flex", "either"),)
    policies = {"flex": "position-path"}
    validate_handle_policies(_map("root", (root, c, l2, lf)), vocab, policies)  # no raise


# ================================================================================================ #
# inv 6 (rendered-handle clause) — node_id must not be a substring of its own rendered handle
# ================================================================================================ #


def test_node_id_equal_to_rendered_handle_raises_derived():
    # The S4.3 re-run of inv 6 (§3.C.3): the leaf's node_id "book-chapter" equals the full-chain
    # designation html_slug (Book › Chapter) — a case the S4.2 single-field slug(designation) cheat does
    # NOT catch (slug("Chapter") == "chapter" != "book-chapter"), so it is genuinely the rendered-handle
    # clause's job. Isolation: the otherwise-clean map fires only NODE_ID_DERIVED, and the finding names
    # the rendered handle (so dropping this clause reds a named test).
    root = _cont("root", children=("book-chapter",), designation="Book", node_class="document")
    leaf = _leaf("book-chapter", designation="Chapter")
    vocab = (NodeClassSpec("document", "container"), NodeClassSpec("para", "leaf"))
    policies = {"document": "designation-string", "para": "designation-string"}
    with pytest.raises(StructureValidationError) as ei:
        validate_handle_policies(_map("root", (root, leaf)), vocab, policies)
    assert _codes(ei.value) == {EC.NODE_ID_DERIVED}
    assert "rendered handle" in str(ei.value)


def test_node_id_proper_substring_of_own_handle_raises_derived():
    # A PROPER substring of the node's OWN-scoped handle: node_id "hap" sits inside the own designation
    # slug "chapter" (not equal to it). This makes the OWN arm a *substring* test, not equality — a
    # mutation weakening `nid in own` to `nid == own` survives the equality fixtures but reds here.
    root = _cont("root", children=("hap",), designation="Book", node_class="document")
    leaf = _leaf("hap", designation="Chapter")  # own slug "chapter" ⊃ "hap"
    vocab = (NodeClassSpec("document", "container"), NodeClassSpec("para", "leaf"))
    policies = {"document": "designation-string", "para": "designation-string"}
    with pytest.raises(StructureValidationError) as ei:
        validate_handle_policies(_map("root", (root, leaf)), vocab, policies)
    assert _codes(ei.value) == {EC.NODE_ID_DERIVED}


def test_parse_md_derived_node_id_raises_derived():
    # Adversarial-audit regression (test-quality lens F1): the parse_md derivation arm was untested (all
    # inv6 ids were hyphenated, caught via html_slug). node_id "book_chapter" equals the full parse_md
    # handle only (html_slug renders "book-chapter"), so ONLY the parse_md arm fires. Dropping the
    # parse_md target from the derivation loop reds this.
    root = _cont("root", children=("book_chapter",), designation="Book", node_class="document")
    leaf = _leaf("book_chapter", designation="Chapter")
    vocab = (NodeClassSpec("document", "container"), NodeClassSpec("para", "leaf"))
    policies = {"document": "designation-string", "para": "designation-string"}
    with pytest.raises(StructureValidationError) as ei:
        validate_handle_policies(_map("root", (root, leaf)), vocab, policies)
    assert _codes(ei.value) == {EC.NODE_ID_DERIVED}


def test_node_id_inside_an_ancestor_slug_only_validates_clean():
    # Adversarial-audit regression (correctness lens F2): the derivation clause must use EQUALITY on the
    # full ancestor-inclusive handle, SUBSTRING only on the own-scoped handle. node_id "abc" is opaque
    # w.r.t. the leaf ("Widgets") but appears inside the ANCESTOR "ABChapter" → full handle
    # "abchapter-widgets" contains "abc". A substring test on the full handle would falsely reject this
    # legitimately-opaque id; the narrowed rule validates it clean. A `nid == full` → `nid in full`
    # mutation reds this.
    root = _cont("root", children=("abc",), designation="ABChapter", node_class="document")
    leaf = _leaf("abc", designation="Widgets")
    vocab = (NodeClassSpec("document", "container"), NodeClassSpec("para", "leaf"))
    policies = {"document": "designation-string", "para": "designation-string"}
    validate_handle_policies(_map("root", (root, leaf)), vocab, policies)  # no raise


def test_opaque_node_id_not_a_substring_of_its_handle_validates_clean():
    # The positive: a node carrying a designation but an opaque, independently-minted id (not a
    # substring of any rendered slug) validates. Proves the clause keys on the substring MATCH, not the
    # mere presence of a designation.
    root = _cont("root", children=("n-7",), designation="Book", node_class="document")
    leaf = _leaf("n-7", designation="Chapter")
    vocab = (NodeClassSpec("document", "container"), NodeClassSpec("para", "leaf"))
    policies = {"document": "designation-string", "para": "designation-string"}
    validate_handle_policies(_map("root", (root, leaf)), vocab, policies)  # no raise


def test_position_shaped_node_id_is_not_derived_when_not_its_own_position():
    # Delta-audit regression (new-code correctness F1): under position-path, a node_id equal to its
    # SIBLING INDEX ("2" as the 3rd child) is NOT position-derived — its own-scoped position is "0" (self
    # is its own scope-root) and its full path is "0-2" ≠ "2". Before the _index_path scope-root guard,
    # the own-scope wrongly rendered "2", flagging this opaque id AND making the verdict sibling-position
    # dependent (node_id "0" flagged as 1st child, cleared as 3rd). Now it validates clean.
    root = _cont("root", children=("x", "y", "2"), node_class="document")
    nodes = (root, _leaf("x"), _leaf("y"), _leaf("2"))
    vocab = (NodeClassSpec("document", "container"), NodeClassSpec("para", "leaf"))
    policies = {"document": "position-path", "para": "position-path"}
    validate_handle_policies(_map("root", nodes), vocab, policies)  # no raise


# ================================================================================================ #
# inv 18 — alias integrity (collision / dangling / temporal), at validate AND at resolve
# ================================================================================================ #

# A tiny map with two live nodes to point aliases at.
def _alias_map():
    root = _cont("root", children=("sec", "p"), node_class="document")
    sec = _cont("sec", children=(), node_class="section", designation="s")  # a live container scope
    p = _leaf("p", node_class="para")
    return _map("root", (root, sec, p))


def _alias(value="old", *, handle_type="html_slug", scope="global", locale="en",
           target="p", valid_from=0, valid_to=None, status="active"):
    return Alias(
        handle_type=handle_type,
        value=value,
        scope=scope,
        locale_or_witness=locale,
        target_node_id=target,
        valid_from=valid_from,
        valid_to=valid_to,
        status=status,
    )


def test_clean_aliases_validate():
    aliases = (_alias(value="old-a", target="p"), _alias(value="old-b", target="sec"))
    validate_aliases(_alias_map(), aliases, map_revision=3)  # no raise


def test_alias_interval_boundaries_validate_clean():
    # Adversarial-audit regression (test-quality lens F3): every interval comparison in validate_aliases
    # could be flipped by one operator and survive, because no LEGITIMATE boundary-touching alias was
    # tested. All three below are valid and must validate clean at map_revision=5:
    #   a: active, valid_from == map_revision (created this revision)      → guards `valid_from > rev`
    #   b: retired, single-revision interval valid_to == valid_from        → guards `valid_to < from`
    #   c: active, valid_to == map_revision (interval closes exactly now)   → guards `rev > valid_to`
    aliases = (
        _alias(value="a", target="p", status="active", valid_from=5, valid_to=None),
        _alias(value="b", target="sec", status="retired", valid_from=2, valid_to=2),
        _alias(value="c", target="p", status="active", valid_from=1, valid_to=5),
    )
    validate_aliases(_alias_map(), aliases, map_revision=5)  # no raise


def test_active_alias_collision_raises():
    # ALIAS_COLLISION: two active aliases sharing (handle_type, value, scope, locale) — even pointing at
    # different nodes, the key must be unique. Distinct targets so nothing else co-fires.
    aliases = (_alias(value="dup", target="p"), _alias(value="dup", target="sec"))
    with pytest.raises(StructureValidationError) as ei:
        validate_aliases(_alias_map(), aliases, map_revision=3)
    assert _codes(ei.value) == {EC.ALIAS_COLLISION}


def test_two_active_aliases_with_different_keys_do_not_collide():
    # Isolation floor for the collision check: same value but different locale is a different key → no
    # collision. Drop the locale from the key and this reds (a spurious collision).
    aliases = (_alias(value="same", locale="en", target="p"), _alias(value="same", locale="fr", target="p"))
    validate_aliases(_alias_map(), aliases, map_revision=3)  # no raise


def test_alias_dangling_target_raises():
    # ALIAS_DANGLING_TARGET: a target_node_id naming no live node.
    aliases = (_alias(value="old", target="ghost"),)
    with pytest.raises(StructureValidationError) as ei:
        validate_aliases(_alias_map(), aliases, map_revision=3)
    assert _codes(ei.value) == {EC.ALIAS_DANGLING_TARGET}


def test_alias_non_global_scope_must_be_a_live_container():
    # A non-global scope must name a live CONTAINER node. 'p' is a live leaf → ALIAS_DANGLING_TARGET;
    # the container 'sec' would be fine. target stays live so only the scope fault fires.
    aliases = (_alias(value="old", scope="p", target="sec"),)
    with pytest.raises(StructureValidationError) as ei:
        validate_aliases(_alias_map(), aliases, map_revision=3)
    assert _codes(ei.value) == {EC.ALIAS_DANGLING_TARGET}


def test_alias_non_global_scope_naming_a_live_container_is_ok():
    # The positive: scope = the live container 'sec' resolves. Pins that the scope check accepts a
    # container (not just 'global') — a mutation rejecting every non-global scope reds here.
    aliases = (_alias(value="old", scope="sec", target="p"),)
    validate_aliases(_alias_map(), aliases, map_revision=3)  # no raise


def test_alias_interval_invalid_valid_to_before_valid_from():
    # ALIAS_INTERVAL_INVALID (valid_to < valid_from). A retired alias with a well-formed status so
    # TEMPORAL_INCOMPLETE cannot co-fire (valid_to is present) — the code isolates (P3B-6).
    aliases = (_alias(value="old", status="retired", valid_from=2, valid_to=1),)
    with pytest.raises(StructureValidationError) as ei:
        validate_aliases(_alias_map(), aliases, map_revision=5)
    assert _codes(ei.value) == {EC.ALIAS_INTERVAL_INVALID}


def test_alias_interval_invalid_valid_from_after_current_revision():
    # ALIAS_INTERVAL_INVALID (valid_from > map_revision): an alias from the future. Active + open
    # interval so TEMPORAL_INCOMPLETE cannot co-fire. Pins the from-after-current arm independently of
    # the to-before-from arm.
    aliases = (_alias(value="old", status="active", valid_from=9, valid_to=None),)
    with pytest.raises(StructureValidationError) as ei:
        validate_aliases(_alias_map(), aliases, map_revision=5)
    assert _codes(ei.value) == {EC.ALIAS_INTERVAL_INVALID}


def test_alias_temporal_incomplete_retired_missing_valid_to():
    # ALIAS_TEMPORAL_INCOMPLETE: a non-active (retired) alias must carry a valid_to. Well-formed
    # valid_from (≤ current) so INTERVAL_INVALID cannot co-fire — the code isolates.
    aliases = (_alias(value="old", status="retired", valid_from=1, valid_to=None),)
    with pytest.raises(StructureValidationError) as ei:
        validate_aliases(_alias_map(), aliases, map_revision=5)
    assert _codes(ei.value) == {EC.ALIAS_TEMPORAL_INCOMPLETE}


def test_alias_temporal_incomplete_active_past_its_interval():
    # ALIAS_TEMPORAL_INCOMPLETE: an active alias whose interval already closed (map_revision beyond
    # valid_to). The interval itself is well-formed (valid_to ≥ valid_from, valid_from ≤ current) so
    # INTERVAL_INVALID cannot co-fire — isolates the active-arm of Rule B from the retired-arm.
    aliases = (_alias(value="old", status="active", valid_from=1, valid_to=2),)
    with pytest.raises(StructureValidationError) as ei:
        validate_aliases(_alias_map(), aliases, map_revision=5)
    assert _codes(ei.value) == {EC.ALIAS_TEMPORAL_INCOMPLETE}


# --- resolve: default (active), re-guard collision, historical (at_revision) --------------------- #


def test_resolve_default_returns_the_active_target():
    # resolve maps a retired handle string back to the current node via an active alias.
    m = _alias_map()
    aliases = (_alias(value="old-handle", target="p"),)
    assert resolve(m, aliases, handle_type="html_slug", value="old-handle", scope="global", locale_or_witness="en") == "p"


def test_resolve_missing_handle_returns_none():
    m = _alias_map()
    aliases = (_alias(value="old-handle", target="p"),)
    assert resolve(m, aliases, handle_type="html_slug", value="absent", scope="global", locale_or_witness="en") is None


def test_resolve_reguards_active_alias_collision():
    # inv 18 C-8: colliding active aliases constructed directly (bypassing validate_aliases), then
    # resolve() — resolve RE-GUARDS uniqueness and raises ALIAS_COLLISION rather than silently picking
    # one. Remove the resolve-time re-guard and this survives (resolve returns some target).
    m = _alias_map()
    aliases = (_alias(value="dup", target="p"), _alias(value="dup", target="sec"))
    with pytest.raises(StructureValidationError) as ei:
        resolve(m, aliases, handle_type="html_slug", value="dup", scope="global", locale_or_witness="en")
    assert _codes(ei.value) == {EC.ALIAS_COLLISION}  # resolve raises only the collision code


def test_resolve_default_ignores_retired_but_at_revision_finds_it():
    # Default resolve considers only active aliases (a retired one misses); at_revision=N resolves the
    # alias whose interval contained N (historical lookup). Pins that the status/interval filter is real
    # — a mutation ignoring status would resolve the retired alias by default.
    m = _alias_map()
    retired = _alias(value="gone", target="sec", status="retired", valid_from=1, valid_to=3)

    def _at(rev):
        return resolve(m, (retired,), handle_type="html_slug", value="gone", scope="global", locale_or_witness="en", at_revision=rev)

    assert resolve(m, (retired,), handle_type="html_slug", value="gone", scope="global", locale_or_witness="en") is None
    assert _at(2) == "sec"
    # BOTH interval bounds are INCLUSIVE, and a revision outside [1, 3] misses (test-quality lens F3:
    # the boundary was untested, so a `<`↔`<=` flip on either bound survived). valid_from and valid_to
    # both resolve; valid_from-1 and valid_to+ do not.
    assert _at(1) == "sec"   # == valid_from (inclusive lower)
    assert _at(3) == "sec"   # == valid_to (inclusive upper)
    assert _at(0) is None    # valid_from - 1 (below the interval)
    assert _at(5) is None    # above valid_to


# ================================================================================================ #
# inv 9 — a handle change leaves node_id fixed; the old handle survives as a resolvable alias
# ================================================================================================ #


def test_handle_change_leaves_node_id_fixed_and_old_handle_aliased():
    # The BR-021 property. A node keeps its opaque node_id "n-3" while its designation changes from
    # "Old Title" (→ handle "old-title") to "New Title" (→ "new-title"); a hand-authored active alias
    # preserves the old handle, so resolve("old-title") still returns "n-3". The new handle differs from
    # the alias value (the change is real).
    root = _cont("root", children=("n-3",), node_class="document", designation="Book")
    renamed = _leaf("n-3", designation="New Title")
    m = _map("root", (root, renamed))
    new_handle = render_handle(m, "n-3", "designation-string", "html_slug", "global")
    assert new_handle == "book-new-title"
    old_alias = _alias(value="book-old-title", target="n-3")
    assert resolve(m, (old_alias,), handle_type="html_slug", value="book-old-title", scope="global", locale_or_witness="en") == "n-3"
    # deleting the alias makes the old handle unresolvable (the mutation the alias exists to survive)
    assert resolve(m, (), handle_type="html_slug", value="book-old-title", scope="global", locale_or_witness="en") is None
    assert renamed.node_id == "n-3"  # unchanged across the rename


# ================================================================================================ #
# construction hygiene + export surface
# ================================================================================================ #


@pytest.mark.parametrize("blank", ["handle_type", "value", "scope", "locale_or_witness", "target_node_id", "status"])
def test_alias_rejects_blank_core_fields(blank):
    fields = dict(handle_type="html_slug", value="v", scope="global", locale_or_witness="en",
                  target_node_id="p", valid_from=0, valid_to=None, status="active")
    fields[blank] = ""
    with pytest.raises(ValueError):
        Alias(**fields)


@pytest.mark.parametrize("bad_from", [-1, True])
def test_alias_rejects_non_ordinal_valid_from(bad_from):
    # valid_from is a non-negative int map_revision; bool is an int subclass and is excluded so a stray
    # True can't ride in as revision 1.
    with pytest.raises(ValueError):
        Alias(handle_type="html_slug", value="v", scope="global", locale_or_witness="en",
              target_node_id="p", valid_from=bad_from)


@pytest.mark.parametrize("bad_to", [True, "x", 1.5])
def test_alias_rejects_non_ordinal_valid_to(bad_to):
    # valid_to mirrors valid_from: None or a plain int map_revision — bool/str/float excluded (bool is
    # an int subclass, so a stray True must not ride in as revision 1). Untested before the adversarial
    # audit (test-quality lens F5): the valid_to guard could be dropped and survive.
    with pytest.raises(ValueError):
        Alias(handle_type="html_slug", value="v", scope="global", locale_or_witness="en",
              target_node_id="p", valid_from=0, valid_to=bad_to)


def test_node_class_spec_rejects_unknown_kind():
    with pytest.raises(ValueError):
        NodeClassSpec("document", "not-a-kind")
    with pytest.raises(ValueError):
        NodeClassSpec("", "container")  # empty name


def test_handle_surface_is_exported():
    # R2-02 amendment: the S4.3 public surface (render_handle / resolve / Alias) resolves on the
    # package. A dropped re-export AttributeErrors here rather than passing green (validate_bindings).
    for name in ("render_handle", "resolve", "Alias"):
        assert hasattr(structure, name), f"{name!r} not exported from engine.structure"
