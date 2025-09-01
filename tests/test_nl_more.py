from __future__ import annotations

from mcp_rules_assistant import nl


def test_more_nl_synonyms() -> None:
    assert nl.parse('应用门禁') == 'rules.enforce'
    assert nl.parse('enforce rules') == 'rules.enforce'
    assert nl.parse('apply gates') == 'rules.enforce'

