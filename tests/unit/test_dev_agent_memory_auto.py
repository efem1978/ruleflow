from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.dev_agent import DevAgent


def _mk_status() -> dict:
    return {
        "plan": {"status": "in_progress", "current": "X"},
        "coverage": {"weak": []},
        "progress": {"overall": 0.75},
        "timestamp": 0.0,
    }


def test_dev_agent_auto_memory_rate_limited(tmp_path: Path, monkeypatch) -> None:
    agent = DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp/dashboard"
    dash.mkdir(parents=True, exist_ok=True)

    # enable auto memory with very high min interval to test rate-limit
    monkeypatch.setenv("DEV_AGENT_MEM_ENABLE", "1")
    monkeypatch.setenv("DEV_AGENT_MEM_MIN_SEC", "9999")
    monkeypatch.setenv("DEV_AGENT_MEM_MAX_TURNS", "5")

    s = _mk_status()
    # first append should succeed
    ok1 = agent._auto_append_memory(s, dash)  # type: ignore[attr-defined]
    assert ok1 is True
    mem = tmp_path / ".mcp/memory.json"
    data = json.loads(mem.read_text(encoding="utf-8"))
    assert isinstance(data.get("turns"), list) and len(data.get("turns")) == 1

    # second append should be rate-limited and not add a new turn
    ok2 = agent._auto_append_memory(s, dash)  # type: ignore[attr-defined]
    assert ok2 is False
    data2 = json.loads(mem.read_text(encoding="utf-8"))
    assert len(data2.get("turns")) == 1
