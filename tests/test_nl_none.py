from __future__ import annotations

from mcp_rules_assistant import nl


def test_nl_parse_none_for_unrelated_text() -> None:
    assert nl.parse("no matching command here") is None
