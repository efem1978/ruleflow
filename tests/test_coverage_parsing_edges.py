from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.coverage_summary import summarize, summarize_groups


def test_coverage_parsing_fallbacks_and_skips(tmp_path: Path) -> None:
    # a: invalid line-rate → fallback to lines-valid/covered (0.9)
    # b: no line-rate, zero valid → treated as 1.0
    # c: valid line-rate (0.5)
    # d: missing attributes → skipped
    xml = (
        "<coverage>\n  <packages><package><classes>\n"
        '<class filename="edge/a.py" line-rate="abc" lines-valid="10" lines-covered="9"/>\n'
        '<class filename="edge/b.py" lines-valid="0" lines-covered="0"/>\n'
        '<class filename="edge/c.py" line-rate="0.5"/>\n'
        '<class filename="bad/d.py"/>\n'
        "</classes></package></packages>\n</coverage>\n"
    )
    (tmp_path / "coverage.xml").write_text(xml, encoding="utf-8")

    res = summarize(project_root=tmp_path, min_module=0.9)
    assert res.get("ok") is True
    weak = res.get("weak") or []
    files = [w.get("file") for w in weak]
    assert "edge/c.py" in files
    assert "edge/a.py" not in files  # 0.9 is not below 0.9
    # groups with policy: edge/ at 0.95 → a,c should be weak in that group
    grp = summarize_groups(
        project_root=tmp_path, policy={"edge/": 0.95}, min_module=0.9
    )
    assert grp.get("ok") is True
    groups = {g.get("prefix"): g for g in grp.get("groups") or []}
    assert "edge/" in groups and "other" in groups
    assert groups["edge/"]["weak_count"] >= 1
