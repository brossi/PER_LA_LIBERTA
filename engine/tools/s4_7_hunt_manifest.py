#!/usr/bin/env python3
"""Run the S4.7 mutation/red protocol and emit one repository-local evidence manifest.

The shared mutation runner owns patch/test/restore safety and structured liveness.  This wrapper
streams its operator messages to stderr while retaining the exact invocation output, binds its JSON
and progress log to the table and runner bytes, inlines normalized patches, records any still-carried
reds plus the named green command, and verifies the hunted source set is byte-identical afterward.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import runpy
import signal
import subprocess
import sys
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUNNER = Path.home() / ".claude/skills/mutation-hunt/hunt.py"
DEFAULT_TABLE = ENGINE_ROOT / "tests/hunts/hunt_rebind.py"
DEFAULT_SEEDS = tuple(range(2700, 2716))
MUTATION_HEARTBEAT_INTERVAL_SECONDS = 5.0
LOCK_FILES = (
    "src/engine/structure/boundary_anchor.py",
    "tests/harness/relation.py",
    "tests/harness/materialize.py",
    "tests/harness/oracle.py",
    "tests/unit/test_s4_7_inv1_inv2.py",
    "tests/harness/boundary.py",
    "tests/harness/invariants_3_5.py",
    "tests/unit/test_s4_7_inv3_inv5.py",
    "tests/harness/scale.py",
    "tests/unit/test_s4_7_inv6_inv7.py",
    "tests/unit/test_authoring_evidence.py",
    "tools/s4_7_perf_baseline.py",
    "docs/probes/s4_7_item2_prereg.md",
    "docs/probes/s4_7_priority4_perf_baseline.json",
    "tools/s4_7_hunt_manifest.py",
)
PRIORITY5_LOCK_FILES = (
    "docs/ENGINE_STRUCTURE_TASKS.md",
    "docs/probes/s4_7_priority5_perf_baseline.json",
    "src/engine/structure/__init__.py",
    "src/engine/structure/artifacts.py",
    "src/engine/structure/boundary_anchor.py",
    "src/engine/structure/projection.py",
    "src/engine/structure/reanchor.py",
    "src/engine/structure/rebind.py",
    "src/engine/structure/schema/structure_map.schema.json",
    "src/engine/structure/structure_map.py",
    "tests/fixtures/structure/rebind_positive_structure_map.json",
    "tests/harness/boundary.py",
    "tests/harness/invariants_3_5.py",
    "tests/harness/materialize.py",
    "tests/harness/oracle.py",
    "tests/harness/relation.py",
    "tests/harness/scale.py",
    "tests/hunts/hunt_rebind.py",
    "tests/unit/test_rebind.py",
    "tests/unit/test_s4_7_inv1_inv2.py",
    "tests/unit/test_s4_7_inv3_inv5.py",
    "tests/unit/test_s4_7_inv6_inv7.py",
    "tests/unit/test_s4_7_mutation_progress.py",
    "tests/unit/test_s4_7_reanchor.py",
    "tests/unit/test_structure_artifacts.py",
    "tests/unit/test_structure_born_gate.py",
    "tests/unit/test_structure_map.py",
    "tools/s4_7_hunt_manifest.py",
    "tools/s4_7_perf_baseline.py",
)
DEFAULT_RED_SCOPES = (
    "test_inv1_shipped_rebind_bound_set_is_subset_of_shared_corpus_oracle",
    "test_inv1_anchor_poor_sentinels_abstain_within_and_cross_container",
    "test_inv1_cross_slot_merge_fails_both_affected_nodes_as_global_conflict",
    "test_inv2_interior_char_substitution_with_unchanged_boundaries_binds",
    "test_inv2_atom_split_with_unchanged_tokens_binds_exact_descendant_tuple",
    "test_inv2_atom_merge_with_unambiguous_ownership_binds",
)
PRIORITY3_RED_SCOPES = (
    "test_inv3_planted_greedy_wrong_span_is_rejected",
    "test_inv3_destination_atom_bind_with_invalid_map_is_rejected",
    "test_inv4_nonclean_insert_boundary_without_confirmation_fails_both_sides_loud",
    "test_inv4_clean_token_projection_inside_merged_atom_never_rounds_to_a_slot",
    "test_inv4_every_nonclean_class_without_confirmation_abstains",
    "test_inv4_independently_confirmed_boundary_uses_the_confirmation_path",
    "test_inv5_same_page_repeated_content_is_ambiguous_in_both_geometry_modes",
)
PRIORITY4_RED_SCOPES = (
    "test_inv6_shipped_rebind_wall_growth_exceeds_the_preregistered_bar",
    "test_inv6_shipped_end_to_end_wall_growth_exceeds_the_preregistered_bar",
    "test_inv7_deep_evidence_wall_clock_exceeds_the_preregistered_ceiling",
)
PRIORITY5_RESIDUAL_SCOPES: tuple[str, ...] = ()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_hashes(paths: tuple[str, ...]) -> dict[str, str]:
    return {path: _sha256(ENGINE_ROOT / path) for path in paths}


def _aggregate_hash(hashes: dict[str, str]) -> str:
    payload = "".join(f"{path}\0{digest}\n" for path, digest in sorted(hashes.items()))
    return hashlib.sha256(payload.encode()).hexdigest()


def _run(argv: list[str], *, env: dict[str, str] | None = None) -> dict:
    completed = subprocess.run(
        argv,
        cwd=ENGINE_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "argv": argv,
        "rc": completed.returncode,
        "output": completed.stdout,
    }


def _run_live(argv: list[str], *, env: dict[str, str] | None = None) -> dict:
    """Capture the runner exactly while forwarding its progress/result lines live."""
    proc = subprocess.Popen(
        argv,
        cwd=ENGINE_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        errors="replace",
        bufsize=1,
    )
    output: list[str] = []
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            output.append(line)
            try:
                print(line, end="", file=sys.stderr, flush=True)
            except OSError:
                pass
    except BaseException:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        raise
    finally:
        proc.stdout.close()
    return {
        "argv": argv,
        "rc": proc.wait(),
        "output": "".join(output),
    }


def _git(*args: str) -> str:
    result = _run(["git", *args])
    return result["output"].strip() if result["rc"] == 0 else f"<git rc={result['rc']}>"


def _normalized_patches(table_path: Path) -> list[dict]:
    table = runpy.run_path(str(table_path))
    normalized: list[dict] = []
    for raw in table["MUTANTS"]:
        if isinstance(raw, (tuple, list)):
            label, file, old, new, scope = raw
            sites = ({"file": file, "old": old, "new": new},)
        else:
            label, scope = raw["label"], raw["scope"]
            sites = raw.get("patches") or (
                {"file": raw["file"], "old": raw["old"], "new": raw["new"]},
            )
        normalized.append(
            {
                "label": label,
                "scope": scope,
                "patches": [
                    {
                        "file": site["file"],
                        "old": site["old"].replace("\r\n", "\n"),
                        "new": site["new"].replace("\r\n", "\n"),
                    }
                    for site in sites
                ],
            }
        )
    return normalized


def _imported_rebind_path(python: str) -> dict:
    code = (
        "import importlib, json; "
        "m=importlib.import_module('engine.structure.rebind'); "
        "print(json.dumps({'module': m.__name__, 'path': m.__file__}))"
    )
    result = _run([python, "-c", code])
    if result["rc"] != 0:
        raise RuntimeError(
            f"could not resolve imported rebind module:\n{result['output']}"
        )
    return json.loads(result["output"])


def main(argv: list[str] | None = None) -> int:
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--runner", type=Path, default=DEFAULT_RUNNER)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument(
        "--heartbeat-interval",
        type=float,
        default=MUTATION_HEARTBEAT_INTERVAL_SECONDS,
        help="shared mutation-runner heartbeat cadence (default: 5 seconds)",
    )
    parser.add_argument(
        "--progress-log",
        type=Path,
        help="structured mutation progress log (default: artifact stem + .progress.ndjson)",
    )
    parser.add_argument("--seed", type=int, action="append", dest="seeds")
    parser.add_argument(
        "--profile",
        choices=("priority2", "priority3", "priority4", "priority5"),
        default="priority2",
    )
    args = parser.parse_args(argv)

    runner = args.runner.resolve()
    table = args.table.resolve()
    artifact = args.artifact.resolve()
    if (
        not math.isfinite(args.heartbeat_interval)
        or args.heartbeat_interval <= 0
    ):
        raise ValueError("--heartbeat-interval must be a positive finite number")
    progress_log = (
        args.progress_log.resolve()
        if args.progress_log is not None
        else artifact.with_suffix(".progress.ndjson")
    )
    if progress_log == artifact:
        raise ValueError("--progress-log must differ from --artifact")
    seeds = tuple(args.seeds) if args.seeds else DEFAULT_SEEDS
    if args.profile != "priority2" and args.seeds:
        raise ValueError("--seed overrides apply only to the priority2 seeded corpus")
    python_path = ENGINE_ROOT / ".venv/bin/python"
    python = str(python_path if python_path.is_file() else Path(sys.executable))
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONPYCACHEPREFIX", None)
    env.pop("PYTEST_ADDOPTS", None)

    imported = _imported_rebind_path(python)
    expected_import = (ENGINE_ROOT / "src/engine/structure/rebind.py").resolve()
    if Path(imported["path"]).resolve() != expected_import:
        raise RuntimeError(
            f"imported module mismatch: {imported['path']} != repository source {expected_import}"
        )

    normalized_mutants = _normalized_patches(table)
    mutated_files = {
        patch["file"] for mutant in normalized_mutants for patch in mutant["patches"]
    }
    lock_files = PRIORITY5_LOCK_FILES if args.profile == "priority5" else LOCK_FILES
    source_files = tuple(sorted(set(lock_files) | mutated_files))
    pre_hashes = _file_hashes(source_files)
    test_files = {
        "priority2": ("tests/unit/test_s4_7_inv1_inv2.py",),
        "priority3": ("tests/unit/test_s4_7_inv3_inv5.py",),
        "priority4": ("tests/unit/test_s4_7_inv6_inv7.py",),
        "priority5": (
            "tests/unit/test_rebind.py",
            "tests/unit/test_structure_map.py",
            "tests/unit/test_structure_artifacts.py",
            "tests/unit/test_structure_born_gate.py",
            "tests/unit/test_s4_7_inv1_inv2.py",
            "tests/unit/test_s4_7_inv3_inv5.py",
            "tests/unit/test_s4_7_reanchor.py",
            "tests/unit/test_s4_7_inv6_inv7.py",
            "tests/unit/test_s4_7_mutation_progress.py",
            "tests/unit/test_authoring_evidence.py",
        ),
    }[args.profile]
    red_scopes = {
        "priority2": DEFAULT_RED_SCOPES,
        "priority3": PRIORITY3_RED_SCOPES,
        "priority4": PRIORITY4_RED_SCOPES,
        "priority5": PRIORITY5_RESIDUAL_SCOPES,
    }[args.profile]
    green_command = [
        python,
        "-m",
        "pytest",
        *test_files,
        "-q",
        "-p",
        "no:cacheprovider",
    ]
    if args.profile != "priority5":
        green_command.extend(
            [
                "-k",
                {
                    "priority2": "s4_7_inv1_inv2",
                    "priority3": "s4_7_inv3_inv5",
                    "priority4": "s4_7_inv6_inv7",
                }[args.profile],
            ]
        )
    red_commands = [
        [
            python,
            "-m",
            "pytest",
            f"tests/unit/test_s4_7_inv6_inv7.py::{scope}"
            if args.profile == "priority5"
            else f"{test_files[0]}::{scope}",
            "--runxfail",
            "-q",
            "-p",
            "no:cacheprovider",
        ]
        for scope in red_scopes
    ]

    temp_handle = tempfile.NamedTemporaryFile(
        prefix="s4_7_runner_", suffix=".json", delete=False
    )
    temp_handle.close()
    runner_artifact = Path(temp_handle.name)
    try:
        try:
            runner_run = _run_live(
                [
                    python,
                    str(runner),
                    "--table",
                    str(table),
                    "--artifact",
                    str(runner_artifact),
                    "--heartbeat-interval",
                    str(args.heartbeat_interval),
                    "--progress-log",
                    str(progress_log),
                ],
                env=env,
            )
        except KeyboardInterrupt:
            print(
                "S4.7 mutation evidence run interrupted after runner restoration; "
                f"inspect {progress_log}",
                file=sys.stderr,
            )
            return 130
        runner_json = json.loads(runner_artifact.read_text(encoding="utf-8"))
    finally:
        runner_artifact.unlink(missing_ok=True)

    red_runs = [_run(command, env=env) for command in red_commands]
    green_run = _run(green_command, env=env)
    if args.profile == "priority2":
        case_matrix = list(priority_case_names(seeds))
        diagnostics = priority_diagnostics(seeds)
        recorded_seeds = list(seeds)
        modes = ["no-geometry"]
    elif args.profile == "priority3":
        case_matrix, diagnostics, recorded_seeds = priority3_manifest_data()
        modes = ["no-geometry", "geometry-primary", "geometry-tie-break"]
    elif args.profile == "priority4":
        case_matrix, diagnostics, recorded_seeds = priority4_manifest_data()
        modes = ["no-geometry", "deep-evidence-isolated-core"]
    else:
        case_matrix, diagnostics, recorded_seeds = priority5_manifest_data()
        modes = [
            "no-geometry",
            "geometry-primary",
            "geometry-tie-break",
            "deep-evidence-isolated-core",
        ]
    post_hashes = _file_hashes(source_files)

    manifest = {
        "schema": (
            "s4.7-item3-priority5-audit-manifest@v1"
            if args.profile == "priority5"
            else f"s4.7-item2-{args.profile}-red-manifest@v1"
        ),
        "profile": args.profile,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(ENGINE_ROOT),
        "git": {
            "head": _git("rev-parse", "HEAD"),
            "branch": _git("branch", "--show-current"),
            "status": _git("status", "--short"),
        },
        "seeds": recorded_seeds,
        "modes": modes,
        "case_matrix": case_matrix,
        "diagnostics": diagnostics,
        "environment": {
            "python": platform.python_version(),
            "python_executable": python,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "uv_lock_sha256": _sha256(ENGINE_ROOT / "uv.lock"),
        },
        "imported_module": imported,
        "source_identity": {
            "files": list(source_files),
            "pre": pre_hashes,
            "post": post_hashes,
            "pre_aggregate_sha256": _aggregate_hash(pre_hashes),
            "post_aggregate_sha256": _aggregate_hash(post_hashes),
            "byte_identical_after": pre_hashes == post_hashes,
        },
        "mutant_table": {
            "path": str(table.relative_to(ENGINE_ROOT)),
            "sha256": _sha256(table),
            "normalized_mutants": normalized_mutants,
        },
        "runner": {
            "path": str(runner),
            "sha256": _sha256(runner),
            "invocation": runner_run,
            "artifact": runner_json,
            "progress": {
                "path": str(progress_log),
                "sha256": _sha256(progress_log),
                "heartbeat_interval_seconds": args.heartbeat_interval,
            },
        },
        "carried_red_demonstrations": red_runs,
        "green": green_run,
    }
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    red_ok = all(run["rc"] == 1 for run in red_runs)
    okay = (
        runner_run["rc"] == 0
        and runner_json.get("restore_verified") is True
        and pre_hashes == post_hashes
        and red_ok
        and green_run["rc"] == 0
    )
    if not okay:
        print(f"S4.7 evidence run failed; inspect {artifact}", file=sys.stderr)
        return 1
    print(f"S4.7 evidence manifest written: {artifact}")
    return 0


def priority_case_names(seeds: tuple[int, ...] = DEFAULT_SEEDS) -> tuple[str, ...]:
    """Resolve the materialized corpus itself; a hand-copied case ledger could silently drift."""
    tests_path = str(ENGINE_ROOT / "tests")
    if tests_path not in sys.path:
        sys.path.insert(0, tests_path)
    from harness.oracle import priority2_shared_corpus

    corpus = priority2_shared_corpus()
    if seeds != corpus.random_seeds:
        raise ValueError(
            f"manifest seeds {seeds} do not equal corpus seeds {corpus.random_seeds}"
        )
    return corpus.case_names


def priority_diagnostics(seeds: tuple[int, ...] = DEFAULT_SEEDS) -> list[dict]:
    """Report bound-correct / abstained / wrong counts per case; never compute a gate rate."""
    tests_path = str(ENGINE_ROOT / "tests")
    if tests_path not in sys.path:
        sys.path.insert(0, tests_path)
    from engine.structure.rebind import RebindContext, rebind
    from harness.oracle import (
        AllowedBind,
        ObservedBind,
        SlotRef,
        allowed_bind_set,
        case_oracle,
        diagnose_case,
        priority2_shared_corpus,
        required_inv2_binds,
    )

    corpus = priority2_shared_corpus()
    if seeds != corpus.random_seeds:
        raise ValueError(
            f"manifest seeds {seeds} do not equal corpus seeds {corpus.random_seeds}"
        )
    required = required_inv2_binds(corpus)
    rows: list[dict] = []
    for case in corpus.cases:
        bundle = case.bundle
        result = rebind(
            RebindContext(
                bundle.old_map,
                bundle.old_streams,
                bundle.fresh_streams,
                old_evidence=bundle.old_evidence,
                geometry_mode=bundle.geometry_mode,
                policy=bundle.policy,
            )
        )
        observed = tuple(
            ObservedBind(SlotRef(node.node_id, slot.slot_name), slot.fresh_atom_ids)
            for node in result.report.nodes
            for slot in node.slots
            if slot.bound
        )
        allowed = allowed_bind_set(bundle)
        diagnostic = diagnose_case(case.name, case_oracle(bundle), observed, allowed)
        observed_pairs = {
            AllowedBind(bind.slot, bind.fresh_atom_ids) for bind in observed
        }
        rows.append(
            {
                "case": case.name,
                "seed": bundle.config.seed,
                "config": _jsonable(asdict(bundle.config)),
                "bound_correct": diagnostic.bound_correct,
                "abstained": diagnostic.abstained,
                "wrong": diagnostic.wrong,
                "allowed_pair_count": len(allowed),
                "required_inv2": [
                    {
                        "node_id": pair.slot.node_id,
                        "slot_name": pair.slot.slot_name,
                        "fresh_atom_ids": list(pair.fresh_atom_ids),
                        "observed": pair in observed_pairs,
                    }
                    for pair in required.get(case.name, ())
                ],
            }
        )
    return rows


def priority3_manifest_data() -> tuple[list[str], list[dict], list[int]]:
    """Resolve the analytic/move/mode matrices used by the Priority 3 carried reds."""
    tests_path = str(ENGINE_ROOT / "tests")
    if tests_path not in sys.path:
        sys.path.insert(0, tests_path)
    from harness.boundary import mandatory_boundary_cases
    from harness.invariants_3_5 import geometry_interaction_matrix, priority3_move_cases

    rows: list[dict] = []
    seeds: set[int] = set()
    for case in mandatory_boundary_cases():
        rows.append(
            {
                "family": "boundary-classification",
                "case": case.name,
                "boundary": case.boundary,
                "expected": case.expected,
                "blocks": _jsonable(asdict(case)["blocks"]),
            }
        )
    for case in priority3_move_cases():
        seeds.add(case.bundle.config.seed)
        rows.append(
            {
                "family": "move",
                "case": case.name,
                "seed": case.bundle.config.seed,
                "config": _jsonable(asdict(case.bundle.config)),
                "affected": [asdict(slot) for slot in case.affected],
            }
        )
    for row in geometry_interaction_matrix():
        seeds.add(row.bundle.config.seed)
        if row.companion is not None:
            seeds.add(row.companion.config.seed)
        rows.append(
            {
                "family": "geometry-interaction",
                "case": f"{row.drift}:{row.mode}",
                "seed": row.bundle.config.seed,
                "config": _jsonable(asdict(row.bundle.config)),
                "companion_config": _jsonable(asdict(row.companion.config))
                if row.companion is not None
                else None,
                "expected": row.expected,
            }
        )
    case_matrix = [f"{row['family']}:{row['case']}" for row in rows]
    return case_matrix, rows, sorted(seeds)


def priority4_manifest_data() -> tuple[list[str], list[dict], list[int]]:
    """Read the saved baseline; the evidence wrapper never re-times or tunes the result."""
    baseline_path = ENGINE_ROOT / "docs/probes/s4_7_priority4_perf_baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if baseline.get("schema") != "s4.7-item2-priority4-perf-baseline@v1":
        raise ValueError("unexpected Priority 4 performance baseline schema")
    points = baseline["inv6"]["points"]
    cases = [f"inv6:rebind:T={point['ledger']['T']}" for point in points]
    cases.append("inv7:evidence_findings:D=3000")
    rows = [
        {
            "family": "inv6-rebind",
            "seed": point["seed"],
            "ledger": point["ledger"],
            "preflight": point["preflight"],
            "rebind": point["phases"]["rebind"],
            "end_to_end": point["phases"]["end_to_end"],
        }
        for point in points
    ]
    rows.append(
        {
            "family": "inv7-evidence",
            "ledger": baseline["inv7"]["ledger"],
            "preflight": baseline["inv7"]["preflight"],
            "evidence_findings": baseline["inv7"]["evidence_findings"],
            "within_wall_clock_ceiling": baseline["inv7"]["within_wall_clock_ceiling"],
            "within_tracemalloc_ceiling": baseline["inv7"][
                "within_tracemalloc_ceiling"
            ],
        }
    )
    return cases, rows, [point["seed"] for point in points]


def priority5_manifest_data() -> tuple[list[str], list[dict], list[int]]:
    """Read the final S4.7 baseline and expose every registered measured phase."""
    baseline_path = ENGINE_ROOT / "docs/probes/s4_7_priority5_perf_baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if baseline.get("schema") != "s4.7-perf-baseline@v2":
        raise ValueError("unexpected Priority 5 performance baseline schema")
    points = baseline["inv6"]["points"]
    cases = [
        f"inv6:{phase}:T={point['ledger']['T']}"
        for point in points
        for phase in ("serialize", "load", "index", "rebind", "end_to_end")
    ]
    cases.append("inv7:evidence_findings:D=3000")
    rows = [
        {
            "family": "inv6-production",
            "seed": point["seed"],
            "ledger": point["ledger"],
            "preflight": point["preflight"],
            "phases": point["phases"],
        }
        for point in points
    ]
    rows.append(
        {
            "family": "inv6-growth",
            "limits": baseline["inv6"]["limits"],
            "growth_by_phase": baseline["inv6"]["growth_by_phase"],
        }
    )
    rows.append(
        {
            "family": "inv7-registered-passing",
            "ledger": baseline["inv7"]["ledger"],
            "limits": baseline["inv7"]["limits"],
            "preflight": baseline["inv7"]["preflight"],
            "evidence_findings": baseline["inv7"]["evidence_findings"],
            "within_wall_clock_ceiling": baseline["inv7"]["within_wall_clock_ceiling"],
            "within_tracemalloc_ceiling": baseline["inv7"][
                "within_tracemalloc_ceiling"
            ],
        }
    )
    return cases, rows, [point["seed"] for point in points]


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return [_jsonable(item) for item in sorted(value, key=repr)]
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
