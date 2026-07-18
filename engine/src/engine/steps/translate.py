"""Single-model literary translation with source-bound, restartable section checkpoints.

Clean Markdown supplies rendered boundaries; ``reconciled_chapters.json`` supplies stable upstream
ids. The two are matched exactly before any model call. Failed or truncated sections remain as
restartable evidence, but canonical English output is published only when all sections complete.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Protocol

from ..config.models import ResolvedConfig
from ..errors import BackendError, MissingInputError
from ..lang.base import LanguagePlugin
from ..paths import BookWorkspace
from ..prompts.templating import PromptTemplate, build_prompt_context
from ..util.jsonio import atomic_write_json, atomic_write_text, read_json
from ..util.retry import retry_api_call

CLEAN_FILE = "clean.md"
RECONCILED_FILE = "reconciled_chapters.json"
CHAPTER_PAGES_FILE = "chapter_pages.json"
VALIDATION_FILE = "validation_report.json"
TRANSLATION_FILE = "english_translation.md"
SOURCE_PAGES_FILE = "source_pages.json"
PROGRESS_FILE = "translation_progress.json"
RUN_REPORT_FILE = "translation_run.json"

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 128_000
_DEFAULT_THINKING_BUDGET = 4_096
_MIN_OUTPUT_RATIO = 0.30
_PAGE_MARKER_RE = re.compile(r"(?m)^<!-- pages:(\d+)-(\d+) -->\s*\n?")
_SECTION_RE = re.compile(r"^(#{2,3})\s+(.+?)\s*$")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class TranslationUnit:
    id: str
    title: str
    part: int
    level: int
    text: str
    pages: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CompletionResult:
    text: str
    stop_reason: str


class Completion(Protocol):
    """One extended-thinking text completion; injected by offline tests."""

    model: str

    def complete(
        self, *, system: str, user: str, thinking_budget: int | None
    ) -> CompletionResult: ...


class AnthropicCompletion:
    model = _MODEL

    def __init__(self, *, api_key: str | None = None, max_tokens: int = _MAX_TOKENS) -> None:
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise BackendError("No Anthropic API key. Set ANTHROPIC_API_KEY or pass --api-key.")
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key, timeout=600.0)
        self._max_tokens = max_tokens

    def complete(
        self, *, system: str, user: str, thinking_budget: int | None
    ) -> CompletionResult:
        kwargs = {
            "model": self.model,
            "max_tokens": self._max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "thinking": (
                {"type": "disabled"}
                if thinking_budget is None
                else {"type": "enabled", "budget_tokens": thinking_budget}
            ),
        }
        response = retry_api_call(lambda: self._client.messages.create(**kwargs))
        text_blocks = [
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ]
        if not text_blocks:
            raise BackendError("translation backend returned no text block")
        return CompletionResult(
            text="\n".join(text_blocks).strip(),
            stop_reason=str(response.stop_reason or "unknown"),
        )


def render_system_prompt(cfg: ResolvedConfig) -> str:
    return PromptTemplate.load("translate").render(**build_prompt_context(cfg))


def _rendered_sections(markdown: str) -> list[tuple[int, str, str]]:
    sections: list[tuple[int, str, str]] = []
    current: tuple[int, str] | None = None
    lines: list[str] = []

    def flush() -> None:
        if current is None:
            return
        body = "\n".join(lines).strip()
        if body:  # structural part headings have no body of their own
            sections.append((current[0], current[1], body))

    for line in markdown.splitlines():
        match = _SECTION_RE.fullmatch(line)
        if match:
            flush()
            current = (len(match.group(1)), match.group(2).strip())
            lines = []
        elif current is not None:
            lines.append(line)
    flush()
    return sections


def parse_translation_units(
    markdown: str, reconciled: list[dict], chapter_pages: dict[str, list[int]],
) -> list[TranslationUnit]:
    """Bind rendered bodies to stable upstream ids, failing on any structural drift."""
    rendered = _rendered_sections(markdown)
    ordered = sorted(enumerate(reconciled), key=lambda pair: (pair[1]["part"], pair[0]))
    source = [chapter for _, chapter in ordered]
    if len(rendered) != len(source):
        raise MissingInputError(
            f"clean Markdown has {len(rendered)} content sections but reconciliation has "
            f"{len(source)}; refusing positional translation"
        )

    units = []
    seen_ids: set[str] = set()
    for (level, title, body), chapter in zip(rendered, source, strict=True):
        if title != chapter["title"]:
            raise MissingInputError(
                f"clean/reconciled section title mismatch: {title!r} != {chapter['title']!r}"
            )
        chapter_id = chapter["id"]
        if chapter_id in seen_ids:
            raise MissingInputError(f"duplicate reconciled section id: {chapter_id!r}")
        seen_ids.add(chapter_id)
        body = _PAGE_MARKER_RE.sub("", body, count=1).strip()
        if not body:
            raise MissingInputError(f"translation section {chapter_id!r} has no body text")
        units.append(TranslationUnit(
            id=chapter_id,
            title=title,
            part=int(chapter["part"]),
            level=level,
            text=body,
            pages=tuple(int(page) for page in chapter_pages.get(chapter_id, [])),
        ))
    return units


def build_user_message(unit: TranslationUnit) -> str:
    return f"Translate the following section ({unit.title}). Return only its body:\n\n{unit.text}"


def _fingerprint(unit: TranslationUnit, system: str, model: str, thinking: int | None) -> str:
    value = json.dumps({
        "unit_id": unit.id,
        "source_sha256": _sha256_text(unit.text),
        "system_sha256": _sha256_text(system),
        "user_sha256": _sha256_text(build_user_message(unit)),
        "model": model,
        "thinking_budget": thinking,
        "max_tokens": _MAX_TOKENS,
    }, sort_keys=True, ensure_ascii=False)
    return _sha256_text(value)


def _valid_checkpoint(path, meta: dict, fingerprint: str) -> bool:
    if meta.get("status") != "done" or meta.get("fingerprint") != fingerprint:
        return False
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return bool(text.strip()) and meta.get("output_sha256") == _sha256_text(text)


def assemble_translation(
    units: list[TranslationUnit], *, workspace: BookWorkspace, cfg: ResolvedConfig,
    lang: LanguagePlugin,
) -> str:
    ed = cfg.manifest.edition
    lines = [f"# {ed.title_en}", ""]
    if ed.subtitle_en:
        lines.extend([f"*{ed.subtitle_en}*", ""])
    lines.extend([
        f"**{ed.author}** ({ed.year})", "", f"*Translated from {cfg.language.display_name}*",
        "", "---", "",
    ])
    current_part = 0
    for unit in units:
        if unit.part != current_part and unit.part >= 1:
            if current_part >= 1:
                lines.extend(["---", ""])
            part_title = cfg.structure.parts[unit.part - 1].name
            lines.extend([f"## {lang.title_to_english(part_title)}", ""])
            current_part = unit.part
        level = "##" if unit.part == 0 else "###"
        lines.extend([f"{level} {lang.title_to_english(unit.title)}", ""])
        if unit.pages:
            lines.extend([f"<!-- pages:{unit.pages[0]}-{unit.pages[-1]} -->", ""])
        translated = (workspace.state / "translations" / f"{unit.id}.md").read_text(
            encoding="utf-8"
        ).strip()
        lines.extend([translated, "", ""])
    return "\n".join(lines).rstrip() + "\n"


def run(
    *,
    workspace: BookWorkspace,
    cfg: ResolvedConfig,
    lang: LanguagePlugin,
    workers: int = 1,
    thinking_budget: int = _DEFAULT_THINKING_BUDGET,
    no_thinking: bool = False,
    completion: Completion | None = None,
    api_key: str | None = None,
) -> dict:
    ws = workspace.ensure()
    clean_path = ws.output / CLEAN_FILE
    reconciled_path = ws.data / RECONCILED_FILE
    validation_path = ws.data / VALIDATION_FILE
    missing = [str(path) for path in (clean_path, reconciled_path, validation_path) if not path.is_file()]
    if missing:
        raise MissingInputError(f"translate needs validated cleaned input; missing: {', '.join(missing)}")
    validation = read_json(validation_path)
    if validation.get("overall") != "pass":
        raise MissingInputError("translate refuses input whose validation report is not PASS")

    clean_text = clean_path.read_text(encoding="utf-8")
    if validation.get("input_sha256") != _sha256_text(clean_text):
        raise MissingInputError(
            "translate refuses a stale validation report whose clean-text hash does not match"
        )
    reconciled = read_json(reconciled_path)
    pages_path = ws.data / CHAPTER_PAGES_FILE
    chapter_pages = read_json(pages_path) if pages_path.is_file() else {}
    units = parse_translation_units(clean_text, reconciled, chapter_pages)
    system = render_system_prompt(cfg)
    thinking = None if no_thinking else thinking_budget

    translations_dir = ws.state / "translations"
    translations_dir.mkdir(parents=True, exist_ok=True)
    progress_path = ws.state / PROGRESS_FILE
    progress = read_json(progress_path) if progress_path.is_file() else {}
    current_ids = {unit.id for unit in units}
    progress = {key: value for key, value in progress.items() if key in current_ids}

    model = completion.model if completion is not None else _MODEL
    todo = []
    for unit in units:
        fingerprint = _fingerprint(unit, system, model, thinking)
        path = translations_dir / f"{unit.id}.md"
        if not _valid_checkpoint(path, progress.get(unit.id, {}), fingerprint):
            todo.append((unit, fingerprint))
    # Once any source-bound checkpoint is stale, a previous aggregate is stale too. Remove its
    # canonical names before model work so a failed refresh cannot leave an old edition looking
    # current. Per-section checkpoints remain available for restart.
    if todo:
        for stale in (
            ws.output / TRANSLATION_FILE,
            ws.output / SOURCE_PAGES_FILE,
            ws.data / RUN_REPORT_FILE,
        ):
            if stale.exists():
                stale.unlink()
    if todo and completion is None:
        completion = AnthropicCompletion(api_key=api_key)

    lock = threading.Lock()
    failures: list[str] = []

    def translate_one(item: tuple[TranslationUnit, str]) -> None:
        unit, fingerprint = item
        assert completion is not None
        with lock:
            progress[unit.id] = {"status": "in_progress", "fingerprint": fingerprint}
            atomic_write_json(progress_path, progress)
        try:
            result = completion.complete(
                system=system, user=build_user_message(unit), thinking_budget=thinking,
            )
            translated = result.text.strip()
            ratio = len(translated) / max(len(unit.text), 1)
            if not translated:
                raise BackendError("empty translation")
            if result.stop_reason == "max_tokens" or ratio < _MIN_OUTPUT_RATIO:
                error = f"stop={result.stop_reason}, output/source ratio={ratio:.3f}"
                with lock:
                    progress[unit.id] = {
                        "status": "truncated", "fingerprint": fingerprint, "error": error,
                    }
                    atomic_write_json(progress_path, progress)
                    failures.append(f"{unit.id}: {error}")
                return
            output_path = translations_dir / f"{unit.id}.md"
            atomic_write_text(output_path, translated + "\n")
            with lock:
                progress[unit.id] = {
                    "status": "done",
                    "fingerprint": fingerprint,
                    "source_sha256": _sha256_text(unit.text),
                    "output_sha256": _sha256_text(translated + "\n"),
                    "model": model,
                    "stop_reason": result.stop_reason,
                    "source_chars": len(unit.text),
                    "output_chars": len(translated),
                    "source_paragraphs": len(unit.text.split("\n\n")),
                    "output_paragraphs": len(translated.split("\n\n")),
                }
                atomic_write_json(progress_path, progress)
            print(f"  translated {unit.id}: {len(translated):,} chars", flush=True)
        except Exception as exc:  # preserve successful sibling checkpoints, then fail the step
            with lock:
                progress[unit.id] = {
                    "status": "error", "fingerprint": fingerprint, "error": str(exc),
                }
                atomic_write_json(progress_path, progress)
                failures.append(f"{unit.id}: {exc}")

    if workers <= 1:
        for item in todo:
            translate_one(item)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(translate_one, item) for item in todo]
            for future in as_completed(futures):
                future.result()
    if failures:
        raise BackendError(
            f"translation incomplete ({len(failures)} section failures); checkpoints retained: "
            + "; ".join(failures)
        )

    english = assemble_translation(units, workspace=ws, cfg=cfg, lang=lang)
    atomic_write_text(ws.resolve("output", TRANSLATION_FILE), english)
    source_pages = {
        unit.id: {
            "title": lang.title_to_english(unit.title),
            "pages": list(unit.pages),
            "ia_url": (
                f"https://archive.org/details/{cfg.manifest.edition.ia_item_id}/page/"
                f"n{max(unit.pages[0] - 1, 0)}/mode/1up"
                if unit.pages else None
            ),
        }
        for unit in units
    }
    atomic_write_json(ws.resolve("output", SOURCE_PAGES_FILE), source_pages)
    report = {
        "status": "complete",
        "book_id": cfg.book_id,
        "source_sha256": _sha256_text(clean_text),
        "system_prompt_sha256": _sha256_text(system),
        "output_sha256": _sha256_text(english),
        "model": model,
        "thinking_budget": thinking,
        "sections": [progress[unit.id] | {"id": unit.id} for unit in units],
    }
    atomic_write_json(ws.resolve("data", RUN_REPORT_FILE), report)
    print(f"  English translation: {ws.output / TRANSLATION_FILE}")
    return {"sections": len(units), "translated": len(todo), "output_sha256": report["output_sha256"]}
