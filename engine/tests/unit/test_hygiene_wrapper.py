"""tools/test.py — the hygiene pytest wrapper (issue #42).

The wrapper's whole job is invariants: env pin, flag pins, purge, verbatim
passthrough, exit-code fidelity. Each test here names one; the mutation hunt
pins each to a named mutant.
"""
import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

ENGINE_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ENGINE_ROOT / "tools" / "test.py"

PASS_FAIL = (
    "def test_alpha():\n    assert True\n"
    "def test_beta():\n    assert False\n"
)
OK = "def test_ok():\n    assert True\n"
# Discriminating probe: red unless the child interpreter has the env pin.
ENV_PROBE = "import sys\ndef test_probe():\n    assert sys.dont_write_bytecode\n"


def _load():
    spec = importlib.util.spec_from_file_location("engine_hygiene_wrapper", WRAPPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def wrapper():
    return _load()


def _write(tmp_path: Path, name: str, body: str) -> Path:
    f = tmp_path / name
    f.write_text(body)
    return f


def _seed_probe_pycache(base: Path) -> Path:
    # The probe lives in the REAL engine tree (that is what the purge sweeps),
    # so these tests assume a single sequential suite run per checkout — a
    # concurrent run's purge would race the seed/assert window.
    if base.exists():
        os.chmod(base, 0o700)  # heal a chmod-locked leftover from a killed run
    pyc = base / "__pycache__"
    pyc.mkdir(parents=True, exist_ok=True)
    (pyc / "sentinel.pyc").write_bytes(b"stale")
    return pyc


def _control_env() -> dict:
    # Plain-pytest controls must not inherit the very vars the wrapper guards
    # against, or a developer's shell env can turn a control red.
    drop = {"PYTHONDONTWRITEBYTECODE", "PYTEST_ADDOPTS", "PYTHONPYCACHEPREFIX"}
    return {k: v for k, v in os.environ.items() if k not in drop}


class TestPassthrough:
    def test_k_expression_reaches_pytest_verbatim(self, wrapper, tmp_path):
        # The expression contains spaces: if the wrapper re-splits or mangles
        # tokens, pytest sees stray args (rc 4); if it drops -k, beta runs (rc 1).
        f = _write(tmp_path, "test_kexpr.py", PASS_FAIL)
        assert wrapper.main([str(f), "-k", "alpha and not beta"]) == 0

    def test_red_suite_exit_code_propagates(self, wrapper, tmp_path):
        f = _write(tmp_path, "test_red.py", PASS_FAIL)
        assert wrapper.main([str(f)]) == 1

    def test_exit_code_passes_through_verbatim_not_boolean(self, wrapper, tmp_path):
        # pytest exits 5 when nothing is collected; a bool-ified rc would be 1.
        empty = tmp_path / "empty"
        empty.mkdir()
        assert wrapper.main([str(empty)]) == 5

class TestHygienePins:
    def test_child_env_pins_dont_write_bytecode(self, wrapper, tmp_path):
        f = _write(tmp_path, "test_envprobe.py", ENV_PROBE)
        with mock.patch.dict(os.environ):
            os.environ.pop("PYTHONDONTWRITEBYTECODE", None)
            assert wrapper.main([str(f)]) == 0

    def test_child_env_inherits_the_parent(self, wrapper, tmp_path):
        # Passthrough is env-wide, not just argv: API keys and the like must
        # reach the child alongside the pin (minus the stripped side doors,
        # PYTEST_ADDOPTS and PYTHONPYCACHEPREFIX — see the tests below).
        f = _write(
            tmp_path, "test_inherit.py",
            "import os\ndef test_inherit():\n"
            "    assert os.environ.get('WRAPPER_ENV_PROBE') == '42'\n",
        )
        with mock.patch.dict(os.environ, {"WRAPPER_ENV_PROBE": "42"}):
            assert wrapper.main([str(f)]) == 0

    def test_env_probe_discriminates_without_the_wrapper(self, tmp_path):
        # Control: the same probe goes red under a plain pytest child with the
        # var stripped — so the green above is the wrapper's doing.
        f = _write(tmp_path, "test_envprobe.py", ENV_PROBE)
        rc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(f)],
            env=_control_env(), cwd=tmp_path, capture_output=True,
        ).returncode
        assert rc == 1

    def test_cacheprovider_disabled_leaves_no_pytest_cache(self, wrapper, tmp_path):
        # pytest.ini pins rootdir to tmp_path so the cache location is known.
        (tmp_path / "pytest.ini").write_text("[pytest]\n")
        f = _write(tmp_path, "test_red.py", PASS_FAIL)
        assert wrapper.main([str(f)]) == 1
        assert not (tmp_path / ".pytest_cache").exists()
        # Control: without the pin, the failing run writes the cache.
        rc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", str(f)],
            cwd=tmp_path, env=_control_env(), capture_output=True,
        ).returncode
        assert rc == 1
        assert (tmp_path / ".pytest_cache").exists()

    def test_quiet_flag_pinned(self, tmp_path):
        # -q suppresses the session header; "rootdir:" only prints without it.
        # Exercises the __main__ entry (subprocess) rather than main() in-process.
        f = _write(tmp_path, "test_ok.py", OK)
        out = subprocess.run(
            [sys.executable, str(WRAPPER), str(f)],
            capture_output=True, text=True,
        )
        assert out.returncode == 0
        assert "rootdir:" not in out.stdout
        plain = subprocess.run(
            [sys.executable, "-m", "pytest", str(f)],
            cwd=tmp_path, env=_control_env(), capture_output=True, text=True,
        )
        assert "rootdir:" in plain.stdout

    def test_pytest_addopts_cannot_defeat_the_pins(self, wrapper, tmp_path, capfd):
        # PYTEST_ADDOPTS prepends args that can neutralize the pinned flags
        # (-v cancels -q, -p cacheprovider re-enables the cache), so the
        # wrapper strips it; options belong in argv, which forwards verbatim.
        f = _write(tmp_path, "test_ok.py", OK)
        with mock.patch.dict(os.environ, {"PYTEST_ADDOPTS": "-v"}):
            assert wrapper.main([str(f)]) == 0
        assert "rootdir:" not in capfd.readouterr().out

    def test_pycacheprefix_cannot_smuggle_stale_bytecode(self, wrapper, tmp_path):
        # PYTHONPYCACHEPREFIX relocates bytecode caches outside the purge's
        # reach while PYTHONDONTWRITEBYTECODE only stops writes — together a
        # primed prefix cache serves pre-edit code after a same-size,
        # same-mtime rewrite. The wrapper must strip the prefix var.
        prefix = tmp_path / "prefix"
        mod = _write(tmp_path, "mod.py", 'VALUE = "AAAA"\n')
        _write(
            tmp_path, "test_import.py",
            "import mod\ndef test_import():\n    assert mod.VALUE == 'BBBB'\n",
        )
        prime_env = _control_env()
        prime_env["PYTHONPYCACHEPREFIX"] = str(prefix)
        # Prime with the wrapper's own child interpreter: a pyc only fools
        # the freshness check when its magic tag matches the reader.
        subprocess.run(
            [wrapper._child_python(ENGINE_ROOT), "-c", "import mod"],
            cwd=tmp_path, env=prime_env, capture_output=True, check=True,
        )
        assert list(prefix.rglob("*.pyc")), "priming the prefix cache failed"
        stat = mod.stat()
        mod.write_text('VALUE = "BBBB"\n')
        os.utime(mod, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        with mock.patch.dict(os.environ, {"PYTHONPYCACHEPREFIX": str(prefix)}):
            assert wrapper.main([str(tmp_path / "test_import.py")]) == 0


class TestPurge:
    def test_purge_removes_stale_pycache_by_default(self, wrapper, tmp_path):
        probe = ENGINE_ROOT / "tests" / "_purge_probe"
        pyc = _seed_probe_pycache(probe)
        try:
            # The child itself checks the probe is already gone DURING its
            # run: purging after the child would satisfy a post-run check
            # while the child still read stale bytecode.
            f = _write(
                tmp_path, "test_probe_gone.py",
                "import pathlib\ndef test_probe_gone():\n"
                f"    assert not pathlib.Path({str(pyc)!r}).exists()\n",
            )
            assert wrapper.main([str(f)]) == 0
            assert not pyc.exists()
        finally:
            shutil.rmtree(probe, ignore_errors=True)

    def test_repeated_no_purge_tokens_are_all_consumed(self, wrapper, tmp_path):
        probe = ENGINE_ROOT / "tests" / "_purge_probe"
        pyc = _seed_probe_pycache(probe)
        try:
            f = _write(tmp_path, "test_ok.py", OK)
            # rc 4 if the second token leaks to pytest.
            assert wrapper.main(["--no-purge", "--no-purge", str(f)]) == 0
            assert pyc.exists()
        finally:
            shutil.rmtree(probe, ignore_errors=True)

    def test_purge_is_best_effort_on_undeletable_dirs(self, wrapper, tmp_path):
        # A permission-blocked cache dir must not break the run.
        probe = ENGINE_ROOT / "tests" / "_purge_probe"
        pyc = _seed_probe_pycache(probe)
        os.chmod(probe, 0o500)  # rmdir of pyc needs write on its parent
        try:
            f = _write(tmp_path, "test_ok.py", OK)
            assert wrapper.main([str(f)]) == 0
            # best-effort, not silent-skip: the purge tried and hit the permission wall, so the
            # undeletable cache dir SURVIVES (0o500 keeps search rights, so exists() still resolves).
            assert pyc.exists()
        finally:
            os.chmod(probe, 0o700)
            shutil.rmtree(probe, ignore_errors=True)

    def test_no_purge_flag_skips_purge_and_is_not_passed_to_pytest(self, wrapper, tmp_path):
        probe = ENGINE_ROOT / "tests" / "_purge_probe"
        pyc = _seed_probe_pycache(probe)
        try:
            f = _write(tmp_path, "test_ok.py", OK)
            # rc 0 also proves the flag was consumed (pytest would exit 4 on it).
            assert wrapper.main(["--no-purge", str(f)]) == 0
            assert pyc.exists()
        finally:
            shutil.rmtree(probe, ignore_errors=True)

    def test_purge_helper_spares_the_venv_tree(self, wrapper, tmp_path):
        root = tmp_path / "root"
        keep = root / ".venv" / "lib" / "pkg" / "__pycache__"
        keep.mkdir(parents=True)
        kill = root / "src" / "pkg" / "__pycache__"
        kill.mkdir(parents=True)
        wrapper._purge_pycache(root)
        assert keep.exists()
        assert not kill.exists()


class TestChildProcess:
    def test_child_python_prefers_the_engine_venv(self, wrapper, tmp_path):
        fake = tmp_path / ".venv" / "bin" / "python"
        fake.parent.mkdir(parents=True)
        fake.write_text("")
        assert wrapper._child_python(tmp_path) == str(fake)
        bare = tmp_path / "bare"
        bare.mkdir()
        assert wrapper._child_python(bare) == sys.executable

    def test_child_runs_from_engine_root(self, wrapper, tmp_path, monkeypatch):
        # A root-relative path must resolve regardless of the caller's cwd
        # (rc 4 "file not found" if the child inherited the caller's cwd).
        monkeypatch.chdir(tmp_path)
        assert wrapper.main(["--co", "-q", "tests/unit/test_hygiene_wrapper.py"]) == 0

    def test_signal_killed_child_maps_to_128_plus_signal(self, wrapper, tmp_path):
        # subprocess reports a signal death as a negative returncode; passing
        # that to sys.exit() wraps mod 256 (SIGKILL -> 247). Callers expect
        # the shell convention 128+N (137).
        f = _write(
            tmp_path, "test_kill.py",
            "import os, signal\ndef test_kill():\n"
            "    os.kill(os.getpid(), signal.SIGKILL)\n",
        )
        assert wrapper.main([str(f)]) == 137

    def test_sigint_returns_130(self, tmp_path):
        started = tmp_path / "started"
        f = _write(
            tmp_path, "test_sleep.py",
            "import pathlib, time\n"
            "def test_sleep():\n"
            f"    pathlib.Path({str(started)!r}).write_text('x')\n"
            "    time.sleep(30)\n",
        )
        proc = subprocess.Popen(
            [sys.executable, str(WRAPPER), "--no-purge", str(f)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 20
            while not started.exists():
                assert time.monotonic() < deadline, "wrapped test never started"
                time.sleep(0.05)
            os.kill(proc.pid, signal.SIGINT)  # the wrapper only, not the group
            assert proc.wait(timeout=15) == 130
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
