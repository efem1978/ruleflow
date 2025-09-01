from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple


class Scenario(str, Enum):
    PERSONAL = "personal"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    INSTITUTION = "institution"


class Complexity(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class DevMode(str, Enum):
    TDD = "tdd"
    BDD = "bdd"
    DOC = "doc"
    SPIKE = "spike"


@dataclass
class RuleThresholds:
    coverage_min_module: float
    coverage_min_core: float
    mutation_required: bool
    strict_no_skip: bool = True
    no_warnings: bool = True


def choose_thresholds(s: Scenario, c: Complexity) -> RuleThresholds:
    # 默认：最低级模块 >= 90%，核心 >= 95%
    if s == Scenario.PERSONAL and c == Complexity.SMALL:
        return RuleThresholds(0.90, 0.95, False)
    if s in {Scenario.PRO} and c in {Complexity.MEDIUM, Complexity.LARGE}:
        return RuleThresholds(0.92, 0.96, False)
    if s in {Scenario.ENTERPRISE, Scenario.INSTITUTION} and c in {Complexity.MEDIUM, Complexity.LARGE}:
        return RuleThresholds(0.95, 0.97, True)
    # 默认回退
    return RuleThresholds(0.90, 0.95, False)


def explain_thresholds(th: RuleThresholds) -> str:
    return (
        f"min_module={int(th.coverage_min_module*100)}%, "
        f"min_core={int(th.coverage_min_core*100)}%, "
        f"mutation_required={th.mutation_required}, no_skip={th.strict_no_skip}, no_warnings={th.no_warnings}"
    )

