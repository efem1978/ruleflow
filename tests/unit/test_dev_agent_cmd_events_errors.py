from __future__ import annotations

import types
from pathlib import Path

from mcp_rules_assistant import dev_agent


def _monkey_status_ok(monkeypatch):
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


def _monkey_run_ok(monkeypatch):
    monkeypatch.setattr(
        dev_agent, "_run_impacted_or_full", lambda *a, **k: {"ok": True, "mode": "full"},
    )

    def fake_run_cmd(cmd, cwd=None, capture_stdout=False, check=False, env=None, on_event=None):  # type: ignore[no-untyped-def]
        if callable(on_event):
            on_event({"phase": "start", "cmd": cmd})
            on_event({"phase": "end", "cmd": cmd, "returncode": 0})
        P = types.SimpleNamespace(returncode=0, stdout="", stderr="")
        return P

    monkeypatch.setattr(dev_agent, "run_cmd", fake_run_cmd)


def test_cmd_events_invalid_json_recovers(monkeypatch, tmp_path: Path) -> None:
    agent = dev_agent.DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp" / "dashboard"

    def inst_ensure(rebuild: bool = False):  # type: ignore[no-untyped-def]
        dash.mkdir(parents=True, exist_ok=True)
        return dash

    monkeypatch.setattr(agent, "_ensure_dashboard_dir", inst_ensure)
    _monkey_run_ok(monkeypatch)
    _monkey_status_ok(monkeypatch)

    # Pre-create invalid JSON to trigger ValueError path
    dash.mkdir(parents=True, exist_ok=True)
    (dash / "cmd_events.json").write_text("{invalid", encoding="utf-8")

    monkeypatch.setenv("DEV_AGENT_MAX_CYCLES", "1")
    agent.run(interval=1, max_cycles=1)
    # Should have recovered by ignoring invalid previous JSON
    import json as _json

    data = _json.loads((dash / "cmd_events.json").read_text(encoding="utf-8"))
    assert isinstance(data, list)


def test_cmd_events_jsonl_write_error_is_soft(monkeypatch, tmp_path: Path) -> None:
    agent = dev_agent.DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp" / "dashboard"

    def inst_ensure(rebuild: bool = False):  # type: ignore[no-untyped-def]
        dash.mkdir(parents=True, exist_ok=True)
        return dash

    monkeypatch.setattr(agent, "_ensure_dashboard_dir", inst_ensure)
    _monkey_run_ok(monkeypatch)
    _monkey_status_ok(monkeypatch)

    # Monkeypatch Path.open to raise for cmd_events.jsonl append
    import pathlib as _p

    _orig_open = _p.Path.open

    def _fake_open(self, *a, **k):  # type: ignore[no-untyped-def]
        if str(self).endswith("cmd_events.jsonl"):
            raise OSError("simulated append failure")
        return _orig_open(self, *a, **k)

    monkeypatch.setattr(_p.Path, "open", _fake_open)
    monkeypatch.setenv("DEV_AGENT_MAX_CYCLES", "1")
    agent.run(interval=1, max_cycles=1)
    # Should not raise; json file still present
    assert (dash / "cmd_events.json").exists()
