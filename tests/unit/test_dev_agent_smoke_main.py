from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import dev_agent


def test_main_one_cycle(monkeypatch, tmp_path: Path) -> None:
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        dev_agent, "_ensure_dashboard_dir", lambda root, rebuild=False: dash
    )
    monkeypatch.setenv("DEV_AGENT_MAX_CYCLES", "1")
    monkeypatch.setattr(
        dev_agent, "_run_impacted_or_full", lambda *a, **k: {"ok": True, "mode": "full"}
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
    dev_agent.main(["--interval", "1", "--max-cycles", "1"])  # cover main()
    assert (dash / "status.json").exists()
