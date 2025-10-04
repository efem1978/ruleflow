from __future__ import annotations

import types
from pathlib import Path

from mcp_rules_assistant import dev_agent


def test_run_writes_cmd_events(monkeypatch, tmp_path: Path) -> None:
    agent = dev_agent.DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp" / "dashboard"

    # ensure dashboard dir exists via instance method
    def inst_ensure(rebuild: bool = False):  # type: ignore[no-untyped-def]
        dash.mkdir(parents=True, exist_ok=True)
        return dash

    monkeypatch.setattr(agent, "_ensure_dashboard_dir", inst_ensure)

    # monkeypatch run_cmd to emit events and succeed
    def fake_run_cmd(cmd, cwd=None, capture_stdout=False, check=False, env=None, on_event=None):  # type: ignore[no-untyped-def]
        if callable(on_event):
            on_event({"phase": "start", "cmd": cmd})
            on_event({"phase": "end", "cmd": cmd, "returncode": 0})
        P = types.SimpleNamespace(returncode=0, stdout="", stderr="")
        return P

    monkeypatch.setattr(dev_agent, "run_cmd", fake_run_cmd)

    # run one cycle with OK tests to exercise event persistence and jsonl append
    monkeypatch.setenv("DEV_AGENT_MAX_CYCLES", "1")
    monkeypatch.setattr(
        dev_agent, "_run_impacted_or_full", lambda *a, **k: {"ok": True, "mode": "full"},
    )
    monkeypatch.setattr(
        dev_agent,
        "compute_status",
        lambda *a, **k: {
            "plan": {"status": "in_progress", "current": "x", "next": "y"},
            "coverage": {
                "weak": [],
                "groups": [],
                "near": [],
                "min_module": 0.9,
                "count": 1,
                "progress": 1.0,
            },
            "progress": {
                "overall": 1.0,
                "coverage": 1.0,
                "plan": 1.0,
                "doc": 1.0,
                "prod": 1.0,
                "counts": {
                    "coverage_total": 1,
                    "coverage_weak": 0,
                    "plan_done": 1,
                    "plan_pending": 0,
                },
            },
            "tasks": {"pending": [], "done": []},
        },
    )
    agent.run(interval=1, max_cycles=1)
    assert (dash / "cmd_events.json").exists()
    # append once more to exercise jsonl append branch
    agent.run(interval=1, max_cycles=1)
    assert (dash / "cmd_events.jsonl").exists()
