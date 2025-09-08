from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.coverage_summary as cs


def _write_cov(tmp: Path, entries: list[tuple[str, float]]):
    parts = [
        '<coverage line-rate="1.0" branch-rate="0" version="1" timestamp="0">',
        '<packages><package name="p"><classes>',
    ]
    for fname, cov in entries:
        lv = 10
        lc = int(round(cov * lv))
        parts.append(
            f'<class filename="{fname}" line-rate="{cov}" lines-valid="{lv}" lines-covered="{lc}"/>'
        )
    parts.append("</classes></package></packages></coverage>")
    (tmp / "coverage.xml").write_text("\n".join(parts), encoding="utf-8")


def test_near_sorted_by_smallest_gap_and_top_applied(tmp_path: Path) -> None:
    # thresholds all 0.96; entries have gaps: a(0.961)=0.001, b(0.969)=0.009, c(0.970)=0.010
    _write_cov(tmp_path, [("a.py", 0.961), ("b.py", 0.969), ("c.py", 0.970)])
    pol = {"a.py": 0.96, "b.py": 0.96, "c.py": 0.96}
    out = cs.summarize_near(
        project_root=tmp_path,
        coverage_xml="coverage.xml",
        policy=pol,
        min_module=0.90,
        within=0.05,
        top=2,
    )
    near = out.get("near") or []
    # 应只返回 gap 最小的前 2 个（a, b），并按 gap 升序
    files = [str(it.get("file")) for it in near]
    assert files == ["a.py", "b.py"]
