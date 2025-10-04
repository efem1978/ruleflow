from __future__ import annotations

import subprocess
from pathlib import Path

from mcp_rules_assistant.process import run_cmd


class _Ok:
    def __init__(self) -> None:
        self.returncode = 0
        self.stdout = "ok"
        self.stderr = ""


def test_run_cmd_retry_on_timeout(monkeypatch, tmp_path: Path) -> None:
    calls = {"n": 0}

    def fake_run(cmd, cwd=None, check=False, **kwargs):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:
            raise subprocess.TimeoutExpired(cmd, timeout=0.01)
        return _Ok()

    monkeypatch.setattr(subprocess, "run", fake_run)
    p = run_cmd(
        ["echo", "ok"],
        cwd=tmp_path,
        retries=1,
        retry_on_timeout_only=True,
    )
    assert getattr(p, "returncode", 1) == 0
    assert calls["n"] == 2
