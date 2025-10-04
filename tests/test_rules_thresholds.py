from __future__ import annotations

from mcp_rules_assistant.rules import (
    Complexity,
    Scenario,
    choose_thresholds,
    explain_thresholds,
)


def test_rules_choose_thresholds_and_explain() -> None:
    t1 = choose_thresholds(Scenario.PERSONAL, Complexity.SMALL)
    assert (
        abs(t1.coverage_min_module - 0.90) < 1e-9
        and abs(t1.coverage_min_core - 0.95) < 1e-9
    )
    assert t1.mutation_required is False
    assert "min_module=90%" in explain_thresholds(t1)

    t2 = choose_thresholds(Scenario.PRO, Complexity.MEDIUM)
    assert (
        abs(t2.coverage_min_module - 0.92) < 1e-9
        and abs(t2.coverage_min_core - 0.96) < 1e-9
    )
    assert t2.mutation_required is False

    t3 = choose_thresholds(Scenario.ENTERPRISE, Complexity.LARGE)
    assert (
        abs(t3.coverage_min_module - 0.95) < 1e-9
        and abs(t3.coverage_min_core - 0.97) < 1e-9
    )
    assert t3.mutation_required is True
