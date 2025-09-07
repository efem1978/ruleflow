from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from mcp_rules_assistant.dev_agent import DevAgent


def _run_cmd_stub(*args, **kwargs):  # type: ignore[no-redef]
    # 模拟当传入 on_event 参数时触发 TypeError，从而走 fallback 分支
    if "on_event" in kwargs:
        raise TypeError("stub does not accept on_event")
    # 返回一个具备 returncode/stdout/stderr 属性的对象
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def test_typeerror_fallbacks_in_helpers(monkeypatch, tmp_path: Path) -> None:
    agent = DevAgent(project_root=tmp_path)
    monkeypatch.setattr("mcp_rules_assistant.dev_agent.run_cmd", _run_cmd_stub)

    # _run_tests_with_coverage 走 TypeError fallback
    out = agent._run_tests_with_coverage(on_event=lambda e: None)
    assert out["ok"] is True

    # _git_changed_files 走 TypeError fallback
    files = agent._git_changed_files(on_event=lambda e: None)
    assert isinstance(files, list)

    # _run_quick_status_check 走 TypeError fallback
    stat = agent._run_quick_status_check(["echo", "hi"], on_event=lambda e: None)
    assert stat in ("ok", "fail", "skipped")
