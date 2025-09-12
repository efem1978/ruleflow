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


def test_run_cmd_events_trim(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_RUN_CMD_EVENTS", "1")
    out_dir = tmp_path / ".mcp" / "dashboard"
    out_dir.mkdir(parents=True, exist_ok=True)
    jl = out_dir / "cmd_events.jsonl"
    # pre-fill > 200 lines
    jl.write_text(
        "\n".join('{"phase":"end"}' for _ in range(205)) + "\n", encoding="utf-8"
    )
    run_cmd([sys.executable, "-c", "print('ok')"], cwd=tmp_path)
    # ensure file trims to <= 200 lines
    lines = jl.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 200


def test_run_cmd_minimal_kwargs_path(tmp_path: Path) -> None:
    # when capture_stdout=False and env=None and timeout=None, use minimal subprocess.run path
    p = run_cmd(
        [sys.executable, "-c", "print('x')"],
        cwd=tmp_path,
        capture_stdout=False,
        env=None,
        timeout=None,
    )
    assert p.returncode == 0
