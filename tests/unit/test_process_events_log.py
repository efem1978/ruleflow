from __future__ import annotations

import os
import sys
from pathlib import Path

from mcp_rules_assistant.process import run_cmd


def test_run_cmd_events_written(tmp_path: Path, monkeypatch) -> None:
    # enable event logging to .mcp/dashboard/cmd_events.jsonl
    monkeypatch.setenv("MCP_RUN_CMD_EVENTS", "1")
    # simple success command
    p = run_cmd([sys.executable, "-c", "print('ok')"], cwd=tmp_path)
    assert p.returncode == 0
    jl = tmp_path / ".mcp" / "dashboard" / "cmd_events.jsonl"
    assert jl.exists()
    content = jl.read_text(encoding="utf-8")
    assert '"phase": "start"' in content
    assert '"phase": "end"' in content


def test_run_cmd_error_event(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_RUN_CMD_EVENTS", "1")
    # a failing command with check=True triggers error path
    try:
        run_cmd(
            [sys.executable, "-c", "import sys; sys.exit(1)"], cwd=tmp_path, check=True
        )
        assert False, "expected CalledProcessError"
    except Exception:
        pass
    jl = tmp_path / ".mcp" / "dashboard" / "cmd_events.jsonl"
    assert jl.exists()
    content = jl.read_text(encoding="utf-8")
    assert '"phase": "error"' in content
