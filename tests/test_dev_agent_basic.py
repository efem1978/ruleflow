from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mcp_rules_assistant import dev_agent


def test_compute_status_fallback_reads_previous_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange: write previous status with coverage count>0 so fallback branch is exercised
    proj = Path.cwd()
    dash = proj / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    prev = {"coverage": {"count": 3, "weak": [], "groups": [], "near": []}}
    (dash / "status.json").write_text(json.dumps(prev), encoding="utf-8")

    # Make summarize return count=0 to trigger fallback
    monkeypatch.setattr(dev_agent, "summarize", lambda **kw: {"ok": True, "count": 0, "weak": []})
    monkeypatch.setattr(dev_agent, "summarize_groups", lambda **kw: {"ok": True, "groups": []})
    monkeypatch.setattr(dev_agent, "summarize_near", lambda **kw: {"ok": True, "near": []})

    out = dev_agent.compute_status(proj)
    assert out.get("coverage", {}).get("count") == 3


def test_compute_status_groups_and_near(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    proj = tmp_path
    # 计划文件，7 done / 12 pending -> 37%
    (proj / ".mcp").mkdir(parents=True, exist_ok=True)
    (proj / ".mcp/plan.md").write_text("- [x] a\n- [x] b\n- [x] c\n- [x] d\n- [x] e\n- [x] f\n- [x] g\n- [ ] h\n- [ ] i\n- [ ] j\n- [ ] k\n- [ ] l\n- [ ] m\n- [ ] n\n- [ ] o\n- [ ] p\n- [ ] q\n- [ ] r\n", encoding="utf-8")
    # 覆盖率：17 个文件，weak=11（通过=6）
    monkeypatch.setattr(dev_agent, "summarize", lambda **k: {"ok": True, "count": 17, "weak": [{"file": "x", "coverage": 0.1, "threshold": 0.95}]*11})
    monkeypatch.setattr(dev_agent, "summarize_groups", lambda **k: {"ok": True, "groups": [{"prefix": "mcp_server.py", "coverage": 1.0, "threshold": 0.98, "weak_count": 0, "files_count": 1}]})
    monkeypatch.setattr(dev_agent, "summarize_near", lambda **k: {"ok": True, "near": []})
    out = dev_agent.compute_status(proj)
    prog = out.get("progress", {})
    covp = float(prog.get("coverage", 0))
    planp = float(prog.get("plan", 0))
    assert round(covp, 2) == round(6/17, 2)
    assert round(planp, 2) == round(7/18, 2)


def test_main_runs_one_cycle_and_writes_status(monkeypatch: pytest.MonkeyPatch) -> None:
    # Speed up: avoid running real pytest/coverage by stubbing internals
    monkeypatch.setattr(dev_agent, "_run_impacted_or_full", lambda *a, **k: {"ok": True, "code": 0, "stdout": "", "stderr": "", "mode": "full"})
    fake_cov = {
        "plan": {"status": "in_progress", "current": "Work", "next": "Next"},
        "coverage": {"weak": [], "groups": [], "near": [], "min_module": 0.95, "count": 2, "progress": 1.0},
        "progress": {"overall": 1.0, "coverage": 1.0, "plan": 1.0, "doc": 1.0, "prod": 1.0, "counts": {"coverage_total": 2, "coverage_weak": 0, "plan_done": 1, "plan_pending": 0}},
        "tasks": {"pending": [], "done": ["ok"]},
    }
    monkeypatch.setattr(dev_agent, "compute_status", lambda *a, **k: fake_cov)

    os.environ["DEV_AGENT_MAX_CYCLES"] = "1"
    os.environ["DEV_AGENT_AUTOCOMMIT"] = "0"
    dev_agent.main(["--interval", "1"])  # should return after one loop

    p = Path(".mcp/dashboard/status.json")
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data.get("tests", {}).get("ok") is True
    assert "interval" in data


def test_history_trim(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 预置 55 条历史，运行一轮后应裁剪为 ≤50
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    hist = [{"ts": i, "duration": 0.1, "overall": 0.5, "coverage_weak": 0, "checks": {}} for i in range(55)]
    (dash / "history.json").write_text(json.dumps(hist), encoding="utf-8")
    monkeypatch.setattr(dev_agent, "_ensure_dashboard_dir", lambda root, rebuild=False: dash)
    # stub 测试/状态
    monkeypatch.setattr(dev_agent, "_run_impacted_or_full", lambda *a, **k: {"ok": True, "code": 0, "stdout": "", "stderr": "", "mode": "full"})
    monkeypatch.setattr(dev_agent, "compute_status", lambda *a, **k: {"plan": {"status": "in_progress", "current": "x", "next": "y"}, "coverage": {"weak": [], "groups": [], "near": [], "min_module": 0.95, "count": 1, "progress": 1.0}, "progress": {"overall": 1.0, "coverage": 1.0, "plan": 1.0, "doc": 1.0, "prod": 1.0, "counts": {"coverage_total": 1, "coverage_weak": 0, "plan_done": 1, "plan_pending": 0}}, "tasks": {"pending": [], "done": []}})
    os.environ["DEV_AGENT_MAX_CYCLES"] = "1"
    dev_agent.main(["--interval", "1"])  # 单循环
    H = json.loads((dash / "history.json").read_text(encoding="utf-8"))
    assert len(H) <= 50
    # 前端服务已移除，不再测试 serve_directory


def test_fail_counters_and_freeze_recover(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 让阈值在第一次失败就触发冻结
    os.environ["DEV_AGENT_THR_TESTS"] = "1"
    os.environ["DEV_AGENT_THR_BUILD"] = "1"
    os.environ["DEV_AGENT_THR_SEVERE"] = "1"
    os.environ["DEV_AGENT_MAX_CYCLES"] = "1"
    # 指定 dashboard 目录到临时目录，避免污染真实仓库
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dev_agent, "_ensure_dashboard_dir", lambda root, rebuild=False: dash)
    # 第一次：制造失败（tests 不通过）
    monkeypatch.setattr(dev_agent, "_run_impacted_or_full", lambda *a, **k: {"ok": False, "code": 1, "stdout": "fail", "stderr": "", "mode": "full"})
    fake_cov_fail = {
        "plan": {"status": "in_progress", "current": "Work", "next": "Next"},
        "coverage": {"weak": [{"file": "x", "coverage": 0.5, "threshold": 0.95}], "groups": [], "near": [], "min_module": 0.95, "count": 1, "progress": 0.0},
        "progress": {"overall": 0.2, "coverage": 0.0, "plan": 1.0, "doc": 1.0, "prod": 0.2, "counts": {"coverage_total": 1, "coverage_weak": 1, "plan_done": 1, "plan_pending": 0}},
        "tasks": {"pending": [], "done": []},
    }
    monkeypatch.setattr(dev_agent, "compute_status", lambda *a, **k: fake_cov_fail)
    dev_agent.main(["--interval", "1"])  # 运行一次
    s1 = json.loads((dash / "status.json").read_text(encoding="utf-8"))
    assert s1.get("freeze", {}).get("active") is True
    # 第二次：模拟恢复（tests 通过且弱项清零且 lint/type ok），应解冻
    os.environ["DEV_AGENT_MAX_CYCLES"] = "1"
    os.environ["DEV_AGENT_AUTOCOMMIT"] = "0"
    monkeypatch.setattr(dev_agent, "_run_impacted_or_full", lambda *a, **k: {"ok": True, "code": 0, "stdout": "ok", "stderr": "", "mode": "full"})
    # 让 quick status 的 ruff/mypy 返回 0
    import types, subprocess as sp
    class P:
        def __init__(self, rc=0):
            self.returncode=rc; self.stdout=''; self.stderr=''
    def fake_run(cmd, cwd=None, text=None, capture_output=None, env=None, check=False):
        if isinstance(cmd, (list, tuple)) and (cmd and ("ruff" in cmd[0] or "mypy" in cmd[0])):
            return P(0)
        return P(0)
    monkeypatch.setattr(sp, 'run', fake_run)
    fake_cov_ok = {
        "plan": {"status": "in_progress", "current": "Work", "next": "Next"},
        "coverage": {"weak": [], "groups": [], "near": [], "min_module": 0.95, "count": 1, "progress": 1.0},
        "progress": {"overall": 1.0, "coverage": 1.0, "plan": 1.0, "doc": 1.0, "prod": 1.0, "counts": {"coverage_total": 1, "coverage_weak": 0, "plan_done": 1, "plan_pending": 0}},
        "tasks": {"pending": [], "done": []},
    }
    monkeypatch.setattr(dev_agent, "compute_status", lambda *a, **k: fake_cov_ok)
    dev_agent.main(["--interval", "1"])  # 再运行一次
    s2 = json.loads((dash / "status.json").read_text(encoding="utf-8"))
    assert s2.get("freeze", {}).get("active") is False
