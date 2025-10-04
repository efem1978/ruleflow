from __future__ import annotations

import os
from pathlib import Path

import mcp_rules_assistant.dev_agent as dev


def test_run_impacted_quick_monkeypatch(tmp_path: Path, monkeypatch) -> None:
    # monkeypatch changed files to trigger quick path
    monkeypatch.setattr(dev, "_git_changed_files", lambda project_root: [tmp_path / "x.py"])  # type: ignore[attr-defined]
    monkeypatch.setattr(
        dev.checks,
        "run_quick_tests",
        lambda changed, cwd=None: {"ok": True, "skipped": False},
    )
    out = dev.run_impacted_or_full(tmp_path, cycle_idx=1, full_every=5)
    assert out.get("mode") == "quick" and out.get("ok") is True


def test_get_run_config_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DEV_AGENT_AUTOCOMMIT", "1")
    monkeypatch.setenv("DEV_AGENT_AUTOPUSH", "1")
    monkeypatch.setenv("DEV_AGENT_COMMIT_INTERVAL", "120")
    monkeypatch.setenv("DEV_AGENT_BYPASS", "1")
    monkeypatch.setenv("DEV_AGENT_BYPASS_THRESHOLD", "4")
    a = dev.DevAgent(project_root=tmp_path)
    cfg = dev.get_run_config(a)
    assert (
        cfg.get("auto_commit") is True
        and cfg.get("auto_push") is True
        and int(cfg.get("commit_interval") or 0) == 120
    )


def test_auto_append_memory_disabled(tmp_path: Path, monkeypatch) -> None:
    a = dev.DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp/dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    # ensure disabled path returns False
    if os.environ.get("DEV_AGENT_MEM_ENABLE"):
        monkeypatch.delenv("DEV_AGENT_MEM_ENABLE", raising=False)
    ok = a._auto_append_memory({"plan": {}, "coverage": {}, "progress": {}}, dash)  # type: ignore[attr-defined]
    assert ok is False


def test_ensure_dashboard_dir_rebuild(tmp_path: Path) -> None:
    a = dev.DevAgent(project_root=tmp_path)
    d = tmp_path / ".mcp/dashboard"
    d.mkdir(parents=True, exist_ok=True)
    (d / "t.txt").write_text("x", encoding="utf-8")
    out = a._ensure_dashboard_dir(rebuild=True)
    assert out.exists() and out.is_dir()
