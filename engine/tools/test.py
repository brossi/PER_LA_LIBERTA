#!/usr/bin/env python3
"""Hygiene pytest wrapper — the engine's one local test entry point (issue #42).

Pins the invariants that ad-hoc invocations kept dropping mid-hunt:

  * env   — the child runs with PYTHONDONTWRITEBYTECODE=1 (stale-bytecode guard);
  * flags — ``-q -p no:cacheprovider`` are always present;
  * purge — ``__pycache__`` under the engine root is removed before the run
    (``.venv`` excluded — its site-packages caches are legitimate and large);
    opt out with ``--no-purge``.

Everything else passes through to pytest verbatim (paths, -k, -x, markers),
and the child's exit code is the wrapper's (a signal death maps to the shell
convention 128+N; SIGINT exits 130). The child always runs from the engine
root, preferring the engine venv's python, so root-relative paths work from
any cwd.

Two env side doors around the pins are stripped from the child: PYTEST_ADDOPTS
(prepends args that can neutralize the pinned flags) and PYTHONPYCACHEPREFIX
(relocates bytecode caches outside the purge's reach). Pass options in argv.

    tools/test.py                          # full suite, hygiene pinned
    tools/test.py tests/unit -k handles    # narrowed, args verbatim
    tools/test.py --no-purge tests/unit/test_x.py -x
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
PINNED_FLAGS = ("-q", "-p", "no:cacheprovider")


def _child_python(root: Path) -> str:
    venv = root / ".venv" / "bin" / "python"
    return str(venv) if venv.is_file() else sys.executable


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("PYTHONPYCACHEPREFIX", None)
    return env


def _purge_pycache(root: Path) -> None:
    for p in root.rglob("__pycache__"):
        if ".venv" in p.parts:
            continue
        shutil.rmtree(p, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    purge = True
    while args and args[0] == "--no-purge":
        args.pop(0)
        purge = False
    if purge:
        _purge_pycache(ENGINE_ROOT)
    cmd = [_child_python(ENGINE_ROOT), "-m", "pytest", *PINNED_FLAGS, *args]
    try:
        rc = subprocess.run(cmd, cwd=ENGINE_ROOT, env=_child_env()).returncode
    except KeyboardInterrupt:
        return 130
    # subprocess reports a signal death as -N; sys.exit(-N) would wrap mod 256.
    return 128 - rc if rc < 0 else rc


if __name__ == "__main__":
    sys.exit(main())
