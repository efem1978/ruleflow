from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import coverage_summary as cs


def _write_cov_xml(path: Path) -> None:
    text = (
        "<coverage>\n"
        "  <packages><package><classes>\n"
        "    <class filename=\"pkg/a.py\" line-rate=\"0.96\" lines-valid=\"100\" lines-covered=\"96\"/>\n"
        "    <class filename=\"other/b.py\" line-rate=\"0.95\" lines-valid=\"100\" lines-covered=\"95\"/>\n"
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def test_groups_and_near_combination(tmp_path: Path) -> None:
    _write_cov_xml(tmp_path / "coverage.xml")
    # policy 覆盖前缀分组、near 窗口与 top
    groups = cs.summarize_groups(project_root=tmp_path, policy={"pkg/": 0.97}, min_module=0.95)
    assert groups.get("ok") is True
    near = cs.summarize_near(project_root=tmp_path, policy={"pkg/": 0.97}, min_module=0.95, within=0.03, top=10)
    assert near.get("ok") is True
    tree = cs.summarize_tree(project_root=tmp_path, policy={"pkg/": 0.97}, min_module=0.95)
    assert tree.get("ok") is True

