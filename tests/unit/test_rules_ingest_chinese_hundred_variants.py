from __future__ import annotations

from mcp_rules_assistant.rules_ingest import _chinese_numeral_to_int


def test_chinese_hundred_variants() -> None:
    assert _chinese_numeral_to_int("一百") == 100
    assert _chinese_numeral_to_int("一百零五") == 105
