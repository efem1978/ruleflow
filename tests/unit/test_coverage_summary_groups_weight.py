from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.coverage_summary as cs


def _cov(tmp: Path, entries: list[tuple[str, float, int | None, int | None]]):
    parts = [
        '<coverage line-rate="1.0" branch-rate="0" version="1" timestamp="0">',
        '<packages><package name="p"><classes>',
    ]
    for fname, cov, lv, lc in entries:
        attrs = [f'filename="{fname}"', f'line-rate="{cov}"']
        if lv is not None:
            attrs.append(f'lines-valid="{lv}"')
        if lc is not None:
            attrs.append(f'lines-covered="{lc}"')
        parts.append("<class " + " ".join(attrs) + "/>")
    parts.append("</classes></package></packages></coverage>")
    (tmp / "coverage.xml").write_text("\n".join(parts), encoding="utf-8")


def test_groups_weight_fallback_when_missing_lines(tmp_path: Path) -> None:
    # 缺失 lines_valid/covered 时，按每文件权重=1 近似聚合
    _cov(tmp_path, [("m/a.py", 0.90, None, None), ("m/b.py", 1.0, None, None)])
    pol = {"m/": 0.95}
    out = cs.summarize_groups(
        project_root=tmp_path, coverage_xml="coverage.xml", policy=pol, min_module=0.90
    )
    assert out.get("ok") is True
    g = next((g for g in (out.get("groups") or []) if g.get("prefix") == "m/"), None)
    assert g is not None
    # 两个文件等权，平均覆盖率 ~ 0.95；弱项应计 1（0.90 < 0.95）
    cov = float(g.get("coverage", 0.0))
    assert 0.949 <= cov <= 0.951
    assert int(g.get("weak_count", 0)) == 1
