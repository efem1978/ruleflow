from __future__ import annotations

import subprocess
from pathlib import Path

from mcp_rules_assistant.process import DEFAULT_TIMEOUT, run_cmd


def test_run_cmd_logging_and_nocapture(tmp_path: Path, monkeypatch) -> None:
    # logging path (start/end logger.info) with capture
    p = run_cmd(["bash", "-lc", "echo hi"], cwd=tmp_path, capture_stdout=True, log=True)
    assert p.returncode == 0
    # no-capture branch (no pipes)
    p2 = run_cmd(
        ["bash", "-lc", "true"],
        cwd=tmp_path,
        capture_stdout=False,
        env=None,
        timeout=DEFAULT_TIMEOUT,
    )
    assert p2.returncode == 0


def test_run_cmd_retry_on_timeout(monkeypatch, tmp_path: Path) -> None:
    calls = {"n": 0}

    class _Timeout(subprocess.TimeoutExpired):
        def __init__(self):
            super().__init__(cmd=["bash"], timeout=0.01)

    def fake_run(cmd, cwd=None, check=False, **kwargs):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:
            raise _Timeout()

        class P:  # minimal proc
            returncode = 0
            stdout = "ok"
            stderr = ""

        return P()

    monkeypatch.setattr(subprocess, "run", fake_run)
    p = run_cmd(
        ["bash", "-lc", "echo after"],
        cwd=tmp_path,
        retries=1,
        retry_on_timeout_only=True,
        capture_stdout=True,
        log=True,
    )
    assert getattr(p, "returncode", 1) == 0 and calls["n"] == 2
