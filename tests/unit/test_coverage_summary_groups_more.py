from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.coverage_summary as cs


def _write_cov(
    tmp: Path, classes: list[tuple[str, float, int | None, int | None]]
) -> None:
    parts = [
        '<coverage line-rate="1.0" branch-rate="0" version="1" timestamp="0">',
        '<packages><package name="pkg"><classes>',
    ]
    for fname, cov, lv, lc in classes:
        attrs = [f'filename="{fname}"', f'line-rate="{cov}"']
        if lv is not None:
            attrs.append(f'lines-valid="{lv}"')
        if lc is not None:
            attrs.append(f'lines-covered="{lc}"')
        parts.append("<class " + " ".join(attrs) + "/>")
    parts.append("</classes></package></packages></coverage>")
    (tmp / "coverage.xml").write_text("\n".join(parts), encoding="utf-8")


def test_groups_suffix_over_prefix(tmp_path: Path) -> None:
    # 文件 mcp_rules_assistant/cli.py 覆盖率 0.95；策略中 cli.py=0.99、mcp_rules_assistant/=0.90
    _write_cov(tmp_path, [("mcp_rules_assistant/cli.py", 0.95, 10, 9)])
    pol = {"cli.py": 0.99, "mcp_rules_assistant/": 0.90}
    out = cs.summarize_groups(
        project_root=tmp_path, coverage_xml="coverage.xml", policy=pol, min_module=0.90
    )
    assert out.get("ok") is True
    groups = out.get("groups") or []
    # 应命中更具体的后缀 cli.py 分组（弱项=1）
    g = next((g for g in groups if g.get("prefix") == "cli.py"), None)
    assert g is not None
    assert abs(float(g.get("threshold", 0.0)) - 0.99) < 1e-9
    assert int(g.get("weak_count", 0)) == 1


def test_groups_other_when_no_match(tmp_path: Path) -> None:
    _write_cov(tmp_path, [("pkg/other.py", 0.96, None, None)])
    pol = {"mcp_rules_assistant/": 0.98}
    out = cs.summarize_groups(
        project_root=tmp_path, coverage_xml="coverage.xml", policy=pol, min_module=0.95
    )
    groups = out.get("groups") or []
    g_other = next((g for g in groups if g.get("prefix") == "other"), None)
    assert g_other is not None
    # 由于未命中策略分组，按 other 统计，阈值为 min_module
    assert abs(float(g_other.get("threshold", 0.0)) - 0.95) < 1e-9
