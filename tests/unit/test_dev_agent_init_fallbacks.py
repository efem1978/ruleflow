from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import dev_agent


def test_initialize_run_status_fallbacks(monkeypatch, tmp_path: Path) -> None:
    agent = dev_agent.DevAgent(project_root=tmp_path)

    # Ensure instance dir exists via instance method
    dash = tmp_path / ".mcp" / "dashboard"

    def inst_ensure(rebuild: bool = False):  # type: ignore[no-untyped-def]
        dash.mkdir(parents=True, exist_ok=True)
        return dash

    monkeypatch.setattr(agent, "_ensure_dashboard_dir", inst_ensure)

    # Force exceptions in initial tests/status to hit fallback except branches
    def bad_run(*a, **k):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    def bad_status(*a, **k):  # type: ignore[no-untyped-def]
        raise RuntimeError("bad")

    monkeypatch.setattr(agent, "_run_impacted_or_full", bad_run)
    monkeypatch.setattr(agent, "compute_status", bad_status)

    agent._initialize_run_status(dash, interval=1)
    # Should still create initial status file with fallback content
    assert (dash / "status.json").exists()


def test_run_else_calls_instance_method_when_module_not_callable(
    monkeypatch, tmp_path: Path,
) -> None:
    # Not in instance __dict__, and module-level ensure is non-callable -> else branch calls instance method
    agent = dev_agent.DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp" / "dashboard"
    # Make module-level symbol non-callable
    monkeypatch.setattr(dev_agent, "_ensure_dashboard_dir", 123, raising=True)

    # Provide instance method to be used by the else branch
    def inst_ensure(rebuild: bool = False):  # type: ignore[no-untyped-def]
        dash.mkdir(parents=True, exist_ok=True)
        return dash

    monkeypatch.setattr(agent, "_ensure_dashboard_dir", inst_ensure)

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
    assert (dash / "status.json").exists()
