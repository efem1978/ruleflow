from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_rules_assistant import dev_agent


def test_git_changed_files_blank_and_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # blank line should be ignored
    class P:
        stdout = "\n M a.py\n?? b.txt\n\n"
    monkeypatch.setattr(dev_agent.subprocess, "run", lambda *a, **k: P())
    out = dev_agent._git_changed_files(tmp_path)
    assert any(p.name == "a.py" for p in out)
    # error path returns []
    def boom(*a, **k):
        raise RuntimeError("git failed")
    monkeypatch.setattr(dev_agent.subprocess, "run", boom)
    out2 = dev_agent._git_changed_files(tmp_path)
    assert out2 == []


def test_ensure_dashboard_rmtree_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    (dash / "x").write_text("1", encoding="utf-8")
    calls = {"rm": 0}
    def bad_rmtree(_):
        calls["rm"] += 1
        raise OSError("nope")
    monkeypatch.setattr(dev_agent.shutil, "rmtree", bad_rmtree)
    d = dev_agent._ensure_dashboard_dir(tmp_path, rebuild=True)
    assert d.exists() and calls["rm"] >= 1


def test_compute_status_exceptions_and_next_break(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 1) read_plan/load_config raise -> defaults, with summarize* returning count=0
    monkeypatch.setattr(dev_agent, "read_plan", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no plan")))
    monkeypatch.setattr(dev_agent, "load_config", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no cfg")))
    monkeypatch.setattr(dev_agent, "summarize", lambda **k: {"ok": True, "count": 0, "weak": []})
    monkeypatch.setattr(dev_agent, "summarize_groups", lambda **k: {"ok": True, "groups": []})
    monkeypatch.setattr(dev_agent, "summarize_near", lambda **k: {"ok": True, "near": []})
    out = dev_agent.compute_status(tmp_path)
    assert isinstance(out.get("coverage"), dict) and out["coverage"].get("count") == 0
    # 2) 手动“下一步”段落遇到空行后应停止采集（命中 break）
    monkeypatch.setattr(dev_agent, "read_plan", lambda *a, **k: "摘要\n下一步\n- A\n\n# H\n- 忽略\n")
    out2 = dev_agent.compute_status(tmp_path)
    pending = out2.get("tasks", {}).get("pending") or []
    assert "A" in pending and all("忽略" not in x for x in pending)


def test_main_initial_exceptions_and_history_invalid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 工作目录切换 + dashboard 目录
    monkeypatch.chdir(tmp_path)
    dash = tmp_path / ".mcp" / "dashboard"; dash.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dev_agent, "_ensure_dashboard_dir", lambda root, rebuild=False: dash)
    # 初始阶段：_run_impacted_or_full & compute_status 抛出异常，覆盖 except 路径
    state = {"n": 0}
    def boom_then_ok(*a, **k):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("x")
        return {"ok": False, "code": 1, "stdout": "", "stderr": "", "mode": "full"}
    def status_then_ok(*a, **k):
        # first call raises (initial), second call returns minimal status
        if state.get("s") is None:
            state["s"] = 1
            raise RuntimeError("y")
        return {"plan": {"status": "in_progress", "current": "x", "next": "y"}, "coverage": {"weak": [], "groups": [], "near": [], "min_module": 0.95, "count": 0, "progress": 0.0}, "progress": {"overall": 0.0, "coverage": 0.0, "plan": 0.0, "doc": 0.0, "prod": 0.0, "counts": {"coverage_total": 0, "coverage_weak": 0, "plan_done": 0, "plan_pending": 0}}, "tasks": {"pending": [], "done": []}}
    monkeypatch.setattr(dev_agent, "_run_impacted_or_full", boom_then_ok)
    monkeypatch.setattr(dev_agent, "compute_status", status_then_ok)
    # 循环参数与 bypass 读取异常
    monkeypatch.setenv("DEV_AGENT_MAX_CYCLES", "1")
    orig_read = dev_agent._read_json
    def read_maybe_raise(p: Path) -> dict:  # type: ignore[override]
        if p.name == "bypass_state.json":
            raise RuntimeError("bad")
        return orig_read(p)
    monkeypatch.setattr(dev_agent, "_read_json", read_maybe_raise)
    # history.json 非法 JSON，覆盖读取异常路径
    (dash / "history.json").write_text("{invalid", encoding="utf-8")
    dev_agent.main(["--interval", "1"])  # 单循环
    st = json.loads((dash / "status.json").read_text(encoding="utf-8"))
    # 至少应落盘一条状态，且 tests 最终为失败（由第二次 _run_impacted_or_full 返回）
    assert st.get("tests", {}).get("ok") is False


def test_main_loop_excepts_and_counters_and_commits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # set cwd and dashboard
    import subprocess as sp
    monkeypatch.chdir(tmp_path)
    dash = tmp_path / ".mcp" / "dashboard"; dash.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dev_agent, "_ensure_dashboard_dir", lambda root, rebuild=False: dash)
    # one loop only
    monkeypatch.setenv("DEV_AGENT_MAX_CYCLES", "1")
    # compute_status raises inside loop to hit except (360-361)
    monkeypatch.setattr(dev_agent, "compute_status", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    # tests ok to allow can_commit branch
    monkeypatch.setattr(dev_agent, "_run_impacted_or_full", lambda *a, **k: {"ok": True, "code": 0, "stdout": "", "stderr": "", "mode": "full"})
    # mock subprocess.run to: ruff->rc=1 (lint fail); mypy->rc=0; git status -> raise to hit commit except
    class P:
        def __init__(self, rc=0, out=""):
            self.returncode = rc; self.stdout = out; self.stderr = ""
    import subprocess as sp
    def fake_run(cmd, cwd=None, text=None, stdout=None, env=None, check=False):
        s = " ".join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
        if s.startswith("ruff check"):
            return P(1)
        if s.startswith("mypy"):
            return P(0)
        if "git status --porcelain" in s:
            raise RuntimeError("git down")
        return P(0)
    monkeypatch.setattr(sp, "run", fake_run)
    # fail writes for fail_counters.json & history.json only (427-428, 452-453)
    orig_write = Path.write_text
    def guarded_write(self: Path, *a, **k):  # type: ignore[override]
        if self.name in ("fail_counters.json", "history.json"):
            raise OSError("deny")
        return orig_write(self, *a, **k)
    monkeypatch.setattr(Path, "write_text", guarded_write)
    # auto-commit enabled (commit except already covered by fake_run)
    monkeypatch.setenv("DEV_AGENT_AUTOCOMMIT", "1")
    dev_agent.main(["--interval", "1"])  # single loop
    st = json.loads((dash / "status.json").read_text(encoding="utf-8"))
    assert st.get("checks", {}).get("lint") == "fail"


def test_bypass_signature_count_increment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    dash = tmp_path / ".mcp" / "dashboard"; dash.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dev_agent, "_ensure_dashboard_dir", lambda root, rebuild=False: dash)
    # two cycles to increment same failure signature; threshold high so not active
    monkeypatch.setenv("DEV_AGENT_MAX_CYCLES", "2")
    monkeypatch.setenv("DEV_AGENT_BYPASS_THRESHOLD", "99")
    # same failure signature in both cycles, and seed bypass_state to trigger 'equal' branch (339)
    (dash / "bypass_state.json").write_text(json.dumps({"signature": "2|e|oops", "count": 1}), encoding="utf-8")
    # same failure signature in both cycles
    monkeypatch.setattr(dev_agent, "_run_impacted_or_full", lambda *a, **k: {"ok": False, "code": 2, "stdout": "oops", "stderr": "e", "mode": "full"})
    monkeypatch.setattr(dev_agent, "compute_status", lambda *a, **k: {"plan": {"status": "in_progress", "current": "x", "next": "y"}, "coverage": {"weak": [], "groups": [], "near": [], "min_module": 0.95, "count": 1, "progress": 1.0}, "progress": {"overall": 1.0, "coverage": 1.0, "plan": 1.0, "doc": 1.0, "prod": 1.0, "counts": {"coverage_total": 1, "coverage_weak": 0, "plan_done": 1, "plan_pending": 0}}, "tasks": {"pending": [], "done": []}})
    dev_agent.main(["--interval", "1"])  # two cycles
    st = json.loads((dash / "status.json").read_text(encoding="utf-8"))
    assert int(st.get("bypass", {}).get("count", 0)) >= 2
