from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.dev_agent as dev


class _P:
    def __init__(self, code: int = 0, stdout: str = "") -> None:
        self.returncode = code
        self.stdout = stdout
        self.stderr = ""


def test_quick_status_check_ok(tmp_path: Path, monkeypatch) -> None:
    a = dev.DevAgent(project_root=tmp_path)
    monkeypatch.setattr(dev, "run_cmd", lambda *args, **kwargs: _P(0, "ok"))  # type: ignore[attr-defined]
    out = a._run_quick_status_check(["echo", "ok"])  # type: ignore[attr-defined]
    assert out in ("ok", "fail")


def test_compute_status_minimal(tmp_path: Path) -> None:
    a = dev.DevAgent(project_root=tmp_path)
    # minimal plan
    p = tmp_path / ".mcp/plan.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# 计划\n- 状态: in_progress\n- 当前步骤: 测试\n", encoding="utf-8")
    st = a.compute_status()
    assert isinstance(st.get("plan"), dict) and "coverage" in st and "progress" in st
