from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_chinese_cheng_nine_tenths(tmp_path: Path) -> None:
    d = tmp_path / "c1.md"
    d.write_text("- 覆盖率 九成", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_module")) - 0.90) < 1e-6


def test_chinese_cheng_ten_tenths(tmp_path: Path) -> None:
    d = tmp_path / "c2.md"
    d.write_text("- 核心 覆盖率 十成", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_core")) - 1.0) < 1e-6


def test_chinese_cheng_with_decimal(tmp_path: Path) -> None:
    d = tmp_path / "c3.md"
    d.write_text("- 覆盖率 九成五", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_module")) - 0.95) < 1e-6

    d2 = tmp_path / "c4.md"
    d2.write_text("- 核心 八成三 覆盖率", encoding="utf-8")
    res2 = ri.ingest([str(d2)], project_root=tmp_path)
    pol2 = (res2.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol2.get("coverage.min_core")) - 0.83) < 1e-6
