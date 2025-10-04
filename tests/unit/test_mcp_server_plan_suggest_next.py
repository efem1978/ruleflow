from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer
from mcp_rules_assistant.progress import write_plan


def test_plan_suggest_next_fallback_to_current(tmp_path: Path) -> None:
    # Prepare plan with status and current but no explicit next
    plan = (
        "# 项目计划 / Project Plan\n\n"
        "- 状态: in_progress\n"
        "- 当前步骤: 修复A\n"
        "- 下一步: \n"
    )
    write_plan(plan, project_root=tmp_path)
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # rebind helpers for the new root
    from mcp_rules_assistant.config import load_config
    from mcp_rules_assistant.fs_wrapper import FSGuard
    from mcp_rules_assistant.memory import MemoryManager

    srv.mm = MemoryManager(tmp_path)
    srv.fs = FSGuard(tmp_path)
    srv.cfg = load_config(tmp_path)

    out = srv._tool_plan_suggest_next()
    assert out.get("ok") is True
    sugg = (out.get("suggestions") or {}).get("handoff_plan", "")
    assert "继续：修复A" in sugg
