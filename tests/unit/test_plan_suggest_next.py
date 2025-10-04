from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer
from mcp_rules_assistant.progress import write_plan


def test_plan_suggest_next_from_plan_and_summary(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # seed plan with next
    write_plan(
        "# 项目计划 / Project Plan\n\n- 状态: in_progress\n- 当前步骤: 编写代码\n- 下一步: 编写测试\n",
        tmp_path,
    )
    srv._call_tool(
        "memory.append_turn",
        {"role": "assistant", "content": "总结：完成A；下一步：增强覆盖率"},
    )
    out = srv._call_tool("plan.suggest_next", {})
    assert out.get("ok") is True
    sug = out.get("suggestions", {})
    assert any("测试" in s or "覆盖" in s for s in sug.get("next_steps", []))
    assert isinstance(sug.get("handoff_plan", ""), str) and sug.get("handoff_plan")
