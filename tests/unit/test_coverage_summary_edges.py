from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.coverage_summary import (
    summarize,
    summarize_tree,
    summarize_near,
)


def test_missing_coverage_xml_returns_message(tmp_path: Path) -> None:
    res = summarize(project_root=tmp_path)
    assert res.get("ok") is False
    assert "coverage.xml" in str(res.get("message", ""))


def test_summarize_tree_structure(tmp_path: Path) -> None:
    cov = (
        "<?xml version='1.0'?><coverage><packages><package><classes>"
        "<class filename='a/b/c.py' line-rate='0.80' lines-valid='10' lines-covered='8'/>"
        "<class filename='a/b/d.py' line-rate='0.70' lines-valid='10' lines-covered='7'/>"
        "</classes></package></packages></coverage>"
    )
    (tmp_path / "coverage.xml").write_text(cov, encoding="utf-8")
    # threshold 0.9 -> 两个都弱项，目录树应包含 a/b 层级
    tree = summarize_tree(project_root=tmp_path, min_module=0.9)
    assert tree["ok"] is True
    t = tree.get("tree", {})
    assert isinstance(t, dict) and t.get("children")


def test_near_window_and_top_limit(tmp_path: Path) -> None:
    lines = [
        "<?xml version='1.0'?><coverage><packages><package><classes>",
    ]
    # produce files just above threshold within 3%
    for i in range(10):
        cov = 0.9 + (i + 1) / 100.0 * 0.02  # 0.902..0.918
        lines.append(
            f"<class filename='m/x{i}.py' line-rate='{cov:.3f}' lines-valid='100' lines-covered='{int(100*cov)}'/>"
        )
    lines.append("</classes></package></packages></coverage>")
    (tmp_path / "coverage.xml").write_text("".join(lines), encoding="utf-8")
    out = summarize_near(project_root=tmp_path, min_module=0.90, within=0.03, top=5)
    near = out.get("near", [])
    assert out["ok"] is True and len(near) == 5

