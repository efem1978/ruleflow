from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.progress import (
    ensure_plan,
    parse_plan,
    read_plan,
    update_plan_fields,
    write_plan,
)


def test_ensure_read_write_and_parse(tmp_path: Path) -> None:
    p = ensure_plan(tmp_path)
    assert p.exists()
    text = read_plan(tmp_path)
    assert "项目计划" in text
    # update fields
    update_plan_fields(tmp_path, status="in_progress", current="X", nxt="Y")
    text2 = read_plan(tmp_path)
    st, cur, nxt = parse_plan(text2)
    assert st == "in_progress" and cur == "X" and nxt == "Y"
    # write raw text and parse again
    write_plan("- 状态: done\n- 当前步骤: A\n- 下一步: B\n", tmp_path)
    st3, cur3, nxt3 = parse_plan(read_plan(tmp_path))
    assert st3 == "done" and cur3 == "A" and nxt3 == "B"
