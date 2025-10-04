from __future__ import annotations

import json
import time
import types
from pathlib import Path

from mcp_rules_assistant.dev_agent import DevAgent


def test_dev_agent_run_once_minimal(tmp_path: Path, monkeypatch) -> None:
    a = DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp/dashboard"
    dash.mkdir(parents=True, exist_ok=True)

    # stub methods to avoid heavy operations
    monkeypatch.setattr(
        a,
        "_ensure_dashboard_dir",
        types.MethodType(lambda self, rebuild=False: dash, a),
    )
    monkeypatch.setattr(
        a,
        "_run_impacted_or_full",
        types.MethodType(
            lambda self, cycle_idx, full_every=5, on_event=None: {
                "ok": True,
                "code": 0,
                "stdout": "",
                "stderr": "",
                "mode": "full",
            },
            a,
        ),
    )
    monkeypatch.setattr(
        a,
        "_run_cycle_checks",
        types.MethodType(
            lambda self, on_event=None: {"lint": "ok", "type": "ok", "tests": "ok"}, a,
        ),
    )
    monkeypatch.setattr(
        a,
        "_update_bypass_status",
        types.MethodType(lambda self, tests, run_config: (tests, {"active": False}), a),
    )

    def _fake_build(self, tests, bypass, checks, interval, cmd_error_count=0):
        return {
            "plan": {"status": "in_progress", "current": "X"},
            "coverage": {"weak": []},
            "progress": {"overall": 0.6},
            "timestamp": time.time(),
            "checks": checks,
        }

    monkeypatch.setattr(a, "_build_current_status", types.MethodType(_fake_build, a))
    monkeypatch.setattr(
        a,
        "_update_failure_and_freeze_status",
        types.MethodType(lambda self, status, dash: None, a),
    )
    monkeypatch.setattr(
        a,
        "_persist_status_and_history",
        types.MethodType(
            lambda self, status, dash, t0: dash.joinpath("status.json").write_text(
                json.dumps(status), encoding="utf-8",
            ),
            a,
        ),
    )
    monkeypatch.setattr(
        a,
        "_handle_auto_commit",
        types.MethodType(
            lambda self, tests, bypass, run_config, last_ts, on_event=None: time.time(),
            a,
        ),
    )
    monkeypatch.setattr(
        a,
        "_handle_auto_tag",
        types.MethodType(
            lambda self, tests, status, run_config, last, on_event=None: last, a,
        ),
    )
    monkeypatch.setattr(
        a, "_auto_append_memory", types.MethodType(lambda self, status, dash: True, a),
    )

    a.run(interval=1, max_cycles=1)
    assert (dash / "status.json").exists()
