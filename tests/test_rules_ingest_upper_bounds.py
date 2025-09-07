from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_upper_bound_chinese_module(tmp_path: Path) -> None:
    d = tmp_path / "ub1.md"
    d.write_text("- 覆盖率 不超过 95%", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    comp = res.get("compiled") or {}
    sugg = comp.get("suggestions") or []
    # should contain monitor suggestion for coverage.max_module
    assert any(
        (s.get("key") == "coverage.max_module" and s.get("action") == "monitor")
        for s in sugg
    )


def test_upper_bound_english_core(tmp_path: Path) -> None:
    d = tmp_path / "ub2.md"
    d.write_text("- core at most 97 percent", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    comp = res.get("compiled") or {}
    sugg = comp.get("suggestions") or []
    assert any(
        (s.get("key") == "coverage.max_core" and s.get("action") == "monitor")
        for s in sugg
    )


def test_interval_lower_and_upper(tmp_path: Path) -> None:
    d = tmp_path / "ub3.md"
    d.write_text("- 覆盖率 ≥ 90% 且 < 95%", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_module")) - 0.90) < 1e-6
    comp = res.get("compiled") or {}
    sugg = comp.get("suggestions") or []
    assert any((s.get("key") == "coverage.max_module") for s in sugg)
