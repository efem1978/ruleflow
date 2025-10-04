from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.process import run_cmd


def test_events_guard_when_mcp_dir_is_file(monkeypatch, tmp_path: Path) -> None:
    # Create a file named .mcp so that creating .mcp/dashboard fails
    (tmp_path / ".mcp").write_text("x", encoding="utf-8")
    monkeypatch.setenv("MCP_RUN_CMD_EVENTS", "1")
    # Should not raise even if event logging fails internally
    p = run_cmd(["python3", "-c", "print('ok')"], cwd=tmp_path, capture_stdout=True)
    assert getattr(p, "returncode", 1) == 0
