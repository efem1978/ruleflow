from __future__ import annotations

from mcp_rules_assistant.config import get_coverage_policy


def test_get_coverage_policy_returns_none_when_non_dict() -> None:
    cfg = {"coverage": 123}  # 非 dict，走兜底 None 分支
    assert get_coverage_policy(cfg) is None
