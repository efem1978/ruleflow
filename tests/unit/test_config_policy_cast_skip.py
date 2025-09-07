from __future__ import annotations

from mcp_rules_assistant.config import get_coverage_policy


def test_get_coverage_policy_skips_non_numeric_values() -> None:
    cfg = {"coverage": {"policy": {"a": 0.9, "b": "NaN", "c": "text", "d": 1}}}
    pol = get_coverage_policy(cfg)
    # 'c' cannot be cast to float and should be skipped; 'b' (NaN) becomes a float NaN and is kept
    assert pol is not None and "a" in pol and "d" in pol and "c" not in pol
