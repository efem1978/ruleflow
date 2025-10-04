from __future__ import annotations

from mcp_rules_assistant import nl


def test_nl_synonyms_to_tools() -> None:
    assert nl.parse("生成CI") == "ci.generate"
    assert nl.parse("校验 ci") == "ci.validate"
    assert nl.parse("开启滚动记忆") == "memory.toggle_auto"
    assert nl.parse("摄取规则") == "rules.ingest"
    assert nl.parse("近阈值") == "coverage.near"
    assert nl.parse("prepare environment") == "env.prepare"
