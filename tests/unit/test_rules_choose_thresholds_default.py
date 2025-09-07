from __future__ import annotations

from mcp_rules_assistant.rules import Complexity, Scenario, choose_thresholds


def test_choose_thresholds_default_fallback() -> None:
    th = choose_thresholds(Scenario.PERSONAL, Complexity.MEDIUM)
    assert (
        int(th.coverage_min_module * 100) == 90
        and int(th.coverage_min_core * 100) == 95
        and th.mutation_required is False
    )
