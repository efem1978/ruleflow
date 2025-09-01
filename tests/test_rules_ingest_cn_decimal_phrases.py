from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_chinese_not_less_than_decimal_module(tmp_path: Path) -> None:
    d = tmp_path / 'cn_dec1.md'
    d.write_text('- 不低于 93.5% 覆盖率', encoding='utf-8')
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get('compiled') or {}).get('policy') or {}
    assert abs(float(pol.get('coverage.min_module')) - 0.935) < 1e-6


def test_chinese_not_less_than_decimal_core(tmp_path: Path) -> None:
    d = tmp_path / 'cn_dec2.md'
    d.write_text('- 核心 不少于 96.2%', encoding='utf-8')
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get('compiled') or {}).get('policy') or {}
    assert abs(float(pol.get('coverage.min_core')) - 0.962) < 1e-6

