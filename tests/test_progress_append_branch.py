from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.progress import write_plan, update_plan_fields, read_plan


def test_update_plan_appends_when_missing_fields(tmp_path: Path) -> None:
    # write a minimal plan without 当前步骤/下一步 lines
    text = "# 计划\n- 状态: planned\n"
    write_plan(text, tmp_path)
    update_plan_fields(tmp_path, current="实现功能X", nxt="发布v1")
    out = read_plan(tmp_path)
    assert "- 当前步骤: 实现功能X" in out
    assert "- 下一步: 发布v1" in out

