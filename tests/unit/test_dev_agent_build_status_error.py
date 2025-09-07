from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import dev_agent


def test_build_current_status_error_path(monkeypatch, tmp_path: Path) -> None:
    agent = dev_agent.DevAgent(project_root=tmp_path)
    # Force compute_status to raise to cover error assignment
    monkeypatch.setattr(
        agent,
        "compute_status",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    tests = {"ok": False}
    bypass = {"active": False}
    checks = {"lint": "ok", "type": "skipped", "tdd": "skipped"}
    st = agent._build_current_status(
        tests, bypass, checks, interval=1, cmd_error_count=0
    )
    assert isinstance(st, dict) and "error" in st
