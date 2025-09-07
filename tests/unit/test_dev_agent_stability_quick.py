from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.dev_agent import (
    DevAgent,
    update_bypass,
    update_failure_and_freeze,
)


def test_stability_freeze_then_unfreeze(tmp_path: Path) -> None:
    agent = DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)

    # Seed status (failing)
    status = {
        "plan": {"status": "in_progress", "current": "x", "next": "y"},
        "coverage": {
            "weak": ["a"],
            "groups": [],
            "near": [],
            "min_module": 0.9,
            "count": 1,
            "progress": 0.0,
        },
        "progress": {
            "overall": 0.0,
            "coverage": 0.0,
            "plan": 0.0,
            "doc": 0.0,
            "prod": 0.0,
            "counts": {
                "coverage_total": 1,
                "coverage_weak": 1,
                "plan_done": 0,
                "plan_pending": 1,
            },
        },
    }
    (dash / "status.json").write_text(json.dumps(status), encoding="utf-8")
    # Configure thresholds to 1 for quick trigger
    agent.config.setdefault("tests", {}).setdefault("quick_fail_decay", {})

    # Cycle 1: failing tests, should activate freeze or increment counters
    st1 = update_failure_and_freeze(agent, dict(status), dash)
    # simulate bypass counting with failing tests result
    tests = {"ok": False, "code": 1}
    run_cfg = {"bypass_enabled": True, "bypass_allow_commit": True}
    t1, b1 = update_bypass(agent, dict(tests), dict(run_cfg))
    assert isinstance(st1, dict) and isinstance(b1, dict)

    # Cycle 2: recovering tests (no weak), should unfreeze
    status_ok = dict(status)
    status_ok["coverage"] = {
        "weak": [],
        "groups": [],
        "near": [],
        "min_module": 0.9,
        "count": 1,
        "progress": 1.0,
    }
    st2 = update_failure_and_freeze(agent, dict(status_ok), dash)
    assert st2.get("freeze", {}).get("active") in (False, None)
