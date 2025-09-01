from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.memory import MemoryManager
from mcp_rules_assistant.progress import ensure_plan, read_plan, write_plan, parse_plan, update_plan_fields


def test_memory_manager_window_and_summary(tmp_path: Path) -> None:
    mm = MemoryManager(project_root=tmp_path, window=3)
    mm.append_turn("user", "请给出计划和下一步", {})
    mm.append_turn("assistant", "计划：A\n下一步：B", {})
    mm.append_turn("user", "无关内容", {})
    mm.append_turn("assistant", "总结：完成", {})
    snap = mm.snapshot()
    # keep only last 3 turns
    assert len(snap.get("turns", [])) == 3
    # summary should extract recent Q/A lines with keywords
    summary = snap.get("summary", "")
    assert "Q: 无关内容" in summary
    assert "A: 总结" in summary or "总结" in summary
    assert "A: 计划" in summary or "计划" in summary
    # ensure memory file is created
    assert (tmp_path / ".mcp/memory.json").exists()


def test_progress_parse_and_update_fields(tmp_path: Path) -> None:
    # ensure default plan exists
    p = ensure_plan(tmp_path)
    assert p.exists()
    # parse defaults
    status, cur, nxt = parse_plan(read_plan(tmp_path))
    assert status == "planned" and isinstance(cur, str) and isinstance(nxt, str)
    # write english keys and parse
    text = (
        "# 项目计划 / Project Plan\n\n"
        "- status: in_progress\n"
        "- current step: implement feature\n"
        "- next: write tests\n"
    )
    write_plan(text, tmp_path)
    s2, c2, n2 = parse_plan(read_plan(tmp_path))
    assert s2 == "in_progress" and c2 == "implement feature" and n2 == "write tests"
    # update fields (append if missing) and ensure trailing newline
    update_plan_fields(tmp_path, status="done", current="refactor", nxt="release")
    new_text = read_plan(tmp_path)
    assert "- 状态: done" in new_text
    assert "- 当前步骤: refactor" in new_text
    assert "- 下一步: release" in new_text
    assert new_text.endswith("\n")
