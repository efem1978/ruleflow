from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_greater_than_module(tmp_path: Path) -> None:
    d = tmp_path / "gt1.md"
    d.write_text("- 覆盖率 超过 90%", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_module")) - 0.90) < 1e-6


def test_greater_than_core_english(tmp_path: Path) -> None:
    d = tmp_path / "gt2.md"
    d.write_text("- core greater than 97 percent", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_core")) - 0.97) < 1e-6


def test_upper_bound_does_not_set_min(tmp_path: Path) -> None:
    d = tmp_path / "gt3.md"
    d.write_text("- 覆盖率 不超过 95%", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert "coverage.min_module" not in pol
