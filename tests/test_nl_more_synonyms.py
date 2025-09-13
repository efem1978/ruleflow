from __future__ import annotations

from mcp_rules_assistant import nl


def test_more_nl_synonyms() -> None:
    assert nl.parse("追加记忆") == "memory.append_turn"
    assert nl.parse("建议下一步") == "plan.suggest_next"
    assert nl.parse("项目关联") == "project.link"
    # new aliases
    assert nl.parse("受控写入 多文件") == "fs.apply_patch"
    assert nl.parse("apply patch") == "fs.apply_patch"
    assert nl.parse("计划 更新") == "plan.set"
    assert nl.parse("plan update") == "plan.set"
    assert nl.parse("规则 摘要") == "rules.maxima"
    assert nl.parse("rules summary") == "rules.maxima"
