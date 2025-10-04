from pathlib import Path

from mcp_rules_assistant.dev_agent import DevAgent


def test_fail_counters_freeze_and_copy_prev_coverage(
    tmp_path: Path, monkeypatch,
) -> None:
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    # 写入上一轮的 coverage（将被 freeze 分支复制到当前 status.coverage）
    prev = {"coverage": {"weak": [{"file": "x.py", "coverage": 0.5, "threshold": 0.9}]}}
    (dash / "status.json").write_text(__import__("json").dumps(prev), encoding="utf-8")

    agent = DevAgent(project_root=tmp_path)

    # 降低 severe 阈值，触发 freeze 激活
    monkeypatch.setenv("DEV_AGENT_THR_SEVERE", "1")

    status: dict = {
        "checks": {},
        "tests": {},
        "error": True,  # 触发 severe 计数
        "progress": {"overall": 0.0, "progress": 0.0},
        "timestamp": 0.0,
    }

    agent._update_failure_and_freeze_status(status, dash)

    assert (
        isinstance(status.get("freeze"), dict)
        and status["freeze"].get("active") is True
    )
    # 冻结时应从上一轮复制 coverage
    cov = status.get("coverage", {})
    assert (
        isinstance(cov, dict) and isinstance(cov.get("weak"), list) and cov["weak"]
    ), "coverage should be copied from previous status.json"
    # brief 文件应被写入
    assert (dash / "status_brief.json").exists()


def test_auto_tag_best_effort_exception_path(tmp_path: Path, monkeypatch) -> None:
    agent = DevAgent(project_root=tmp_path)
    tests = {"ok": True, "mode": "full"}
    status = {"coverage": {"weak": []}}

    # 让内部 git 命令抛异常，覆盖 except 分支（best-effort）
    import mcp_rules_assistant.dev_agent as dev_mod

    def boom(*_a, **_k):  # noqa: ANN001
        raise RuntimeError("git failed")

    monkeypatch.setattr(dev_mod, "run_cmd", boom, raising=True)
    out = agent._handle_auto_tag(tests, status, {"auto_tag": True}, last_tag_date="")
    assert out == ""  # 未更新日期（异常分支吞掉）
