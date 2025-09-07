from __future__ import annotations

from mcp_rules_assistant import nl


def test_more_nl_synonyms() -> None:
    assert nl.parse("追加记忆") == "memory.append_turn"
    assert nl.parse("建议下一步") == "plan.suggest_next"
    assert nl.parse("项目关联") == "project.link"
