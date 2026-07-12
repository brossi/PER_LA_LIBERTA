"""triage step — LLM classification + resolution of the OCR disagreements reconcile flagged.

Faithful port of the top-level ``triage.py``. The mechanics are book/language-neutral *code* and
port ~verbatim: the needs-triage filter (``resolution_method in {all_differ, score_heuristic}``),
the batch loop, ``_is_plausible_correction`` (SequenceMatcher ≥ 0.4), the three resolution passes,
and ``_apply_resolutions`` (group-by-(chapter, paragraph), first-uncorrected-occurrence replace).
These are pure → unit-tested directly.

The book/language opinion leaves the code (BR-011):

  - the disagreement **taxonomy** (``CATEGORIES`` + the ``classify_disagreement`` tool schema) is a
    settled general OCR-triage default, kept as module constants — not config;
  - the **system prompt** is the book-neutral ``triage`` template, rendered with the book/language
    context (``build_prompt_context``) plus the witness list derived from ``manifest.sources`` and
    the ocr-produced copy3 (D2/BR-008). The live prompt's Italian *example words* (``più``,
    ``pàtria``) are intentionally **not** carried: they would render under any Italian-profiled book
    — including the synthetic separability book — and trip the no-Italian-leak render test the
    engine-agnostic invariant rests on. The category set, witness setup, and the (config-gated)
    optional-accent rule carry the essential guidance; triage is an LLM step with no equivalence
    golden, so the concrete priming examples are not load-bearing.

The model call is the one injectable seam (BR-014), defaulting to the real Anthropic client, so the
property / separability tiers run offline. Whether triage/cleanup/translate share one ``ChatBackend``
that M5's ``providers.py`` generalizes is BR-009's open half, explicitly M4c's call; M4b uses a
minimal per-step seam, the same "siblings, not a premature unification" choice M4a made.
"""

from __future__ import annotations

import time
from typing import Protocol

from ..config.models import ResolvedConfig
from ..errors import BackendError, MissingInputError
from ..lang.base import LanguagePlugin
from ..paths import BookWorkspace
from ..prompts.templating import PromptTemplate, build_prompt_context
from ..util.jsonio import atomic_write_json, read_json
from ..util.retry import retry_api_call

# --- taxonomy: a settled general OCR-triage default, not config (BR-011) ---------------- #

#: The disagreement categories the model chooses among. General OCR-failure taxonomy (no book or
#: language opinion); kept as a module constant, the engine's default classification scheme.
CATEGORIES = [
    "ocr_confusion",        # single-char swap: e/c, ii/u, m/rn
    "ocr_corruption",       # multi-char garble
    "punctuation_artifact",  # extra/missing punctuation
    "alignment_drift",      # text displaced between witnesses
    "missing_text",         # witness missing content
    "archaic_spelling",     # period spelling variant, not an error
    "unknown",
]

TRIAGE_TOOL = {
    "name": "classify_disagreement",
    "description": (
        "Classify an OCR disagreement between witnesses and propose the correct reading."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": CATEGORIES,
                "description": "The type of OCR disagreement.",
            },
            "proposed_reading": {
                "type": "string",
                "description": "The correct reading of the word. May be from any witness or a correction.",
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
            "reasoning": {
                "type": "string",
                "description": "One-sentence explanation of the classification.",
            },
            "needs_human": {
                "type": "boolean",
                "description": "True if this item needs human review.",
            },
        },
        "required": ["category", "proposed_reading", "confidence", "reasoning", "needs_human"],
    },
}

# Model + batch tuning — engine processing defaults (the triage model is not output provenance, so
# unlike ocr's it stays a code default, not a manifest field). Verbatim from live triage.
_TRIAGE_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096
_DEFAULT_BATCH_SIZE = 5
#: Inter-batch politeness delay (seconds). Module constant so tests patch it to 0.
_BATCH_DELAY = 1.0

# The two resolution methods reconcile leaves unsettled — the items triage exists to classify.
_NEEDS_TRIAGE_METHODS = ("all_differ", "score_heuristic")


# --- injectable chat seam (BR-014) ------------------------------------------------------ #

class Chat(Protocol):
    """One tool-use classification call. Returns the ``input`` dict of every invocation of the
    named tool, in order — the provider-neutral surface the step consumes (it never sees raw
    response blocks). Injectable so the property / separability tiers run offline."""

    def classify(self, *, system: str, tool: dict, user: str) -> list[dict]: ...


class AnthropicChat:
    """Default ``Chat`` — Anthropic ``messages.create`` with a single tool, wrapped in
    ``retry_api_call``. The model is a code default (the live triage id); a missing key is a
    ``BackendError`` (CLI exit 5), matching ocr's backend."""

    def __init__(
        self, *, model: str = _TRIAGE_MODEL, api_key: str | None = None, max_tokens: int = _MAX_TOKENS
    ) -> None:
        if not api_key:
            import os

            api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise BackendError("No Anthropic API key. Set ANTHROPIC_API_KEY or pass --api-key.")

        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key, timeout=300.0)
        self._model = model
        self._max_tokens = max_tokens

    def classify(self, *, system: str, tool: dict, user: str) -> list[dict]:
        def _call():
            return self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                tools=[tool],
                messages=[{"role": "user", "content": user}],
            )

        response = retry_api_call(_call)
        return [
            block.input
            for block in response.content
            if getattr(block, "type", None) == "tool_use"
            and getattr(block, "name", None) == tool["name"]
        ]


# --- pure mechanics ---------------------------------------------------------------------- #

def _is_plausible_correction(original: str, correction: str) -> bool:
    """Whether ``correction`` is a plausible fix of ``original`` (not alignment drift): character
    similarity ≥ 0.4. Pure; ``.lower()`` is Unicode-general, no language opinion. Verbatim."""
    if not original or not correction:
        return False
    from difflib import SequenceMatcher

    return SequenceMatcher(None, original.lower(), correction.lower()).ratio() >= 0.4


def build_witnesses(cfg: ResolvedConfig) -> list[str]:
    """Human-readable descriptions of voting witnesses for the triage prompt.

    Downloaded diagnostic roles such as ``comparison`` are intentionally excluded: they did not
    vote in reconciliation and must not be presented to triage as if they had.
    """
    labels = {source.role: source.label for source in cfg.manifest.sources}
    witnesses = []
    if "copy1" in labels:
        witnesses.append(f"Copy 1: {labels['copy1']}")
    if "copy2" in labels:
        witnesses.append(f"Copy 2: {labels['copy2']}")
    witnesses.append("Copy 3: vision-model OCR of the source scan")
    return witnesses


def render_system_prompt(cfg: ResolvedConfig) -> str:
    """Render the book-neutral ``triage`` system prompt with the book/language context + witnesses.

    Public so the leakage render test can call it directly (mirrors ocr's ``_render_ocr_prompt``).
    """
    template = PromptTemplate.load("triage")
    context = build_prompt_context(cfg)
    return template.render(
        **context,
        witnesses=build_witnesses(cfg),
        accent_optional=cfg.language.accent_optional,
    )


def _item_description(item: dict, index: int) -> str:
    """Render one flagged item as the per-item block of the batch user message. Pure. Verbatim."""
    desc = f"Item {index}:\n"
    desc += f"  Chapter: {item['chapter']}, Paragraph: {item['paragraph']}\n"
    desc += f"  Copy 1: \"{item.get('word_copy1', 'N/A')}\"\n"
    desc += f"  Copy 2: \"{item.get('word_copy2', 'N/A')}\"\n"
    if item.get("word_copy3"):
        desc += f"  Copy 3: \"{item['word_copy3']}\"\n"
    if item.get("context"):
        desc += f"  Context: ...{item['context']}...\n"
    desc += f"  Currently chosen: \"{item['chosen']}\"\n"
    return desc


def build_user_message(batch: list[dict]) -> str:
    """Assemble the batch user message: one classify-the-disagreement instruction + per-item blocks.
    Pure. Verbatim from the live inline construction."""
    blocks = [_item_description(item, i + 1) for i, item in enumerate(batch)]
    return (
        f"Classify each of these {len(batch)} OCR disagreements. "
        f"Call the classify_disagreement tool once for each item.\n\n"
        + "\n".join(blocks)
    )


def _unknown_triage(item: dict, reasoning: str) -> dict:
    """The fallback classification when the model returns no result for an item (or errored)."""
    return {
        "category": "unknown",
        "proposed_reading": item["chosen"],
        "confidence": "low",
        "reasoning": reasoning,
        "needs_human": True,
    }


def _classify_batch(chat: Chat, system: str, batch: list[dict]) -> list[dict]:
    """Classify one batch: call the seam, match results back to items (a short result list falls
    back to ``unknown`` for the unmatched tail), and attach ``triage`` to each item copy."""
    try:
        results = chat.classify(system=system, tool=TRIAGE_TOOL, user=build_user_message(batch))
    except Exception as exc:  # noqa: BLE001 — a batch failure degrades to unknown, run continues
        return [{**item, "triage": _unknown_triage(item, f"API error: {exc}")} for item in batch]

    reviewed = []
    for i, item in enumerate(batch):
        result = results[i] if i < len(results) else None
        triage = result if result else _unknown_triage(item, "No LLM response for this item")
        reviewed.append({**item, "triage": triage})
    return reviewed


def apply_resolution_passes(reviewed: list[dict]) -> tuple[list[dict], dict]:
    """Map each item's ``triage`` verdict to a resolution. Pure (no I/O, no mutation of ``reviewed``).

    Returns ``(resolved, stats)``. Auto-accept a high/medium-confidence, non-human correction only
    when it is *plausible* (else keep the current choice — an implausible "correction" is alignment
    drift); everything else keeps the current choice and is counted as needing human review.
    Verbatim from the live resolution loop, extracted to a pure function for property testing.
    """
    resolved: list[dict] = []
    stats = {"auto_accepted": 0, "needs_human": 0, "by_category": {}}

    for item in reviewed:
        triage = item["triage"]
        category = triage["category"]
        stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
        out = {**item}

        if not triage["needs_human"] and triage["confidence"] in ("high", "medium"):
            proposed = triage["proposed_reading"]
            if _is_plausible_correction(item["chosen"], proposed):
                out["resolved"] = proposed
                out["resolution_source"] = "llm_triage"
                stats["auto_accepted"] += 1
            else:
                out["resolved"] = item["chosen"]
                out["resolution_source"] = "plausibility_rejected"
                stats["needs_human"] += 1
        elif triage["needs_human"]:
            out["resolved"] = item["chosen"]
            out["resolution_source"] = "needs_human"
            stats["needs_human"] += 1
        else:
            out["resolved"] = item["chosen"]
            out["resolution_source"] = "low_confidence"
            stats["needs_human"] += 1

        resolved.append(out)

    return resolved, stats


def apply_resolutions(ws: BookWorkspace, resolved_items: list[dict]) -> int:
    """Apply accepted resolutions back into ``reconciled_chapters.json`` (atomic). Returns the count.

    Groups corrections by ``(chapter, paragraph)`` and replaces the *first uncorrected* occurrence
    of each original word, so a word recurring in a paragraph is not over-replaced. Verbatim from
    the live ``_apply_resolutions`` minus the I/O target (``ws.data`` here)."""
    from collections import defaultdict

    chapters_path = ws.resolve("data", "reconciled_chapters.json")
    if not chapters_path.is_file():
        raise MissingInputError(
            f"reconciled_chapters.json not found at {chapters_path} — run reconcile first"
        )

    per_para = defaultdict(list)
    for item in resolved_items:
        if item.get("resolved") and item["resolved"] != item["chosen"]:
            per_para[(item["chapter"], item["paragraph"])].append((item["chosen"], item["resolved"]))

    if not per_para:
        print("    triage: no corrections to apply")
        return 0

    chapters = read_json(chapters_path)
    applied = 0
    for ch in chapters:
        ch_id = ch["id"]
        paras = ch["text"].split("\n\n")
        modified = False
        for para_idx, para in enumerate(paras):
            corrections = per_para.get((ch_id, para_idx))
            if not corrections:
                continue
            words = para.split()
            new_words = list(words)
            corrected_positions: set[int] = set()
            for old_word, new_word in corrections:
                for i, w in enumerate(words):
                    if i not in corrected_positions and w == old_word:
                        new_words[i] = new_word
                        corrected_positions.add(i)
                        applied += 1
                        modified = True
                        break
            paras[para_idx] = " ".join(new_words)
        if modified:
            ch["text"] = "\n\n".join(paras)

    atomic_write_json(chapters_path, chapters)
    print(f"    triage: applied {applied} corrections to reconciled_chapters.json")
    return applied


# --- orchestration ----------------------------------------------------------------------- #

def run(
    *,
    workspace: BookWorkspace,
    cfg: ResolvedConfig,
    lang: LanguagePlugin,
    chat: Chat | None = None,
    batch_size: int | None = None,
    api_key: str | None = None,
) -> dict:
    """Triage reconcile's unresolved disagreements and apply accepted fixes to the chapters.

    Reads ``flagged_segments.json`` (reconcile's word-disagreement output), classifies the
    ``all_differ`` / ``score_heuristic`` items via the ``chat`` seam, writes the audit sidecars
    (``triage_review.json`` = classifications, ``triage_resolved.json`` = +resolutions), and mutates
    ``reconciled_chapters.json`` in place. ``chat`` defaults to the real Anthropic backend (built
    only when there is something to triage, so a no-op run needs no key). ``lang`` is unused —
    triage's code is language-neutral — but kept for the uniform signature. Returns a summary dict.
    """
    ws = workspace
    ws.ensure()

    flagged_path = ws.resolve("data", "flagged_segments.json")
    if not flagged_path.is_file():
        raise MissingInputError(
            f"flagged_segments.json not found at {flagged_path} — run reconcile first"
        )

    all_items = read_json(flagged_path)
    needs = [it for it in all_items if it.get("resolution_method") in _NEEDS_TRIAGE_METHODS]
    print(f"  triage: {len(all_items)} flagged, {len(needs)} need triage")
    if not needs:
        return {"flagged": len(all_items), "triaged": 0, "auto_accepted": 0, "applied": 0}

    if chat is None:
        chat = AnthropicChat(api_key=api_key)

    size = batch_size or _DEFAULT_BATCH_SIZE
    system = render_system_prompt(cfg)
    reviewed: list[dict] = []
    for start in range(0, len(needs), size):
        reviewed.extend(_classify_batch(chat, system, needs[start:start + size]))
        if _BATCH_DELAY:
            time.sleep(_BATCH_DELAY)

    resolved, stats = apply_resolution_passes(reviewed)

    atomic_write_json(ws.resolve("data", "triage_review.json"), reviewed)
    atomic_write_json(ws.resolve("data", "triage_resolved.json"), resolved)
    applied = apply_resolutions(ws, resolved)

    print(
        f"  triage: auto-accepted {stats['auto_accepted']}, "
        f"needs-human {stats['needs_human']}, applied {applied}"
    )
    return {
        "flagged": len(all_items),
        "triaged": len(needs),
        "auto_accepted": stats["auto_accepted"],
        "applied": applied,
        "by_category": stats["by_category"],
    }
