from __future__ import annotations

import os
from pathlib import Path

from mcp_rules_assistant.dev_agent import DevAgent


class WeirdCoverage:
    def get(self, *_a, **_k):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")


def test_dev_agent_freeze_activate_and_recover(tmp_path: Path, monkeypatch) -> None:
    agent = DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp/dashboard"
    dash.mkdir(parents=True, exist_ok=True)

    # 1) Activate freeze via tests failure reaching threshold
    os.environ["DEV_AGENT_THR_TESTS"] = "1"
    status = {
        "checks": {"lint": "ok", "type": "ok", "tests": "fail", "tdd": "ok"},
        "tests": {"ok": False, "code": 1, "mode": "full"},
        "error": False,
        "progress": {"overall": 0.1, "progress": 0.1},
        "timestamp": 0,
        "coverage": {"weak": ["x"]},
    }
    agent._update_failure_and_freeze_status(status, dash)
    assert status.get("freeze", {}).get("active") is True
    assert status.get("freeze", {}).get("reason") == "threshold_reached"

    # 2) Recover when tests ok, lint ok/type ok, and weak_count==0
    status2 = {
        "checks": {"lint": "ok", "type": "ok", "tests": "ok", "tdd": "ok"},
        "tests": {"ok": True, "code": 0, "mode": "full"},
        "error": False,
        # Force _weak_count_now except path (returns 0) by using object with broken get()
        "coverage": WeirdCoverage(),
        "progress": {"overall": 0.3, "progress": 0.3},
        "timestamp": 0,
    }
    agent._update_failure_and_freeze_status(status2, dash)
    assert status2.get("freeze", {}).get("active") is False
    assert status2.get("freeze", {}).get("reason") == "recovered"
