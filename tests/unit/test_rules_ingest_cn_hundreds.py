from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_chinese_hundred_ten_clamp_core(tmp_path: Path) -> None:
    p = tmp_path / 'cn1.md'
    # 使用明确下限关键词 + 超 100% 的数值，期望 clamp 到 100%
    p.write_text('- 核心 不少于 150%', encoding='utf-8')
    out = ri.ingest([str(p)], project_root=tmp_path)
    pol = (out.get('compiled') or {}).get('policy') or {}
    assert abs(float(pol.get('coverage.min_core')) - 1.0) < 1e-6


def test_chinese_two_hundred_clamp_module(tmp_path: Path) -> None:
    p = tmp_path / 'cn2.md'
    p.write_text('- 覆盖率 不低于 200%', encoding='utf-8')
    out = ri.ingest([str(p)], project_root=tmp_path)
    pol = (out.get('compiled') or {}).get('policy') or {}
    assert abs(float(pol.get('coverage.min_module')) - 1.0) < 1e-6
