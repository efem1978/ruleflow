from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_rules_assistant.dev_agent import DevAgent, get_run_config, update_bypass


def test_bypass_activation_and_allow_commit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    # Prepare minimal project
    (tmp_path / ".mcp" / "dashboard").mkdir(parents=True, exist_ok=True)

    agent = DevAgent(project_root=tmp_path)

    # Configure bypass to trigger quickly and allow commit when bypassed
    monkeypatch.setenv("DEV_AGENT_BYPASS", "1")
    monkeypatch.setenv("DEV_AGENT_BYPASS_THRESHOLD", "2")
    monkeypatch.setenv("DEV_AGENT_BYPASS_COMMIT", "1")

    run_cfg = get_run_config(agent)

    # Simulate two consecutive identical failures (code 2)
    failing = {"ok": False, "code": 2, "stdout": "", "stderr": "boom"}

    tests, bypass = update_bypass(agent, dict(failing), dict(run_cfg))
    assert not tests.get("ok")
    assert not bypass.get("active")

    # Persist bypass state to file to simulate next cycle behavior
    bypass_file = run_cfg["bypass_state_file"]
    assert isinstance(bypass_file, Path)
    bypass_file.write_text(json.dumps(bypass), encoding="utf-8")

    tests, bypass = update_bypass(agent, dict(failing), dict(run_cfg))
    # After threshold, bypass should activate and tests treated as ok due to allow-commit
    assert bypass.get("active") is True
    assert tests.get("bypassed") is True
    assert tests.get("ok") is True
