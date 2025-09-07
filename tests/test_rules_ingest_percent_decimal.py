from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_decimal_percent_module(tmp_path: Path) -> None:
    d = tmp_path / "d1.md"
    d.write_text("- 覆盖率 95.5%", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_module")) - 0.955) < 1e-6


def test_decimal_percent_core_english(tmp_path: Path) -> None:
    d = tmp_path / "d2.md"
    d.write_text("- core 96.7 percent", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_core")) - 0.967) < 1e-6
