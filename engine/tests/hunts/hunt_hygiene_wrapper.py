"""Mutant table for tools/test.py — the hygiene pytest wrapper (issue #42).

Run with the mutation-hunt runner:

    python3 ~/.claude/skills/mutation-hunt/hunt.py \
        --table tests/hunts/hunt_hygiene_wrapper.py --artifact /tmp/hunt42.json

The hunt's own TEST_CMD deliberately does NOT go through tools/test.py: the
wrapper is the artifact under mutation, and the measurement instrument must
not be the thing being measured. The runner's default command pins the same
hygiene (PYTHONDONTWRITEBYTECODE=1, no:cacheprovider, pycache purge) itself.
"""
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[2])
TIMEOUT = 300

W = "tools/test.py"
T = "tests/unit/test_hygiene_wrapper.py"


def m(label, old, new, test_id):
    return {"label": label, "file": W, "old": old, "new": new,
            "scope": f"{T}::{test_id}"}


MUTANTS = [
    # --- env pins ---
    m("env-pin-dropped",
      '    env["PYTHONDONTWRITEBYTECODE"] = "1"',
      '    env.pop("PYTHONDONTWRITEBYTECODE", None)',
      "TestHygienePins::test_child_env_pins_dont_write_bytecode"),
    m("env-inheritance-dropped",
      "    env = dict(os.environ)",
      "    env = {}",
      "TestHygienePins::test_child_env_inherits_the_parent"),
    m("addopts-strip-dropped",
      '    env.pop("PYTEST_ADDOPTS", None)',
      '    env.get("PYTEST_ADDOPTS", None)',
      "TestHygienePins::test_pytest_addopts_cannot_defeat_the_pins"),
    m("pycacheprefix-strip-dropped",
      '    env.pop("PYTHONPYCACHEPREFIX", None)',
      '    env.get("PYTHONPYCACHEPREFIX", None)',
      "TestHygienePins::test_pycacheprefix_cannot_smuggle_stale_bytecode"),
    # --- flag pins ---
    m("quiet-flag-dropped",
      'PINNED_FLAGS = ("-q", "-p", "no:cacheprovider")',
      'PINNED_FLAGS = ("-p", "no:cacheprovider")',
      "TestHygienePins::test_quiet_flag_pinned"),
    m("cacheprovider-pin-dropped",
      'PINNED_FLAGS = ("-q", "-p", "no:cacheprovider")',
      'PINNED_FLAGS = ("-q",)',
      "TestHygienePins::test_cacheprovider_disabled_leaves_no_pytest_cache"),
    # --- verbatim passthrough / exit codes ---
    m("args-split-mangled",
      '    cmd = [_child_python(ENGINE_ROOT), "-m", "pytest", *PINNED_FLAGS, *args]',
      '    cmd = [_child_python(ENGINE_ROOT), "-m", "pytest", *PINNED_FLAGS,\n'
      "           *(t for a in args for t in a.split())]",
      "TestPassthrough::test_k_expression_reaches_pytest_verbatim"),
    m("exit-code-boolified",
      "    return 128 - rc if rc < 0 else rc",
      "    return 1 if rc else 0",
      "TestPassthrough::test_exit_code_passes_through_verbatim_not_boolean"),
    m("child-rc-discarded",
      "    return 128 - rc if rc < 0 else rc",
      "    return 0",
      "TestPassthrough::test_red_suite_exit_code_propagates"),
    m("signal-death-unmapped",
      "    return 128 - rc if rc < 0 else rc",
      "    return rc",
      "TestChildProcess::test_signal_killed_child_maps_to_128_plus_signal"),
    m("signal-mapping-off-by-one",
      "    return 128 - rc if rc < 0 else rc",
      "    return 129 - rc if rc < 0 else rc",
      "TestChildProcess::test_signal_killed_child_maps_to_128_plus_signal"),
    m("zero-rc-misread-as-signal-death",
      "    return 128 - rc if rc < 0 else rc",
      "    return 128 - rc if rc <= 0 else rc",
      "TestPassthrough::test_k_expression_reaches_pytest_verbatim"),
    # --- purge ---
    m("purge-call-dropped",
      "    if purge:\n        _purge_pycache(ENGINE_ROOT)",
      "    if False:\n        _purge_pycache(ENGINE_ROOT)",
      "TestPurge::test_purge_removes_stale_pycache_by_default"),
    m("purge-reordered-after-child",
      "    if purge:\n"
      "        _purge_pycache(ENGINE_ROOT)\n"
      '    cmd = [_child_python(ENGINE_ROOT), "-m", "pytest", *PINNED_FLAGS, *args]\n'
      "    try:\n"
      "        rc = subprocess.run(cmd, cwd=ENGINE_ROOT, env=_child_env()).returncode\n"
      "    except KeyboardInterrupt:\n"
      "        return 130",
      '    cmd = [_child_python(ENGINE_ROOT), "-m", "pytest", *PINNED_FLAGS, *args]\n'
      "    try:\n"
      "        rc = subprocess.run(cmd, cwd=ENGINE_ROOT, env=_child_env()).returncode\n"
      "    except KeyboardInterrupt:\n"
      "        return 130\n"
      "    if purge:\n"
      "        _purge_pycache(ENGINE_ROOT)",
      "TestPurge::test_purge_removes_stale_pycache_by_default"),
    m("multi-token-consumption-dropped",
      '    while args and args[0] == "--no-purge":',
      '    if args and args[0] == "--no-purge":',
      "TestPurge::test_repeated_no_purge_tokens_are_all_consumed"),
    m("purge-not-best-effort",
      "        shutil.rmtree(p, ignore_errors=True)",
      "        shutil.rmtree(p)",
      "TestPurge::test_purge_is_best_effort_on_undeletable_dirs"),
    m("no-purge-flag-ignored",
      "        args.pop(0)\n        purge = False",
      "        args.pop(0)\n        purge = True",
      "TestPurge::test_no_purge_flag_skips_purge_and_is_not_passed_to_pytest"),
    m("no-purge-leaks-to-pytest",
      "        args.pop(0)\n        purge = False",
      "        purge = False\n        break",
      "TestPurge::test_no_purge_flag_skips_purge_and_is_not_passed_to_pytest"),
    m("venv-exclusion-dropped",
      '        if ".venv" in p.parts:\n            continue',
      "        if False:\n            continue",
      "TestPurge::test_purge_helper_spares_the_venv_tree"),
    # --- child process ---
    m("venv-python-preference-dropped",
      "    return str(venv) if venv.is_file() else sys.executable",
      "    return sys.executable",
      "TestChildProcess::test_child_python_prefers_the_engine_venv"),
    m("cwd-pin-dropped",
      "        rc = subprocess.run(cmd, cwd=ENGINE_ROOT, env=_child_env()).returncode",
      "        rc = subprocess.run(cmd, env=_child_env()).returncode",
      "TestChildProcess::test_child_runs_from_engine_root"),
    m("engine-root-mis-derived",
      "ENGINE_ROOT = Path(__file__).resolve().parent.parent",
      "ENGINE_ROOT = Path(__file__).resolve().parent",
      "TestChildProcess::test_child_runs_from_engine_root"),
    m("interrupt-code-swapped",
      "    except KeyboardInterrupt:\n        return 130",
      "    except KeyboardInterrupt:\n        return 1",
      "TestChildProcess::test_sigint_returns_130"),
]
