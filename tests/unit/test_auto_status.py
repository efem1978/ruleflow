from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.auto_status import generate_status
from mcp_rules_assistant.progress import write_plan


def _write_cov_xml(path: Path) -> None:
    text = (
        "<coverage>\n"
        "  <packages><package><classes>\n"
        '    <class filename="pkg/a.py" line-rate="0.80" lines-valid="10" lines-covered="8"/>\n'
        '    <class filename="pkg/b.py" line-rate="0.95" lines-valid="20" lines-covered="19"/>\n'
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def test_status_minimal_no_coverage_no_memory(tmp_path: Path) -> None:
    # no coverage.xml and no memory.json
    out = generate_status(project_root=tmp_path)
    dash = tmp_path / ".mcp" / "dashboard"
    assert (dash / "status.json").exists()
    assert (dash / "history.json").exists()
    assert out["coverage"]["count"] == 0
    assert out["memory"]["exists"] is False


def test_status_with_coverage_memory_and_plan(tmp_path: Path) -> None:
    # coverage sample
    (tmp_path / "coverage.xml").write_text("", encoding="utf-8")  # seed file path
    _write_cov_xml(tmp_path / "coverage.xml")
    # memory sample
    mem = tmp_path / ".mcp/memory.json"
    mem.parent.mkdir(parents=True, exist_ok=True)
    mem.write_text(
        json.dumps(
            {
                "turns": [
                    {"role": "user", "content": "问1", "meta": {}},
                    {"role": "assistant", "content": "答1：计划 与 下一步", "meta": {}},
                ],
                "summary": "Q: 问1\nA: 计划 与 下一步",
                "links": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    # plan with checkboxes
    write_plan(
        (
            "# 项目计划 / Project Plan\n\n"
            "- 状态: in_progress\n"
            "- 当前步骤: 单测\n"
            "- 下一步: 提升覆盖率\n\n"
            "- [x] A\n"
            "- [x] B\n"
            "- [ ] C\n"
        ),
        tmp_path,
    )
    out1 = generate_status(project_root=tmp_path)
    assert out1["coverage"]["count"] == 2
    assert out1["memory"]["exists"] is True
    assert out1["plan"]["status"] == "in_progress"
    assert out1["plan"]["counts"]["done"] == 2
    assert out1["plan"]["counts"]["pending"] == 1

    # run again to append history
    out2 = generate_status(project_root=tmp_path)
    hist = json.loads(
        (tmp_path / ".mcp/dashboard/history.json").read_text(encoding="utf-8")
    )
    assert isinstance(hist, list) and len(hist) >= 2


def test_status_handles_corrupt_memory(tmp_path: Path) -> None:
    p = tmp_path / ".mcp/memory.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{ not: json }", encoding="utf-8")
    out = generate_status(project_root=tmp_path)
    assert out["memory"]["exists"] is False
