from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import dev_agent


def test_run_uses_instance_ensure_dir(monkeypatch, tmp_path: Path) -> None:
    agent = dev_agent.DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp" / "dashboard"

    def inst_ensure(rebuild: bool = False):  # type: ignore[no-untyped-def]
        dash.mkdir(parents=True, exist_ok=True)
        return dash

    monkeypatch.setattr(agent, "_ensure_dashboard_dir", inst_ensure)
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
    agent.run(interval=1, max_cycles=1)
    assert (dash / "status.json").exists()


def test_run_fallback_module_level(monkeypatch, tmp_path: Path) -> None:
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)

    # ensure instance dict has no override, use module-level fallback
    agent = dev_agent.DevAgent(project_root=tmp_path)

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
    agent.run(interval=1, max_cycles=1)
    assert (dash / "status.json").exists()


def test_run_last_resort_fallback(monkeypatch, tmp_path: Path) -> None:
    # 模块级函数抛异常 -> 触发最后回退分支，仍应创建 dashboard/status.json
    agent = dev_agent.DevAgent(project_root=tmp_path)
    # 确保实例 __dict__ 没有覆盖（默认如此）
    if "_ensure_dashboard_dir" in getattr(agent, "__dict__", {}):
        delattr(agent, "_ensure_dashboard_dir")

    def bad_ensure(root, rebuild=False):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    monkeypatch.setattr(dev_agent, "_ensure_dashboard_dir", bad_ensure)
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
    agent.run(interval=1, max_cycles=1)
    # 回退分支会写入默认 dashboard 目录
    dash = tmp_path / ".mcp" / "dashboard"
    assert (dash / "status.json").exists()
