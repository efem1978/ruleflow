from __future__ import annotations

from pathlib import Path

import pytest

from mcp_rules_assistant.dev_agent import DevAgent, update_failure_and_freeze


def test_freeze_activate_and_recover(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)

    agent = DevAgent(project_root=tmp_path)

    # Set low thresholds to trigger quickly
    monkeypatch.setenv("DEV_AGENT_THR_TESTS", "1")
    monkeypatch.setenv("DEV_AGENT_THR_BUILD", "1")
    monkeypatch.setenv("DEV_AGENT_THR_SEVERE", "1")

    # Start with a failing status to accumulate counters
    status = {
        "tests": {"ok": False, "code": 2, "mode": "full"},
        "checks": {"lint": "ok", "type": "ok", "tdd": "skipped"},
        "coverage": {"weak": ["a"], "count": 1},
        "progress": {"overall": 0.0},
    }

    # First update: should trip thresholds and enter freeze
    status = update_failure_and_freeze(agent, status, dash)
    assert isinstance(status, dict)
    assert status.get("freeze", {}).get("active") is True

    # While frozen and after a passing cycle, with no weak coverage and lint/type ok, should recover
    status_pass = {
        "tests": {"ok": True, "code": 0, "mode": "full"},
        "checks": {"lint": "ok", "type": "ok", "tdd": "skipped"},
        "coverage": {"weak": [], "count": 1},
        "progress": {"overall": 0.0},
    }
    status_pass = update_failure_and_freeze(agent, status_pass, dash)
    assert isinstance(status_pass, dict)
    assert status_pass.get("freeze", {}).get("active") is False
