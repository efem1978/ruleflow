from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from mcp_rules_assistant import dev_agent


def test_run_tests_with_coverage_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class P:
        def __init__(self):
            self.returncode = 0
            self.stdout = "ok"
            self.stderr = ""
    monkeypatch.setattr(dev_agent.subprocess, "run", lambda *a, **k: P())
    out = dev_agent._run_tests_with_coverage(tmp_path)
    assert out["ok"] is True and out["code"] == 0 and "stdout" in out


def test_run_tests_with_coverage_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def raise_fn(*a, **k):
        raise FileNotFoundError
    monkeypatch.setattr(dev_agent.subprocess, "run", raise_fn)
    out = dev_agent._run_tests_with_coverage(tmp_path)
    assert out["ok"] is False and out["code"] == 127


def test_git_changed_files_parse(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class P:
        stdout = " M foo.py\nA  bar/baz.py\n?? ignored.txt\n"
    monkeypatch.setattr(dev_agent.subprocess, "run", lambda *a, **k: P())
    out = dev_agent._git_changed_files(tmp_path)
    assert any(p.name == "foo.py" for p in out)
    assert any(p.name == "bar/baz.py".split("/")[-1] for p in out)


def test_run_impacted_or_full_quick_and_full(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 1) quick path（有改动文件 + quick 测试不跳过）
    monkeypatch.setattr(dev_agent, "_git_changed_files", lambda *a, **k: [tmp_path / "a.py"])
    monkeypatch.setattr(dev_agent.checks, "run_quick_tests", lambda *a, **k: {"ok": True})
    out = dev_agent._run_impacted_or_full(tmp_path, cycle_idx=1, full_every=5)
    assert out["mode"] == "quick"
    # 2) fallback 到 full（quick 被标记 skipped）
    monkeypatch.setattr(dev_agent.checks, "run_quick_tests", lambda *a, **k: {"ok": True, "skipped": True})
    monkeypatch.setattr(dev_agent, "_run_tests_with_coverage", lambda *_: {"ok": True, "code": 0, "stdout": "", "stderr": ""})
    out2 = dev_agent._run_impacted_or_full(tmp_path, cycle_idx=2, full_every=5)
    assert out2["mode"] == "full"


def test_bypass_activation_and_signature(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 准备 dashboard 目录
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dev_agent, "_ensure_dashboard_dir", lambda root, rebuild=False: dash)
    # 设置阈值为 1，并允许绕过提交
    monkeypatch.setenv("DEV_AGENT_BYPASS", "1")
    monkeypatch.setenv("DEV_AGENT_BYPASS_THRESHOLD", "1")
    monkeypatch.setenv("DEV_AGENT_BYPASS_COMMIT", "1")
    monkeypatch.setenv("DEV_AGENT_MAX_CYCLES", "1")
    # 首轮：失败 -> 应激活 bypass 并把 tests 伪装为 ok（因为允许 COMMIT）
    monkeypatch.setattr(dev_agent, "_run_impacted_or_full", lambda *a, **k: {"ok": False, "code": 2, "stdout": "", "stderr": "e", "mode": "full"})
    monkeypatch.setattr(dev_agent, "compute_status", lambda *a, **k: {"plan": {"status": "in_progress", "current": "x", "next": "y"}, "coverage": {"weak": [], "groups": [], "near": [], "min_module": 0.95, "count": 1, "progress": 1.0}, "progress": {"overall": 1.0, "coverage": 1.0, "plan": 1.0, "doc": 1.0, "prod": 1.0, "counts": {"coverage_total": 1, "coverage_weak": 0, "plan_done": 1, "plan_pending": 0}}, "tasks": {"pending": [], "done": []}})
    dev_agent.main(["--interval", "1"])  # 单循环
    st = json.loads((dash / "status.json").read_text(encoding="utf-8"))
    assert st.get("bypass", {}).get("active") is True
    assert st.get("tests", {}).get("ok") is True  # 允许伪装通过以不中断自动提交


def test_plan_fallback_next_section(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 不创建复选框，read_plan 返回“下一步”段落，触发降级解析
    monkeypatch.setattr(dev_agent, "read_plan", lambda *a, **k: "摘要\n下一步\n- 任务A\n- 任务B\n")
    out = dev_agent.compute_status(tmp_path)
    prog = out.get("progress", {})
    assert prog.get("plan") == 0.0 and out.get("tasks", {}).get("pending")


def test_main_autocommit_and_tag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 将工作目录切到临时项目
    import subprocess as sp
    monkeypatch.chdir(tmp_path)
    dash = tmp_path / ".mcp" / "dashboard"; dash.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dev_agent, "_ensure_dashboard_dir", lambda root, rebuild=False: dash)
    # 环境：开启自动提交/推送/打标签，快速间隔
    monkeypatch.setenv("DEV_AGENT_AUTOCOMMIT", "1")
    monkeypatch.setenv("DEV_AGENT_AUTOPUSH", "1")
    monkeypatch.setenv("DEV_AGENT_AUTOTAG", "1")
    monkeypatch.setenv("DEV_AGENT_COMMIT_INTERVAL", "1")
    monkeypatch.setenv("DEV_AGENT_MAX_CYCLES", "1")
    # 准备计划为 in_progress 且有当前步骤，以满足 auto-commit 门禁
    p = tmp_path / '.mcp/plan.md'; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('- 状态: in_progress\n- 当前步骤: Step1\n- 下一步: N\n', encoding='utf-8')
    # 测试输出：通过 + full；状态：weak 空
    monkeypatch.setattr(dev_agent, "_run_impacted_or_full", lambda *a, **k: {"ok": True, "code": 0, "stdout": "ok", "stderr": "", "mode": "full"})
    fake_cov = {"plan": {"status": "in_progress", "current": "Step1", "next": "N"}, "coverage": {"weak": [], "groups": [], "near": [], "min_module": 0.95, "count": 1, "progress": 1.0}, "progress": {"overall": 1.0, "coverage": 1.0, "plan": 1.0, "doc": 1.0, "prod": 1.0, "counts": {"coverage_total": 1, "coverage_weak": 0, "plan_done": 1, "plan_pending": 0}}, "tasks": {"pending": [], "done": []}}
    monkeypatch.setattr(dev_agent, "compute_status", lambda *a, **k: fake_cov)
    # stub subprocess.run：对 git status/add/commit/push/tag 做最小模拟
    class P:
        def __init__(self, rc=0, out=""):
            self.returncode=rc; self.stdout=out; self.stderr=""
    def fake_run(cmd, cwd=None, text=None, stdout=None, env=None, check=False):
        s = " ".join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
        if "git status --porcelain" in s:
            return P(0, " M file.py\n")  # 有变更 -> 触发 add/commit/push
        if "git tag -l" in s:
            return P(0, "")  # 不存在该 tag
        return P(0, "")
    monkeypatch.setattr(sp, "run", fake_run)
    dev_agent.main(["--interval", "1"])  # 单循环，覆盖 auto-commit 与 auto-tag 分支
