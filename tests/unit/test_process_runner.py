from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.process as proc


def test_run_cmd_trims_outputs(monkeypatch, tmp_path: Path) -> None:
    class P:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = "x" * 12000
            self.stderr = "y" * 12000

    calls = {}

    def fake_run(cmd, cwd=None, check=False, **kwargs):  # type: ignore[no-untyped-def]
        calls["kwargs"] = kwargs
        return P()

    monkeypatch.setattr(proc.subprocess, "run", fake_run)
    out = proc.run_cmd(["echo", "ok"], cwd=tmp_path, capture_stdout=True)
    assert out.returncode == 0
    assert isinstance(out.stdout, str) and len(out.stdout) <= 8000
    assert isinstance(out.stderr, str) and len(out.stderr) <= 8000
    # when capture_stdout=True, stderr should be captured
    assert "stderr" in calls.get("kwargs", {})


def test_run_cmd_minimal_kwargs_when_no_capture(monkeypatch, tmp_path: Path) -> None:
    recorded = {}

    def fake_run(cmd, cwd=None, check=False, **kwargs):  # type: ignore[no-untyped-def]
        recorded["cwd"] = cwd
        recorded["check"] = check
        recorded["kwargs"] = kwargs

        class P:
            returncode = 0

        return P()

    monkeypatch.setattr(proc.subprocess, "run", fake_run)
    out = proc.run_cmd(["true"], cwd=tmp_path, capture_stdout=False)
    assert out.returncode == 0
    # ensure we did not pass extra kwargs like timeout/text/stdout
    assert recorded["kwargs"] == {}
