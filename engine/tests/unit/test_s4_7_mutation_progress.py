"""Operator-liveness contracts for the S4.7 mutation evidence wrapper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


TOOL_PATH = Path(__file__).resolve().parents[2] / "tools/s4_7_hunt_manifest.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("s4_7_hunt_manifest", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_runner_output_is_forwarded_and_captured_bit_for_bit(capsys):
    tool = _load_tool()
    command = [
        sys.executable,
        "-c",
        (
            "import sys; "
            "print('mutation-progress', file=sys.stderr, flush=True); "
            "print('mutation-result', flush=True)"
        ),
    ]

    result = tool._run_live(command)

    assert result["rc"] == 0
    assert result["argv"] == command
    assert result["output"] == "mutation-progress\nmutation-result\n"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == result["output"]


def test_mutation_manifest_heartbeat_default_is_five_seconds():
    tool = _load_tool()

    assert tool.MUTATION_HEARTBEAT_INTERVAL_SECONDS == 5.0


def test_manifest_interrupt_exits_130_without_wrapper_traceback(
    monkeypatch, capsys, tmp_path
):
    tool = _load_tool()

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(tool, "_run_live", interrupt)
    rc = tool.main(["--artifact", str(tmp_path / "manifest.json")])

    assert rc == 130
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "interrupted after runner restoration" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_manifest_rejects_nonpositive_or_nonfinite_heartbeat(value, tmp_path):
    tool = _load_tool()

    with pytest.raises(ValueError, match="positive finite"):
        tool.main(
            [
                "--artifact",
                str(tmp_path / "manifest.json"),
                "--heartbeat-interval",
                value,
            ]
        )
