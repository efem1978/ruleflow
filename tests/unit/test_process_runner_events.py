from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import mcp_rules_assistant.process as proc


def test_run_cmd_on_event_success(monkeypatch, tmp_path: Path) -> None:
    class P:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = "ok"
            self.stderr = ""

    monkeypatch.setattr(proc.subprocess, "run", lambda *a, **k: P())
    events: list[dict[str, Any]] = []
    out = proc.run_cmd(
        ["echo", "ok"], cwd=tmp_path, on_event=lambda e: events.append(e),
    )
    assert out.returncode == 0
    phases = [e.get("phase") for e in events]
    assert "start" in phases and "end" in phases


def test_run_cmd_on_event_error_timeout_only(monkeypatch, tmp_path: Path) -> None:
    def boom(*a, **k):  # type: ignore[no-untyped-def]
        raise subprocess.TimeoutExpired(cmd="x", timeout=0.1)

    monkeypatch.setattr(proc.subprocess, "run", boom)
    events: list[dict[str, Any]] = []
    try:
        proc.run_cmd(
            ["sleep", "1"],
            cwd=tmp_path,
            on_event=lambda e: events.append(e),
            retries=0,
            retry_on_timeout_only=True,
        )
        assert False, "expected TimeoutExpired"
    except subprocess.TimeoutExpired:
        pass
    phases = [e.get("phase") for e in events]
    assert "start" in phases and "error" in phases
