from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

from mcp_rules_assistant.dev_agent import DevAgent
from mcp_rules_assistant.progress import write_plan


def _run_cmd_git_stub(args, cwd, capture_stdout=True, check=False, on_event=None, env=None):  # type: ignore[no-redef]
    # Simulate minimal git behavior
    if args[:3] == ["git", "status", "--porcelain"]:
        return SimpleNamespace(returncode=0, stdout=" M x.py\n", stderr="")
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def test_handle_auto_commit(monkeypatch, tmp_path: Path) -> None:
    agent = DevAgent(project_root=tmp_path)
    # Prepare plan
    write_plan(
        "- 状态: in_progress\n- 当前步骤: 单测\n- 下一步: 收尾\n",
        tmp_path,
    )
    monkeypatch.setattr("mcp_rules_assistant.dev_agent.run_cmd", _run_cmd_git_stub)
    tests = {"ok": True, "mode": "full", "code": 0}
    bypass = {"active": False}
    run_config = {
        "bypass_allow_commit": False,
        "auto_commit": True,
        "auto_push": False,
        "commit_interval": 0,
    }
    t0 = time.time() - 100
    ts = agent._handle_auto_commit(tests, bypass, run_config, t0)
    assert isinstance(ts, float) and ts >= t0
