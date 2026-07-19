"""S4.6c/#90 — generalized, advisory structural-content source observations."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from engine.errors import MissingInputError, RegenerationGuardError, StaleArtifactError
from engine.structure.structural_contents import (
    LOCUS_BODY_LIKE,
    LOCUS_CONTENTS_LIKE,
    LOCUS_UNRESOLVED,
    MATCH_LITERAL,
    MATCH_NORMALIZED,
    SourceSpec,
    StructuralExpectation,
    load_structural_contents_report,
    load_structural_contents_schema,
    load_source_bytes,
    observe_structural_contents,
    structural_contents_schema_version_const,
    validate_structural_contents_report,
    write_structural_contents_report,
)


def _spec(source_id: str, format: str, data: bytes) -> SourceSpec:
    return SourceSpec(
        source_id=source_id,
        format=format,
        source_ref=f"fixture:{source_id}",
        sha256=hashlib.sha256(data).hexdigest(),
        n_bytes=len(data),
    )


def _plain(source_id: str, text: str):
    data = text.encode("utf-8")
    return load_source_bytes(_spec(source_id, "plain-text", data), data)


def _djvu(source_id: str, pages: list[list[str]]):
    objects = []
    for page, lines in enumerate(pages, 1):
        rendered_lines = []
        for line in lines:
            words = "".join(
                f'<WORD coords="10,20,30,5">{word}</WORD>' for word in line.split()
            )
            rendered_lines.append(f"<LINE>{words}</LINE>")
        objects.append(
            f'<OBJECT><PARAM name="PAGE" value="page_{page:04d}.djvu"/>'
            f'<HIDDENTEXT><PAGECOLUMN><REGION><PARAGRAPH>{"".join(rendered_lines)}'
            "</PARAGRAPH></REGION></PAGECOLUMN></HIDDENTEXT></OBJECT>"
        )
    data = ("<?xml version=\"1.0\"?><DjVuXML><BODY>" + "".join(objects) +
            "</BODY></DjVuXML>").encode("utf-8")
    return load_source_bytes(_spec(source_id, "djvu-xml", data), data)


PART_ONE = StructuralExpectation("part-1", "Parte Prima", "part")
PART_TWO = StructuralExpectation("part-2", "Parte Seconda", "part")


def _report(*sources, expectations=(PART_ONE, PART_TWO)):
    return observe_structural_contents(
        book="specimen",
        sources=sources,
        expectations=expectations,
    )


def test_djvu_and_plain_text_find_equivalent_normalized_text_with_distinct_locators():
    plain = _plain("plain", "PARTE   PRIMA\n")
    djvu = _djvu("djvu", [["Parte Prima"]])

    report = _report(plain, djvu, expectations=(PART_ONE,))
    sightings = report["sightings"]

    assert [(item["source_id"], item["match_kind"]) for item in sightings] == [
        ("plain", MATCH_NORMALIZED),
        ("djvu", MATCH_LITERAL),
    ]
    assert sightings[0]["locator"] == {
        "line_start": 1,
        "line_end": 1,
        "normalized_token_start": 0,
        "normalized_token_end": 2,
        "byte_start": 0,
        "byte_end": 13,
    }
    assert sightings[1]["locator"]["page"] == 1
    assert sightings[1]["locator"]["bbox"] == [10, 5, 30, 20]


def test_declared_string_may_span_three_lines_but_never_silently_widens_to_four():
    three = StructuralExpectation("three", "Prima divisione del libro", "part")
    four = StructuralExpectation("four", "Questa divisione attraversa quattro linee", "part")
    source = _plain(
        "plain",
        "Prima\ndivisione del\nlibro\nQuesta\ndivisione\nattraversa quattro\nlinee\n",
    )

    report = _report(source, expectations=(three, four))

    assert [item["expectation_id"] for item in report["sightings"]] == ["three"]
    summaries = {item["expectation_id"]: item for item in report["summaries"]}
    assert summaries["three"]["total"] == 1
    assert summaries["four"]["total"] == 0


def test_repeated_declared_string_on_one_line_has_distinct_exact_locators():
    source = _plain("plain", "Parte Prima e Parte Prima")

    report = _report(source, expectations=(PART_ONE,))

    assert len(report["sightings"]) == 2
    assert len({item["sighting_id"] for item in report["sightings"]}) == 2
    assert [item["locator"]["normalized_token_start"] for item in report["sightings"]] == [0, 3]


def test_duplicate_source_and_expectation_ids_fail_loud():
    source = _plain("same", "Parte Prima")
    with pytest.raises(ValueError, match="duplicate source_id"):
        _report(source, source, expectations=(PART_ONE,))
    with pytest.raises(ValueError, match="duplicate expectation_id"):
        _report(
            source,
            expectations=(PART_ONE, StructuralExpectation("part-1", "Other", "part")),
        )


def test_hash_length_utf8_and_xml_failures_are_stale_not_absence():
    data = b"Parte Prima"
    with pytest.raises(StaleArtifactError, match="SHA-256"):
        load_source_bytes(
            SourceSpec("plain", "plain-text", "fixture:plain", "0" * 64, len(data)), data
        )
    with pytest.raises(StaleArtifactError, match="byte length"):
        load_source_bytes(
            SourceSpec(
                "plain", "plain-text", "fixture:plain", hashlib.sha256(data).hexdigest(), 999
            ),
            data,
        )

    non_utf8 = b"\xff"
    with pytest.raises(StaleArtifactError, match="UTF-8"):
        load_source_bytes(_spec("plain", "plain-text", non_utf8), non_utf8)

    malformed = b"<DjVuXML><OBJECT>"
    with pytest.raises(StaleArtifactError, match="XML"):
        load_source_bytes(_spec("djvu", "djvu-xml", malformed), malformed)


def test_djvu_auxiliary_fifth_coordinate_is_accepted_but_short_coords_fail():
    extended = (
        b'<DjVuXML><BODY><OBJECT><LINE><WORD coords="37,187,351,79,156">Parte</WORD>'
        b'<WORD coords="352,187,500,79">Prima</WORD></LINE></OBJECT></BODY></DjVuXML>'
    )
    source = load_source_bytes(_spec("extended", "djvu-xml", extended), extended)
    assert source.lines[0].bbox == (37, 79, 500, 187)

    short = b'<DjVuXML><BODY><OBJECT><LINE><WORD coords="1,2,3">x</WORD></LINE></OBJECT></BODY></DjVuXML>'
    with pytest.raises(StaleArtifactError, match="malformed WORD coords"):
        load_source_bytes(_spec("short", "djvu-xml", short), short)


def test_contents_like_feature_requires_five_rows_and_sixty_percent_monotonicity():
    qualifying = _djvu(
        "qualifying",
        [["INDICE", "Uno 1", "Due 3", "Tre 3", "Quattro 8", "Cinque 13", "Parte Prima"]],
    )
    too_short = _djvu(
        "short",
        [["INDICE", "Uno 1", "Due 3", "Tre 5", "Quattro 8", "Parte Prima"]],
    )
    nonmonotone = _djvu(
        "reordered",
        [["INDICE", "Uno 9", "Due 1", "Tre 8", "Quattro 2", "Cinque 7", "Parte Prima"]],
    )

    report = _report(qualifying, too_short, nonmonotone, expectations=(PART_ONE,))
    by_source = {item["source_id"]: item for item in report["page_features"]}

    assert by_source["qualifying"]["contents_like"] is True
    assert by_source["qualifying"]["trailing_page_references"] == [1, 3, 3, 8, 13]
    assert by_source["short"]["contents_like"] is False
    assert by_source["reordered"]["contents_like"] is False
    loci = {item["source_id"]: item["locus"] for item in report["sightings"]}
    assert loci == {
        "qualifying": LOCUS_CONTENTS_LIKE,
        "short": LOCUS_BODY_LIKE,
        "reordered": LOCUS_BODY_LIKE,
    }


def test_lowercase_roman_letter_words_and_sparse_reference_rows_do_not_make_contents():
    source = _djvu(
        "body",
        [[
            "Riga ordinaria di",
            "Altra frase mi",
            "Ancora parole ci",
            "Testo comune vi",
            "Prosa finisce li",
            "Capitolo 1",
            "molto testo senza riferimento",
            "un'altra riga di prosa",
            "ancora una riga",
            "chiusura della pagina",
            "ulteriore prosa",
        ]],
    )

    report = _report(source, expectations=(StructuralExpectation("chapter", "Capitolo", "chapter"),))

    feature = report["page_features"][0]
    assert feature["trailing_page_reference_lines"] == 1
    assert feature["contents_like"] is False
    assert report["sightings"][0]["locus"] == LOCUS_BODY_LIKE


def test_topical_index_shape_is_only_an_unverified_candidate_not_asserted_hierarchy():
    source = _djvu(
        "topical",
        [["INDICE ANALITICO", "Alberi 1", "Battaglie 7", "Citta 9", "Dazio 15", "Eroi 20",
          "Parte Prima"]],
    )

    report = _report(source, expectations=(PART_ONE,))

    assert report["page_features"][0]["contents_like"] is True
    assert report["page_features"][0]["interpretation"] == "inferred"
    assert report["sightings"][0]["unverified"] is True
    assert "hierarchy" not in json.dumps(report).lower()


def test_unpaged_sighting_and_bounded_zero_counts_remain_unresolved():
    present = _plain("present", "Parte Prima")
    absent = _plain("absent", "No division label here")

    report = _report(present, absent, expectations=(PART_ONE,))
    summaries = {item["source_id"]: item for item in report["summaries"]}

    assert report["sightings"][0]["locus"] == LOCUS_UNRESOLVED
    assert summaries["present"] == {
        "expectation_id": "part-1",
        "source_id": "present",
        "body_like": 0,
        "contents_like": 0,
        "unresolved": 1,
        "total": 1,
        "interpretation": "observed",
    }
    assert summaries["absent"]["total"] == 0
    assert summaries["absent"]["interpretation"] == "observed"
    assert {item["source_id"] for item in report["sources"]} == {"present", "absent"}


def test_non_pll_non_italian_explicit_division_needs_no_language_plugin():
    source = _djvu("german-djvu", [["ERSTER TEIL", "Kapitel Eins"]])
    expectation = StructuralExpectation("division-1", "Erster Teil", "division")

    report = observe_structural_contents(
        book="der_schweizerische_robinson",
        sources=(source,),
        expectations=(expectation,),
    )

    assert report["book"] == "der_schweizerische_robinson"
    assert report["sightings"][0]["matched_text"] == "ERSTER TEIL"
    assert report["sightings"][0]["locus"] == LOCUS_BODY_LIKE


def test_cross_witness_disagreement_is_preserved_without_resolution():
    explicit = _djvu("explicit", [["Part One", "Chapter One"]])
    absent = _djvu("absent", [["Chapter One"]])
    expectation = StructuralExpectation("part-1", "Part One", "part")

    report = observe_structural_contents(
        book="conflicting_specimen",
        sources=(explicit, absent),
        expectations=(expectation,),
    )
    summaries = {item["source_id"]: item for item in report["summaries"]}

    assert summaries["explicit"]["body_like"] == 1
    assert summaries["absent"]["total"] == 0
    assert len(report["sightings"]) == 1
    assert "resolved" not in report


def test_report_is_deterministic_and_writer_is_guarded(tmp_path):
    source = _plain("plain", "Parte Prima")
    first = _report(source, expectations=(PART_ONE,))
    second = _report(source, expectations=(PART_ONE,))
    assert first == second
    assert json.dumps(first, ensure_ascii=False) == json.dumps(second, ensure_ascii=False)

    path = tmp_path / "structure_observations.json"
    write_structural_contents_report(path, first)
    first_bytes = path.read_bytes()
    write_structural_contents_report(path, first)
    assert path.read_bytes() == first_bytes

    changed = dict(first, book="different")
    with pytest.raises(RegenerationGuardError, match="refusing to overwrite"):
        write_structural_contents_report(path, changed)
    write_structural_contents_report(path, changed, force=True)
    assert json.loads(path.read_text(encoding="utf-8"))["book"] == "different"


def test_schema_loader_and_semantic_coherence_fail_stale(tmp_path):
    report = _report(_plain("plain", "Parte Prima"), expectations=(PART_ONE,))
    assert structural_contents_schema_version_const() == 1
    assert structural_contents_schema_version_const(load_structural_contents_schema()) == 1
    validate_structural_contents_report(report)

    path = tmp_path / "structure_observations.json"
    write_structural_contents_report(path, report)
    assert load_structural_contents_report(path, expected_book="specimen") == report
    with pytest.raises(StaleArtifactError, match="names book"):
        load_structural_contents_report(path, expected_book="other")

    mutations = []
    stale_version = deepcopy(report)
    stale_version["schema_version"] = 2
    mutations.append(stale_version)
    wrong_hash = deepcopy(report)
    wrong_hash["expectations_sha256"] = "0" * 64
    mutations.append(wrong_hash)
    wrong_id = deepcopy(report)
    wrong_id["sightings"][0]["sighting_id"] = "obs-" + "0" * 20
    mutations.append(wrong_id)
    wrong_summary = deepcopy(report)
    wrong_summary["summaries"][0]["total"] = 2
    mutations.append(wrong_summary)

    for index, mutation in enumerate(mutations):
        target = tmp_path / f"bad_{index}.json"
        target.write_text(json.dumps(mutation), encoding="utf-8")
        with pytest.raises(StaleArtifactError, match="invalid"):
            load_structural_contents_report(target)
        with pytest.raises(ValueError, match="refusing to write invalid"):
            write_structural_contents_report(tmp_path / f"write_{index}.json", mutation)

    with pytest.raises(MissingInputError, match="not found"):
        load_structural_contents_report(tmp_path / "missing.json")


def test_mechanism_has_no_pll_literal_or_language_structure_dependency():
    module = Path(__file__).parents[2] / "src/engine/structure/structural_contents.py"
    text = module.read_text(encoding="utf-8")
    assert "per_la_liberta" not in text
    assert "Parte Prima" not in text
    assert "engine.lang" not in text
