"""S2.1.3 — witness↔geometry matcher: normalizer, monotone page-locate, token-bow-v1 window
match, and the ``attach_geometry`` overlay (``s2_1_plan.md`` DT-3/DT-8; issue #37).

The OCR backend (#36) yields word boxes from a *different* OCR pass than the witness text, so a
box is not a fact about that text until a matcher proves it. This module is that proof:

- :func:`normalize_tokens` — the **one** shared normalizer (promoted from the S2.0 probe): NFC →
  whitespace split → strip edge punctuation → casefold. Deliberately **no** accent stripping and
  **no** stopword removal in core — both are language opinions (the probe's content-token variant
  stays probe-side as a metric).
- :func:`locate_pages` — DT-3's monotone page-locate: choose monotone boundaries over the witness
  token stream maximizing the summed per-page multiset intersection, via a banded DP (P-2: band =
  :data:`BAND_BAG_MULTIPLIER` × the max page bag) with integer scores only and a deterministic
  **earliest**-boundary tie-break (G-7): among optimal boundary vectors, the lexicographically
  first — computed exactly by a backward suffix DP plus a forward earliest-argmax walk. Boundaries
  are a pure function of the two token streams.
- :func:`match_stream` — DT-8's per-atom window match (``match_method`` :data:`MATCH_METHOD`):
  within its assigned page, greedy multiset token matching with **consumption** (a box token
  consumed by one atom is unavailable to the next — atoms in witness order, token→box assignment
  first-available in canonical box order, so a repeated phrase cannot double-bind, G-24);
  ``match_confidence = matched/total`` (G-5); ``bbox`` = union over **matched boxes only** (G-6);
  the P-4 distinctive-token floor (``matched >= MIN_DISTINCTIVE_TOKENS`` OR one matched
  page-unique token) writes ``ambiguous`` below it — absent, never a plausible wrong bbox. The
  page acceptance rate and the per-atom floor are **required parameters with no defaults**: both
  are proposals ratified only at the slice-1 run report (plan §8), so there is no ruled value to
  bake.
- :func:`attach_geometry` — the R12 overlay, both modes: (a) per-witness stream by direct id
  lookup; (b) canonical stream by resolving ``derived_from`` entries filtered to the sidecar's
  witness. A canonical atom with **no** primary derivation is ``ineligible`` — an eligibility
  outcome, never a match failure (G-25/DT-13); one back-linking to **multiple** primary atoms is
  ``unmatched(multi_primary_derivation)`` — never a silent union or first-pick (G-20). Attachment
  binds stream↔sidecar via ``stream_source_hash`` first (G-15, stale fail-loud) and produces new
  frozen instances; the streams are untouched.

Box emission order is contractually unspecified at the seam (DT-2): the matcher canonicalizes box
order at entry, so its output is invariant to emission order (G-24's determinism red). Pure core:
no language, book, or witness-name literal lives here — the anchor witness and every *unruled*
threshold come in as parameters, while the two ruled algorithm constants (P-2's band multiplier,
P-4's distinctive floor) are baked and value-pin tested (the S0.2 neutrality guard scans this
module).
"""

from __future__ import annotations

import unicodedata
from bisect import bisect_right
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from engine.errors import StaleArtifactError
from engine.structure.atom_store import CANONICAL, WITNESS, AtomStream
from engine.structure.atoms import Atom, Geom
from engine.structure.geometry import PageGeometry
from engine.structure.geom_sidecar import (
    ATOM_MATCHED,
    ATOM_UNMATCHED,
    AtomPages,
    AtomRecord,
    GeomSidecar,
    PAGE_MATCHED,
    PAGE_DECLINED,
    PAGE_ROUTED,
    PageRecord,
    REASON_AMBIGUOUS,
    REASON_BELOW_ATOM_FLOOR,
    REASON_ZERO_MATCH,
    SourceScan,
)

#: The per-atom match algorithm this module implements; written verbatim into every matched
#: record's ``match_method`` (DT-8).
MATCH_METHOD = "token-bow-v1"
#: The page-locate algorithm; written verbatim into the sidecar's ``locate_method`` (DT-3).
LOCATE_METHOD = "monotone-align-v1"
#: P-4 (RULED 2026-07-03): an atom binds only if it matched at least this many tokens OR at least
#: one matched token is unique within its page bag. A partial match below the floor writes
#: ``ambiguous``; a zero-match atom writes ``zero_match`` (it never reaches the floor question).
MIN_DISTINCTIVE_TOKENS = 3
#: P-2 (RULED 2026-07-03: 3; SUPERSEDED by Ben 2026-07-05: 16): the DP band width is this
#: multiple of the largest page bag's token count — boundary candidates per page stay O(band),
#: not O(stream). The 3x width proved narrower than the band-center prior's real error: centers
#: are cumulative-bag-mass positions, and pages holding bag mass but no stream tokens (covers,
#: scan noise, back matter) stretch that estimate by more pages than 3 bags cover — on the PLL
#: slice-1 run the drift reached +10 pages and collapsed the calibration tail to 0% exact while
#: the true pages held ~95% of the atoms' tokens. 16x covers the worst observed drift with ~60%
#: margin at ~10x locate cost (a once-per-book step); evidence + remedy family in
#: engine/docs/probes/s2_1_band_drift.md.
BAND_BAG_MULTIPLIER = 16

# Attach-time outcome vocabulary (never persisted in the sidecar — its per-atom reason enum is
# closed at the three match reasons, R19; these are derived at attach from the sidecar's page
# state and the canonical stream's ``derived_from``).
OUTCOME_MATCHED = "matched"
OUTCOME_UNMATCHED = "unmatched"
OUTCOME_PENDING = "pending"
OUTCOME_DECLINED = "declined"
OUTCOME_INELIGIBLE = "ineligible"
REASON_NO_PRIMARY_DERIVATION = "no_primary_derivation"
REASON_MULTI_PRIMARY_DERIVATION = "multi_primary_derivation"

_NEG = -(10**18)  # impossible-path sentinel; gains are bounded by the stream length, so it never
# climbs into the range of real scores


# --- the shared normalizer (DT-8) ---------------------------------------------------------------- #


def normalize_tokens(text: str) -> list[str]:
    """The one token normalizer page-locate and the matcher share: NFC → whitespace split → strip
    edge punctuation → casefold.

    Edge stripping removes leading/trailing non-alphanumerics per Unicode (so a quote mark, bracket,
    or dash shell comes off either language's tokens without a hand-kept punctuation list); interior
    punctuation (apostrophes, hyphens) stays — splitting contractions is a language opinion. Accents
    are **preserved**: composed and decomposed spellings of the same accented word match through NFC,
    but an accent-stripped form never equals an accented one (no accent folding in core). A token
    that is all punctuation normalizes away."""
    out: list[str] = []
    for raw in unicodedata.normalize("NFC", text).split():
        start = 0
        end = len(raw)
        while start < end and not raw[start].isalnum():
            start += 1
        while end > start and not raw[end - 1].isalnum():
            end -= 1
        if start < end:
            out.append(raw[start:end].casefold())
    return out


# --- monotone page-locate (DT-3) ------------------------------------------------------------------ #


class _BandMax:
    """Range-add / suffix-max over one contiguous integer band (sqrt decomposition) — the
    incremental-scoring structure behind the DP transition: growing the window by one token is a
    +1 range-add over the boundary candidates whose window still has bag capacity for that token,
    and reading a DP cell is a suffix max. Integer values only."""

    __slots__ = ("lo", "n", "bs", "nb", "val", "add", "vmax")

    def __init__(self, lo: int, hi: int) -> None:
        self.lo = lo
        self.n = hi - lo + 1
        self.bs = max(1, int(self.n**0.5))
        self.nb = (self.n + self.bs - 1) // self.bs
        self.val = [_NEG] * self.n
        self.add = [0] * self.nb
        self.vmax = [_NEG] * self.nb

    def activate(self, pos: int, value: int) -> None:
        # No pending-add compensation is needed: the sweep activates position c before adding, and
        # every gain range starts at c+1, so no add (partial or full-block) has ever covered a
        # not-yet-activated position. (The #37 hunt proved a compensation term here is dead code.)
        j = pos - self.lo
        b = j // self.bs
        self.val[j] = value
        if value > self.vmax[b]:
            self.vmax[b] = value

    def add_range(self, plo: int, phi: int) -> None:
        jlo = max(0, plo - self.lo)
        jhi = min(self.n - 1, phi - self.lo)
        if jlo > jhi:
            return
        blo = jlo // self.bs
        bhi = jhi // self.bs
        if blo == bhi:
            self._add_partial(blo, jlo, jhi)
            return
        self._add_partial(blo, jlo, (blo + 1) * self.bs - 1)
        for b in range(blo + 1, bhi):
            self.add[b] += 1
        self._add_partial(bhi, bhi * self.bs, jhi)

    def _add_partial(self, b: int, jlo: int, jhi: int) -> None:
        val = self.val
        for j in range(jlo, jhi + 1):
            if val[j] > _NEG:  # inactive slots must not accumulate adds
                val[j] += 1
        best = _NEG
        for j in range(b * self.bs, min(self.n, (b + 1) * self.bs)):
            if val[j] > best:
                best = val[j]
        self.vmax[b] = best

    def suffix_max(self, pos: int) -> int:
        jlo = max(0, pos - self.lo)
        if jlo >= self.n:
            return _NEG
        blo = jlo // self.bs
        best = _NEG
        for j in range(jlo, min(self.n, (blo + 1) * self.bs)):
            if self.val[j] > _NEG:
                v = self.val[j] + self.add[blo]
                if v > best:
                    best = v
        for b in range(blo + 1, self.nb):
            if self.vmax[b] > _NEG:
                v = self.vmax[b] + self.add[b]
                if v > best:
                    best = v
        return best


def _bands(n_tokens: int, bag_sizes: Sequence[int], width: int) -> list[tuple[int, int]]:
    """Candidate range per boundary: ``c_0``/``c_K`` fixed at the stream ends; interior boundary
    ``c_p`` banded around the cumulative-token-ratio position (DT-3). Monotone centers give
    monotone bands, so a feasible monotone path always exists."""
    total = sum(bag_sizes)
    k = len(bag_sizes)
    half = width // 2
    bands: list[tuple[int, int]] = [(0, 0)]
    cum = 0
    for p in range(1, k):
        cum += bag_sizes[p - 1]
        center = round(n_tokens * cum / total) if total else round(n_tokens * p / k)
        bands.append((max(0, center - half), min(n_tokens, center + half)))
    bands.append((n_tokens, n_tokens))
    return bands


def locate_pages(
    tokens: Sequence[str],
    page_bags: Sequence[Mapping[str, int]],
    *,
    band_tokens: int | None = None,
) -> tuple[int, ...]:
    """Monotone boundaries ``c_0 = 0 <= c_1 <= ... <= c_K = N`` over ``tokens`` maximizing
    the summed multiset intersection of each window ``tokens[c_{p-1}:c_p)`` with its page bag
    (DT-3's pinned objective). Integer scores only; unmatched tokens simply score zero; among
    optimal boundary vectors the **lexicographically earliest** is returned (G-7's pinned
    tie-break).

    ``page_bags`` are the per-page box token bags in scan order. ``band_tokens`` overrides the
    band width (a test seam for pinning band behavior and for whole-range brute-force
    equivalence); the default is the P-2 ruling, :data:`BAND_BAG_MULTIPLIER` × the largest bag.
    """
    k = len(page_bags)
    if k == 0:
        raise ValueError("locate_pages needs at least one page bag")
    bags: list[dict[str, int]] = []
    sizes: list[int] = []
    for i, bag in enumerate(page_bags):
        if not isinstance(bag, Mapping):
            raise ValueError(f"page_bags[{i}] must be a token->count mapping, got {type(bag).__name__}")
        clean: dict[str, int] = {}
        for token, count in bag.items():
            if not isinstance(token, str) or type(count) is not int or count < 0:
                raise ValueError(f"page_bags[{i}] must map str tokens to non-negative int counts")
            if count:
                clean[token] = count
        bags.append(clean)
        sizes.append(sum(clean.values()))
    n = len(tokens)
    if n == 0:
        return (0,) * (k + 1)
    if band_tokens is not None and not (type(band_tokens) is int and band_tokens > 0):
        raise ValueError(f"band_tokens must be a positive integer, got {band_tokens!r}")
    width = band_tokens if band_tokens is not None else max(1, BAND_BAG_MULTIPLIER * max(sizes))
    bands = _bands(n, sizes, width)

    tokens = list(tokens)
    positions: dict[str, list[int]] = {}
    for i, token in enumerate(tokens):
        positions.setdefault(token, []).append(i)

    # Backward suffix DP: dp[p][c] = best score for pages p+1..K given boundary c_p = c. The sweep
    # walks c downward; moving the window start onto token t is a +1 range-add over the end
    # boundaries whose window holds fewer than bag[t] copies of t — a contiguous prefix of the end
    # band, located via t's position list (the O(1)-amortized incremental multiset scoring DT-3
    # pins, in place of re-scoring every window).
    dp: list[dict[int, int] | None] = [None] * (k + 1)
    dp[k] = {n: 0}
    for p in range(k - 1, -1, -1):
        bag = bags[p]  # the transition scores page p+1 (0-indexed p)
        lo_c, hi_c = bands[p]
        nlo, nhi = bands[p + 1]
        nxt = dp[p + 1]
        struct = _BandMax(nlo, nhi)
        cur: dict[int, int] = {}
        for c in range(nhi, lo_c - 1, -1):
            if nlo <= c <= nhi:
                struct.activate(c, nxt[c])
            if c < n:
                t = tokens[c]
                m = bag.get(t, 0)
                if m:
                    plist = positions[t]
                    idx = bisect_right(plist, c)  # occurrences of t strictly after c
                    theta = plist[idx + m - 1] if idx + m - 1 < len(plist) else nhi
                    struct.add_range(c + 1, theta)
            if lo_c <= c <= hi_c:
                cur[c] = struct.suffix_max(c)
        dp[p] = cur

    # Forward walk: with suffix values exact, picking the smallest boundary achieving the global
    # max at each successive page yields the lexicographically earliest optimal vector.
    boundaries = [0]
    c_prev = 0
    for p in range(1, k + 1):
        bag = bags[p - 1]
        lo_c, hi_c = bands[p]
        dpp = dp[p]
        occ: dict[str, int] = {}
        score = 0
        best_total: int | None = None
        best_c: int | None = None
        for c in range(c_prev, hi_c + 1):
            if c >= lo_c and dpp[c] > _NEG:
                total_score = score + dpp[c]
                if best_total is None or total_score > best_total:
                    best_total = total_score
                    best_c = c
            if c < hi_c:
                t = tokens[c]
                cnt = occ.get(t, 0) + 1
                occ[t] = cnt
                if cnt <= bag.get(t, 0):
                    score += 1
        if best_c is None:
            raise RuntimeError(
                "page-locate found no feasible boundary — the band construction's monotone "
                "feasibility invariant is broken"
            )
        boundaries.append(best_c)
        c_prev = best_c
    return tuple(boundaries)


# --- token-bow-v1 window match (DT-8) ------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class MatchOutcome:
    """Everything one :func:`match_stream` run produced, in sidecar-record vocabulary: the located
    ``boundaries``, a :class:`~engine.structure.geom_sidecar.PageRecord` per input page, an
    :class:`~engine.structure.geom_sidecar.AtomRecord` per accepted-page atom (a routed page's
    atoms are pending — no records, G-12), the derived per-atom page attribution (DT-3's
    byproduct), and the per-atom normalizer token counts (the P-5 tripwire's denominators).
    ``witness_id``/``stream_source_hash`` are captured from the matched stream so the sidecar
    builder cannot be handed a different stream's identity."""

    witness_id: str
    stream_source_hash: str
    boundaries: tuple[int, ...]
    pages: Mapping[int, PageRecord]
    atoms: Mapping[str, AtomRecord]
    atom_pages: Mapping[str, AtomPages]
    token_counts: Mapping[str, int]
    locate_failed_pages: tuple[int, ...]


def _canonical_box_order(page: PageGeometry) -> list[int]:
    """Box indices in the stable geometric total order ``(y0, x0, x1, y1, text)`` — deterministic
    regardless of backend emission order (DT-8 pt. 3, G-24)."""
    def key(i: int):
        x0, y0, x1, y1 = page.words[i].bbox
        return (y0, x0, x1, y1, page.words[i].text)

    return sorted(range(len(page.words)), key=key)


def match_stream(
    stream: AtomStream,
    pages: Sequence[PageGeometry],
    *,
    page_accept_rate: float,
    atom_match_floor: float,
    dropped_boxes: Mapping[int, int] | None = None,
    band_tokens: int | None = None,
) -> MatchOutcome:
    """Run page-locate + the per-atom window match for one witness stream against one scan's page
    geometry (DT-3/DT-8).

    ``page_accept_rate`` (a page is accepted when its atom-weighted match rate reaches it) and
    ``atom_match_floor`` (an accepted-page atom writes ``matched`` at or above it) are **required
    with no defaults** — both are ratified only at the slice-1 run report. ``dropped_boxes`` is
    the backend's per-page DT-2 normalization count, passed through to the page records
    (``None`` = the producer had no count). ``band_tokens`` threads to :func:`locate_pages`.

    Per page (scan order), atoms in witness order: each atom greedily consumes matching box
    tokens (first-available in canonical box order); consumption is unconditional — a consumed
    token is unavailable to later atoms whether or not this atom ends up binding. An atom binds
    only past the P-4 distinctive floor; a page below ``page_accept_rate`` routes
    (``stage="match"``) and its atoms stay pending; a page whose located window holds no atoms
    routes as a locate failure (``stage="locate"``, ``signal="empty-window"`` — an S2.1.3 wire
    extension beyond DT-10's stage/signal examples, up for ratification with the run report;
    DT-3's counter alone would leave the page's state unrepresented in the pages map).

    "Atom-weighted match rate" (DT-8's page gate) is token-mass weighting: the page rate is
    ``sum(matched tokens) / sum(atom tokens)`` over the page's atoms — a long unmatched atom
    drags the page down proportionally; it is NOT an unweighted mean of per-atom confidences.
    """
    if stream.kind != WITNESS:
        raise ValueError(
            f"match_stream matches a witness stream against its scan (R19), got kind {stream.kind!r}"
        )
    if not pages:
        raise ValueError("match_stream needs at least one PageGeometry")
    page_numbers = [pg.page for pg in pages]
    # One consecutive scan range (what read_pages yields): a gap would make the derived atom
    # windows name pages the sidecar has no record for (the GeomSidecar window invariant).
    if any(b != a + 1 for a, b in zip(page_numbers, page_numbers[1:])):
        raise ValueError(
            f"pages must arrive as one consecutive scan range in order, got {page_numbers}"
        )
    for name, value in (("page_accept_rate", page_accept_rate), ("atom_match_floor", atom_match_floor)):
        if not (isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= value <= 1.0):
            raise ValueError(f"{name} must be a rate in [0, 1], got {value!r}")
    if dropped_boxes is not None and not isinstance(dropped_boxes, Mapping):
        raise ValueError(f"dropped_boxes must be a page->count mapping or None, got {type(dropped_boxes).__name__}")

    atom_tokens: list[list[str]] = [normalize_tokens(a.text) for a in stream.atoms]
    token_counts = {a.atom_id: len(toks) for a, toks in zip(stream.atoms, atom_tokens)}
    spans: list[tuple[int, int]] = []
    stream_tokens: list[str] = []
    for toks in atom_tokens:
        start = len(stream_tokens)
        stream_tokens.extend(toks)
        spans.append((start, len(stream_tokens)))

    # Page bags from single-token boxes only: a box whose text normalizes to zero tokens (pure
    # punctuation) or several tokens carries no unambiguous token key, so it can never bind —
    # the never-wrongly-bind posture, counted nowhere as a match.
    box_keys: list[list[str | None]] = []
    bags: list[Counter] = []
    for pg in pages:
        keys: list[str | None] = []
        for word in pg.words:
            norm = normalize_tokens(word.text)
            keys.append(norm[0] if len(norm) == 1 else None)
        box_keys.append(keys)
        bags.append(Counter(k for k in keys if k is not None))

    boundaries = locate_pages(stream_tokens, bags, band_tokens=band_tokens)

    # Derived page attribution (DT-3's byproduct): the window of pages an atom's token span
    # overlaps, plus the single assigned page — majority token overlap, earliest on a tie — whose
    # bag the atom matches against and whose record governs its state.
    per_page_atoms: dict[int, list[int]] = {i: [] for i in range(len(pages))}
    atom_windows: dict[str, AtomPages] = {}
    for i, atom in enumerate(stream.atoms):
        start, end = spans[i]
        if start == end:
            # A tokenless atom still needs an address: the page whose window holds its stream
            # position (earliest when it sits exactly on a boundary).
            slot = next(p for p in range(1, len(boundaries)) if boundaries[p] >= start)
            first_idx = last_idx = assigned_idx = slot - 1
        else:
            overlaps: list[tuple[int, int]] = []
            for p in range(1, len(boundaries)):
                ov = min(end, boundaries[p]) - max(start, boundaries[p - 1])
                if ov > 0:
                    overlaps.append((p - 1, ov))
            first_idx = overlaps[0][0]
            last_idx = overlaps[-1][0]
            # max() keeps the first maximum → the earliest page wins an overlap tie
            assigned_idx = max(overlaps, key=lambda item: item[1])[0]
        atom_windows[atom.atom_id] = AtomPages(
            first=pages[first_idx].page, last=pages[last_idx].page, assigned=pages[assigned_idx].page
        )
        per_page_atoms[assigned_idx].append(i)

    page_records: dict[int, PageRecord] = {}
    atom_records: dict[str, AtomRecord] = {}
    locate_failed: list[int] = []
    for p_idx, pg in enumerate(pages):
        dropped = dropped_boxes.get(pg.page) if dropped_boxes is not None else None
        members = per_page_atoms[p_idx]
        if not members:
            locate_failed.append(pg.page)
            page_records[pg.page] = PageRecord(
                status=PAGE_ROUTED, stage="locate", signal="empty-window", value=0.0, dropped_boxes=dropped
            )
            continue

        order = _canonical_box_order(pg)
        available: dict[str, list[int]] = {}
        for box_idx in order:
            key = box_keys[p_idx][box_idx]
            if key is not None:
                available.setdefault(key, []).append(box_idx)
        cursor: dict[str, int] = {}
        original_bag = bags[p_idx]

        tentative: list[tuple[str, AtomRecord]] = []
        matched_sum = 0
        total_sum = 0
        for i in members:
            atom = stream.atoms[i]
            toks = atom_tokens[i]
            total = len(toks)
            matched = 0
            consumed: list[int] = []
            has_page_unique = False
            for t in toks:
                queue = available.get(t)
                at = cursor.get(t, 0)
                if queue is not None and at < len(queue):
                    consumed.append(queue[at])
                    cursor[t] = at + 1
                    matched += 1
                    if original_bag[t] == 1:
                        has_page_unique = True
            matched_sum += matched
            total_sum += total
            confidence = (matched / total) if total else 0.0
            if matched == 0:
                record = AtomRecord(status=ATOM_UNMATCHED, match_confidence=confidence, reason=REASON_ZERO_MATCH)
            elif matched < MIN_DISTINCTIVE_TOKENS and not has_page_unique:
                record = AtomRecord(status=ATOM_UNMATCHED, match_confidence=confidence, reason=REASON_AMBIGUOUS)
            elif confidence < atom_match_floor:
                record = AtomRecord(
                    status=ATOM_UNMATCHED, match_confidence=confidence, reason=REASON_BELOW_ATOM_FLOOR
                )
            else:
                x0 = min(pg.words[b].bbox[0] for b in consumed)
                y0 = min(pg.words[b].bbox[1] for b in consumed)
                x1 = max(pg.words[b].bbox[2] for b in consumed)
                y1 = max(pg.words[b].bbox[3] for b in consumed)
                record = AtomRecord(
                    status=ATOM_MATCHED,
                    match_confidence=confidence,
                    page=pg.page,
                    bbox=(x0, y0, x1, y1),
                    match_method=MATCH_METHOD,
                )
            tentative.append((atom.atom_id, record))

        rate = (matched_sum / total_sum) if total_sum else 0.0
        if rate >= page_accept_rate:
            page_records[pg.page] = PageRecord(status=PAGE_MATCHED, match_rate=rate, dropped_boxes=dropped)
            atom_records.update(tentative)
        else:
            # The page routes to human review; its tentative outcomes are discarded — the atoms
            # stay pending (absent from the records), never auto-absent before a verdict (G-12).
            page_records[pg.page] = PageRecord(
                status=PAGE_ROUTED, stage="match", signal="match-rate", value=rate, dropped_boxes=dropped
            )

    return MatchOutcome(
        witness_id=stream.stream_id,
        stream_source_hash=stream.source_hash,
        boundaries=boundaries,
        pages=page_records,
        atoms=atom_records,
        atom_pages=atom_windows,
        token_counts=token_counts,
        locate_failed_pages=tuple(locate_failed),
    )


# --- sidecar assembly ------------------------------------------------------------------------------ #


def build_geom_sidecar(
    outcome: MatchOutcome,
    *,
    source_scan: SourceScan,
    backend_params: Mapping[str, object],
    engine_id: str,
    canonical_stream: AtomStream | None = None,
    classifier_version: str | None = None,
    classifier_params: Mapping[str, object] | None = None,
) -> GeomSidecar:
    """Assemble the persisted sidecar from one match outcome (DT-9).

    The witness identity and the ``stream_source_hash`` binding come from the outcome itself
    (captured off the matched stream), so the sidecar can only ever bind the stream that was
    actually matched. ``canonical_stream``, when given, fills the two canonical coverage counters
    (DT-13's evidence): atoms with **no** derivation from this witness and atoms with **multiple**
    — counted by cause, never folded into match failures (G-25). When it is not given the two
    counters persist as ``null`` — *unmeasured*, deliberately distinguishable from a measured
    zero, so a witness-only sidecar can never read as "canonical fully covered"."""
    no_primary: int | None = None
    multi_primary: int | None = None
    if canonical_stream is not None:
        if canonical_stream.kind != CANONICAL:
            raise ValueError(
                f"canonical_stream must be the canonical projection, got kind {canonical_stream.kind!r}"
            )
        no_primary = 0
        multi_primary = 0
        for atom in canonical_stream.atoms:
            derivations = [d for d in atom.derived_from if d.witness == outcome.witness_id]
            if not derivations:
                no_primary += 1
            elif len(derivations) > 1:
                multi_primary += 1
    coverage = {
        "pages_locate_failed": len(outcome.locate_failed_pages),
        "atoms_unmatched_on_accepted_pages": sum(
            1 for r in outcome.atoms.values() if r.status == ATOM_UNMATCHED
        ),
        "canonical_no_primary_derivation": no_primary,
        "canonical_multi_primary_derivation": multi_primary,
    }
    return GeomSidecar(
        witness_id=outcome.witness_id,
        stream_source_hash=outcome.stream_source_hash,
        source_scan=source_scan,
        backend_params=backend_params,
        engine_id=engine_id,
        locate_method=LOCATE_METHOD,
        pages=outcome.pages,
        atoms=outcome.atoms,
        atom_pages=outcome.atom_pages,
        coverage=coverage,
        classifier_version=classifier_version,
        classifier_params=classifier_params,
    )


# --- attach_geometry (R12) -------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class AttachOutcome:
    """One atom's attach-time state: ``status`` ∈ {matched, unmatched, pending, declined,
    ineligible}; ``reason`` carries the unmatched reason (persisted enum or
    ``multi_primary_derivation``) or ``no_primary_derivation`` for ineligible."""

    status: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class AttachResult:
    """The overlay: new frozen atoms (input order) + per-atom outcomes keyed by the input
    stream's atom ids. Matched atoms carry a full-provenance ``Geom``; every other state carries
    ``Geom.absent()`` — the pending/declined/ineligible distinctions live in ``outcomes`` and the
    sidecar, never as invented coordinates."""

    atoms: tuple[Atom, ...]
    outcomes: Mapping[str, AttachOutcome]


def _check_binding(sidecar: GeomSidecar, witness: AtomStream) -> None:
    """G-15: the sidecar binds one witness stream by id + source-hash anchor; a mismatch is a
    stale sidecar (or the wrong one), never silently attached."""
    if witness.stream_id != sidecar.witness_id:
        raise StaleArtifactError(
            f"geometry sidecar binds witness {sidecar.witness_id!r}, got stream "
            f"{witness.stream_id!r} — wrong sidecar for this stream"
        )
    if witness.source_hash != sidecar.stream_source_hash:
        raise StaleArtifactError(
            f"geometry sidecar is stale for witness {witness.stream_id!r}: sidecar "
            f"stream_source_hash {sidecar.stream_source_hash!r} != stream source_hash "
            f"{witness.source_hash!r} — the stream changed since matching; regenerate the sidecar "
            f"(G-15)"
        )


def _witness_geom(atom_id: str, sidecar: GeomSidecar) -> tuple[Geom, AttachOutcome]:
    record = sidecar.atoms.get(atom_id)
    if record is not None:
        if record.status == ATOM_MATCHED:
            geom = Geom.matched(
                page=record.page,
                bbox=record.bbox,
                geometry_engine=sidecar.engine_id,
                matched_witness_id=sidecar.witness_id,
                match_method=record.match_method,
                match_confidence=record.match_confidence,
            )
            return geom, AttachOutcome(status=OUTCOME_MATCHED)
        return Geom.absent(), AttachOutcome(status=OUTCOME_UNMATCHED, reason=record.reason)
    window = sidecar.atom_pages.get(atom_id)
    if window is None:
        # The hash bind should make this unreachable; if it fires, the sidecar was generated from
        # different atoms than this stream holds — corrupt correspondence, not a match state.
        raise StaleArtifactError(
            f"geometry sidecar for witness {sidecar.witness_id!r} has no page attribution for atom "
            f"{atom_id!r} — the sidecar does not correspond to this stream"
        )
    status = sidecar.pages[window.assigned].status
    if status == PAGE_ROUTED:
        return Geom.absent(), AttachOutcome(status=OUTCOME_PENDING)
    if status == PAGE_DECLINED:
        return Geom.absent(), AttachOutcome(status=OUTCOME_DECLINED)
    raise StaleArtifactError(
        f"atom {atom_id!r} has no record yet sits on matched page {window.assigned} — the sidecar "
        f"does not correspond to this stream"
    )


def attach_geometry(
    stream: AtomStream,
    sidecar: GeomSidecar,
    *,
    witness_stream: AtomStream | None = None,
) -> AttachResult:
    """Overlay a sidecar's proven geometry onto a stream's atoms (R12), both modes:

    - **witness mode** (``stream`` is the matched witness): direct id lookup. Binding is checked
      first — ``stream_source_hash`` mismatch is stale fail-loud (G-15).
    - **canonical mode** (``stream`` is the canonical projection): each atom's ``derived_from``
      entries are filtered to the sidecar's witness; the single primary atom's geometry attaches.
      ``witness_stream`` (the matched witness stream) is required — the canonical stream carries
      no source anchor of its own, so the G-15 bind runs against the witness stream it links into.
      No primary derivation → ``ineligible`` (an eligibility outcome, never a match failure,
      G-25); multiple primary derivations → ``unmatched(multi_primary_derivation)``, never a
      silent union or first-pick (G-20).

    Returns new frozen instances; the input streams are untouched (D25/DT-9)."""
    if stream.kind == WITNESS:
        if witness_stream is not None:
            raise ValueError("witness-mode attach takes no separate witness_stream")
        _check_binding(sidecar, stream)

        def resolve(atom: Atom) -> tuple[Geom, AttachOutcome]:
            return _witness_geom(atom.atom_id, sidecar)
    elif stream.kind == CANONICAL:
        if witness_stream is None:
            raise ValueError(
                "canonical-mode attach requires the matched witness stream (the canonical stream "
                "has no source anchor to bind the sidecar against)"
            )
        if witness_stream.kind != WITNESS:
            raise ValueError(f"witness_stream must be a witness stream, got kind {witness_stream.kind!r}")
        _check_binding(sidecar, witness_stream)

        def resolve(atom: Atom) -> tuple[Geom, AttachOutcome]:
            derivations = [d for d in atom.derived_from if d.witness == sidecar.witness_id]
            if not derivations:
                return Geom.absent(), AttachOutcome(
                    status=OUTCOME_INELIGIBLE, reason=REASON_NO_PRIMARY_DERIVATION
                )
            if len(derivations) > 1:
                return Geom.absent(), AttachOutcome(
                    status=OUTCOME_UNMATCHED, reason=REASON_MULTI_PRIMARY_DERIVATION
                )
            return _witness_geom(derivations[0].atom_id, sidecar)
    else:  # unreachable while AtomStream's kind vocabulary is closed; belt for a future flavour
        raise ValueError(f"attach_geometry cannot attach to a stream of kind {stream.kind!r}")

    new_atoms: list[Atom] = []
    outcomes: dict[str, AttachOutcome] = {}
    for atom in stream.atoms:
        geom, outcome = resolve(atom)
        new_atoms.append(replace(atom, geom=geom))
        outcomes[atom.atom_id] = outcome
    return AttachResult(atoms=tuple(new_atoms), outcomes=outcomes)
