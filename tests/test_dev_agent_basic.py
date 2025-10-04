from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from mcp_rules_assistant.dev_agent import DevAgent


def test_compute_status_fallback_reads_previous_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: write previous status with coverage count>0 so fallback branch is exercised
    proj = tmp_path
    dash = proj / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    prev: dict[str, Any] = {
        "coverage": {"count": 3, "weak": [], "groups": [], "near": []},
    }
    (dash / "status.json").write_text(json.dumps(prev), encoding="utf-8")

    agent = DevAgent(project_root=proj)

    # Make summarize return count=0 to trigger fallback
    monkeypatch.setattr(
        "mcp_rules_assistant.dev_agent.summarize",
        lambda **kw: {"ok": True, "count": 0, "weak": []},
    )
    monkeypatch.setattr(
        "mcp_rules_assistant.dev_agent.summarize_groups",
        lambda **kw: {"ok": True, "groups": []},
    )
    monkeypatch.setattr(
        "mcp_rules_assistant.dev_agent.summarize_near",
        lambda **kw: {"ok": True, "near": []},
    )

    out = agent.compute_status()
    assert out.get("coverage", {}).get("count") == 3


def test_compute_status_groups_and_near(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    proj = tmp_path
    # Plan file, 7 done / 18 total -> ~38.9%
    (proj / ".mcp").mkdir(parents=True, exist_ok=True)
    (proj / ".mcp/plan.md").write_text(
        "- [x] a\n- [x] b\n- [x] c\n- [x] d\n- [x] e\n- [x] f\n- [x] g\n"
        "- [ ] h\n- [ ] i\n- [ ] j\n- [ ] k\n- [ ] l\n- [ ] m\n- [ ] n\n- [ ] o\n- [ ] p\n- [ ] q\n- [ ] r\n",
        encoding="utf-8",
    )

    agent = DevAgent(project_root=proj)

    # Coverage: 17 files, weak=11 (so passed=6)
    monkeypatch.setattr(
        "mcp_rules_assistant.dev_agent.summarize",
        lambda **k: {
            "ok": True,
            "count": 17,
            "weak": [{"file": "x", "coverage": 0.1, "threshold": 0.95}] * 11,
        },
    )
    monkeypatch.setattr(
        "mcp_rules_assistant.dev_agent.summarize_groups",
        lambda **k: {
            "ok": True,
            "groups": [
                {
                    "prefix": "mcp_server.py",
                    "coverage": 1.0,
                    "threshold": 0.98,
                    "weak_count": 0,
                    "files_count": 1,
                },
            ],
        },
    )
    monkeypatch.setattr(
        "mcp_rules_assistant.dev_agent.summarize_near",
        lambda **k: {"ok": True, "near": []},
    )

    out = agent.compute_status()
    prog = out.get("progress", {})
    assert isinstance(prog, dict)
    covp = float(prog.get("coverage", 0.0))
    planp = float(prog.get("plan", 0.0) or 0.0)
    assert round(covp, 2) == round(6 / 17, 2)
    assert round(planp, 2) == round(7 / 18, 2)


def test_main_runs_one_cycle_and_writes_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    # Speed up: avoid running real pytest/coverage by stubbing internals
    agent = DevAgent(project_root=tmp_path)
    monkeypatch.setattr(
        agent,
        "_run_impacted_or_full",
        lambda *a, **kw: {
            "ok": True,
            "code": 0,
            "stdout": "",
            "stderr": "",
            "mode": "full",
        },
    )
    fake_cov: dict[str, Any] = {
        "plan": {"status": "in_progress", "current": "Work", "next": "Next"},
        "coverage": {
            "weak": [],
            "groups": [],
            "near": [],
            "min_module": 0.95,
            "count": 2,
            "progress": 1.0,
        },
        "progress": {
            "overall": 1.0,
            "coverage": 1.0,
            "plan": 1.0,
            "doc": 1.0,
            "prod": 1.0,
            "counts": {
                "coverage_total": 2,
                "coverage_weak": 0,
                "plan_done": 1,
                "plan_pending": 0,
            },
        },
        "tasks": {"pending": [], "done": ["ok"]},
    }
    monkeypatch.setattr(agent, "compute_status", lambda: fake_cov)

    agent.run(interval=1, max_cycles=1)

    p = tmp_path / ".mcp/dashboard/status.json"
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data.get("tests", {}).get("ok") is True
    assert "interval" in data


def test_history_trim(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Pre-seed with 55 history entries, should be trimmed to <=50 after one run
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    hist: list[dict[str, Any]] = [
        {"ts": i, "duration": 0.1, "overall": 0.5, "coverage_weak": 0, "checks": {}}
        for i in range(55)
    ]
    (dash / "history.json").write_text(json.dumps(hist), encoding="utf-8")

    agent = DevAgent(project_root=tmp_path)
    # stub tests/status
    monkeypatch.setattr(
        agent,
        "_run_impacted_or_full",
        lambda *a, **kw: {
            "ok": True,
            "code": 0,
            "stdout": "",
            "stderr": "",
            "mode": "full",
        },
    )
    monkeypatch.setattr(
        agent,
        "compute_status",
        lambda: {
            "plan": {"status": "in_progress", "current": "x", "next": "y"},
            "coverage": {
                "weak": [],
                "groups": [],
                "near": [],
                "min_module": 0.95,
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

    agent.run(interval=1, max_cycles=1)  # single cycle

    H = json.loads((dash / "history.json").read_text(encoding="utf-8"))
    assert len(H) <= 50


def test_fail_counters_and_freeze_recover(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    # Set thresholds to 1 to trigger freeze on first failure
    os.environ["DEV_AGENT_THR_TESTS"] = "1"
    os.environ["DEV_AGENT_THR_BUILD"] = "1"
    os.environ["DEV_AGENT_THR_SEVERE"] = "1"

    agent = DevAgent(project_root=tmp_path)

    # First run: induce failure (tests fail)
    monkeypatch.setattr(
        agent,
        "_run_impacted_or_full",
        lambda *a, **kw: {
            "ok": False,
            "code": 1,
            "stdout": "fail",
            "stderr": "",
            "mode": "full",
        },
    )
    fake_cov_fail: dict[str, Any] = {
        "plan": {"status": "in_progress", "current": "Work", "next": "Next"},
        "coverage": {
            "weak": [{"file": "x", "coverage": 0.5, "threshold": 0.95}],
            "groups": [],
            "near": [],
            "min_module": 0.95,
            "count": 1,
            "progress": 0.0,
        },
        "progress": {
            "overall": 0.2,
            "coverage": 0.0,
            "plan": 1.0,
            "doc": 1.0,
            "prod": 0.2,
            "counts": {
                "coverage_total": 1,
                "coverage_weak": 1,
                "plan_done": 1,
                "plan_pending": 0,
            },
        },
        "tasks": {"pending": [], "done": []},
    }
    monkeypatch.setattr(agent, "compute_status", lambda: fake_cov_fail)

    agent.run(interval=1, max_cycles=1)

    dash = tmp_path / ".mcp" / "dashboard"
    s1 = json.loads((dash / "status.json").read_text(encoding="utf-8"))
    assert s1.get("freeze", {}).get("active") is True

    # Second run: simulate recovery (tests pass, weak cleared, lint/type ok), should unfreeze
    monkeypatch.setattr(
        agent,
        "_run_impacted_or_full",
        lambda *a, **kw: {
            "ok": True,
            "code": 0,
            "stdout": "ok",
            "stderr": "",
            "mode": "full",
        },
    )
    monkeypatch.setattr(
        agent,
        "_run_cycle_checks",
        lambda: {"lint": "ok", "type": "ok", "tdd": "skipped"},
    )

    fake_cov_ok: dict[str, Any] = {
        "plan": {"status": "in_progress", "current": "Work", "next": "Next"},
        "coverage": {
            "weak": [],
            "groups": [],
            "near": [],
            "min_module": 0.95,
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
    }
    monkeypatch.setattr(agent, "compute_status", lambda: fake_cov_ok)

    agent.run(interval=1, max_cycles=1)

    s2 = json.loads((dash / "status.json").read_text(encoding="utf-8"))
    assert s2.get("freeze", {}).get("active") is False
