"""Post-seal diagnostic comparison of the accepted Italian artifact to Gutenberg #28231.

This script is evaluation-only. It reads the human-produced reference only after
``accepted_outputs.sha256`` exists and never mutates the accepted pipeline artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import unicodedata
from pathlib import Path

from rapidfuzz.distance import Levenshtein

from engine.util.jsonio import atomic_write_json

ROOT = Path(__file__).resolve().parent
DEFAULT_CLEAN = ROOT / "work" / "output" / "clean.md"
DEFAULT_REFERENCE = ROOT / "evaluation" / "gutenberg_28231.txt"
DEFAULT_ACCEPTED_HASHES = ROOT / "work" / "data" / "accepted_outputs.sha256"
DEFAULT_REPORT = ROOT / "work" / "data" / "gutenberg_evaluation.json"

SECTIONS = (
    ("storiella_vecchia", "Storiella vecchia", "STORIELLA VECCHIA"),
    ("era_matto_o_aveva_fame", "Era matto o aveva fame?", "ERA MATTO O AVEVA FAME?..."),
    ("cavalleria_assassina", "Cavalleria assassina", "CAVALLERIA ASSASSINA"),
    ("scellerata", "Scellerata!", "SCELLERATA!..."),
    ("quintino_e_marco", "Quintino e Marco", "QUINTINO E MARCO"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_sections(markdown: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^## (.+?)\s*$", markdown))
    result = {}
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        body = markdown[match.end():stop]
        result[match.group(1)] = re.sub(
            r"(?m)^<!-- pages:\d+-\d+ -->\s*\n?", "", body, count=1
        ).strip()
    return result


def reference_sections(text: str) -> dict[str, str]:
    positions = []
    for _section_id, title, heading in SECTIONS:
        match = re.search(rf"(?m)^{re.escape(heading)}\s*$", text)
        if not match:
            raise ValueError(f"reference heading not found: {heading!r}")
        positions.append((title, match.start(), match.end()))
    end_match = re.search(r"(?m)^\*\*\* END OF THE PROJECT GUTENBERG EBOOK", text)
    end = end_match.start() if end_match else len(text)
    return {
        title: text[start : (positions[index + 1][1] if index + 1 < len(positions) else end)].strip()
        for index, (title, _heading_start, start) in enumerate(positions)
    }


def tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text).lower().replace("’", "'")
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    return re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)*", text, flags=re.UNICODE)


def compare(output: list[str], reference: list[str]) -> dict:
    opcodes = Levenshtein.opcodes(output, reference)
    samples = []
    counts = {"replace": 0, "insert": 0, "delete": 0}
    for op in opcodes:
        if op.tag == "equal":
            continue
        counts[op.tag] += max(op.src_end - op.src_start, op.dest_end - op.dest_start)
        if len(samples) < 20:
            left = max(0, op.dest_start - 5)
            right = min(len(reference), op.dest_end + 5)
            samples.append({
                "operation": op.tag,
                "accepted": " ".join(output[op.src_start:op.src_end]),
                "reference": " ".join(reference[op.dest_start:op.dest_end]),
                "reference_context": " ".join(reference[left:right]),
            })
    distance = Levenshtein.distance(output, reference)
    return {
        "accepted_tokens": len(output),
        "reference_tokens": len(reference),
        "token_edit_distance": distance,
        "word_error_rate": round(distance / max(len(reference), 1), 6),
        "token_similarity": round(1 - distance / max(len(output), len(reference), 1), 6),
        "edit_counts": counts,
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", type=Path, default=DEFAULT_CLEAN)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--accepted-hashes", type=Path, default=DEFAULT_ACCEPTED_HASHES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    if not args.accepted_hashes.is_file():
        raise SystemExit("accepted output hashes must exist before unsealing the reference")

    accepted = clean_sections(args.clean.read_text(encoding="utf-8"))
    reference = reference_sections(args.reference.read_text(encoding="utf-8-sig"))
    sections = []
    for section_id, title, _heading in SECTIONS:
        sections.append({"id": section_id, "title": title} | compare(
            tokens(accepted[title]), tokens(reference[title])
        ))
    total_accepted = sum(section["accepted_tokens"] for section in sections)
    total_reference = sum(section["reference_tokens"] for section in sections)
    total_distance = sum(section["token_edit_distance"] for section in sections)
    report = {
        "status": "diagnostic_complete",
        "reference": "Project Gutenberg #28231 human-produced transcription",
        "accepted_clean_sha256": sha256(args.clean),
        "reference_sha256": sha256(args.reference),
        "accepted_hash_manifest_sha256": sha256(args.accepted_hashes),
        "overall": {
            "accepted_tokens": total_accepted,
            "reference_tokens": total_reference,
            "token_edit_distance": total_distance,
            "word_error_rate": round(total_distance / max(total_reference, 1), 6),
        },
        "sections": sections,
        "remediation_applied": False,
    }
    atomic_write_json(args.report, report)
    print(f"Gutenberg evaluation: {args.report}")
    print(f"Overall token WER: {report['overall']['word_error_rate']:.2%}")
    for section in sections:
        print(f"  {section['id']}: {section['word_error_rate']:.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
