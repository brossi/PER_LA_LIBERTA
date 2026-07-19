"""Strict advisory seed-flag artifact and deterministic live lifecycle (#93)."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Mapping

import jsonschema

from engine.errors import MissingInputError, StaleArtifactError
from engine.structure.evidence import decision_digest, extent_digest
from engine.structure.projection import ContainerNode, MINTED_BY_HUMAN, ProjectionMap

STRUCTURE_REVIEW_FLAGS_SCHEMA_VERSION = 1
STRUCTURE_REVIEW_FLAGS_STALE_CLASS = "structure-review-flags"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "structure_review_flags.schema.json"


@lru_cache(maxsize=1)
def _validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def flag_id(producer_id: str, ordinal: int, message: str) -> str:
    """Stable id over producer, one-based emission order, and immutable legacy message."""

    payload = json.dumps(
        [producer_id, ordinal, message], ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return "flag-" + hashlib.sha256(payload).hexdigest()[:20]


def validate_structure_review_flags(doc: Mapping) -> None:
    errors = sorted(
        _validator().iter_errors(doc),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ValueError(f"structure-review flags schema failure at {location}: {error.message}")
    if type(doc["schema_version"]) is not int or type(doc["producer"]["version"]) is not int:
        raise ValueError("structure-review flag versions must be genuine integers")
    seen: set[str] = set()
    for ordinal, flag in enumerate(doc["flags"], 1):
        if flag["flag_id"] in seen:
            raise ValueError(f"duplicate structure-review flag id {flag['flag_id']!r}")
        seen.add(flag["flag_id"])
        expected = flag_id(doc["producer"]["id"], ordinal, flag["message"])
        if flag["flag_id"] != expected:
            raise ValueError(
                f"structure-review flag {flag['flag_id']!r} does not reproduce as {expected!r}"
            )
        bound = flag["target_node_id"] is not None
        if bound != (flag["seed_decision_digest"] is not None) or bound != (
            flag["seed_extent_digest"] is not None
        ):
            raise ValueError(
                f"structure-review flag {flag['flag_id']!r} must carry both seed digests iff bound"
            )


def load_structure_review_flags(path: Path, *, expected_book: str) -> dict:
    path = Path(path)
    if not path.is_file():
        raise MissingInputError(f"structure-review flags not found at {path}")
    try:
        doc = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise StaleArtifactError(f"structure-review flags at {path} are unreadable") from exc
    try:
        validate_structure_review_flags(doc)
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        raise StaleArtifactError(f"structure-review flags at {path} are invalid: {exc}") from exc
    if doc["book"] != expected_book:
        raise StaleArtifactError(
            f"structure-review flags name book {doc['book']!r}, not {expected_book!r}"
        )
    return doc


def live_flag(
    flag: Mapping,
    projection: ProjectionMap,
    *,
    current_observation_ids: set[str],
) -> dict:
    """Decorate one immutable seed flag with its deterministic current lifecycle state."""

    target_id = flag["target_node_id"]
    node = projection.by_id.get(target_id) if target_id is not None else None
    if target_id is None:
        base_state = "unresolved"
    elif not isinstance(node, ContainerNode) or node.minted_by != MINTED_BY_HUMAN:
        base_state = "superseded"
    elif (
        decision_digest(node) != flag["seed_decision_digest"]
        or extent_digest(node, projection) != flag["seed_extent_digest"]
    ):
        base_state = "superseded"
    elif flag["resolution_posture"] == "correction-required":
        base_state = "unresolved"
    else:
        base_state = "applicable"
    present = [
        observation_id
        for observation_id in flag["corroborating_observation_ids"]
        if observation_id in current_observation_ids
    ]
    state = (
        "corroborated"
        if base_state in {"applicable", "unresolved"} and present
        else base_state
    )
    return {
        **dict(flag),
        "state": state,
        "base_state": base_state,
        "present_corroborating_observation_ids": present,
    }

