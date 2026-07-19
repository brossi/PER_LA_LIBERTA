"""Generalized, advisory structural-content source observations (S4.6c/#90).

The observer searches caller-declared structural strings across source-locked OCR surfaces.  Its
output is factual and explicitly unverified: source sightings, mechanically derived candidate
loci, and bounded zero counts.  It has no route into structure-map or authoring-evidence mutation;
profile-calibrated grammar and recognition remain S9 work.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence

import jsonschema

from engine.errors import MissingInputError, RegenerationGuardError, StaleArtifactError
from engine.util.jsonio import atomic_write_json, read_json

STRUCTURAL_CONTENTS_SCHEMA_VERSION = 1
STRUCTURAL_CONTENTS_STALE_CLASS = "structural-contents-observation"
OBSERVER_POLICY_ID = "structural-contents-sightings-v1"

FORMAT_DJVU_XML = "djvu-xml"
FORMAT_PLAIN_TEXT = "plain-text"
SOURCE_FORMATS = frozenset({FORMAT_DJVU_XML, FORMAT_PLAIN_TEXT})

MATCH_LITERAL = "literal"
MATCH_NORMALIZED = "normalized"

LOCUS_BODY_LIKE = "body-like"
LOCUS_CONTENTS_LIKE = "contents-like"
LOCUS_UNRESOLVED = "unresolved"

INTERPRETATION_OBSERVED = "observed"
INTERPRETATION_INFERRED = "inferred"
INTERPRETATION_UNRESOLVED = "unresolved"

MAX_MATCH_LINES = 3
CONTENTS_REFERENCE_MIN = 5
CONTENTS_MONOTONE_MIN = 0.60
CONTENTS_REFERENCE_FRACTION_MIN = 0.50

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_TRAILING_PAGE_REFERENCE = re.compile(
    r"(?:^|\s)(?P<reference>[0-9]{1,4}|[ivxlcdmIVXLCDM]{1,12})\s*[.)]?\s*$"
)
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
_CANONICAL_ROMAN = re.compile(
    r"^M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})$"
)

SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "structural_contents.schema.json"


def load_structural_contents_schema() -> dict:
    """Return a fresh parsed copy of the registered advisory-artifact schema."""

    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _report_validator() -> jsonschema.Draft202012Validator:
    schema = load_structural_contents_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def structural_contents_schema_version_const(schema: Mapping | None = None) -> int:
    """The schema literal paired with :data:`STRUCTURAL_CONTENTS_SCHEMA_VERSION`."""

    schema = load_structural_contents_schema() if schema is None else schema
    value = schema["properties"]["schema_version"]["const"]
    if type(value) is not int:
        raise ValueError(f"structural contents schema_version const must be an int, got {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """Source identity and exact byte lock supplied before parsing."""

    source_id: str
    format: str
    source_ref: str
    sha256: str
    n_bytes: int

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or _SOURCE_ID.fullmatch(self.source_id) is None:
            raise ValueError(f"invalid structural observation source_id {self.source_id!r}")
        if self.format not in SOURCE_FORMATS:
            raise ValueError(
                f"structural observation source format must be one of {sorted(SOURCE_FORMATS)}, "
                f"got {self.format!r}"
            )
        if not isinstance(self.source_ref, str) or not self.source_ref.strip():
            raise ValueError("structural observation source_ref must be non-empty")
        if not isinstance(self.sha256, str) or _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("structural observation source sha256 must be a bare lowercase SHA-256")
        if type(self.n_bytes) is not int or self.n_bytes < 0:
            raise ValueError("structural observation source n_bytes must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class StructuralExpectation:
    """One caller-declared string to search for; ``role`` is descriptive only."""

    expectation_id: str
    literal: str
    role: str

    def __post_init__(self) -> None:
        if not isinstance(self.expectation_id, str) or _SOURCE_ID.fullmatch(self.expectation_id) is None:
            raise ValueError(f"invalid structural expectation_id {self.expectation_id!r}")
        if not isinstance(self.literal, str) or not self.literal.strip():
            raise ValueError("structural expectation literal must be non-empty")
        if not _normalized_tokens(self.literal):
            raise ValueError("structural expectation literal must contain an alphanumeric token")
        if not isinstance(self.role, str) or not self.role.strip():
            raise ValueError("structural expectation role must be non-empty")


@dataclass(frozen=True, slots=True)
class SourceLine:
    """One adapter-normalized literal line with a format-specific locator."""

    ordinal: int
    text: str
    page: int | None = None
    page_line: int | None = None
    bbox: tuple[int, int, int, int] | None = None
    byte_start: int | None = None
    byte_end: int | None = None


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """A successfully hash-locked and parsed source surface."""

    spec: SourceSpec
    lines: tuple[SourceLine, ...]


def _normalized_tokens(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    tokens: list[str] = []
    current: list[str] = []
    for character in normalized:
        if character.isalnum():
            current.append(character)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tuple(tokens)


def _normalized_text(text: str) -> str:
    return " ".join(_normalized_tokens(text))


def _collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def _source_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _verify_source_lock(spec: SourceSpec, data: bytes) -> None:
    if len(data) != spec.n_bytes:
        raise StaleArtifactError(
            f"structural observation source {spec.source_id!r} byte length {len(data)} does not "
            f"match locked {spec.n_bytes}"
        )
    digest = _source_digest(data)
    if digest != spec.sha256:
        raise StaleArtifactError(
            f"structural observation source {spec.source_id!r} SHA-256 {digest!r} does not match "
            f"locked {spec.sha256!r}"
        )


def _plain_text_lines(spec: SourceSpec, data: bytes) -> tuple[SourceLine, ...]:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StaleArtifactError(
            f"plain-text structural observation source {spec.source_id!r} is not UTF-8"
        ) from exc

    lines: list[SourceLine] = []
    offset = 0
    raw_lines = data.splitlines(keepends=True)
    if not raw_lines and data == b"":
        raw_lines = []
    elif data and not raw_lines:
        raw_lines = [data]
    for ordinal, raw in enumerate(raw_lines, 1):
        content = raw.rstrip(b"\r\n")
        text = content.decode("utf-8")
        lines.append(
            SourceLine(
                ordinal=ordinal,
                text=text,
                byte_start=offset,
                byte_end=offset + len(content),
            )
        )
        offset += len(raw)
    return tuple(lines)


def _word_bbox(word: ET.Element, *, source_id: str) -> tuple[int, int, int, int] | None:
    raw = word.get("coords")
    if raw is None:
        return None
    try:
        values = tuple(int(value) for value in raw.split(","))
    except ValueError as exc:
        raise StaleArtifactError(
            f"DjVu XML source {source_id!r} carries malformed WORD coords {raw!r}"
        ) from exc
    # IA DjVu derivatives ordinarily expose the four rectangle coordinates, but some OCR records
    # append an auxiliary fifth value.  The rectangle remains the first four values; accepting the
    # extension preserves cross-derivative compatibility without interpreting the auxiliary field.
    if len(values) < 4:
        raise StaleArtifactError(
            f"DjVu XML source {source_id!r} carries malformed WORD coords {raw!r}"
        )
    x1, y1, x2, y2 = values[:4]
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def _union_bbox(boxes: Iterable[tuple[int, int, int, int]]) -> tuple[int, int, int, int] | None:
    materialized = tuple(boxes)
    if not materialized:
        return None
    return (
        min(box[0] for box in materialized),
        min(box[1] for box in materialized),
        max(box[2] for box in materialized),
        max(box[3] for box in materialized),
    )


def _djvu_xml_lines(spec: SourceSpec, data: bytes) -> tuple[SourceLine, ...]:
    if b"<!ENTITY" in data.upper():
        raise StaleArtifactError(
            f"DjVu XML structural observation source {spec.source_id!r} declares an entity"
        )
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise StaleArtifactError(
            f"DjVu XML structural observation source {spec.source_id!r} is malformed XML"
        ) from exc
    if root.tag != "DjVuXML":
        raise StaleArtifactError(
            f"DjVu XML structural observation source {spec.source_id!r} has root {root.tag!r}, "
            "not 'DjVuXML'"
        )

    objects = tuple(root.iter("OBJECT"))
    if not objects:
        raise StaleArtifactError(
            f"DjVu XML structural observation source {spec.source_id!r} carries no OBJECT pages"
        )
    lines: list[SourceLine] = []
    ordinal = 0
    for page, obj in enumerate(objects, 1):
        for page_line, line in enumerate(obj.iter("LINE"), 1):
            words: list[str] = []
            boxes: list[tuple[int, int, int, int]] = []
            for word in line.findall("WORD"):
                literal = "".join(word.itertext()).strip()
                if literal:
                    words.append(literal)
                bbox = _word_bbox(word, source_id=spec.source_id)
                if bbox is not None:
                    boxes.append(bbox)
            ordinal += 1
            lines.append(
                SourceLine(
                    ordinal=ordinal,
                    text=" ".join(words),
                    page=page,
                    page_line=page_line,
                    bbox=_union_bbox(boxes),
                )
            )
    return tuple(lines)


def load_source_bytes(spec: SourceSpec, data: bytes) -> SourceDocument:
    """Verify an exact source lock and parse its format surface, or fail loud as stale."""

    if not isinstance(data, bytes):
        raise TypeError("structural observation source data must be bytes")
    _verify_source_lock(spec, data)
    if spec.format == FORMAT_PLAIN_TEXT:
        lines = _plain_text_lines(spec, data)
    else:
        lines = _djvu_xml_lines(spec, data)
    return SourceDocument(spec=spec, lines=lines)


def _roman_value(text: str) -> int | None:
    upper = text.upper()
    if (
        not upper
        or text != upper
        or _CANONICAL_ROMAN.fullmatch(upper) is None
        or any(character not in _ROMAN_VALUES for character in upper)
    ):
        return None
    total = 0
    previous = 0
    for character in reversed(upper):
        value = _ROMAN_VALUES[character]
        if value < previous:
            total -= value
        else:
            total += value
            previous = value
    return total if total > 0 else None


def _trailing_reference(text: str) -> int | None:
    match = _TRAILING_PAGE_REFERENCE.search(text)
    if match is None:
        return None
    # A page reference belongs to an entry row, not a standalone page number/header/footer.
    if not _normalized_tokens(text[: match.start("reference")]):
        return None
    raw = match.group("reference")
    if raw.isdigit():
        return int(raw)
    return _roman_value(raw)


def _page_features(source: SourceDocument) -> tuple[dict, ...]:
    pages: dict[int, list[SourceLine]] = {}
    for line in source.lines:
        if line.page is not None:
            pages.setdefault(line.page, []).append(line)
    records: list[dict] = []
    for page in sorted(pages):
        lines = pages[page]
        nonempty = [line for line in lines if line.text.strip()]
        references = [
            reference
            for line in nonempty
            if (reference := _trailing_reference(line.text)) is not None
        ]
        comparable = max(0, len(references) - 1)
        nondecreasing = sum(
            1 for left, right in zip(references, references[1:]) if right >= left
        )
        fraction = nondecreasing / comparable if comparable else None
        reference_fraction = len(references) / len(nonempty) if nonempty else 0.0
        contents_like = (
            len(references) >= CONTENTS_REFERENCE_MIN
            and comparable > 0
            and fraction is not None
            and fraction >= CONTENTS_MONOTONE_MIN
            and reference_fraction >= CONTENTS_REFERENCE_FRACTION_MIN
        )
        records.append(
            {
                "source_id": source.spec.source_id,
                "page": page,
                "nonempty_lines": len(nonempty),
                "trailing_page_reference_lines": len(references),
                "trailing_page_references": references,
                "comparable_adjacent_references": comparable,
                "nondecreasing_adjacent_references": nondecreasing,
                "nondecreasing_fraction": fraction,
                "trailing_page_reference_fraction": reference_fraction,
                "contents_like": contents_like,
                "interpretation": INTERPRETATION_INFERRED,
                "unverified": True,
            }
        )
    return tuple(records)


def _groups(lines: Sequence[SourceLine]) -> tuple[tuple[SourceLine, ...], ...]:
    if not lines:
        return ()
    if all(line.page is None for line in lines):
        return (tuple(lines),)
    groups: list[list[SourceLine]] = []
    active_page: int | None | object = object()
    for line in lines:
        if not groups or line.page != active_page:
            groups.append([])
            active_page = line.page
        groups[-1].append(line)
    return tuple(tuple(group) for group in groups)


def _expectation_hash(expectations: Sequence[StructuralExpectation]) -> str:
    payload = [
        {
            "expectation_id": expectation.expectation_id,
            "literal": expectation.literal,
            "role": expectation.role,
        }
        for expectation in expectations
    ]
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _locator(
    lines: Sequence[SourceLine], *, normalized_token_start: int, normalized_token_end: int
) -> dict:
    first, last = lines[0], lines[-1]
    locator: dict[str, object] = {
        "line_start": first.ordinal,
        "line_end": last.ordinal,
        "normalized_token_start": normalized_token_start,
        "normalized_token_end": normalized_token_end,
    }
    if first.page is not None:
        locator["page"] = first.page
        locator["page_line_start"] = first.page_line
        locator["page_line_end"] = last.page_line
        bbox = _union_bbox(line.bbox for line in lines if line.bbox is not None)
        if bbox is not None:
            locator["bbox"] = list(bbox)
    else:
        locator["byte_start"] = first.byte_start
        locator["byte_end"] = last.byte_end
    return locator


def _sighting_id(source_id: str, expectation_id: str, locator: dict) -> str:
    payload = json.dumps(
        [source_id, expectation_id, locator],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "obs-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _source_sightings(
    source: SourceDocument,
    expectations: Sequence[StructuralExpectation],
    page_features: dict[int, dict],
) -> tuple[dict, ...]:
    sightings: list[dict] = []
    for group in _groups(source.lines):
        flattened: list[tuple[str, int, int]] = []
        for line_index, line in enumerate(group):
            flattened.extend(
                (token, line_index, token_index)
                for token_index, token in enumerate(_normalized_tokens(line.text))
            )
        token_values = [token for token, _, _ in flattened]
        for expectation in expectations:
            wanted = _normalized_tokens(expectation.literal)
            width = len(wanted)
            if width == 0 or width > len(flattened):
                continue
            for token_start in range(0, len(flattened) - width + 1):
                if tuple(token_values[token_start : token_start + width]) != wanted:
                    continue
                first_line_index = flattened[token_start][1]
                last_line_index = flattened[token_start + width - 1][1]
                if last_line_index - first_line_index + 1 > MAX_MATCH_LINES:
                    continue
                lines = group[first_line_index : last_line_index + 1]
                matched_text = "\n".join(line.text for line in lines)
                literal = _collapse_whitespace(expectation.literal)
                match_kind = (
                    MATCH_LITERAL
                    if literal in _collapse_whitespace(matched_text)
                    else MATCH_NORMALIZED
                )
                page = lines[0].page
                if page is None:
                    locus = LOCUS_UNRESOLVED
                    locus_features = None
                    interpretation = INTERPRETATION_UNRESOLVED
                else:
                    locus_features = page_features[page]
                    locus = (
                        LOCUS_CONTENTS_LIKE
                        if locus_features["contents_like"]
                        else LOCUS_BODY_LIKE
                    )
                    interpretation = INTERPRETATION_INFERRED
                locator = _locator(
                    lines,
                    normalized_token_start=flattened[token_start][2],
                    normalized_token_end=flattened[token_start + width - 1][2] + 1,
                )
                before = group[first_line_index - 1].text if first_line_index > 0 else None
                after = (
                    group[last_line_index + 1].text
                    if last_line_index + 1 < len(group)
                    else None
                )
                sightings.append(
                    {
                        "sighting_id": _sighting_id(
                            source.spec.source_id, expectation.expectation_id, locator
                        ),
                        "expectation_id": expectation.expectation_id,
                        "source_id": source.spec.source_id,
                        "match_kind": match_kind,
                        "matched_text": matched_text,
                        "normalized_expectation": _normalized_text(expectation.literal),
                        "locator": locator,
                        "context_before": before,
                        "context_after": after,
                        "locus": locus,
                        "locus_features": (
                            {
                                "trailing_page_reference_lines": locus_features[
                                    "trailing_page_reference_lines"
                                ],
                                "comparable_adjacent_references": locus_features[
                                    "comparable_adjacent_references"
                                ],
                                "nondecreasing_adjacent_references": locus_features[
                                    "nondecreasing_adjacent_references"
                                ],
                                "nondecreasing_fraction": locus_features[
                                    "nondecreasing_fraction"
                                ],
                                "trailing_page_reference_fraction": locus_features[
                                    "trailing_page_reference_fraction"
                                ],
                                "contents_like": locus_features["contents_like"],
                            }
                            if locus_features is not None
                            else None
                        ),
                        "interpretation": interpretation,
                        "unverified": True,
                    }
                )
    return tuple(sightings)


def _assert_unique(values: Sequence[object], attribute: str, label: str) -> None:
    seen: set[str] = set()
    for value in values:
        identifier = getattr(value, attribute)
        if identifier in seen:
            raise ValueError(f"duplicate {label} {identifier!r}")
        seen.add(identifier)


def observe_structural_contents(
    *,
    book: str,
    sources: Sequence[SourceDocument],
    expectations: Sequence[StructuralExpectation],
) -> dict:
    """Build one deterministic advisory report from successfully loaded sources."""

    if not isinstance(book, str) or not book.strip():
        raise ValueError("structural observation book must be non-empty")
    sources = tuple(sources)
    expectations = tuple(expectations)
    if not sources:
        raise ValueError("structural observation requires at least one source")
    if not expectations:
        raise ValueError("structural observation requires at least one expectation")
    # SourceDocument nests its id under spec; retain the public source-id vocabulary here.
    source_ids: set[str] = set()
    for source in sources:
        if source.spec.source_id in source_ids:
            raise ValueError(f"duplicate source_id {source.spec.source_id!r}")
        source_ids.add(source.spec.source_id)
    _assert_unique(expectations, "expectation_id", "expectation_id")

    features: list[dict] = []
    sightings: list[dict] = []
    for source in sources:
        source_features = _page_features(source)
        features.extend(source_features)
        by_page = {item["page"]: item for item in source_features}
        sightings.extend(_source_sightings(source, expectations, by_page))

    summaries: list[dict] = []
    for expectation in expectations:
        for source in sources:
            scoped = [
                sighting
                for sighting in sightings
                if sighting["expectation_id"] == expectation.expectation_id
                and sighting["source_id"] == source.spec.source_id
            ]
            counts = {
                LOCUS_BODY_LIKE: sum(1 for sighting in scoped if sighting["locus"] == LOCUS_BODY_LIKE),
                LOCUS_CONTENTS_LIKE: sum(
                    1 for sighting in scoped if sighting["locus"] == LOCUS_CONTENTS_LIKE
                ),
                LOCUS_UNRESOLVED: sum(
                    1 for sighting in scoped if sighting["locus"] == LOCUS_UNRESOLVED
                ),
            }
            summaries.append(
                {
                    "expectation_id": expectation.expectation_id,
                    "source_id": source.spec.source_id,
                    "body_like": counts[LOCUS_BODY_LIKE],
                    "contents_like": counts[LOCUS_CONTENTS_LIKE],
                    "unresolved": counts[LOCUS_UNRESOLVED],
                    "total": len(scoped),
                    "interpretation": INTERPRETATION_OBSERVED,
                }
            )

    return {
        "schema_version": STRUCTURAL_CONTENTS_SCHEMA_VERSION,
        "stale_class": STRUCTURAL_CONTENTS_STALE_CLASS,
        "book": book,
        "observer_policy": OBSERVER_POLICY_ID,
        "expectations_sha256": _expectation_hash(expectations),
        "sources": [
            {
                "source_id": source.spec.source_id,
                "format": source.spec.format,
                "source_ref": source.spec.source_ref,
                "sha256": source.spec.sha256,
                "bytes": source.spec.n_bytes,
                "lines": len(source.lines),
                "interpretation": INTERPRETATION_OBSERVED,
            }
            for source in sources
        ],
        "expectations": [
            {
                "expectation_id": expectation.expectation_id,
                "literal": expectation.literal,
                "role": expectation.role,
                "normalized": _normalized_text(expectation.literal),
            }
            for expectation in expectations
        ],
        "page_features": features,
        "sightings": sightings,
        "summaries": summaries,
    }


def validate_structural_contents_report(report: Mapping) -> None:
    """Validate persisted shape and all deterministic cross-field invariants."""

    errors = sorted(
        _report_validator().iter_errors(report),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if errors:
        error = errors[0]
        path = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ValueError(f"structural observation schema failure at {path}: {error.message}")
    if structural_contents_schema_version_const() != STRUCTURAL_CONTENTS_SCHEMA_VERSION:
        raise ValueError(
            "structural observation schema version literal does not match the Python constant"
        )

    sources = report["sources"]
    source_ids = [source["source_id"] for source in sources]
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("structural observation report has duplicate source ids")
    source_by_id = {source["source_id"]: source for source in sources}
    for source in sources:
        SourceSpec(
            source_id=source["source_id"],
            format=source["format"],
            source_ref=source["source_ref"],
            sha256=source["sha256"],
            n_bytes=source["bytes"],
        )

    expectations = tuple(
        StructuralExpectation(
            expectation_id=entry["expectation_id"],
            literal=entry["literal"],
            role=entry["role"],
        )
        for entry in report["expectations"]
    )
    expectation_ids = [expectation.expectation_id for expectation in expectations]
    if len(set(expectation_ids)) != len(expectation_ids):
        raise ValueError("structural observation report has duplicate expectation ids")
    expectation_by_id = {
        expectation.expectation_id: expectation for expectation in expectations
    }
    for entry, expectation in zip(report["expectations"], expectations):
        if entry["normalized"] != _normalized_text(expectation.literal):
            raise ValueError(
                f"structural expectation {expectation.expectation_id!r} normalized value drifted"
            )
    if report["expectations_sha256"] != _expectation_hash(expectations):
        raise ValueError("structural observation expectations_sha256 does not match expectations")

    feature_by_source_page: dict[tuple[str, int], dict] = {}
    for feature in report["page_features"]:
        source_id = feature["source_id"]
        if source_id not in source_by_id:
            raise ValueError(f"page feature names unknown source {source_id!r}")
        if source_by_id[source_id]["format"] != FORMAT_DJVU_XML:
            raise ValueError(f"unpaged source {source_id!r} cannot carry a page feature")
        key = (source_id, feature["page"])
        if key in feature_by_source_page:
            raise ValueError(f"duplicate page feature for {source_id!r} page {feature['page']}")
        references = feature["trailing_page_references"]
        comparable = max(0, len(references) - 1)
        nondecreasing = sum(
            1 for left, right in zip(references, references[1:]) if right >= left
        )
        monotone_fraction = nondecreasing / comparable if comparable else None
        row_fraction = (
            len(references) / feature["nonempty_lines"]
            if feature["nonempty_lines"]
            else 0.0
        )
        contents_like = (
            len(references) >= CONTENTS_REFERENCE_MIN
            and comparable > 0
            and monotone_fraction is not None
            and monotone_fraction >= CONTENTS_MONOTONE_MIN
            and row_fraction >= CONTENTS_REFERENCE_FRACTION_MIN
        )
        expected = {
            "trailing_page_reference_lines": len(references),
            "comparable_adjacent_references": comparable,
            "nondecreasing_adjacent_references": nondecreasing,
            "nondecreasing_fraction": monotone_fraction,
            "trailing_page_reference_fraction": row_fraction,
            "contents_like": contents_like,
        }
        for field, value in expected.items():
            if feature[field] != value:
                raise ValueError(
                    f"page feature {source_id!r} page {feature['page']} field {field!r} "
                    "does not reproduce from its factual rows"
                )
        feature_by_source_page[key] = feature

    sighting_ids: set[str] = set()
    for sighting in report["sightings"]:
        source_id = sighting["source_id"]
        expectation_id = sighting["expectation_id"]
        if source_id not in source_by_id:
            raise ValueError(f"sighting names unknown source {source_id!r}")
        if expectation_id not in expectation_by_id:
            raise ValueError(f"sighting names unknown expectation {expectation_id!r}")
        if sighting["sighting_id"] in sighting_ids:
            raise ValueError(f"duplicate sighting id {sighting['sighting_id']!r}")
        sighting_ids.add(sighting["sighting_id"])
        if sighting["sighting_id"] != _sighting_id(
            source_id, expectation_id, sighting["locator"]
        ):
            raise ValueError(f"sighting id for {source_id!r}/{expectation_id!r} is incoherent")
        expectation = expectation_by_id[expectation_id]
        if sighting["normalized_expectation"] != _normalized_text(expectation.literal):
            raise ValueError(
                f"sighting for {source_id!r}/{expectation_id!r} carries the wrong normalization"
            )

        source_format = source_by_id[source_id]["format"]
        locator = sighting["locator"]
        if source_format == FORMAT_PLAIN_TEXT:
            if sighting["locus"] != LOCUS_UNRESOLVED or sighting["locus_features"] is not None:
                raise ValueError(f"plain-text sighting for {source_id!r} must have unresolved locus")
            if sighting["interpretation"] != INTERPRETATION_UNRESOLVED:
                raise ValueError(f"plain-text sighting for {source_id!r} must remain unresolved")
        else:
            key = (source_id, locator["page"])
            if key not in feature_by_source_page:
                raise ValueError(
                    f"DjVu sighting for {source_id!r} page {locator['page']} has no page feature"
                )
            feature = feature_by_source_page[key]
            locus = LOCUS_CONTENTS_LIKE if feature["contents_like"] else LOCUS_BODY_LIKE
            if sighting["locus"] != locus or sighting["interpretation"] != INTERPRETATION_INFERRED:
                raise ValueError(f"DjVu sighting for {source_id!r} carries an incoherent locus")
            expected_locus_features = {
                "trailing_page_reference_lines": feature["trailing_page_reference_lines"],
                "comparable_adjacent_references": feature["comparable_adjacent_references"],
                "nondecreasing_adjacent_references": feature[
                    "nondecreasing_adjacent_references"
                ],
                "nondecreasing_fraction": feature["nondecreasing_fraction"],
                "trailing_page_reference_fraction": feature[
                    "trailing_page_reference_fraction"
                ],
                "contents_like": feature["contents_like"],
            }
            if sighting["locus_features"] != expected_locus_features:
                raise ValueError(f"DjVu sighting for {source_id!r} does not copy its page features")

    expected_summaries: list[dict] = []
    for expectation in expectations:
        for source in sources:
            scoped = [
                sighting
                for sighting in report["sightings"]
                if sighting["expectation_id"] == expectation.expectation_id
                and sighting["source_id"] == source["source_id"]
            ]
            expected_summaries.append(
                {
                    "expectation_id": expectation.expectation_id,
                    "source_id": source["source_id"],
                    "body_like": sum(
                        1 for sighting in scoped if sighting["locus"] == LOCUS_BODY_LIKE
                    ),
                    "contents_like": sum(
                        1 for sighting in scoped if sighting["locus"] == LOCUS_CONTENTS_LIKE
                    ),
                    "unresolved": sum(
                        1 for sighting in scoped if sighting["locus"] == LOCUS_UNRESOLVED
                    ),
                    "total": len(scoped),
                    "interpretation": INTERPRETATION_OBSERVED,
                }
            )
    if report["summaries"] != expected_summaries:
        raise ValueError("structural observation summaries do not reproduce from the sightings")


def load_structural_contents_report(path: Path, *, expected_book: str | None = None) -> dict:
    """Load and fully validate a persisted advisory report, or fail through the artifact taxonomy."""

    path = Path(path)
    if not path.is_file():
        raise MissingInputError(f"structural observation report not found at {path}")
    try:
        report = read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise StaleArtifactError(f"structural observation report at {path} is unreadable") from exc
    try:
        validate_structural_contents_report(report)
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        raise StaleArtifactError(f"structural observation report at {path} is invalid: {exc}") from exc
    if expected_book is not None and report["book"] != expected_book:
        raise StaleArtifactError(
            f"structural observation report at {path} names book {report['book']!r}, not "
            f"{expected_book!r}"
        )
    return report


def write_structural_contents_report(path: Path, report: dict, *, force: bool = False) -> Path:
    """Atomically persist an advisory report with deny-by-default replacement."""

    path = Path(path)
    try:
        validate_structural_contents_report(report)
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        raise ValueError(f"refusing to write invalid structural observation report: {exc}") from exc
    if path.exists():
        try:
            existing = read_json(path)
        except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
            raise RegenerationGuardError(
                f"existing structural observation report at {path} is unreadable; refusing to "
                "overwrite it"
            ) from exc
        if existing == report:
            return path
        if not force:
            raise RegenerationGuardError(
                f"existing structural observation report at {path} differs; refusing to overwrite "
                "it without force=True"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, report)
    return path
